import traceback

import asyncio
import atexit
import datetime
import logging
import nest_asyncio
import os
import signal
import uvicorn
from dotmap import DotMap
from fastapi import FastAPI, WebSocket, HTTPException, Response
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from passlib.context import CryptContext
from pathlib import Path
from pydantic import BaseModel
from starlette.requests import Request
from starlette.status import HTTP_401_UNAUTHORIZED
from typing import Any, Dict, Optional

# noinspection PyUnresolvedReferences
import ccxt as sync_ccxt
# noinspection PyUnresolvedReferences
import ccxt.async_support as async_ccxt
from ccxt import Exchange as RESTExchange
from ccxt.async_support import Exchange as WebSocketExchange
from core import controller
from core.constants import constants
from core.model import model
from core.properties import properties
from core.telegram_bot import telegram
from core.types import SystemStatus, APIResponse, CCXTAPIRequest, Protocol, Environment
from core.utils import deep_merge
from tests.integration_tests import IntegrationTests

ccxt = sync_ccxt

RUN_INTEGRATION_TESTS = os.getenv("RUN_INTEGRATION_TESTS", properties.get_or_default("testing.integration.run", "false")).lower() in ["true", "1"]

nest_asyncio.apply()
root_path = Path(os.path.dirname(__file__)).absolute().as_posix()
debug = properties.get_or_default('server.debug', True)
app = FastAPI(debug=debug, root_path=root_path)
properties.load(app)
# Needs to come after properties loading
from core.logger import logger

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/signIn") # Check: should it be auth/signIn?!!!

unauthorized_exception = HTTPException(
	status_code=HTTP_401_UNAUTHORIZED,
	detail="Unauthorized",
	headers={"WWW-Authenticate": "Bearer"},
)


class Credentials(BaseModel):
	jwtToken: Optional[str] = None
	exchangeId: str
	exchangeEnvironment: Optional[str] = Environment.PRODUCTION.value
	exchangeProtocol: Optional[str] = Protocol.REST.value
	exchangeApiKey: str
	exchangeApiSecret: str
	exchangeOptions: Optional[dict[str, Any]] = None

	@property
	def id(self):
		return f"""{self.exchangeId}|{self.exchangeEnvironment}|{self.exchangeApiKey}"""


def get_user(idOrJwtToken: str) -> Optional[DotMap[str, Any]]:
	user = properties.get_or_default(f"""users.{id}""", None)

	if not user:
		user_id = properties.get_or_default(f"""tokens.{idOrJwtToken}""")
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

	properties.set(f"""tokens.{credentials.jwtToken}""", credentials.id)

	return properties.get_or_default(f"""users.{credentials.id}""")


def delete_user(idOrJwtToken: str):
	user = get_user(idOrJwtToken)

	if user:
		properties.set(f"""users.{user.id}""", None)
		# properties.set(f"""tokens.{token}""", None)


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


@app.post("/auth/signIn")
async def auth_sign_in(request: Credentials, response: Response):
	credentials = await authenticate(request)

	if not credentials:
		raise unauthorized_exception

	credentials: Credentials = credentials

	token_expiration_delta = datetime.timedelta(minutes=constants.authentication.jwt.token.expiration)
	token = create_jwt_token(
		data={"sub": credentials.id}, expires_delta=token_expiration_delta
	)

	response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, secure=True, samesite="lax", max_age=60 * 60 * 1000, path="/", domain="")

	credentials.jwtToken = token

	update_user(credentials)

	return {"token": token, "type": constants.authentication.jwt.token.type}


@app.post("/auth/signOut")
async def auth_sign_out(request: Request, response: Response):
	await validate(request)

	response.delete_cookie(key="access_token")

	delete_user(request.get("id"))

	return {"message": "Cookie successfully deleted."}


@app.post("/auth/refresh")
async def auth_refresh(request: Request, response: Response):
	await validate(request)

	token_expiration_delta = datetime.timedelta(minutes=constants.authentication.jwt.token.expiration)
	token = create_jwt_token(
		data={"sub": str(request.get("id"))}, expires_delta=token_expiration_delta
	)

	response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, secure=True, samesite="lax", max_age=60 * 60 * 1000, path="/", domain="")

	return {"token": token, "type": constants.authentication.jwt.token.type}


@app.get("/service/status")
async def service_status(request: Request) -> Dict[str, Any]:
	await validate(request)

	return DotMap({
		"status": SystemStatus.RUNNING.value
	}).toDict()


@app.get("/run")
@app.post("/run")
@app.put("/run")
@app.delete("/run")
@app.patch("/run")
@app.head("/run")
@app.options("/run")
@app.get("/run/{subpath:path}")
@app.post("/run/{subpath:path}")
@app.post("/run/{subpath:path}")
@app.put("/run/{subpath:path}")
@app.delete("/run/{subpath:path}")
@app.patch("/run/{subpath:path}")
@app.head("/run/{subpath:path}")
@app.options("/run/{subpath:path}")
async def run(request: Request) -> APIResponse:
	await validate(request)

	headers = DotMap(dict(request.headers))

	path_parameters = DotMap(request.path_params)

	query_parameters = DotMap(request.query_params)
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

	user = get_user(str(parameters.get("access_token")).removeprefix('Bearer '))

	options = CCXTAPIRequest(
		user_id=user.id if user else None,
		exchange_id=parameters.get("exchangeId"),
		exchange_environment=parameters.get("environment"),
		exchange_protocol=parameters.get("protocol"),
		exchange_method=parameters.get("method"),
		exchange_method_parameters=parameters.get("parameters")
	)

	return await controller.ccxt(options)


async def start_api():
	signal.signal(signal.SIGTERM, shutdown)
	signal.signal(signal.SIGINT, shutdown)

	logger.log(logging.INFO, f'Environment: {properties.get("environment")}')

	host = os.environ.get("HOST", properties.get('server.host'))
	port = int(os.environ.get("PORT", properties.get('server.port')))
	environment = properties.get_or_default('server.environment', constants.environments.production)

	os.environ['ENV'] = environment

	config = uvicorn.Config(
		"app:app",
		host=host,
		port=port,
		log_level=properties.get_or_default("logging.level", logging.DEBUG),
		#reload=debug,
		# app_dir=os.path.dirname(__file__),
	)
	server = uvicorn.Server(config)

	# if environment == constants.environments.development:
	# 	import pydevd_pycharm
	# 	pydevd_pycharm.settrace('localhost', port=30001, stdoutToServer=True, stderrToServer=True)

	await server.serve()


async def startup():
	pass


# noinspection PyUnusedLocal
def shutdown(*args):
	pass


@atexit.register
def shutdown_helper():
	shutdown()
	asyncio.get_event_loop().close()


app.add_event_handler("startup", startup)
app.add_event_handler("shutdown", shutdown)


def initialize():
	asyncio.get_event_loop().run_until_complete(
		telegram.initialize()
	)


def test():
	if RUN_INTEGRATION_TESTS:
		raw_credentials = properties.get_or_default("testing.integration.credentials")
		credentials = Credentials()
		credentials.exchangeId = raw_credentials.get("exchange.id")
		credentials.exchangeEnvironment = raw_credentials.get("exchange.environment")
		credentials.exchangeApiKey = raw_credentials.get("exchange.api.key")
		credentials.exchangeApiSecret = raw_credentials.get("exchange.api.secret")
		credentials.exchangeOptions = raw_credentials.get("exchange.options")

		user = update_user(credentials)
		rest_exchange = user.get("exchange.rest")
		websocket_exchange = user.get("exchange.websocket")

		IntegrationTests.instance().initialize(
			rest_exchange,
			websocket_exchange,
			telegram,
			model.instance()
		)

		asyncio.get_event_loop().run_until_complete(
			IntegrationTests.instance().run()
		)


async def start_threads():
	coroutines = [
		asyncio.create_task(start_api()),
		asyncio.to_thread(telegram.run())
	]

	await asyncio.gather(*coroutines, return_exceptions=True)


def start():
	asyncio.run(start_threads())


if __name__ == "__main__":
	initialize()
	test()
	start()
