from typing import Any

from enum import Enum


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
	CANCEL_ALL_ORDERS = "cancelAllOrders"
	CANCEL_ORDER = "cancelOrder"
	CREATE_ORDER = "createOrder"
	DESCRIBE = "describe"
	DEPOSIT = "deposit"
	FETCH_BALANCE = "fetchBalance"
	FETCH_CLOSED_ORDERS = "fetchClosedOrders"
	FETCH_CURRENCIES = "fetchCurrencies"
	FETCH_DEPOSIT_ADDRESSES = "fetchDepositAddresses"
	FETCH_MARKETS = "fetchMarkets"
	FETCH_MY_TRADES = "fetchMyTrades"
	FETCH_OHLCV = "fetchOHLCV"
	FETCH_OPEN_ORDERS = "fetchOpenOrders"
	FETCH_ORDER = "fetchOrder"
	FETCH_ORDER_BOOK = "fetchOrderBook"
	FETCH_ORDERS = "fetchOrders"
	FETCH_ORDERS_ALL_MARKETS = "fetchOrdersAllMarkets"
	FETCH_STATUS = "fetchStatus"
	FETCH_TICKER = "fetchTicker"
	FETCH_TICKERS = "fetchTickers"
	FETCH_TRADES = "fetchTrades"
	FETCH_TRADING_FEE = "fetchTradingFee"
	SET_SANDBOX_MODE = "setSandboxMode"
	WITHDRAW = "withdraw"

	@staticmethod
	def is_equivalent(target: str, method: Any):
		return str(target).replace("_", "").lower() == method.value.replace("_", "").lower()

	@staticmethod
	def find(target: str):
		for method in MagicMethod:
			if MagicMethod.is_equivalent(target, method):
				return method

		raise ValueError(f"""Unrecognized magic method "{target}".""")
