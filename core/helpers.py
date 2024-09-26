import datetime
import logging
import traceback
from dotmap import DotMap
from fastapi import WebSocket, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED
from typing import Any, Optional

# noinspection PyUnresolvedReferences
import ccxt as sync_ccxt
# noinspection PyUnresolvedReferences
import ccxt.async_support as async_ccxt
from ccxt import Exchange as RESTExchange
from ccxt.async_support import Exchange as WebSocketExchange
from core.constants import constants
from core.cypher import cypher
from core.database import database
from core.properties import properties
from core.types import Protocol, Credentials, Environment, WebSocketCloseCode
from core.utils import deep_merge

ccxt = sync_ccxt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/signIn")  # TODO Check: should it be auth/signIn?!!!

unauthorized_exception = HTTPException(
	status_code=HTTP_401_UNAUTHORIZED,
	detail="Unauthorized",
	headers={"WWW-Authenticate": "Bearer"},
)


async def extract_all_parameters(request: Request):
	headers = DotMap(dict(request.headers), _dynamic=False)

	path_parameters = DotMap(request.path_params, _dynamic=False)

	query_parameters = DotMap(request.query_params, _dynamic=False)

	# noinspection PyBroadException,PyUnusedLocal
	try:
		body = DotMap(await request.json())
	except Exception as exception:
		body = DotMap({})

	parameters = DotMap({}, _dynamic=False)
	parameters = DotMap(deep_merge(
		parameters.toDict(),
		headers
	), _dynamic=False)
	parameters = DotMap(deep_merge(
		parameters.toDict(),
		path_parameters
	), _dynamic=False)
	parameters = DotMap(deep_merge(
		parameters.toDict(),
		query_parameters
	), _dynamic=False)
	parameters = DotMap(deep_merge(
		parameters.toDict(),
		body.toDict()
	), _dynamic=False)
	parameters = DotMap(deep_merge(
		parameters.toDict(),
		request.cookies
	), _dynamic=False)

	parameters._dynamic = False

	return parameters


def extract_id_or_user_telegram_id_or_jwt_token(parameters: DotMap[str, Any]):
	id_or_user_telegram_id_or_jwt_token = parameters.get("id")
	if not id_or_user_telegram_id_or_jwt_token:
		id_or_user_telegram_id_or_jwt_token = parameters.get("userTelegramId")
	if not id_or_user_telegram_id_or_jwt_token:
		id_or_user_telegram_id_or_jwt_token = extract_jwt_token(parameters)

	return id_or_user_telegram_id_or_jwt_token


def extract_jwt_token(parameters: DotMap[str, Any]):
	token = parameters.get("token")
	if not token:
		token = parameters.get("authorization")
	if not token:
		token = parameters.get("cookie")

	if token:
		token = token.removeprefix("Bearer ").removeprefix("token=")

		return token

	return None


def get_user_exchange(id_or_user_telegram_id_or_jwt_token: str | int, exchange_id: str, exchange_environment: Environment, exchange_protocol: Protocol) -> Optional[RESTExchange | WebSocketExchange]:
	user = get_user(id_or_user_telegram_id_or_jwt_token)

	if user:
		return properties.get_or_default(f"""users.{user.id}.exchange.{exchange_id}.{exchange_environment.value}.{exchange_protocol.value}""")

	return None


def get_user(id_or_user_telegram_id_or_jwt_token: str | int) -> Optional[DotMap[str, Any]]:
	user = properties.get_or_default(f"""users.{id}""", None)

	if not user:
		user_id = properties.get_or_default(f"""telegram.ids.{id_or_user_telegram_id_or_jwt_token}""")
		user = properties.get_or_default(f"""users.{user_id}""", None)

	if not user:
		user_id = properties.get_or_default(f"""tokens.{id_or_user_telegram_id_or_jwt_token}""")
		user = properties.get_or_default(f"""users.{user_id}""", None)

	if user:
		return DotMap(user, _dynamic=False)

	return None


def update_user(credentials: Credentials) -> DotMap[str, Any]:
	user_exists = database.select_single_value("""SELECT EXISTS(SELECT 1 FROM user WHERE id = :id);""", {"id": credentials.id})

	if not user_exists:
		database.insert(
			"""
				INSERT INTO
					user
						(id, exchange_id, exchange_environment, telegram_id, api_key, api_secret, sub_account_id, data)
					VALUES
						(:id, :exchange_id, :exchange_environment, :telegram_id, :api_key, :api_secret, :sub_account_id, :data)
			""", {
				"id": credentials.id,
				"exchange_id": credentials.exchangeId,
				"exchange_environment": credentials.exchangeEnvironment,
				"telegram_id": cypher.encrypt(credentials.userTelegramId),
				"api_key": cypher.encrypt(credentials.exchangeApiKey),
				"api_secret": cypher.encrypt(credentials.exchangeApiSecret),
				"sub_account_id": cypher.encrypt(credentials.exchangeOptions.get("subAccountId") if credentials.exchangeOptions else ""),
				"data": str({
					"favorites": {
						"tokens": [],
						"markets": []
					}
				}),
			},
			True
		)
		user = database.select_single("select * from user where id = :id", {"id": credentials.id})

		print(user)

	rest_exchange: RESTExchange = getattr(ccxt, credentials.exchangeId)({
		"apiKey": credentials.exchangeApiKey,
		"secret": credentials.exchangeApiSecret,
		"options": {
			"environment": credentials.exchangeEnvironment,
			"subaccountId": credentials.exchangeOptions.get("subAccountId"),
		}
	})

	websocket_exchange: WebSocketExchange = getattr(async_ccxt, credentials.exchangeId)({
		"apiKey": credentials.exchangeApiKey,
		"secret": credentials.exchangeApiSecret,
		"options": {
			"environment": credentials.exchangeEnvironment,
			"subaccountId": credentials.exchangeOptions.get("subaccountid"),
		}
	})

	if credentials.exchangeEnvironment != constants.environments.production:
		rest_exchange.set_sandbox_mode(True)
		websocket_exchange.set_sandbox_mode(True)

	rest_exchange.fetch_markets()
	rest_exchange.fetch_currencies()

	properties.set(f"""users.{credentials.id}.id""", credentials.id)
	properties.set(f"""users.{credentials.id}.exchange.{credentials.exchangeId}.{credentials.exchangeEnvironment}.credentials""", credentials)
	properties.set(f"""users.{credentials.id}.exchange.{credentials.exchangeId}.{credentials.exchangeEnvironment}.{Protocol.REST.value}""", rest_exchange)
	properties.set(f"""users.{credentials.id}.exchange.{credentials.exchangeId}.{credentials.exchangeEnvironment}.{Protocol.WebSocket.value}""", websocket_exchange)

	properties.set(f"""telegram.ids.{credentials.userTelegramId}""", credentials.id)
	properties.set(f"""tokens.{credentials.jwtToken}""", credentials.id)

	return properties.get_or_default(f"""users.{credentials.id}""")


def delete_user(idOrJwtToken: str):
	user = get_user(idOrJwtToken)

	if user:
		properties.set(f"""users.{user.id}""", None)
	# properties.set(f"""telegram.ids.{userTelegramId}""", None)
	# properties.set(f"""tokens.{jwtToken}""", None)


def create_jwt_token(data: dict, expires_delta: datetime.timedelta):
	to_encode = data.copy()
	expiration_datetime = datetime.datetime.now(datetime.UTC) + expires_delta
	to_encode.update({"exp": expiration_datetime})
	encoded_jwt = jwt.encode(to_encode, properties.get("cypher.password"), algorithm=constants.authentication.jwt.algorithm)

	return encoded_jwt


async def validate_token(request: Request | WebSocket) -> bool:
	# noinspection PyBroadException,PyUnusedLocal
	try:
		token = request.cookies.get("token")

		if token:
			token = token.removeprefix("Bearer ")
		else:
			authorization = request.headers.get("Authorization")
			if not authorization:
				return False

			token = str(authorization).strip().removeprefix("Bearer ")

		if not token:
			return False

		payload = jwt.decode(token, properties.get("cypher.password"), algorithms=[constants.authentication.jwt.algorithm])
		if not payload:
			return False

		token_expiration_timestamp = payload.get("exp")
		token_expiration_datetime = datetime.datetime.fromtimestamp(token_expiration_timestamp, datetime.UTC)
		if not token_expiration_datetime:
			return False

		if datetime.datetime.now(datetime.UTC) > token_expiration_datetime:
			return False

		return True
	except Exception as exception:
		from core.logger import logger
		logger.log(logging.DEBUG, traceback.format_exc())

		return False


async def validate_request_token(request: Request):
	return await validate_token(request)


async def validate_websocket_token(websocket: WebSocket):
	# noinspection PyBroadException,PyUnusedLocal
	try:
		if not await validate_token(websocket):
			await websocket.close(code=WebSocketCloseCode.POLICY_VIOLATION.value)

			return False
	except Exception as exception:
		await websocket.close(code=WebSocketCloseCode.POLICY_VIOLATION.value)

		return False

	return True


async def validate(target: Credentials | Request | WebSocket) -> Credentials | Request:
	if isinstance(target, Credentials):
		# noinspection PyBroadException,PyUnusedLocal
		try:
			# Automatically validates with the pydantic.BaseModel
			return target
		except Exception as exception:
			raise unauthorized_exception

	# noinspection PyUnusedLocal
	try:
		if properties.get_or_default("server.authentication.require.token", True):
			if isinstance(target, Request):
				if not await validate_request_token(target):
					raise unauthorized_exception
			elif isinstance(target, WebSocket):
				if not await validate_websocket_token(target):
					raise unauthorized_exception
			else:
				raise unauthorized_exception

		return target
	except Exception as exception:
		raise unauthorized_exception
