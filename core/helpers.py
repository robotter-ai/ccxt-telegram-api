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
from core.properties import properties
from core.types import Protocol, Credentials

ccxt = sync_ccxt

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/signIn")  # TODO Check: should it be auth/signIn?!!!

unauthorized_exception = HTTPException(
	status_code=HTTP_401_UNAUTHORIZED,
	detail="Unauthorized",
	headers={"WWW-Authenticate": "Bearer"},
)


def get_user(idOruserTelegramIdOrJwtToken: str) -> Optional[DotMap[str, Any]]:
	user = properties.get_or_default(f"""users.{id}""", None)

	if not user:
		user_id = properties.get_or_default(f"""telegram.ids.{idOruserTelegramIdOrJwtToken}""")
		user = properties.get_or_default(f"""users.{user_id}""", None)

	if not user:
		user_id = properties.get_or_default(f"""tokens.{idOruserTelegramIdOrJwtToken}""")
		user = properties.get_or_default(f"""users.{user_id}""", None)

	if user:
		return DotMap(user, _dynamic=False)

	return None


def update_user(credentials: Credentials) -> DotMap[str, Any]:
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


async def authenticate(credentials: Credentials):
	# noinspection PyBroadException,PyUnusedLocal
	try:
		properties.set(credentials.id, credentials)

		return properties.get(credentials.id)
	except Exception as exception:
		return False


def create_jwt_token(data: dict, expires_delta: datetime.timedelta):
	to_encode = data.copy()
	expiration_datetime = datetime.datetime.now(datetime.UTC) + expires_delta
	to_encode.update({"exp": expiration_datetime})
	encoded_jwt = jwt.encode(to_encode, properties.get("admin.password"), algorithm=constants.authentication.jwt.algorithm)

	return encoded_jwt


async def validate_token(request: Request | WebSocket) -> bool:
	# noinspection PyBroadException,PyUnusedLocal
	try:
		token = request.cookies.get("access_token")

		if token:
			token = token.removeprefix("Bearer ")
		else:
			authorization = request.headers.get("Authorization")
			if not authorization:
				return False

			token = str(authorization).strip().removeprefix("Bearer ")

		if not token:
			return False

		payload = jwt.decode(token, properties.get("admin.password"), algorithms=[constants.authentication.jwt.algorithm])
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
			await websocket.close(code=1008)

			return False
	except Exception as exception:
		await websocket.close(code=1008)

		return False

	return True


async def validate(target: Request | WebSocket) -> Request:
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
