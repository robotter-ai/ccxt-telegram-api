import asyncio
from collections import OrderedDict

import jsonpickle
import logging
import os
import textwrap
import traceback
from dotmap import DotMap
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, filters, MessageHandler
from typing import Any, Dict, List
from singleton.singleton import ThreadSafeSingleton

# noinspection PyUnresolvedReferences
import ccxt as sync_ccxt
# noinspection PyUnresolvedReferences
import ccxt.async_support as async_ccxt
from ccxt.base.types import OrderType, OrderSide

ccxt = sync_ccxt

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.ERROR)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_TELEGRAM_CHANNEL_ID")

administrator = os.getenv("TELEGRAM_ADMIN_USERNAME", "").strip().replace("@", "")
administrators = os.getenv("TELEGRAM_ADMIN_USERNAMES", "").split(",")
administrators = [username.strip().replace("@", "") for username in administrators if username.strip()]
TELEGRAM_ADMIN_USERNAMES = [administrator] + administrators if administrator else administrators

EXCHANGE_NAME = os.getenv("EXCHANGE_ID", "binance")
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")
EXCHANGE_API_SECRET = os.getenv("EXCHANGE_API_SECRET")
EXCHANGE_ENVIRONMENT = os.getenv("EXCHANGE_ENVIRONMENT", "production")
EXCHANGE_SUB_ACCOUNT_ID = os.getenv("EXCHANGE_SUB_ACCOUNT_ID")

UNAUTHORIZED_USER_MESSAGE = "Unauthorized user."

exchange = getattr(ccxt, EXCHANGE_NAME)({
	"apiKey": EXCHANGE_API_KEY,
	"secret": EXCHANGE_API_SECRET,
	"options": {
		"environment": EXCHANGE_ENVIRONMENT,
		"subaccountId": EXCHANGE_SUB_ACCOUNT_ID,
	}
})

exchange.set_sandbox_mode(True)


def sync_handle_exceptions(method):

	@wraps(method)
	def wrapper(*args, **kwargs):
		try:
			return method(*args, **kwargs)
		except Exception as exception:
			try:
				asyncio.get_event_loop().run_until_complete(
					Telegram.instance().send_message(
						str(exception)
					)
				)
			except Exception as telegram_exception:
				logging.debug(telegram_exception)

			raise

	return wrapper


def async_handle_exceptions(method):
	@wraps(method)
	async def wrapper(*args, **kwargs):
		try:
			return await method(*args, **kwargs)
		except Exception as exception:
			try:
				await Telegram.instance().send_message(str(exception))
			except Exception as telegram_exception:
				logging.debug(telegram_exception)

			raise

	return wrapper


def handle_exceptions(cls):
	for attr, method in cls.__dict__.items():
		if callable(method):
			if asyncio.iscoroutinefunction(method):
				setattr(cls, attr, async_handle_exceptions(method))
			else:
				setattr(cls, attr, sync_handle_exceptions(method))

	return cls


@handle_exceptions
@ThreadSafeSingleton
class Telegram(object):

	def __init__(self):
		self.model = Model.instance()

	# noinspection PyMethodMayBeStatic
	def initialize(self):
		application = Application.builder().token(TELEGRAM_TOKEN).build()

		application.add_handler(CommandHandler("start", self.start))
		application.add_handler(CommandHandler("help", self.help))
		application.add_handler(CommandHandler("balance", self.get_balance))
		application.add_handler(CommandHandler("balances", self.get_balances))
		application.add_handler(CommandHandler("openOrders", self.get_open_orders))
		application.add_handler(CommandHandler("marketBuyOrder", self.market_buy_order))
		application.add_handler(CommandHandler("marketSellOrder", self.market_sell_order))
		application.add_handler(CommandHandler("limitBuyOrder", self.limit_buy_order))
		application.add_handler(CommandHandler("limitSellOrder", self.limit_sell_order))
		application.add_handler(CommandHandler("placeOrder", self.place_order))

		application.add_handler(CallbackQueryHandler(self.button_handler))
		application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_handler))
		application.add_handler(MessageHandler(filters.COMMAND, self.magic_command_handler))

		application.run_polling()

	# noinspection PyMethodMayBeStatic
	def is_admin(self, username) -> bool:
		if TELEGRAM_ADMIN_USERNAMES and isinstance(TELEGRAM_ADMIN_USERNAMES, List):
			return username in TELEGRAM_ADMIN_USERNAMES

		return False

	async def validate_request(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> bool:
		# noinspection PyBroadException
		try:
			if not self.is_admin(update.message.from_user.username):
				await self.send_message(UNAUTHORIZED_USER_MESSAGE)

				return False

			return True
		except Exception:
			return False

	async def button_handler(self, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None):
		if not await self.validate_request(update, context):
			return

		query = update.callback_query
		await query.answer()
		data = query.data

		if data == "balance":
			context.user_data["balance"] = ""
			await self.send_message("Enter the token id. Ex: btc")
			context.user_data["balance_step"] = "ask_token_id"
		elif data == "balances":
			await self.get_balances(update, context, query, data)
		elif data == "open_orders":
			context.user_data["open_orders"] = ""
			await self.send_message("Enter the market id. Ex: btcusdc")
			context.user_data["open_orders_step"] = "ask_market_id"
		elif data == "place_market_buy_order":
			context.user_data["place_market_buy_order"] = {}
			await self.send_message("Enter the market id. Ex: btcusdc")
			context.user_data["place_market_buy_order_step"] = "ask_market_id"
		elif data == "place_market_sell_order":
			context.user_data["place_market_sell_order"] = {}
			await self.send_message("Enter the market id. Ex: btcusdc")
			context.user_data["place_market_sell_order_step"] = "ask_market_id"
		elif data == "place_limit_buy_order":
			context.user_data["place_limit_buy_order"] = {}
			await self.send_message("Enter the market id. Ex: btcusdc")
			context.user_data["place_limit_buy_order_step"] = "ask_market_id"
		elif data == "place_limit_sell_order":
			context.user_data["place_limit_sell_order"] = {}
			await self.send_message("Enter the market id. Ex: btcusdc")
			context.user_data["place_limit_sell_order_step"] = "ask_market_id"
		elif data == "place_order":
			context.user_data["place_order"] = {}
			await self.send_message("Enter the order type. Ex: market; limit")
			context.user_data["place_order_step"] = "ask_order_type"
		else:
			await self.send_message("Unknown command.")

	async def text_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None):
		if not await self.validate_request(update, context):
			return

		data = context.user_data
		text = update.message.text

		if "balance_step" in data:
			if data["balance_step"] == "ask_token_id":
				if self.model.validate_token_id(text):
					data["balance"] = self.model.sanitize_token_id(text)
					try:
						await self.get_balance(update, context, query, data)
					finally:
						data.clear()
				else:
					await self.send_message("""Please enter a valid token id ("btc").""")
		if "open_orders_step" in data:
			if data["open_orders_step"] == "ask_market_id":
				if self.model.validate_market_id(text):
					data["open_orders"] = self.model.sanitize_market_id(text)
					try:
						await self.get_open_orders(update, context)
					finally:
						data.clear()
				else:
					await self.send_message("""Please enter a valid market id ("btcusdc").""")
		if "place_order_step" in data:
			if data["place_order_step"] == "ask_order_type":
				if self.model.validate_order_type(text):
					data["place_order"]["type"] = self.model.sanitize_order_type(text)
					data["place_order_step"] = "ask_order_side"
					await self.send_message("Enter the order side. Ex.: buy; sell")
				else:
					await self.send_message("""Please enter a valid order type ("market" or "limit").""")
			elif data["place_order_step"] == "ask_order_side":
				if self.model.validate_order_side(text):
					data["place_order"]["side"] = self.model.sanitize_order_side(text)
					data["place_order_step"] = "ask_market_id"
					await self.send_message("Enter the market symbol/ID. Ex.: btcusdc")
				else:
					await self.send_message("""Please enter a valid order side ("buy" or "sell").""")
			elif data["place_order_step"] == "ask_market_id":
				if self.model.validate_market_id(text):
					data["place_order"]["market_id"] = self.model.sanitize_market_id(text)
					data["place_order_step"] = "ask_amount"
					await self.send_message("Enter the amount. Ex.: 123.4567")
				else:
					await self.send_message("""Please enter a valid market id ("btcusdc").""")
			elif data["place_order_step"] == "ask_amount":
				if self.model.validate_order_amount(text):
					data["place_order"]["amount"] = self.model.sanitize_order_amount(text)
					if data["place_order"]["type"] == "market":
						data["place_order_step"] = "confirm"
						formatted = self.model.beautify(data["place_order"])
						await self.send_message(f"""Review your order and type "confirm" to place it or "cancel" to abort.\n\n{formatted}""")
					elif data["place_order"]["type"] == "limit":
						data["place_order_step"] = "ask_price"
						await self.send_message("Enter the price. Ex.: 123.4567")
					else:
						raise ValueError(f"""Unrecognized order type: {data["place_order"]["type"]}""")
				else:
					await self.send_message("Please enter a valid amount. Ex.: 123.4567")
			elif data["place_order_step"] == "ask_price":
				if self.model.validate_order_price(text):
					data["place_order"]["price"] = self.model.sanitize_order_price(text)
					data["place_order_step"] = "confirm"
					formatted = self.model.beautify(data["place_order"])
					await self.send_message(f"""Review your order and type "confirm" to place it or "cancel" to abort.\n\n{formatted}""")
				else:
					await self.send_message("Please enter a valid price. Ex.: 123.4567")
			elif data["place_order_step"] == "confirm":
				text = text.lower()
				if text == "confirm":
					try:
						await self.place_order(update, context, query, data["place_order"])
					finally:
						data.clear()
				elif text.lower() == "cancel":
					data.clear()
					await self.send_message("Order canceled.")
				else:
					await self.send_message("""Please type "confirm" to place the order or "cancel" to abort.""")
		else:
			await self.send_message("Please use /start for the menu.")

	async def magic_command_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		text = update.message.text
		command, *args = text.lstrip("/").split(maxsplit=1)
		args = args[0] if args else ""

		positional_args = []
		named_args = {}

		tokens = args.split()
		for token in tokens:
			if "=" in token:
				key, value = token.split("=", 1)
				named_args[key] = value
			else:
				positional_args.append(token)

		message = await getattr(self.model, command)(*positional_args, **named_args)

		message = self.model.handle_magic_method_output(message)

		await self.send_message(message, update, context, query)

	async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		command_buttons = [
			[InlineKeyboardButton("Get a Token Balance", callback_data="balance")],
			[InlineKeyboardButton("Get All Balances", callback_data="balances")],
			[InlineKeyboardButton("Getl All Open Orders from a Market", callback_data="open_orders")],
			[InlineKeyboardButton("Place a Market Buy Order", callback_data="place_market_buy_order")],
			[InlineKeyboardButton("Place a Market Sell Order", callback_data="place_market_sell_order")],
			[InlineKeyboardButton("Place a Limit Buy Order", callback_data="place_limit_buy_order")],
			[InlineKeyboardButton("Place a Limit Sell Order", callback_data="place_limit_sell_order")],
			[InlineKeyboardButton("Place a Custom Order", callback_data="place_order")],
		]
		reply_markup = InlineKeyboardMarkup(command_buttons)

		await self.send_message(
			textwrap.dedent(
				f"""
					*🤖 Welcome to {str(EXCHANGE_NAME).upper()} Trading Bot! 📈*
					
										*Available commands:*
					
					*/help*
					
					*/balances*
					
					*/balance* `<marketId>`
					
					*/openOrders* `<tokenId>`
					
					*/placeMarketBuyOrder* `<marketId> <amount>`
					
					*/placeMarketSellOrder* `<marketId> <amount>`
					
					*/placeLimitBuyOrder* `<marketId> <amount> <price>`
					
					*/placeLimitSellOrder* `<marketId> <amount> <price>`
					
					*/placeOrder* `<limit/market> <buy/sell> <marketId> <amount> <price>`
					
					
								*Type /help to get more information.
								Feel free to explore and trade safely!* 🚀
				"""
			),
			reply_markup=reply_markup
		)

	async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		await self.send_message(
			textwrap.dedent(
				f"""
					*🤖 Welcome to {str(EXCHANGE_NAME).upper()} Trading Bot! 📈*
					
					Here are the available commands:
					
					*ℹ️ Util Commands:*
						Show this information:
						*- /help*
					
					*🔍 Query Commands:*
						View all balances:
						*- /balances*
						View specific balance from a market:
						*- /balance* `<tokenId>`
						Get all open orders from a market:	
						*- /openOrders* `<marketId>`
					
					*🛒 Trading Commands:*
						Place a market buy order:
						*- /placeMarketBuyOrder* `<marketId> <amount>`
						Place a market sell order:
						*- /placeMarketSellOrder* `<marketId> <amount>`
						Place a limit buy order:
						*- /placeLimitBuyOrder* `<marketId> <amount> <price>`
						Place a limit sell order:
						*- /placeLimitSellOrder* `<marketId> <amount> <price>`
						Place a custom order:
						*- /placeOrder* `<limit/market> <buy/sell> <marketId> <amount> <price>`
					
					*🔧 Advanced Commands:*
						With this special command you can theoretically try any available CCXT command. Some examples are:
						
						*- /anyCCXTMethod* `<arg1Value> <arg2Name>=<arg2Value>`
						
						Examples:
						
						*/fetchTicker* `btcusdc`
						*/fetchTicker* `symbol=btcusdc`
					
					*Type /start for the menu.
					*Feel free to explore and trade safely!* 🚀
				"""
			)
		)

	async def get_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		value = context.args if context.args else data

		if self.model.validate_token_id(value):
			token_id = self.model.sanitize_token_id(value)
			message = await self.model.get_balance(token_id)

			message = self.model.beautify(message)
			await self.send_message(message, update, context, query)
		else:
			await self.send_message("""Please enter a valid token id ("btc").""")

	async def get_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		message = await self.model.get_balances()

		message = self.model.beautify(message)
		await self.send_message(message, update, context, query)

	async def get_open_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		market_id = context.args[0] if context.args else context.user_data["open_orders"]
		message = await self.model.get_open_orders(market_id)

		message = self.model.beautify(message)
		await self.send_message(message, update, context, query)

	async def market_buy_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		if context.args:
			market_id, amount = context.args[0], float(context.args[1])
		else:
			market_id, amount = data["market_id"], data["amount"]
		message = await self.model.market_buy_order(market_id, amount)
		message = self.model.beautify(message)
		message = f"Market Buy Order placed:\n{message}"

		await self.send_message(update, context, message)

	async def market_sell_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount = context.args[0], float(context.args[1])
			message = await self.model.market_sell_order(market_id, amount)
			message = self.model.beautify(message)
			message = f"Market Sell Order placed:\n{message}"

			await self.send_message(update, context, message)
		except Exception as e:
			await self.send_message("Usage: /marketSellOrder <marketId> <amount> <price>")
			raise e

	async def limit_buy_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount, price = context.args[0], float(context.args[1]), float(context.args[2])
			message = await self.model.limit_buy_order(market_id, amount, price)
			message = self.model.beautify(message)
			message = f"Limit Buy Order placed:\n{message}"

			await self.send_message(update, context, message)
		except Exception as e:
			await self.send_message("Usage: /limitBuyOrder <marketId> <amount> <price>")
			raise e

	async def limit_sell_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount, price = context.args[0], float(context.args[1]), float(context.args[2])
			message = await self.model.limit_sell_order(market_id, amount, price)
			message = self.model.beautify(message)
			message = f"Limit Sell Order placed:\n{message}"

			await self.send_message(update, context, message)
		except Exception as e:
			await self.send_message("Usage: /limitSellOrder <marketId> <amount> <price>")
			raise e

	async def place_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		order_type, order_side, market_id, amount, price = (None, None, None, None, None)

		if data:
			if len(data.values()) == 4:
				order_type, order_side, market_id, amount = data.values()
			elif len(data.values()) == 5:
				order_type, order_side, market_id, amount, price = data.values()
		else:
			arguments = context.args
			if len(arguments) == 4:
				order_type, order_side, market_id, amount = arguments[0], arguments[1], arguments[2], arguments[3]
			elif len(arguments) == 5:
				order_type, order_side, market_id, amount, price = arguments[0], arguments[1], arguments[2], arguments[3], arguments[4]
			else:
				message = """Unrecognized command. Usage:\n\n/place <limit/market> <buy/sell> <marketId> <amount> <price>"""

				await self.send_message(update, context, message)

				return

		# noinspection PyTypeChecker
		order_type: OrderType = str(order_type).lower()
		# noinspection PyTypeChecker
		order_side: OrderSide = str(order_side).lower()

		if order_type not in ["limit", "market"]:
			try:
				await self.send_message("""Invalid order type. Allowed values are: limit/market""")
			# await self.send_message(update, context, message)
			except Exception as e:
				raise e

		if order_side not in ["buy", "sell"]:
			message = """Invalid order side. Allowed values are: buy/sell"""

			await self.send_message(update, context, message)

			return

		try:
			amount = float(amount)
		except ValueError:
			message = """Invalid amount. Ex.: 123.45"""

			await self.send_message(update, context, message)

			return

		try:
			if price is not None:
				price = float(price)
		except ValueError:
			message = """Invalid price. Ex.: 123.45"""
			await self.send_message(update, context, message)

			return

		message = await self.model.place_order(market_id, order_type, order_side, amount, price)
		message = self.model.beautify(message)
		message = f"Order placed:\n\n{message}"

		await self.send_message(update, context, message)

	# noinspection PyMethodMayBeStatic,PyUnusedLocal
	async def send_message(self, message: str, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None, query: CallbackQuery = None, parse_mode: str = "Markdown", reply_markup = None):
		formatted = str(message)
		max_length = 4096

		def get_chat_id(update):
			if update.message:
				return update.message.chat_id
			elif update.callback_query:
				return update.callback_query.message.chat_id
			else:
				return None

		def get_reply_method(update: Any = None):
			if update:
				if update.message:
					return update.message.reply_text
				elif update.callback_query:
					# Another possible option to investigate: query.message.reply_text

					async def send_message(message: str):
						await context.bot.send_message(get_chat_id(update), message)

					return send_message

		reply_method = get_reply_method(update)

		if len(formatted) <= max_length:
			await reply_method(formatted)
		else:
			for start in range(0, len(formatted), max_length):
				message_part = formatted[start:start + max_length]

				await reply_method(message_part)


# noinspection PyMethodMayBeStatic
@handle_exceptions
@ThreadSafeSingleton
class Model(object):
	def sanitize_token_id(self, target):
		return str(target).upper()

	def sanitize_market_id(self, target):
		return str(target).replace("/", "").upper()

	def sanitize_order_type(self, target):
		return str(target).lower()

	def sanitize_order_side(self, target):
		return str(target).lower()

	def sanitize_order_amount(self, target):
		return float(target)

	def sanitize_order_price(self, target):
		return float(target)

	def validate_token_id(self, target):
		return True

	def validate_market_id(self, target):
		return True

	def validate_order_type(self, target):
		if self.sanitize_order_type(target) in ["limit", "market"]:
			return True

		return False

	def validate_order_side(self, target):
		if self.sanitize_order_side(target) in ["buy", "sell"]:
			return True

		return False

	def validate_order_amount(self, target):
		return True

	def validate_order_price(self, target):
		return True

	async def get_balance(self, token_id: str):
		balances = await self.get_balances()
		balance = balances.get("total", {}).get(token_id.upper(), 0)

		return {token_id.upper(): balance}

	async def get_balances(self):
		balances = exchange.fetch_balance()

		non_zero_balances = {k: v for k, v in balances.get("total", {}).items() if v > 0}

		sorted_balances = OrderedDict(sorted(non_zero_balances.items(), key=lambda x: x[1], reverse=True))

		return {"total": sorted_balances}

	async def get_open_orders(self, market_id: str):
		return exchange.fetch_open_orders(market_id)

	async def market_buy_order(self, market_id: str, amount: float):
		return exchange.create_order(market_id, "market", "buy", amount)

	async def market_sell_order(self, market_id: str, amount: float):
		return exchange.create_order(market_id, "market", "sell", amount)

	async def limit_buy_order(self, market_id: str, amount: float, price: float):
		return exchange.create_order(market_id, "limit", "buy", amount, price)

	async def limit_sell_order(self, market_id: str, amount: float, price: float):
		return exchange.create_order(market_id, "limit", "sell", amount, price)

	async def place_order(self, market: str, order_type: OrderType, order_side: OrderSide, amount: float, price: float = None):
		return exchange.create_order(market, order_type, order_side, amount, price)

	def __getattr__(self, name):
		attribute = getattr(exchange, name, None)
		if callable(attribute):
			async def method(*args, **kwargs):
				return attribute(*args, **kwargs)
			return method
		return attribute

	def beautify(self, target: Any, indent=0) -> str:
		if isinstance(target, dict):
			result = ""
			for key, value in target.items():
				result += "  " * indent + str(key) + ":"
				if isinstance(value, (dict, list)):
					result += "\n" + self.model.beautify(value, indent + 1)
				else:
					result += " " + str(value) + "\n"
			return result
		elif isinstance(target, list):
			result = ""
			for index, item in enumerate(target):
				result += "  " * indent + f"-"
				if isinstance(item, (dict, list)):
					result += "\n" + self.model.beautify(item, indent + 1)
				else:
					result += " " + str(item) + "\n"
			return result
		else:
			return "  " * indent + str(target) + "\n"

	def handle_magic_method_output(self, target):
		return self.beautify(target)

	def dump(self, target: Any):
		try:
			if isinstance(target, str):
				return target

			if isinstance(target, DotMap):
				target = target.toDict()

			if isinstance(target, Dict):
				return str(target)

			return jsonpickle.encode(target, unpicklable=True, indent=2)
		except (Exception,):
			return target


async def test():
	pass
	# print(await model.get_balances())
	# print(await model.get_balance("BTC"))
	# print(await model.get_open_orders("BTCUSDT"))
	# print(await model.market_buy_order("BTCUSDT", 0.00009))
	# print(await model.market_sell_order("BTCUSDT", 0.00009))
	# print(await model.limit_buy_order("BTCUSDT", 0.001, 20000))
	# print(await model.limit_sell_order("BTCUSDT", 0.00009, 99999))
	# print(await model.place_order("BTCUSDT", "market", "buy", 0.0001))
	# print(await model.place_order("BTCUSDT", "limit", "sell", 0.00009, 99999))

	# print(await model.fetch_markets())
	# print(await model.fetch_balance())
	# print(await model.fetch_ticker("BTCUSDT"))

	# await self.place_order(None, None, {
	# 	"type": "market",
	# 	"side": "buy",
	# 	"market_id": "BTCUSDT",
	# 	"amount": 0.00009
	# })

	# await self.place_order(None, None, {
	# 	"type": "limit",
	# 	"side": "sell",
	# 	"market_id": "BTCUSDT",
	# 	"amount": 0.00009,
	# 	"price": 99999
	# })


def main():
	Telegram.instance().initialize()


if __name__ == "__main__":
	main()
