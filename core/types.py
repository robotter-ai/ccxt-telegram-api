from dataclasses import dataclass
from dotmap import DotMap
from enum import Enum
from pydantic import BaseModel
from starlette.status import *
from typing import Any, Dict, Optional


class Environment(Enum):
	PRODUCTION = "production"
	STAGING = "staging"
	DEVELOPMENT = "development"

	@staticmethod
	def get_by_id(id_: str):
		for environment in Environment:
			if environment.value == id_.lower():
				return environment

		raise ValueError(f"""Environment with id "{id_}" not found.""")


class HttpMethod(Enum):
	GET = 'get'
	POST = 'post'
	PUT = 'put'
	DELETE = 'delete'
	PATCH = 'patch'
	HEAD = 'head'
	OPTIONS = 'options'


class SystemStatus(Enum):
	STOPPED = 'stopped'
	STARTING = 'starting'
	IDLE = 'idle'
	RUNNING = 'running'
	STOPPING = 'stopping'
	UNKNOWN = 'unknown'

	@staticmethod
	def get_by_id(id_: str):
		for status in SystemStatus:
			if status.value == id_:
				return status

		raise ValueError(f"""Status with id "{id_}" not found.""")


class MagicMethod(Enum):
	CANCEL_ALL_ORDERS = ("cancelAllOrders", True)
	CANCEL_ORDER = ("cancelOrder", True)
	CREATE_ORDER = ("createOrder", True)
	DESCRIBE = ("describe", False)
	DEPOSIT = ("deposit", True)
	FETCH_BALANCE = ("fetchBalance", True)
	FETCH_CLOSED_ORDERS = ("fetchClosedOrders", True)
	FETCH_CURRENCIES = ("fetchCurrencies", True)
	FETCH_DEPOSIT_ADDRESSES = ("fetchDepositAddresses", True)
	FETCH_MARKETS = ("fetchMarkets", True)
	FETCH_MY_TRADES = ("fetchMyTrades", True)
	FETCH_OHLCV = ("fetchOHLCV", True)
	FETCH_OPEN_ORDER = ("fetchOpenOrder", True)
	FETCH_OPEN_ORDERS = ("fetchOpenOrders", True)
	FETCH_ORDER = ("fetchOrder", True)
	FETCH_ORDER_BOOK = ("fetchOrderBook", True)
	FETCH_ORDERS = ("fetchOrders", True)
	FETCH_ORDERS_ALL_MARKETS = ("fetchOrdersAllMarkets", True)
	FETCH_STATUS = ("fetchStatus", True)
	FETCH_TICKER = ("fetchTicker", True)
	FETCH_TICKERS = ("fetchTickers", True)
	FETCH_TRADES = ("fetchTrades", True)
	FETCH_TRADING_FEE = ("fetchTradingFee", True)
	SET_SANDBOX_MODE = ("setSandboxMode", True)
	WITHDRAW = ("withdraw", True)

	def __init__(self, id: str, is_private: bool):
		self.id = id
		self.is_private = is_private

	@staticmethod
	def is_equivalent(target: str, method: Any):
		return str(target).replace("_", "").lower() == method.id.replace("_", "").lower()

	@staticmethod
	def find(target: str):
		for method in MagicMethod:
			if MagicMethod.is_equivalent(target, method):
				return method

		raise ValueError(f"""Unrecognized magic method "{target}".""")


class Protocol(Enum):
	REST = "rest"
	WebSocket = "websocket"
	FIX = "fix"


class APIResponseStatus(Enum):
	SUCCESS = ("success", HTTP_200_OK)
	ATTRIBUTE_NOT_FOUND_ERROR = ("attribute_not_found_error", HTTP_404_NOT_FOUND)
	ATTRIBUTE_NOT_AVAILABLE_ERROR = ("attribute_not_available_error", HTTP_404_NOT_FOUND)
	EXCHANGE_NOT_AVAILABLE_ERROR = ("exchange_not_available_error", HTTP_401_UNAUTHORIZED)
	METHOD_EXECUTION_ERROR = ("method_execution_error", HTTP_400_BAD_REQUEST)
	EXPECTATION_FAILED_ERROR = ("expectation_failed_error", HTTP_417_EXPECTATION_FAILED)
	UNAUTHORIZED_ERROR = ("unauthorized_error", HTTP_401_UNAUTHORIZED)
	UNKNOWN_ERROR = ("unknown_error", HTTP_500_INTERNAL_SERVER_ERROR)

	def __init__(self, id: str, http_code: int):
		self.id = id
		self.http_code = http_code


class APIRequest:
	pass


@dataclass
class CCXTAPIRequest(APIRequest):
	user_id: str
	exchange_id: str
	exchange_environment: str
	exchange_protocol: Protocol
	exchange_method: str
	exchange_method_parameters: DotMap[str, Any] = None


class APIResponse(DotMap):
	title: str
	message: str
	status: APIResponseStatus
	result: Dict[str, Any] | Any


class CCXTAPIResponse(APIResponse):
	pass


class Credentials(BaseModel):
	userTelegramId: str | int
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
