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


class WebSocketCloseCode(Enum):
	NORMAL_CLOSURE = 1000  # Normal closure, meaning that the purpose for which the connection was established has been fulfilled.
	GOING_AWAY = 1001  # An endpoint is "going away", such as a server going down or a browser navigating away.
	PROTOCOL_ERROR = 1002  # An endpoint is terminating the connection due to a protocol error.
	UNSUPPORTED_DATA = 1003  # Connection is closed because the received data type is not supported.
	NO_STATUS_RECEIVED = 1005  # Reserved value for indicating no status code was received.
	ABNORMAL_CLOSURE = 1006  # Abnormal closure, indicating that no close frame was received.
	INVALID_FRAME_PAYLOAD_DATA = 1007  # Connection closed due to invalid frame payload data.
	POLICY_VIOLATION = 1008  # Connection closed due to a policy violation (e.g., bad data).
	MESSAGE_TOO_BIG = 1009  # Connection closed because a message was too large.
	MANDATORY_EXTENSION = 1010  # Client requested an extension that the server did not negotiate.
	INTERNAL_SERVER_ERROR = 1011  # Server is terminating the connection due to an internal server error.
	SERVICE_RESTART = 1012  # Server is restarting.
	TRY_AGAIN_LATER = 1013  # Temporary server condition, such as overload, causing the connection to be closed.


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

	@staticmethod
	def get_by_id(id_: str):
		for protocol in Protocol:
			if protocol.value == id_.lower():
				return protocol

		raise ValueError(f"""Protocol with id "{id_}" not found.""")


class APIResponseStatus(Enum):
	SUCCESS = ("success", HTTP_200_OK)
	ATTRIBUTE_NOT_FOUND_ERROR = ("attribute_not_found_error", HTTP_404_NOT_FOUND)
	ATTRIBUTE_NOT_AVAILABLE_ERROR = ("attribute_not_available_error", HTTP_404_NOT_FOUND)
	EXCHANGE_NOT_AVAILABLE_ERROR = ("exchange_not_available_error", HTTP_401_UNAUTHORIZED)
	METHOD_EXECUTION_ERROR = ("method_execution_error", HTTP_400_BAD_REQUEST)
	EXPECTATION_FAILED_ERROR = ("expectation_failed_error", HTTP_417_EXPECTATION_FAILED)
	UNAUTHORIZED_ERROR = ("unauthorized_error", HTTP_401_UNAUTHORIZED)
	UNKNOWN_ERROR = ("unknown_error", HTTP_500_INTERNAL_SERVER_ERROR)
	# INVALID_ORDER_ERROR = ("invalid_order_error", HTTP_400_BAD_REQUEST)
	# ORDER_NOT_FOUND_ERROR = ("order_not_found_error", HTTP_404_NOT_FOUND)
	# DUPLICATE_ORDER_ERROR = ("duplicate_order_error", HTTP_409_CONFLICT)
	# OPERATION_REJECTED_ERROR = ("operation_rejected_error", HTTP_400_BAD_REQUEST)
	# ARGUMENTS_REQUIRED_ERROR = ("arguments_required_error", HTTP_400_BAD_REQUEST)

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
