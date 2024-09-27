from dotmap import DotMap
from fastapi import Response
from singleton.singleton import Singleton
from starlette.requests import Request
from typing import Any, Optional, List

from core.cypher import cypher
from core.database import database
from core.types import Credentials, Environment, Protocol


class User:

	def __init__(self):
		self.id: Optional[str] = None
		self.telegram_id: Optional[str | int] = None
		self.jwt_tokens: List[str] = []
		self.exchange_id: Optional[str] = None
		self.exchange_environment: Environment = Environment.PRODUCTION
		self.exchange_protocol: Protocol = Protocol.REST
		self.exchange_api_key: Optional[str] = None
		self.exchange_api_secret: Optional[str] = None
		self.exchange_options: DotMap[str, Any] = DotMap[str, Any]({}, _dynamic=False)
		self.data: DotMap[str, Any] = DotMap[str, Any]({}, _dynamic=False)

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

	# noinspection PyMethodMayBeStatic
	def validate(self) -> bool:
		return True


@Singleton
class Users:

	def __init__(self):
		self.data: DotMap[str, Any] = DotMap({
			"ids": {},
			"telegram_ids": {},
			"jwt_tokens": {},
		}, _dynamic=False)

	def extract_user(self, request: Request | Credentials) -> Optional[User]:
		pass

	def get_or_create(self, request: Request | Credentials, response: Response) -> Optional[User]:
		user = self.get(request, response)

		if not user:
			request: Credentials = request

			user = User()
			user.id = request.id
			user.telegram_id = request.userTelegramId
			user.jwt_tokens = [request.jwtToken] if request.jwtToken else []
			user.exchange_id = request.exchangeId
			user.exchange_environment = Environment.get_by_id(request.exchangeEnvironment) if request.exchangeEnvironment else Environment.PRODUCTION
			user.exchange_protocol = Protocol.get_by_id(request.exchangeProtocol) if request.exchangeProtocol else Protocol.REST
			user.exchange_api_key = request.exchangeApiKey
			user.exchange_api_secret = request.exchangeApiSecret
			user.exchange_options = DotMap[str, Any](request.exchangeOptions if request.exchangeOptions else {}, _dynamic=False)

			user.validate()

			user = self.create(user)

		return user

	def get(self, request: Request, _response: Response) -> Optional[User]:
		input: User = self.extract_user(request)

		for method in [
			self.get_by_id,
			self.get_by_telegram_id,
			self.get_by_jwt_token,
			self.get_from_database
		]:
			# noinspection PyArgumentList
			user = method(input)
			if user:
				user.validate()

				return user

	def get_by_id(self, input: User) -> Optional[User]:
		return self.data.ids.get(input.id)

	def get_by_telegram_id(self, input: User) -> Optional[User]:
		return self.data.telegram_ids.get(input.telegram_id)

	def get_by_jwt_token(self, input: User) -> Optional[User]:
		return self.data.jwt_tokens.get(input.jwt_tokens[0] if len(input.jwt_tokens) > 0 else None)

	def get_from_database(self, input: User) -> Optional[User]:
		raw_user = database.select_single(
			"""
				select
					*
				from
					user
					left join user_token
						on user.id = user_token.user_id
				where
					user.exchange_id = :exchange_id
					and user.exchange_environment = :exchange_environment
					and (
						user.id = :encrypted_id
						or user.telegram_id = :encrypted_telegram_id
						or usert_token.token = :encrypted_jwt_token
					)
				limit
					1
			""",
			{
				"exchange_id": input.exchange_id,
				"exchange_environment": input.exchange_environment,
				"encrypted_id": cypher.encrypt(input.id),
				"encrypted_telegram_id": cypher.encrypt(input.telegram_id),
				"encrypted_jwt_token": cypher.encrypt(input.jwt_tokens[0] if len(input.jwt_tokens) > 0 else None)
			}
		)

		if raw_user:
			raw_user = DotMap[str, Any](raw_user, _dynamic=False)

			user = User()
			user.id = raw_user.id
			user.telegram_id = raw_user.telegram_id
			user.jwt_tokens = raw_user.jwt_tokens
			user.exchange_id = raw_user.exchange_id
			user.exchange_environment = raw_user.exchange_environment
			user.exchange_protocol = raw_user.exchange_protocol
			user.exchange_api_key = raw_user.exchange_api_key
			user.exchange_api_secret = raw_user.exchange_api_secret
			user.exchange_options = DotMap[str, Any](raw_user.exchange_options, _dynamic=False)
			user.data = DotMap[str, Any](raw_user.data, _dynamic=False)

			user.validate()

			return user

		return None

	def create(self, input: User) -> Optional[User]:
		input.validate()

	def update(self, input: User) -> Optional[User]:
		input.validate()

	def create_or_update(self, input: User) -> Optional[User]:
		input.validate()
		user = self.get(input)

	def delete(self, input: User) -> None:
		database.delete(
			"""
				delete
				from
					user
				where
					user.exchange_id = :exchange_id
					and user.exchange_environment = :exchange_environment
					and (
						user.id = :encrypted_id
						or user.telegram_id = :encrypted_telegram_id
						or user.id in (
							select
								user_id
							from
								user_token
							where
								usert_token.token = :encrypted_jwt_token
						)
					)
			""",
			{
				"exchange_id": input.exchange_id,
				"exchange_environment": input.exchange_environment,
				"encrypted_id": cypher.encrypt(input.id),
				"encrypted_telegram_id": cypher.encrypt(input.telegram_id),
				"encrypted_jwt_token": cypher.encrypt(input.jwt_tokens[0] if len(input.jwt_tokens) > 0 else None)
			}
		)

		if self.data.ids.get(input.id):
			del self.data.ids[input.id]

		if self.data.telegram_ids.get(input.telegram_id):
			del self.data.telegram_ids[input.telegram_id]

		for jwt_token in input.jwt_tokens:
			if self.data.jwt_tokens.get(jwt_token):
				del self.data.jwt_tokens[jwt_token]


users = Users.instance()
