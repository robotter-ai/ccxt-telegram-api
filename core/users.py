import datetime
import json
import re
from dotmap import DotMap
from enum import Enum
from fastapi import Response
from singleton.singleton import Singleton
from starlette.requests import Request
from typing import Any, Optional, List

from core.constants import constants
from core.cypher import cypher
from core.database import database
from core.properties import properties
from core.types import Credentials, Environment, Protocol


class UserSource(Enum):
	REQUEST = 'request',
	CREDENTIALS = 'credentials',
	DATABASE = 'database'


class User:

	def __init__(self):
		self.telegram_id: Optional[str | int] = None
		self.jwt_tokens: List[str] = []
		self.exchange_id: Optional[str] = None
		self.exchange_environment: Environment = Environment.PRODUCTION
		self.exchange_protocol: Protocol = Protocol.REST
		self.exchange_api_key: Optional[str] = None
		self.exchange_api_secret: Optional[str] = None
		self.data: DotMap[str, Any] = DotMap({
			"subAccountId": None,
			"favorites": {
				"tokens": [],
				"markets": []
			}
		}, _dynamic=False)

	@property
	def id(self):
		if self.exchange_id and self.exchange_environment and self.exchange_api_key:
			return cypher.generate_hash(f"""{self.exchange_id}|{self.exchange_environment.value}|{self.exchange_api_key}""")

		return None

	@property
	def sub_account_id(self):
		if self.data:
			return self.data.get('subAccountId')

	def add_favorite_market(self, favorite: str) -> None:
		favorites = self.get_favorite_markets()

		if favorite not in favorites:
			favorites.append(favorite)

	def remove_favorite_market(self, favorite: str) -> None:
		favorites = self.get_favorite_markets()

		if favorite in favorites:
			favorites.remove(favorite)

	def get_favorite_markets(self) -> List[str]:
		self.data._dynamic = True
		if not self.data.favorites.get('markets'):
			self.data.favorites.markets = []

		return self.data.favorites.markets

	def validate(self) -> bool:
		if self.id and not isinstance(self.id, str):
			raise ValueError("Invalid type for id, expected string.")

		if self.telegram_id and not (isinstance(self.telegram_id, (int, str)) and str(self.telegram_id).isdigit()):
			raise ValueError("Invalid telegram_id, expected integer or numeric string.")

		if not isinstance(self.jwt_tokens, list) or any(not isinstance(token, str) or not token.strip() for token in self.jwt_tokens):
			raise ValueError("Invalid jwt_tokens, expected a list of non-empty strings.")

		if self.exchange_id and not isinstance(self.exchange_id, str):
			raise ValueError("Invalid type for exchange_id, expected string.")

		if not isinstance(self.exchange_environment, Environment):
			raise TypeError("Invalid type for environment, expected Environment enum.")

		if not isinstance(self.exchange_protocol, Protocol):
			raise TypeError("Invalid type for exchange_protocol, expected Protocol enum.")

		if self.exchange_api_key and not isinstance(self.exchange_api_key, str):
			raise ValueError("Invalid type for exchange_api_key, expected string.")

		if self.exchange_api_secret and not isinstance(self.exchange_api_secret, str):
			raise ValueError("Invalid type for exchange_api_secret, expected string.")

		if not isinstance(self.data, DotMap):
			raise TypeError("Invalid type for data, expected DotMap.")

		if 'markets' in self.data.get('favorites', {}) and not isinstance(self.data.favorites.markets, list):
			raise ValueError("Invalid type for favorite markets, expected a list.")

		if any(not isinstance(market, str) for market in self.data.favorites.get('markets', [])):
			raise ValueError("Invalid market entry, expected a list of strings.")

		# Regex check for API key (alphanumeric, 32-64 characters)
		if self.exchange_api_key and not re.match(r'^[a-zA-Z0-9-]{36}$', self.exchange_api_key):
			raise ValueError("Invalid exchange_api_key, expected an alphanumeric string between 32 and 64 characters.")

		# Regex check for API secret (alphanumeric, 32-64 characters)
		if self.exchange_api_secret and not re.match(r'^[a-zA-Z0-9]{64}$', self.exchange_api_secret):
			raise ValueError("Invalid exchange_api_secret, expected an alphanumeric string between 32 and 64 characters.")

		return True


@Singleton
class Users:

	def __init__(self):
		self.data: DotMap[str, Any] = DotMap({
			"ids": {},
			"telegram_ids": {},
			"jwt_tokens": {},
		}, _dynamic=False)

	# noinspection PyMethodMayBeStatic
	async def extract_user(self, request: Request | Credentials | DotMap, source: UserSource) -> Optional[User]:
		user = User()

		if source == UserSource.REQUEST:
			from core.helpers import extract_all_parameters
			parameters = await extract_all_parameters(request)

			user.telegram_id = parameters.get("userTelegramId")
			user.jwt_tokens = [parameters.get("token")] if parameters.get("token") else []
		elif source == UserSource.CREDENTIALS:
			user.telegram_id = request.userTelegramId
			user.jwt_tokens = [request.jwtToken] if request.jwtToken else []
			user.exchange_id = request.exchangeId
			user.exchange_environment = Environment.get_by_id(request.exchangeEnvironment) if request.exchangeEnvironment else Environment.PRODUCTION
			user.exchange_protocol = Protocol.get_by_id(request.exchangeProtocol) if request.exchangeProtocol else Protocol.REST
			user.exchange_api_key = request.exchangeApiKey
			user.exchange_api_secret = request.exchangeApiSecret
			user.data.subAccountId = request.exchangeOptions.get("subAccountId") if request.exchangeOptions else None

			user.validate()
		elif source == UserSource.DATABASE:
			user.telegram_id = cypher.decrypt(request.telegram_id)
			user.jwt_tokens = json.loads(request.jwt_tokens) if request.get("jwt_tokens") and isinstance(request.jwt_tokens, str) else []
			user.exchange_id = request.exchange_id
			user.exchange_environment = Environment.get_by_id(request.exchange_environment) if request.get("exchange_environment") else Environment.PRODUCTION
			user.exchange_protocol = Protocol.get_by_id(request.exchange_protocol) if request.get("exchange_protocol") else Protocol.REST
			user.exchange_api_key = cypher.decrypt(request.exchange_api_key)
			user.exchange_api_secret = cypher.decrypt(request.exchange_api_secret)
			user.data = DotMap(json.loads(cypher.decrypt(request.data)), _dynamic=False) if request.get("data") and isinstance(request.data, str) else None

			user.validate()
		else:
			raise ValueError("Invalid source for user extraction.")

		return user

	async def get_or_create(self, request: Request | Credentials, response: Response, user: User = None) -> Optional[User]:
		user = await self.get(request, response, user)

		if not user:
			request: Credentials = request

			user = await self.create(request, response, user)

		return user

	async def get(self, request: Credentials | Request, _response: Response, user: User = None) -> Optional[User]:
		if not user:
			user = await self.extract_user(request, UserSource.REQUEST)

		for method in [
			self.get_by_id,
			self.get_by_telegram_id,
			self.get_by_jwt_token,
			self.get_from_database
		]:
			# noinspection PyArgumentList
			if stored_user := await method(user):
				stored_user.validate()

				return stored_user

	async def get_by_id(self, user: User) -> Optional[User]:
		if not user or user.id:
			return None

		return self.data.ids.get(user.id)

	async def get_by_telegram_id(self, user: User) -> Optional[User]:
		if not user or not user.telegram_id:
			return None

		return self.data.telegram_ids.get(user.telegram_id)

	async def get_by_jwt_token(self, user: User) -> Optional[User]:
		if not user or not user.jwt_tokens or not len(user.jwt_tokens) > 0:
			return None

		return self.data.jwt_tokens.get(user.jwt_tokens[0])

	async def get_from_database(self, user: User) -> Optional[User]:
		if not user:
			return None

		database_user = database.select_single(
			"""
				-- noinspection SqlResolve @ column/"'"
				select
					user.*,
					 '[' || REPLACE(GROUP_CONCAT(quote(token)), "'", '"') || ']' AS jwt_tokens
				from
					user
					left join user_token
						on user.id = user_token.user_id
				where
					(
						user.exchange_id is not null
						and user.exchange_environment is not null
						and user.exchange_id = :exchange_id
						and user.exchange_environment = :exchange_environment
						and (
							(
								user.id is not null
								and user.id = :id
							) or (
								user.telegram_id is not null
								and user.telegram_id = :encrypted_telegram_id
							)
						)
					) or (
						user_token.token is not null
						and user_token.token = :jwt_token
					)
				limit
					1
			""",
			{
				"exchange_id": user.exchange_id,
				"exchange_environment": user.exchange_environment.value,
				"id": user.id,
				"encrypted_telegram_id": cypher.encrypt(user.telegram_id),
				"jwt_token": user.jwt_tokens[0] if (user.jwt_tokens and len(user.jwt_tokens) > 0) else None
			}
		)

		if database_user and database_user.get("id"):
			database_user = DotMap(database_user, _dynamic=False)

			if user := await self.extract_user(database_user, UserSource.DATABASE):
				return user

		return None

	async def create(self, request: Optional[Credentials | Request], response: Optional[Response], user: Optional[User] = None) -> Optional[User]:
		if not user:
			user = await self.extract_user(request, UserSource.REQUEST)

		token = self.set_new_jwt_token_on_response(request, response, user)

		database.insert(
			"""
				insert into
					user
						(
							id,
							exchange_id,
							exchange_environment,
							telegram_id,
							exchange_api_key,
							exchange_api_secret,
							data
						)
					values
						(
							:id,
							:exchange_id,
							:exchange_environment,
							:encrypted_telegram_id,
							:encrypted_exchange_api_key,
							:encrypted_exchange_api_secret,
							:encrypted_data
						)
			""",
			{
				"id": user.id,
				"exchange_id": user.exchange_id,
				"exchange_environment": user.exchange_environment.value,
				"encrypted_telegram_id": cypher.encrypt(user.telegram_id),
				"encrypted_exchange_api_key": cypher.encrypt(user.exchange_api_key),
				"encrypted_exchange_api_secret": cypher.encrypt(user.exchange_api_secret),
				"encrypted_data": cypher.encrypt(json.dumps(user.data.toDict()))
			}
		)

		database.insert(
			"""
				insert into
					user_token
						(
							user_id,
							token
						)
					values
						(
							:encrypted_user_id,
							:token
						)
			""",
			{
				"encrypted_user_id": user.id,
				"token": token
			},
		)

		database.commit()

		user.jwt_tokens.append(token)

		return user

	async def update(self, request: Optional[Credentials | Request], _response: Optional[Response], user: Optional[User] = None) -> Optional[User]:
		if not user:
			user = await self.extract_user(request, UserSource.REQUEST)

		database.update(
			"""
				update
					user
				set
					exchange_id = :exchange_id,
					exchange_environment = :exchange_environment,
					telegram_id = :encrypted_telegram_id,
					exchange_api_key = :encrypted_exchange_api_key,
					exchange_api_secret = :encrypted_exchange_api_secret,
					data = :encrypted_data
				from
					user
				where
					user.exchange_id = :exchange_id
					and user.exchange_environment = :exchange_environment
					and user.id = :id
			""",
			{
				"exchange_id": user.exchange_id,
				"exchange_environment": user.exchange_environment.value,
				"id": user.id,
				"encrypted_telegram_id": cypher.encrypt(user.telegram_id),
				"encrypted_exchange_api_key": cypher.encrypt(user.exchange_api_key),
				"encrypted_exchange_api_secret": cypher.encrypt(user.exchange_api_secret),
				"encrypted_data": cypher.encrypt(json.dumps(user.data.toDict()))
			},
			auto_commit=True
		)

		return user

	async def create_or_update(self, request: Optional[Credentials | Request], response: Optional[Response], user: Optional[User] = None) -> Optional[User]:
		if not user:
			user = await self.extract_user(request, UserSource.CREDENTIALS)

		if stored_user := await self.get(request, response, user):
			return stored_user

		user = await self.create(request, response, user)

		return user

	async def delete(self, request: Optional[Credentials | Request], response: Optional[Response], user: Optional[User] = None) -> None:
		if not user:
			user = await self.get(request, response, user)

		if not user:
			raise ValueError("User not found.")

		database.delete(
			"""
				delete
				from
					user
				where
					user.exchange_id = :exchange_id
					and user.exchange_environment = :exchange_environment
					and (
						user.id = :id
						or user.telegram_id = :encrypted_telegram_id
						or user.id in (
							select
								user_id
							from
								user_token
							where
								token = :jwt_token
						)
					)
			""",
			{
				"exchange_id": user.exchange_id,
				"exchange_environment": user.exchange_environment.value,
				"id": user.id,
				"encrypted_telegram_id": cypher.encrypt(user.telegram_id),
				"jwt_token": user.jwt_tokens[0] if (user.jwt_tokens and len(user.jwt_tokens) > 0) else None
			}
		)

		database.delete(
			"""
				delete
				from
					user_token
				where
					(
						user_id is not null
						and user_id = :id
					) or (
						token is not null
						and token = :jwt_token
					)
			""",
			{
				"id": user.id,
				"jwt_token": user.jwt_tokens[0] if (user.jwt_tokens and len(user.jwt_tokens) > 0) else None
			}
		)

		database.commit()

		if self.data.ids.get(user.id):
			del self.data.ids[user.id]

		if self.data.telegram_ids.get(user.telegram_id):
			del self.data.telegram_ids[user.telegram_id]

		if user.jwt_tokens and len(user.jwt_tokens) > 0:
			for jwt_token in user.jwt_tokens:
				if self.data.jwt_tokens.get(jwt_token):
					del self.data.jwt_tokens[jwt_token]

	def set_new_jwt_token_on_response(self, request: Request, response: Response, user: User) -> str:
		if not user:
			user = self.get(request, response, user)

		token_expiration_delta = datetime.timedelta(
			seconds=properties.get_or_default("server.authentication.cookie.maxAge", constants.authentication.cookie.maxAge)
		)
		from core.helpers import create_jwt_token
		token = create_jwt_token(
			data={"sub": str(user.id)}, expires_delta=token_expiration_delta
		)

		response.set_cookie(
			key="token",
			value=f"Bearer {token}",
			httponly=properties.get_or_default("server.authentication.cookie.httpOnly", constants.authentication.cookie.httpOnly),
			secure=properties.get_or_default("server.authentication.cookie.secure", constants.authentication.cookie.secure),
			samesite=properties.get_or_default("server.authentication.cookie.sameSite", constants.authentication.cookie.sameSite),
			max_age=properties.get_or_default("server.authentication.cookie.maxAge", constants.authentication.cookie.maxAge),
			path=properties.get_or_default("server.authentication.cookie.path", constants.authentication.cookie.path),
			domain=properties.get_or_default("server.authentication.cookie.domain", constants.authentication.cookie.domain),
		)

		return token


users = Users.instance()
