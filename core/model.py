from collections import OrderedDict

import json
import jsonpickle
import re
from dotmap import DotMap
from singleton.singleton import ThreadSafeSingleton
from typing import Any, Dict

# noinspection PyUnresolvedReferences
import ccxt as sync_ccxt
# noinspection PyUnresolvedReferences
import ccxt.async_support as async_ccxt
from ccxt.base.types import OrderType, OrderSide
from core.decorators import handle_exceptions, async_handle_exceptions
from core.types import MagicMethod, Environment, Credentials
from core.utils import remove_non_allowed_characters

ccxt = sync_ccxt


# noinspection PyMethodMayBeStatic
@handle_exceptions
@ThreadSafeSingleton
class Model(object):
	def sanitize_exchange_id(self, target):
		return str(target).lower()

	def sanitize_exchange_environment(self, target):
		# noinspection PyUnusedLocal,PyBroadException
		try:
			return Environment.get_by_id(str(target).lower()).value
		except Exception as exception:
			return None

	def sanitize_exchange_api_key(self, target):
		return remove_non_allowed_characters(target, r"[A-Za-z0-9-_]")

	def sanitize_exchange_api_secret(self, target):
		return remove_non_allowed_characters(target, r"[A-Za-z0-9-_]")

	def sanitize_exchange_options(self, target):
		if not target:
			return None

		if (isinstance(target, Dict) or isinstance(target, DotMap)) and target.get("sub_account_id"):
			return DotMap({
				"subAccountId": self.sanitize_exchange_options_sub_account_id(target.get("sub_account_id"))
			}, _dynamic=False)

		return None

	def sanitize_exchange_options_sub_account_id(self, target):
		return int(target)

	def sanitize_token_id(self, target):
		return str(target).upper()

	def sanitize_market_id(self, target):
		return str(target).upper()

	def sanitize_order_type(self, target):
		return str(target).lower()

	def sanitize_order_side(self, target):
		return str(target).lower()

	def sanitize_order_amount(self, target):
		return float(target)

	def sanitize_order_price(self, target):
		return float(target)

	def validate_exchange_id(self, target):
		if not target:
			return False

		regex = re.compile(r'^[a-zA-Z]+$', re.IGNORECASE)

		return regex.match(target)

	def validate_exchange_environment(self, target):
		if not target:
			return False

		environments = [environment.value for environment in Environment]

		if target not in environments:
			return False

		return True

	def validate_exchange_api_key(self, target):
		if not target:
			return False

		regex = re.compile(r'^[a-zA-Z0-9-_]+$', re.IGNORECASE)

		return regex.match(target)

	def validate_exchange_api_secret(self, target):
		if not target:
			return False

		regex = re.compile(r'^[a-zA-Z0-9-_]+$', re.IGNORECASE)

		return regex.match(target)

	def validate_exchange_options(self, target):
		if not target:
			return True

		if not isinstance(target, DotMap) and not isinstance(target, Dict):
			return False

		auxiliar = target
		if isinstance(target, DotMap):
			auxiliar = target.toDict()

		if len(auxiliar.keys()) != 1 or auxiliar.get("sub_account_id", None) is None:
			return False

		return self.validate_exchange_options_sub_account_id(target["sub_account_id"])

	def validate_exchange_options_sub_account_id(self, target):
		# if not target:
		# 	return False

		regex = re.compile(r'^[0-9]+$')

		return regex.match(str(target))

	def validate_token_id(self, target):
		if not target:
			return False

		regex = re.compile(r'^[A-Z]{2,5}$', re.IGNORECASE)

		return regex.match(target)

	def validate_market_id(self, target):
		if not target:
			return False

		regex = re.compile(r'^([A-Z]{2,5})(/)?([A-Z]{2,5})$', re.IGNORECASE)

		return regex.match(target)

	def validate_order_type(self, target):
		if not target:
			return False

		if self.sanitize_order_type(target) in ["limit", "market"]:
			return True

		return False

	def validate_order_side(self, target):
		if not target:
			return False

		if self.sanitize_order_side(target) in ["buy", "sell"]:
			return True

		return False

	def validate_order_amount(self, target):
		if not target:
			return False

		if isinstance(target, str):
			regex = re.compile(r'^\d+(\.\d+)?$')

			return regex.match(target)
		elif isinstance(target, float) and target > 0:
			return True

		return False

	def validate_order_price(self, target):
		if not target:
			return False

		if isinstance(target, str):
			regex = re.compile(r'^\d+(\.\d+)?$')

			return regex.match(target)
		elif isinstance(target, float) and target > 0:
			return True

		return False

	async def get_exchanges(self):
		response = ccxt.exchanges

		output = [
			item for item in response
		]

		return output

	async def sign_in(self, credentials: Credentials):
		from core.helpers import update_user

		return update_user(credentials)

	async def sign_out(self, user_telegram_id):
		from core.helpers import delete_user

		return delete_user(user_telegram_id)

	async def get_balance(self, exchange, token_id: str):
		balances = await self.get_balances(exchange)
		balance = balances.get(token_id)

		return balance

	async def get_balances(self, exchange) -> Dict[str, Any]:
		balances = exchange.fetch_balance()

		non_zero_balances_keys = {key for key, value in balances.get("total", {}).items() if value > 0}
		non_zero_balances = {key: balances[key] for key in non_zero_balances_keys}

		sorted_balances = OrderedDict(sorted(
			non_zero_balances.items(),
			key=lambda x: (x[0].lower(), -x[1]['total'])
		))

		return sorted_balances

	async def get_open_orders(self, exchange, market_id: str):
		response = exchange.fetch_open_orders(market_id)

		output = [
			{

				"id": item.get("id"),
				"clientOrderId": item.get("clientOrderId"),
				# "timestamp": item.get("timestamp"),
				# "lastTradeTimestamp": item.get("lastTradeTimestamp"),
				"status": item.get("status"),
				"symbol": item.get("symbol"),
				"type": item.get("type"),
				# "timeInForce": item.get("timeInForce"),
				"side": item.get("side"),
				"price": item.get("price"),
				# "average": item.get("average"),
				"amount": item.get("amount"),
				"filled": item.get("filled"),
				# "remaining": item.get("remaining"),
				# "cost": item.get("cost"),
				# "trades": item.get("trades"),
				"datetime": item.get("datetime"),
				"fee": item.get("fee"),
				# "info": item.get("info"),
				# "fees": item.get("fees"),
				# "lastUpdateTimestamp": item.get("lastUpdateTimestamp"),
				# "postOnly": item.get("postOnly"),
				# "reduceOnly": item.get("reduceOnly"),
				# "stopPrice": item.get("stopPrice"),
				# "triggerPrice": item.get("triggerPrice"),
				# "takeProfitPrice": item.get("takeProfitPrice"),
				# "stopLossPrice": item.get("stopLossPrice")

			} for item in response
		]

		return output

	async def market_buy_order(self, exchange, market_id: str, amount: float):
		response = exchange.create_order(market_id, "market", "buy", amount)

		output = {
			'id': response.get("id"),
			'clientOrderId': response.get("clientOrderId"),
			'symbol': response.get("symbol"),
			'type': response.get("type"),
			'side': response.get("side"),
			'amount': response.get("amount"),
			'price': response.get("price"),
			'filled': response.get("filled"),
			'status': response.get("status"),
			'datetime': response.get("datetime"),
			# 'timestamp': response.get('timestamp'),
			# 'lastTradeTimestamp': response.get('lastTradeTimestamp'),
			# 'timeInForce': response.get('timeInForce'),
			# 'average': response.get('average'),
			# 'remaining': response.get('remaining'),
			# 'cost': response.get('cost'),
			# 'trades': response.get('trades'),
			'fee': response.get('fee'),
			# 'fees': response.get('fees'),
			# 'info': response.get('info'),
			# 'lastUpdateTimestamp': response.get('lastUpdateTimestamp'),
			# 'postOnly': response.get('postOnly'),
			# 'reduceOnly': response.get('reduceOnly'),
			# 'stopPrice': response.get('stopPrice'),
			# 'triggerPrice': response.get('triggerPrice'),
			# 'takeProfitPrice': response.get('takeProfitPrice'),
			# 'stopLossPrice': response.get('stopLossPrice'),
		}

		return output

	async def market_sell_order(self, exchange, market_id: str, amount: float):
		response = exchange.create_order(market_id, "market", "sell", amount)

		output = {
			'id': response.get("id"),
			'clientOrderId': response.get("clientOrderId"),
			'symbol': response.get("symbol"),
			'type': response.get("type"),
			'side': response.get("side"),
			'amount': response.get("amount"),
			'price': response.get("price"),
			'filled': response.get("filled"),
			'status': response.get("status"),
			'datetime': response.get("datetime"),
			# 'timestamp': response.get('timestamp'),
			# 'lastTradeTimestamp': response.get('lastTradeTimestamp'),
			# 'timeInForce': response.get('timeInForce'),
			# 'average': response.get('average'),
			# 'remaining': response.get('remaining'),
			# 'cost': response.get('cost'),
			# 'trades': response.get('trades'),
			'fee': response.get('fee'),
			# 'fees': response.get('fees'),
			# 'info': response.get('info'),
			# 'lastUpdateTimestamp': response.get('lastUpdateTimestamp'),
			# 'postOnly': response.get('postOnly'),
			# 'reduceOnly': response.get('reduceOnly'),
			# 'stopPrice': response.get('stopPrice'),
			# 'triggerPrice': response.get('triggerPrice'),
			# 'takeProfitPrice': response.get('takeProfitPrice'),
			# 'stopLossPrice': response.get('stopLossPrice'),
		}

		return output

	async def limit_buy_order(self, exchange, market_id: str, amount: float, price: float):
		response = exchange.create_order(market_id, "limit", "buy", amount, price)

		output = {
			'id': response.get("id"),
			'clientOrderId': response.get("clientOrderId"),
			'symbol': response.get("symbol"),
			'type': response.get("type"),
			'side': response.get("side"),
			'amount': response.get("amount"),
			'price': response.get("price"),
			'filled': response.get("filled"),
			'status': response.get("status"),
			'datetime': response.get("datetime"),
			# 'timestamp': response.get('timestamp'),
			# 'lastTradeTimestamp': response.get('lastTradeTimestamp'),
			# 'timeInForce': response.get('timeInForce'),
			# 'average': response.get('average'),
			# 'remaining': response.get('remaining'),
			# 'cost': response.get('cost'),
			# 'trades': response.get('trades'),
			'fee': response.get('fee'),
			# 'fees': response.get('fees'),
			# 'info': response.get('info'),
			# 'lastUpdateTimestamp': response.get('lastUpdateTimestamp'),
			# 'postOnly': response.get('postOnly'),
			# 'reduceOnly': response.get('reduceOnly'),
			# 'stopPrice': response.get('stopPrice'),
			# 'triggerPrice': response.get('triggerPrice'),
			# 'takeProfitPrice': response.get('takeProfitPrice'),
			# 'stopLossPrice': response.get('stopLossPrice'),
		}

		return output

	async def limit_sell_order(self, exchange, market_id: str, amount: float, price: float):
		response = exchange.create_order(market_id, "limit", "sell", amount, price)

		output = {
			'id': response.get("id"),
			'clientOrderId': response.get("clientOrderId"),
			'symbol': response.get("symbol"),
			'type': response.get("type"),
			'side': response.get("side"),
			'amount': response.get("amount"),
			'price': response.get("price"),
			'filled': response.get("filled"),
			'status': response.get("status"),
			'datetime': response.get("datetime"),
			# 'timestamp': response.get('timestamp'),
			# 'lastTradeTimestamp': response.get('lastTradeTimestamp'),
			# 'timeInForce': response.get('timeInForce'),
			# 'average': response.get('average'),
			# 'remaining': response.get('remaining'),
			# 'cost': response.get('cost'),
			# 'trades': response.get('trades'),
			'fee': response.get('fee'),
			# 'fees': response.get('fees'),
			# 'info': response.get('info'),
			# 'lastUpdateTimestamp': response.get('lastUpdateTimestamp'),
			# 'postOnly': response.get('postOnly'),
			# 'reduceOnly': response.get('reduceOnly'),
			# 'stopPrice': response.get('stopPrice'),
			# 'triggerPrice': response.get('triggerPrice'),
			# 'takeProfitPrice': response.get('takeProfitPrice'),
			# 'stopLossPrice': response.get('stopLossPrice'),
		}

		return output

	async def place_order(self, exchange, market: str, order_type: OrderType, order_side: OrderSide, amount: float, price: float = None, stop_loss_price: float = None):
		response = exchange.create_order(market, order_type, order_side, amount, price)
		if response.get("status") == "rejected":
			output = {'status': response.get('status')}
		else:
			output = {
				'id': response.get("id"),
				'clientOrderId': response.get("clientOrderId"),
				'symbol': response.get("symbol"),
				'type': response.get("type"),
				'side': response.get("side"),
				'amount': response.get("amount"),
				'price': response.get("price"),
				'filled': response.get("filled"),
				'status': response.get("status"),
				'datetime': response.get("datetime"),
				# 'timestamp': response.get('timestamp'),
				# 'lastTradeTimestamp': response.get('lastTradeTimestamp'),
				# 'timeInForce': response.get('timeInForce'),
				# 'average': response.get('average'),
				# 'remaining': response.get('remaining'),
				# 'cost': response.get('cost'),
				# 'trades': response.get('trades'),
				'fee': response.get('fee'),
				# 'fees': response.get('fees'),
				# 'info': response.get('info'),
				# 'lastUpdateTimestamp': response.get('lastUpdateTimestamp'),
				# 'postOnly': response.get('postOnly'),
				# 'reduceOnly': response.get('reduceOnly'),
				# 'stopPrice': response.get('stopPrice'),
				# 'triggerPrice': response.get('triggerPrice'),
				# 'takeProfitPrice': response.get('takeProfitPrice'),
				# 'stopLossPrice': response.get('stopLossPrice'),
			}

		return output

	def __getattr__(self, method_name):
		def call(exchange: Any):
			attribute = getattr(exchange, method_name, None)

			if callable(attribute):
				@async_handle_exceptions
				async def method(*args, **kwargs):
					result = attribute(*args, **kwargs)
					output = self.handle_magic_command_output(
						method_name,
						result
					)

					return output

				return method

			return attribute

		return call

	def beautify(self, target: Any, indent=0) -> str:
		if target is None:
			result = "  " * indent + "<empty result>" + "\n"
		elif isinstance(target, dict):
			result = ""
			for key, value in target.items():
				result += "  " * indent + str(key) + ":"
				if isinstance(value, (dict, list)):
					result += "\n" + self.beautify(value, indent + 1)
				else:
					result += " " + str(value) + "\n"
		elif isinstance(target, list):
			result = ""
			for index, item in enumerate(target):
				result += "  " * indent + f"-"
				if isinstance(item, (dict, list)):
					result += "\n" + self.beautify(item, indent + 1)
				else:
					result += " " + str(item) + "\n"
		else:
			result = "  " * indent + str(target) + "\n"

		if str(result).strip() == "":
			if isinstance(target, dict):
				result = "<empty result>\n"
			elif isinstance(target, list):
				result = "<empty list>\n"
			else:
				result = "<empty result>\n"

		return result

	def handle_magic_command_output(self, method, response):
		if MagicMethod.is_equivalent(method, MagicMethod.CANCEL_ALL_ORDERS):
			output = [
				{
					'id': item.get('id'),
					'clientOrderId': item.get('clientOrderId'),
					'timestamp': item.get('timestamp'),
					'datetime': item.get('datetime'),
					# 'lastTradeTimestamp': item.get('lastTradeTimestamp'),
					# 'lastUpdateTimestamp': item.get('lastUpdateTimestamp'),
					'symbol': item.get('symbol'),
					'type': item.get('type'),
					# 'timeInForce': item.get('timeInForce'),
					# 'postOnly': item.get('postOnly'),
					# 'reduceOnly': item.get('reduceOnly'),
					'side': item.get('side'),
					'price': item.get('price'),
					# 'triggerPrice': item.get('triggerPrice'),
					'amount': item.get('amount'),
					# 'cost': item.get('cost'),
					# 'average': item.get('average'),
					'filled': item.get('filled'),
					# 'remaining': item.get('remaining'),
					'status': item.get('status'),
					'fee': item.get('fee'),
					# 'trades': item.get('trades'),
					# 'fees': item.get('fees'),
					# 'stopPrice': item.get('stopPrice'),
					# 'takeProfitPrice': item.get('takeProfitPrice'),
					# 'stopLossPrice': item.get('stopLossPrice'),
				} for item in response
			]

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.CANCEL_ORDER):
			output = {
				'id': response.get('id'),
				'clientOrderId': response.get('clientOrderId'),
				# 'timestamp': response.get('timestamp'),
				'datetime': response.get('datetime'),
				# 'lastTradeTimestamp': response.get('lastTradeTimestamp'),
				# 'lastUpdateTimestamp': response.get('lastUpdateTimestamp'),
				'symbol': response.get('symbol'),
				'type': response.get('type'),
				# 'timeInForce': response.get('timeInForce'),
				# 'postOnly': response.get('postOnly'),
				# 'reduceOnly': response.get('reduceOnly'),
				'side': response.get('side'),
				'price': response.get('price'),
				# 'triggerPrice': response.get('triggerPrice'),
				'amount': response.get('amount'),
				# 'cost': response.get('cost'),
				# 'average': response.get('average'),
				'filled': response.get('filled'),
				# 'remaining': response.get('remaining'),
				'status': response.get('status'),
				'fee': response.get('fee'),
				# 'trades': response.get('trades'),
				# 'fees': response.get('fees'),
				# 'stopPrice': response.get('stopPrice'),
				# 'takeProfitPrice': response.get('takeProfitPrice'),
				# 'stopLossPrice': response.get('stopLossPrice'),
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.CREATE_ORDER):
			output = {
				'id': response.get('id'),
				'clientOrderId': response.get('clientOrderId'),
				# 'timestamp': response.get('timestamp'),
				'datetime': response.get('datetime'),
				# 'lastTradeTimestamp': response.get('lastTradeTimestamp'),
				# 'lastUpdateTimestamp': response.get('lastUpdateTimestamp'),
				'symbol': response.get('symbol'),
				'type': response.get('type'),
				# 'timeInForce': response.get('timeInForce'),
				# 'postOnly': response.get('postOnly'),
				# 'reduceOnly': response.get('reduceOnly'),
				'side': response.get('side'),
				'price': response.get('price'),
				# 'triggerPrice': response.get('triggerPrice'),
				'amount': response.get('amount'),
				# 'cost': response.get('cost'),
				# 'average': response.get('average'),
				'filled': response.get('filled'),
				# 'remaining': response.get('remaining'),
				'status': response.get('status'),
				'fee': response.get('fee'),
				# 'fees': response.get('fees'),
				# 'stopPrice': response.get('stopPrice'),
				# 'takeProfitPrice': response.get('takeProfitPrice'),
				# 'stopLossPrice': response.get('stopLossPrice')
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.DESCRIBE):
			output = response
			output['apiKey'] = "****"
			output['secret'] = "****"
			output['password'] = "****"

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.DEPOSIT):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_BALANCE):
			output = response

			if output.get("info"):
				del output["info"]

			if output.get("timestamp"):
				del output["timestamp"]

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_CLOSED_ORDERS):
			output = [
				{
					'id': item.get('id'),
					'clientOrderId': item.get('clientOrderId'),
					# 'timestamp': item.get('timestamp'),
					'datetime': item.get('datetime'),
					# 'lastTradeTimestamp': item.get('lastTradeTimestamp'),
					# 'lastUpdateTimestamp': item.get('lastUpdateTimestamp'),
					'symbol': item.get('symbol'),
					'type': item.get('type'),
					# 'timeInForce': item.get('timeInForce'),
					# 'postOnly': item.get('postOnly'),
					# 'reduceOnly': item.get('reduceOnly'),
					'side': item.get('side'),
					'price': item.get('price'),
					# 'triggerPrice': item.get('triggerPrice'),
					'amount': item.get('amount'),
					# 'cost': item.get('cost'),
					# 'average': item.get('average'),
					'filled': item.get('filled'),
					# 'remaining': item.get('remaining'),
					'status': item.get('status'),
					'fee': item.get('fee'),
					# 'trades': item.get('trades'),
					# 'fees': item.get('fees'),
					# 'stopPrice': item.get('stopPrice'),
					# 'takeProfitPrice': item.get('takeProfitPrice'),
					# 'stopLossPrice': item.get('stopLossPrice'),
				} for item in response
			]

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_CURRENCIES):
			output = {
				key: {
					# "info": value.get("info"),
					"id": value.get("id"),
					"numericId": value.get("numericId"),
					# "code": value.get("code"),
					"precision": value.get("precision"),
					# "type": value.get("type"),
					"name": value.get("name"),
					# "active": value.get("active"),
					# "deposit": value.get("deposit"),
					# "withdraw": value.get("withdraw"),
					# "fee": value.get("fee"),
					# "fees": value.get("fees"),
					# "networks": value.get("networks"),
					# "limits": value.get("limits"),
				} for key, value in response.items()
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_DEPOSIT_ADDRESSES):
			if response.get("info"):
				del response["info"]

			output = {
				key: {
					# "info": value.get("info"),
					"currency": value.get("currency"),
					"address": value.get("address"),
					"network": value.get("network"),
					"tag": value.get("tag"),
				} for key, value in response.items()
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_MARKETS):
			output = {
				item.get('symbol'): {
					'id': item.get('id'),
					# 'lowercaseId': item.get('lowercaseId'),
					'symbol': item.get('symbol'),
					'base': item.get('base'),
					'quote': item.get('quote'),
					# 'settle': item.get('settle'),
					'baseId': item.get('baseId'),
					'quoteId': item.get('quoteId'),
					# 'settleId': item.get('settleId'),
					# 'type': item.get('type'),
					# 'spot': item.get('spot'),
					# 'margin': item.get('margin'),
					# 'swap': item.get('swap'),
					# 'future': item.get('future'),
					# 'option': item.get('option'),
					# 'index': item.get('index'),
					# 'active': item.get('active'),
					# 'contract': item.get('contract'),
					# 'linear': item.get('linear'),
					# 'inverse': item.get('inverse'),
					# 'subType': item.get('subType'),
					'taker': item.get('taker'),
					'maker': item.get('maker'),
					# 'contractSize': item.get('contractSize'),
					# 'expiry': item.get('expiry'),
					# 'expiryDatetime': item.get('expiryDatetime'),
					# 'strike': item.get('strike'),
					# 'optionType': item.get('optionType'),
					# 'created': item.get('created'),
				} for item in response
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_MY_TRADES):
			output = [
				{
					# 'id': item["info"].get('id'),
					# 'p': item["info"].get('p'),
					# 'q': item["info"].get('q'),
					# 'infoSide': item["info"].get('side'),
					# 'ts': item["info"].get('ts'),
					'datetime': item.get('datetime'),
					'symbol': item.get('symbol'),
					'order': item.get('order'),
					'type': item.get('type'),
					# 'takerOrMaker': item.get('takerOrMaker'),
					'side': item.get('side'),
					'price': item.get('price'),
					'amount': item.get('amount'),
					# 'cost': item.get('cost'),
					'fee': item.get('fee'),
					# 'costFee': item['fees'].get('cost'),
					# 'currency': item['fees'].get('currency'),
					# 'rate': item['fees'].get('rate'),

				} for item in response
			]

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_OHLCV):
			output = {
				item[0]: {
					"open": item[1],
					"high": item[2],
					"low": item[3],
					"close": item[4],
					"volume": item[5]
				} for item in response
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_OPEN_ORDERS):
			output = [
				{
					'id': item.get('id'),
					'clientOrderId': item.get('clientOrderId'),
					'datetime': item.get('datetime'),
					# 'timestamp': item.get('timestamp'),
					# 'lastTradeTimestamp': item.get('lastTradeTimestamp'),
					'status': item.get('status'),
					'symbol': item.get('symbol'),
					'type': item.get('type'),
					# 'timeInForce': item.get('timeInForce'),
					'side': item.get('side'),
					'price': item.get('price'),
					# 'average': item.get('average'),
					'amount': item.get('amount'),
					'filled': item.get('filled'),
					# 'remaining': item.get('remaining'),
					# 'cost': item.get('cost'),
					# 'trades': item.get('trades'),
					# "feeCurrency": item["fee"].get("currency"),
					# "feeCost": item["fee"].get("cost"),
					# "feeRate": item["fee"].get("rate"),
					# 'lastUpdateTimestamp': item.get('lastUpdateTimestamp'),
					# 'postOnly': item.get('postOnly'),
					# 'reduceOnly': item.get('reduceOnly'),
					# 'stopPrice': item.get('stopPrice'),
					# 'triggerPrice': item.get('triggerPrice'),
					# 'takeProfitPrice': item.get('takeProfitPrice'),
					# 'stopLossPrice': item.get('stopLossPrice'),
				} for item in response
			]

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_OPEN_ORDER):
			output = {
				'id': response.get('id'),
				'clientOrderId': response.get('clientOrderId'),
				'datetime': response.get('datetime'),
				# 'timestamp': response.get('timestamp'),
				# 'lastTradeTimestamp': response.get('lastTradeTimestamp'),
				'status': response.get('status'),
				'symbol': response.get('symbol'),
				'type': response.get('type'),
				# 'timeInForce': response.get('timeInForce'),
				'side': response.get('side'),
				'price': response.get('price'),
				# 'average': response.get('average'),
				'amount': response.get('amount'),
				'filled': response.get('filled'),
				# 'remaining': response.get('remaining'),
				# 'cost': response.get('cost'),
				# 'trades': response.get('trades'),
				# 'info': response.get('info'),
				'fees': response.get('fees'),
				# 'lastUpdateTimestamp': response.get('lastUpdateTimestamp'),
				# 'postOnly': response.get('postOnly'),
				# 'reduceOnly': response.get('reduceOnly'),
				# 'stopPrice': response.get('stopPrice'),
				# 'triggerPrice': response.get('triggerPrice'),
				# 'takeProfitPrice': response.get('takeProfitPrice'),
				# 'stopLossPrice': response.get('stopLossPrice'),
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_ORDER):
			output = {
				'id': response.get('id'),
				'clientOrderId': response.get('clientOrderId'),
				'datetime': response.get('datetime'),
				# 'timestamp': response.get('timestamp'),
				# 'lastTradeTimestamp': response.get('lastTradeTimestamp'),
				'status': response.get('status'),
				'symbol': response.get('symbol'),
				'type': response.get('type'),
				# 'timeInForce': response.get('timeInForce'),
				'side': response.get('side'),
				'price': response.get('price'),
				# 'average': response.get('average'),
				'amount': response.get('amount'),
				'filled': response.get('filled'),
				# 'remaining': response.get('remaining'),
				# 'cost': response.get('cost'),
				# 'trades': response.get('trades'),
				# 'info': response.get('info'),
				'fees': response.get('fees'),
				# 'lastUpdateTimestamp': response.get('lastUpdateTimestamp'),
				# 'postOnly': response.get('postOnly'),
				# 'reduceOnly': response.get('reduceOnly'),
				# 'stopPrice': response.get('stopPrice'),
				# 'triggerPrice': response.get('triggerPrice'),
				# 'takeProfitPrice': response.get('takeProfitPrice'),
				# 'stopLossPrice': response.get('stopLossPrice'),
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_ORDER_BOOK):
			output = {
				"bids": [
					{
						"price": item[0],
						"amount": item[1]
					} for item in response.get("bids")
				],
				"asks": [
					{
						"price": item[0],
						"amount": item[1]
					} for item in response.get("asks")
				],
				'datetime': response.get('datetime'),
				# 'nonce': response.get('nonce'),
				'symbol': response.get('symbol'),
				# 'timestamp': response.get('timestamp'),
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_ORDERS):
			output = [
				{
					'id': item.get('id'),
					'clientOrderId': item.get('clientOrderId'),
					'datetime': item.get('datetime'),
					# 'timestamp': item.get('timestamp'),
					# 'lastTradeTimestamp': item.get('lastTradeTimestamp'),
					'status': item.get('status'),
					'symbol': item.get('symbol'),
					'type': item.get('type'),
					# 'timeInForce': item.get('timeInForce'),
					'side': item.get('side'),
					'price': item.get('price'),
					# 'average': item.get('average'),
					'amount': item.get('amount'),
					'filled': item.get('filled'),
					# 'remaining': item.get('remaining'),
					# 'cost': item.get('cost'),
					# 'trades': item.get('trades'),
					# 'lastUpdateTimestamp': item.get('lastUpdateTimestamp'),
					# 'postOnly': item.get('postOnly'),
					# 'reduceOnly': item.get('reduceOnly'),
					# 'stopPrice': item.get('stopPrice'),
					# 'triggerPrice': item.get('triggerPrice'),
					# 'takeProfitPrice': item.get('takeProfitPrice'),
					# 'stopLossPrice': item.get('stopLossPrice'),
					# 'info': item.get('info'),
					'fees': item.get('fees')
				} for item in response
			]

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_STATUS):
			output = {
				'status': response.get('status'),
				# 'updated': response.get('updated'),
				# 'eta': response.get('eta'),
				# 'url': response.get('url'),
				# 'info': response.get('info'),
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_TICKER):
			output = {
				"symbol": response.get("symbol"),
				"datetime": response.get("datetime"),
				"last": response.get("last"),
				# "open": response.get("open"),
				# "high": response.get("high"),
				# "low": response.get("low"),
				# "close": response.get("close"),
				# "bid": response.get("bid"),
				# "ask": response.get("ask"),
				# "change": response.get("change"),
				# "percentage": response.get("percentage"),
				# "average": response.get("average"),
				# "baseVolume": response.get("baseVolume"),
				# "quoteVolume": response.get("quoteVolume"),
				# "info": response.get("info")
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_TICKERS):
			output = {
				key: {
					'symbol': value.get('symbol'),
					# 'timestamp': value.get('timestamp'),
					'datetime': value.get('datetime'),
					# 'high': value.get('high'),
					# 'low': value.get('low'),
					# 'bid': value.get('bid'),
					# 'bidVolume': value.get('bidVolume'),
					# 'ask': value.get('ask'),
					# 'askVolume': value.get('askVolume'),
					# 'vwap': value.get('vwap'),
					# 'open': value.get('open'),
					# 'close': value.get('close'),
					'last': value.get('last'),
					# 'previousClose': value.get('previousClose'),
					# 'change': value.get('change'),
					# 'percentage': value.get('percentage'),
					# 'average': value.get('average'),
					# 'baseVolume': value.get('baseVolume'),
					# 'quoteVolume': value.get('quoteVolume'),
					# 'info': value.get('info')
				} for key, value in response.items()
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_TRADES):
			output = [
				{
					# 'info': item.get('info'),
					# 'timestamp': item.get('timestamp'),
					'datetime': item.get('datetime'),
					'symbol': item.get('symbol'),
					'id': item.get('id'),
					'order': item.get('order'),
					'type': item.get('type'),
					# 'takerOrMaker': item.get('takerOrMaker'),
					'side': item.get('side'),
					'price': item.get('price'),
					'amount': item.get('amount'),
					# 'cost': item.get('cost'),
					'fee': item.get('fee'),
					# 'fees': item.get('fees'),
				} for item in response
			]

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_TRADING_FEE):
			output = {
				# 'info': response.get('info'),
				'symbol': response.get('symbol'),
				'maker': response.get('maker'),
				'taker': response.get('taker'),
				# 'percentage': response.get('percentage'),
				# 'tierBased': response.get('tierBased'),
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.SET_SANDBOX_MODE):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.WITHDRAW):
			output = response

			return output
		else:
			return response

	def dump(self, target: Any):
		try:
			if isinstance(target, str):
				return target

			if isinstance(target, DotMap):
				target = target.toDict()

			if isinstance(target, Dict):
				return json.dumps(target, indent=2)

			return jsonpickle.encode(target, unpicklable=True, indent=2)
		except (Exception,):
			return target


model = Model.instance()
