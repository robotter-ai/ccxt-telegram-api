import asyncio
import atexit
import datetime
import logging
import nest_asyncio
import os
import signal
import uvicorn
from dotmap import DotMap
from fastapi import FastAPI, Response
from pathlib import Path
from starlette.requests import Request
from starlette.responses import JSONResponse
from typing import Any, Dict

from core import controller
from core.constants import constants
from core.model import model
from core.properties import properties
from core.types import SystemStatus, APIResponse, CCXTAPIRequest, Credentials, APIResponseStatus
from core.utils import deep_merge
from tests.integration_tests import IntegrationTests

RUN_INTEGRATION_TESTS = os.getenv("RUN_INTEGRATION_TESTS", properties.get_or_default("testing.integration.run", "false")).lower() in ["true", "1"]

nest_asyncio.apply()
root_path = Path(os.path.dirname(__file__)).absolute().as_posix()
debug = properties.get_or_default('server.debug', True)
app = FastAPI(debug=debug, root_path=root_path)
properties.load(app)
# Needs to come after properties loading
from core.logger import logger
from core.helpers import authenticate, unauthorized_exception, create_jwt_token, update_user, validate, \
	delete_user, get_user
from core.telegram_bot import telegram


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

	credentials.jwtToken = token

	update_user(credentials)

	return {"token": token, "type": constants.authentication.jwt.token.type}


@app.post("/auth/signOut")
async def auth_sign_out(request: Request, response: Response):
	await validate(request)

	response.delete_cookie(key="token")

	delete_user(request.get("id"))

	return {"message": "Cookie successfully deleted."}


@app.post("/auth/refresh")
async def auth_refresh(request: Request, response: Response):
	await validate(request)

	token_expiration_delta = datetime.timedelta(minutes=constants.authentication.jwt.token.expiration)
	token = create_jwt_token(
		data={"sub": str(request.get("id"))}, expires_delta=token_expiration_delta
	)

	response.set_cookie(key="token", value=f"Bearer {token}", httponly=True, secure=True, samesite="lax", max_age=60 * 60 * 1000, path="/", domain="")

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
async def run(request: Request) -> JSONResponse:
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

	user = get_user(str(parameters.get("token")).removeprefix('Bearer '))

	options = CCXTAPIRequest(
		user_id=user.id if user else None,
		exchange_id=parameters.get("exchangeId"),
		exchange_environment=parameters.get("environment"),
		exchange_protocol=parameters.get("protocol"),
		exchange_method=parameters.get("method"),
		exchange_method_parameters=parameters.get("parameters")
	)

	response = await controller.ccxt(options)

	json_response = JSONResponse(
		status_code=response.status.http_code,
		content={
			"title": response.title,
			"message": response.message,
			"status": response.status.id,
			"result": response.result
		}
	)

	return json_response


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
	pass
	# shutdown()
	# asyncio.get_event_loop().close()


# app.add_event_handler("startup", startup)
# app.add_event_handler("shutdown", shutdown)


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
