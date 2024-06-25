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
from typing import Any, Dict

# noinspection PyUnresolvedReferences
import ccxt as sync_ccxt
# noinspection PyUnresolvedReferences
import ccxt.async_support as async_ccxt
from ccxt import Exchange as CommunityExchange
from ccxt.async_support import Exchange as ProExchange
from core import controller
from core.constants import constants
from core.model import Model
from core.properties import properties
from core.telegram import Telegram
from core.types import SystemStatus
from integration_tests import IntegrationTests

ccxt = sync_ccxt

EXCHANGE_WEB_APP_URL = os.getenv("EXCHANGE_WEB_APP_URL", "https://cube.exchange/")
TELEGRAM_LISTEN_COMMANDS: bool = os.getenv("TELEGRAM_LISTEN_COMMANDS", "true").lower() in ["true", "1"]
RUN_INTEGRATION_TESTS = os.getenv("RUN_INTEGRATION_TESTS", "false").lower() in ["true", "1"]

UNAUTHORIZED_USER_MESSAGE = "Unauthorized user."

community_exchange: CommunityExchange = getattr(ccxt, EXCHANGE_ID)({
	"apiKey": EXCHANGE_API_KEY,
	"secret": EXCHANGE_API_SECRET,
	"options": {
		"environment": EXCHANGE_ENVIRONMENT,
		"subaccountId": EXCHANGE_SUB_ACCOUNT_ID,
	}
})

pro_exchange: ProExchange = getattr(async_ccxt, EXCHANGE_ID)({
	"apiKey": EXCHANGE_API_KEY,
	"secret": EXCHANGE_API_SECRET,
	"options": {
		"environment": EXCHANGE_ENVIRONMENT,
		"subaccountId": EXCHANGE_SUB_ACCOUNT_ID,
	}
})

if EXCHANGE_ENVIRONMENT != "production":
	community_exchange.set_sandbox_mode(True)
	pro_exchange.set_sandbox_mode(True)


nest_asyncio.apply()
root_path = Path(os.path.dirname(__file__)).absolute().as_posix()
debug = properties.get_or_default('server.debug', True)
app = FastAPI(debug=debug, root_path=root_path)
properties.load(app)
# Needs to come after properties loading
from core.logger import logger

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login") # Check: should it be auth/signIn?!!!

unauthorized_exception = HTTPException(
	status_code=HTTP_401_UNAUTHORIZED,
	detail="Unauthorized",
	headers={"WWW-Authenticate": "Bearer"},
)


class Credentials(BaseModel):
	exchangeId: str
	exchangeEnvironment: str
	userApiKey: str
	userApiSecret: str
	userSubAccountId: str

	@property
	def id(self):
		return f"""{self.exchangeId}|{self.exchangeEnvironment}|{self.userApiKey}"""


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

	return {"token": token, "type": constants.authentication.jwt.token.type}


@app.post("/auth/signOut")
async def auth_sign_out(_request: Request, response: Response):
	response.delete_cookie(key="access_token")

	return {"message": "Cookie successfully deleted."}


@app.post("/auth/refresh")
async def auth_refresh(request: Request, response: Response):
	await validate(request)

	token_expiration_delta = datetime.timedelta(minutes=constants.authentication.jwt.token.expiration)
	token = create_jwt_token(
		data={"sub": request.get("id")}, expires_delta=token_expiration_delta
	)

	response.set_cookie(key="access_token", value=f"Bearer {token}", httponly=True, secure=True, samesite="lax", max_age=60 * 60 * 1000, path="/", domain="")

	return {"token": token, "type": constants.authentication.jwt.token.type}


@app.get("/service/status")
async def service_status(request: Request) -> Dict[str, Any]:
	await validate(request)

	return DotMap({
		"status": SystemStatus.RUNNING.value
	}).toDict()


@app.get("/ccxt/")
@app.post("/ccxt/")
@app.put("/ccxt/")
@app.delete("/ccxt/")
@app.patch("/ccxt/")
@app.head("/ccxt/")
@app.options("/ccxt/")
@app.get("/ccxt/{subpath:path}")
@app.post("/ccxt/{subpath:path}")
@app.post("/ccxt/{subpath:path}")
@app.put("/ccxt/{subpath:path}")
@app.delete("/ccxt/{subpath:path}")
@app.patch("/ccxt/{subpath:path}")
@app.head("/ccxt/{subpath:path}")
@app.options("/ccxt/{subpath:path}")
async def ccxt(request: Request) -> Dict[str, Any]:
	await validate(request)

	paths = DotMap(request.path_params)
	parameters = DotMap(request.query_params)
	try:
		body = DotMap(await request.json())
	except:
		body = DotMap({})
	headers = DotMap(dict(request.headers))

	return await controller.ccxt(body)


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
	# TODO check!!!
	logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

	asyncio.get_event_loop().run_until_complete(
		Telegram.instance().initialize()
	)


def test():
	if RUN_INTEGRATION_TESTS:
		IntegrationTests.instance().initialize(
			community_exchange,
			pro_exchange,
			Telegram.instance(),
			Model.instance()
		)

		asyncio.get_event_loop().run_until_complete(
			IntegrationTests.instance().run()
		)


def start():
	Telegram.instance().run()


if __name__ == "__main__":
	initialize()
	test()
	start()
