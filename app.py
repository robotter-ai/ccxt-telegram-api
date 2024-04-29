import json

import re

import asyncio
from collections import OrderedDict

import jsonpickle
import logging
import os
import requests
import textwrap
import traceback
from dotmap import DotMap
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, filters, MessageHandler
from typing import Any, Dict, List
from singleton.singleton import ThreadSafeSingleton
from enum import Enum

# noinspection PyUnresolvedReferences
import ccxt as sync_ccxt
# noinspection PyUnresolvedReferences
import ccxt.async_support as async_ccxt
from ccxt import Exchange as CommunityExchange
from ccxt.async_support import Exchange as ProExchange

from ccxt.base.types import OrderType, OrderSide
from integration_tests import IntegrationTests

ccxt = sync_ccxt

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.ERROR)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
TELEGRAM_LISTEN_COMMANDS: bool = os.getenv("TELEGRAM_LISTEN_COMMANDS", "false").lower() in ["true", "1"]

administrator = os.getenv("TELEGRAM_ADMIN_USERNAME", "").strip().replace("@", "")
administrators = os.getenv("TELEGRAM_ADMIN_USERNAMES", "").split(",")
administrators = [username.strip().replace("@", "") for username in administrators if username.strip()]
TELEGRAM_ADMIN_USERNAMES = [administrator] + administrators if administrator else administrators

EXCHANGE_ID = os.getenv("EXCHANGE_ID", "binance")
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")
EXCHANGE_API_SECRET = os.getenv("EXCHANGE_API_SECRET")
EXCHANGE_ENVIRONMENT = os.getenv("EXCHANGE_ENVIRONMENT", "production")
EXCHANGE_SUB_ACCOUNT_ID = os.getenv("EXCHANGE_SUB_ACCOUNT_ID")

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


class MagicMethod(Enum):
	CANCEL_ALL_ORDERS = "cancelAllOrders"
	CANCEL_ORDER = "cancelOrder"
	CREATE_ORDER = "createOrder"
	DESCRIBE = "describe"
	DEPOSIT = "deposit"
	FETCH_BALANCE = "fetchBalance"
	FETCH_CLOSED_ORDERS = "fetchClosedOrders"
	FETCH_CURRENCIES = "fetchCurrencies"
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
				logging.debug(traceback.format_exception(telegram_exception))

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
				logging.debug(traceback.format_exception(telegram_exception))

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
		self.application = Application.builder().token(TELEGRAM_TOKEN).build()

		self.application.add_handler(CommandHandler("start", self.start))
		self.application.add_handler(CommandHandler("help", self.help))
		self.application.add_handler(CommandHandler("balance", self.get_balance))
		self.application.add_handler(CommandHandler("balances", self.get_balances))
		self.application.add_handler(CommandHandler("openOrders", self.get_open_orders))
		self.application.add_handler(CommandHandler("placeMarketBuyOrder", self.market_buy_order))
		self.application.add_handler(CommandHandler("placeMarketSellOrder", self.market_sell_order))
		self.application.add_handler(CommandHandler("placeLimitBuyOrder", self.limit_buy_order))
		self.application.add_handler(CommandHandler("placeLimitSellOrder", self.limit_sell_order))
		self.application.add_handler(CommandHandler("placeOrder", self.place_order))

		self.application.add_handler(CallbackQueryHandler(self.button_handler))
		self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_handler))
		self.application.add_handler(MessageHandler(filters.COMMAND, self.handle_magic_command_input))

	def run(self):
		if TELEGRAM_LISTEN_COMMANDS:
			self.application.run_polling()

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
		query = update.callback_query
		await query.answer()
		data = query.data

		if data == "balance":
			context.user_data["balance"] = ""
			await self.send_message("Enter the token id. Ex: btc", update, context, query)
			context.user_data["balance_step"] = "ask_token_id"
		elif data == "balances":
			await self.get_balances(update, context, query, data)
		elif data == "open_orders":
			context.user_data["open_orders"] = ""
			await self.send_message("Enter the market id. Ex: btcusdc", update, context, query)
			context.user_data["open_orders_step"] = "ask_market_id"
		elif data == "place_market_buy_order":
			context.user_data["place_market_buy_order"] = {}
			context.user_data["place_market_buy_order"]["order_type"] = "market"
			context.user_data["place_market_buy_order"]["order_side"] = "buy"
			await self.send_message("Enter the market id. Ex: btcusdc", update, context, query)
			context.user_data["place_market_buy_order_step"] = "ask_market_id"
		elif data == "place_market_sell_order":
			context.user_data["place_market_sell_order"] = {}
			context.user_data["place_market_sell_order"]["order_type"] = "market"
			context.user_data["place_market_sell_order"]["order_side"] = "sell"
			await self.send_message("Enter the market id. Ex: btcusdc", update, context, query)
			context.user_data["place_market_sell_order_step"] = "ask_market_id"
		elif data == "place_limit_buy_order":
			context.user_data["place_limit_buy_order"] = {}
			context.user_data["place_limit_buy_order"]["order_type"] = "limit"
			context.user_data["place_limit_buy_order"]["order_side"] = "buy"
			await self.send_message("Enter the market id. Ex: btcusdc", update, context, query)
			context.user_data["place_limit_buy_order_step"] = "ask_market_id"
		elif data == "place_limit_sell_order":
			context.user_data["place_limit_sell_order"] = {}
			context.user_data["place_limit_sell_order"]["order_type"] = "limit"
			context.user_data["place_limit_sell_order"]["order_side"] = "sell"
			await self.send_message("Enter the market id. Ex: btcusdc", update, context, query)
			context.user_data["place_limit_sell_order_step"] = "ask_market_id"
		elif data == "place_order":
			context.user_data["place_order"] = {}
			await self.send_message("Enter the order type. Ex: market; limit", update, context, query)
			context.user_data["place_order_step"] = "ask_order_type"
		else:
			await self.send_message("Unknown command.", update, context, query)

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
					await self.send_message("""Please enter a valid token id ("btc").""", update, context, query)
		if "open_orders_step" in data:
			if data["open_orders_step"] == "ask_market_id":
				if self.model.validate_market_id(text):
					data["open_orders"] = self.model.sanitize_market_id(text)
					try:
						await self.get_open_orders(update, context, query, data)
					finally:
						data.clear()
				else:
					await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
		if "place_market_buy_order_step" in data:
			if data["place_market_buy_order_step"] == "ask_market_id":
				if self.model.validate_market_id(text):
					data["place_market_buy_order"]["market_id"] = self.model.sanitize_market_id(text)
					data["place_market_buy_order_step"] = "ask_amount"
					await self.send_message("Enter the amount. Ex.: 123.4567", update, context, query)
				else:
					await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
			elif data["place_market_buy_order_step"] == "ask_amount":
				if self.model.validate_order_amount(text):
					data["place_market_buy_order"]["amount"] = self.model.sanitize_order_amount(text)
					data["place_market_buy_order_step"] = "confirm"
					formatted = self.model.beautify(data["place_market_buy_order"])
					await self.send_message(f"""Review your order and type "confirm" to place it or "cancel" to abort.\n\n{formatted}""", update, context, query)
				else:
					await self.send_message("Please enter a valid amount. Ex.: 123.4567", update, context, query)
			elif data["place_market_buy_order_step"] == "confirm":
				text = text.lower()
				if text == "confirm":
					try:
						await self.market_buy_order(update, context, query, data["place_market_buy_order"])
					finally:
						data.clear()
				elif text.lower() == "cancel":
					data.clear()
					await self.send_message("Order canceled.", update, context, query)
				else:
					await self.send_message("""Please type "confirm" to place the order or "cancel" to abort.""", update, context, query)
		if "place_market_sell_order_step" in data:
			if data["place_market_sell_order_step"] == "ask_market_id":
				if self.model.validate_market_id(text):
					data["place_market_sell_order"]["market_id"] = self.model.sanitize_market_id(text)
					data["place_market_sell_order_step"] = "ask_amount"
					await self.send_message("Enter the amount. Ex.: 123.4567", update, context, query)
				else:
					await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
			elif data["place_market_sell_order_step"] == "ask_amount":
				if self.model.validate_order_amount(text):
					data["place_market_sell_order"]["amount"] = self.model.sanitize_order_amount(text)
					data["place_market_sell_order_step"] = "confirm"
					formatted = self.model.beautify(data["place_market_sell_order"])
					await self.send_message(f"""Review your order and type "confirm" to place it or "cancel" to abort.\n\n{formatted}""", update, context, query)
				else:
					await self.send_message("Please enter a valid amount. Ex.: 123.4567", update, context, query)
			elif data["place_market_sell_order_step"] == "confirm":
				text = text.lower()
				if text == "confirm":
					try:
						await self.market_sell_order(update, context, query, data["place_market_sell_order"])
					finally:
						data.clear()
				elif text.lower() == "cancel":
					data.clear()
					await self.send_message("Order canceled.", update, context, query)
				else:
					await self.send_message("""Please type "confirm" to place the order or "cancel" to abort.""", update, context, query)
		if "place_limit_buy_order_step" in data:
			if data["place_limit_buy_order_step"] == "ask_market_id":
				if self.model.validate_market_id(text):
					data["place_limit_buy_order"]["market_id"] = self.model.sanitize_market_id(text)
					data["place_limit_buy_order_step"] = "ask_amount"
					await self.send_message("Enter the amount. Ex.: 123.4567", update, context, query)
				else:
					await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
			elif data["place_limit_buy_order_step"] == "ask_amount":
				if self.model.validate_order_amount(text):
					data["place_limit_buy_order"]["amount"] = self.model.sanitize_order_amount(text)
					data["place_limit_buy_order_step"] = "ask_price"
					await self.send_message("Enter the price. Ex.: 123.4567", update, context, query)
				else:
					await self.send_message("Please enter a valid amount. Ex.: 123.4567", update, context, query)
			elif data["place_limit_buy_order_step"] == "ask_price":
				if self.model.validate_order_price(text):
					data["place_limit_buy_order"]["price"] = self.model.sanitize_order_price(text)
					data["place_limit_buy_order_step"] = "confirm"
					formatted = self.model.beautify(data["place_limit_buy_order"])
					await self.send_message(f"""Review your order and type "confirm" to place it or "cancel" to abort.\n\n{formatted}""", update, context, query)
				else:
					await self.send_message("Please enter a valid price. Ex.: 123.4567", update, context, query)
			elif data["place_limit_buy_order_step"] == "confirm":
				text = text.lower()
				if text == "confirm":
					try:
						await self.limit_buy_order(update, context, query, data["place_limit_buy_order"])
					finally:
						data.clear()
				elif text.lower() == "cancel":
					data.clear()
					await self.send_message("Order canceled.", update, context, query)
				else:
					await self.send_message("""Please type "confirm" to place the order or "cancel" to abort.""", update, context, query)
		if "place_limit_sell_order_step" in data:
			if data["place_limit_sell_order_step"] == "ask_market_id":
				if self.model.validate_market_id(text):
					data["place_limit_sell_order"]["market_id"] = self.model.sanitize_market_id(text)
					data["place_limit_sell_order_step"] = "ask_amount"
					await self.send_message("Enter the amount. Ex.: 123.4567", update, context, query)
				else:
					await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
			elif data["place_limit_sell_order_step"] == "ask_amount":
				if self.model.validate_order_amount(text):
					data["place_limit_sell_order"]["amount"] = self.model.sanitize_order_amount(text)
					data["place_limit_sell_order_step"] = "ask_price"
					await self.send_message("Enter the price. Ex.: 123.4567", update, context, query)
				else:
					await self.send_message("Please enter a valid amount. Ex.: 123.4567", update, context, query)
			elif data["place_limit_sell_order_step"] == "ask_price":
				if self.model.validate_order_price(text):
					data["place_limit_sell_order"]["price"] = self.model.sanitize_order_price(text)
					data["place_limit_sell_order_step"] = "confirm"
					formatted = self.model.beautify(data["place_limit_sell_order"])
					await self.send_message(f"""Review your order and type "confirm" to place it or "cancel" to abort.\n\n{formatted}""", update, context, query)
				else:
					await self.send_message("Please enter a valid price. Ex.: 123.4567", update, context, query)
			elif data["place_limit_sell_order_step"] == "confirm":
				text = text.lower()
				if text == "confirm":
					try:
						await self.limit_sell_order(update, context, query, data["place_limit_sell_order"])
					finally:
						data.clear()
				elif text.lower() == "cancel":
					data.clear()
					await self.send_message("Order canceled.", update, context, query)
				else:
					await self.send_message("""Please type "confirm" to place the order or "cancel" to abort.""", update, context, query)
		if "place_order_step" in data:
			if data["place_order_step"] == "ask_order_type":
				if self.model.validate_order_type(text):
					data["place_order"]["order_type"] = self.model.sanitize_order_type(text)
					data["place_order_step"] = "ask_order_side"
					await self.send_message("Enter the order side. Ex.: buy; sell", update, context, query)
				else:
					await self.send_message("""Please enter a valid order type ("market" or "limit").""", update, context, query)
			elif data["place_order_step"] == "ask_order_side":
				if self.model.validate_order_side(text):
					data["place_order"]["order_side"] = self.model.sanitize_order_side(text)
					data["place_order_step"] = "ask_market_id"
					await self.send_message("Enter the market symbol/ID. Ex.: btcusdc", update, context, query)
				else:
					await self.send_message("""Please enter a valid order side ("buy" or "sell").""", update, context, query)
			elif data["place_order_step"] == "ask_market_id":
				if self.model.validate_market_id(text):
					data["place_order"]["market_id"] = self.model.sanitize_market_id(text)
					data["place_order_step"] = "ask_amount"
					await self.send_message("Enter the amount. Ex.: 123.4567", update, context, query)
				else:
					await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
			elif data["place_order_step"] == "ask_amount":
				if self.model.validate_order_amount(text):
					data["place_order"]["amount"] = self.model.sanitize_order_amount(text)
					if data["place_order"]["order_type"] == "market":
						data["place_order_step"] = "confirm"
						formatted = self.model.beautify(data["place_order"])
						await self.send_message(f"""Review your order and type "confirm" to place it or "cancel" to abort.\n\n{formatted}""", update, context, query)
					elif data["place_order"]["order_type"] == "limit":
						data["place_order_step"] = "ask_price"
						await self.send_message("Enter the price. Ex.: 123.4567", update, context, query)
					else:
						raise ValueError(f"""Unrecognized order type: {data["place_order"]["type"]}""")
				else:
					await self.send_message("Please enter a valid amount. Ex.: 123.4567", update, context, query)
			elif data["place_order_step"] == "ask_price":
				if self.model.validate_order_price(text):
					data["place_order"]["price"] = self.model.sanitize_order_price(text)
					data["place_order_step"] = "confirm"
					formatted = self.model.beautify(data["place_order"])
					await self.send_message(f"""Review your order and type "confirm" to place it or "cancel" to abort.\n\n{formatted}""", update, context, query)
				else:
					await self.send_message("Please enter a valid price. Ex.: 123.4567", update, context, query)
			elif data["place_order_step"] == "confirm":
				text = text.lower()
				if text == "confirm":
					try:
						await self.place_order(update, context, query, data["place_order"])
					finally:
						data.clear()
				elif text.lower() == "cancel":
					data.clear()
					await self.send_message("Order canceled.", update, context, query)
				else:
					await self.send_message("""Please type "confirm" to place the order or "cancel" to abort.""", update, context, query)

	async def handle_magic_command_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
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
				named_args[key] = self.parse_argument(value)
			else:
				positional_args.append(self.parse_argument(token))

		method = getattr(self.model, command, None)

		if not method:
			await self.send_message(f"""Unrecognized command "{command}" for exchange {EXCHANGE_ID}.""", update, context, query)
			return

		message = await method(*positional_args, **named_args)

		message = self.model.beautify(message)

		await self.send_message(message, update, context, query)

	# noinspection PyMethodMayBeStatic
	def parse_argument(self, arg):
		try:
			return json.loads(arg)
		except json.JSONDecodeError:
			if arg.isdigit():
				return int(arg)
			try:
				return float(arg)
			except ValueError:
				if arg.lower() in ["true", "false"]:
					return arg.lower() == "true"

		return arg

	async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		command_buttons = [
			# [InlineKeyboardButton("Get a Token Balance", callback_data="balance")],
			[InlineKeyboardButton("Get All Balances", callback_data="balances")],
			[InlineKeyboardButton("Get All Open Orders from a Market", callback_data="open_orders")],
			# [InlineKeyboardButton("Place a Market Buy Order", callback_data="place_market_buy_order")],
			# [InlineKeyboardButton("Place a Market Sell Order", callback_data="place_market_sell_order")],
			# [InlineKeyboardButton("Place a Limit Buy Order", callback_data="place_limit_buy_order")],
			# [InlineKeyboardButton("Place a Limit Sell Order", callback_data="place_limit_sell_order")],
			[InlineKeyboardButton("Place a Custom Order", callback_data="place_order")],
		]
		reply_markup = InlineKeyboardMarkup(command_buttons)

		await self.send_message(
			textwrap.dedent(
				f"""
					*🤖 Welcome to {str(EXCHANGE_ID).upper()} Trading Bot! 📈*
					
					*Available commands:*
					
					*/help*
					
					*/balances*
					
					*/openOrders* `<marketId>`
					
					*/placeOrder* `<limit/market> <buy/sell> <marketId> <amount> <price>`
					
					
					*Type /help to get more information and more advanced commands. Feel free to explore and trade safely!* 🚀
				"""
			),
			update,
			context,
			query,
			parse_mode="Markdown",
			reply_markup=reply_markup
		)

	async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		await self.send_message(
			textwrap.dedent(
				f"""
					*🤖 Welcome to {str(EXCHANGE_ID).upper()} Trading Bot! 📈*
					
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
						With this special command you can theoretically try any available CCXT command. (Note that is also possible use named arguments.)
						
						*- /anyCCXTMethod* `<arg1Value> <arg2Name>=<arg2Value>`
						
						Examples:
					
						*/cancelAllOrders*
						*/cancelOrder* `<orderId> <marketId>`
						*/describe*	
						*/fetchBalance*
						*/fetchCurrencies*
						*/fetchMarkets*
						*/fetchOHLCV* `<marketId>`
						*/fetchOpenOrders* `<marketId>`
						*/fetchOrder* `<orderId> <marketId>`
						*/fetchOrderBook*
						*/fetchOrders* `<marketId>`
						*/fetchStatus*
						*/fetchTicker* `<marketId>`
						*/fetchTickers*
						*/fetchTradingFee* `<marketId>`
						*/setSandboxMode* `<true/false>`
					
					*Type /start for the menu.*
					*Feel free to explore and trade safely!* 🚀
				"""
			),
			update,
			context,
			query,
			parse_mode="Markdown"
		)

	async def get_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		if context.args:
			token_id = (context.args[0:1] or [None])[0]
		elif data:
			token_id = data.get("balance", None)
		else:
			token_id = None

		if self.model.validate_token_id(token_id):
			token_id = self.model.sanitize_token_id(token_id)
			message = await self.model.get_balance(token_id)

			message = self.model.beautify(message)
			await self.send_message(message, update, context, query)
		else:
			await self.send_message("""Please enter a valid token id ("btc").""", update, context, query)

	async def get_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		## Special case, this validation does not apply here because the action is called directly.
		# if not await self.validate_request(update, context):
		# 	return

		message = await self.model.get_balances()

		message = self.model.beautify(message)
		await self.send_message(message, update, context, query)

	async def get_open_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		if context.args:
			market_id = (context.args[0:1] or [None])[0]
		elif data:
			market_id = data.get("open_orders", None)
		else:
			market_id = None

		if self.model.validate_market_id(market_id):
			market_id = self.model.sanitize_market_id(market_id)
			message = await self.model.get_open_orders(market_id)

			message = self.model.beautify(message)
			await self.send_message(message, update, context, query)
		else:
			await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)

	async def market_buy_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		if context.args:
			market_id = (context.args[0:1] or [None])[0]
			amount = (context.args[1:2] or [None])[0]
		elif data:
			market_id = data.get("market_id", None)
			amount = data.get("amount", None)
		else:
			market_id = None
			amount = None

		if self.model.validate_market_id(market_id):
			market_id = self.model.sanitize_market_id(market_id)
		else:
			await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
			return

		if self.model.validate_order_amount(amount):
			amount = self.model.sanitize_order_amount(amount)
		else:
			await self.send_message("Please enter a valid amount. Ex.: 123.4567", update, context, query)
			return

		message = await self.model.market_buy_order(market_id, amount)

		message = self.model.beautify(message)
		message = f"Market buy order successfully placed:\n\n{message}"

		await self.send_message(message, update, context, query)

	async def market_sell_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if context.args:
			market_id = (context.args[0:1] or [None])[0]
			amount = (context.args[1:2] or [None])[0]
		elif data:
			market_id = data.get("market_id", None)
			amount = data.get("amount", None)
		else:
			market_id = None
			amount = None

		if self.model.validate_market_id(market_id):
			market_id = self.model.sanitize_market_id(market_id)
		else:
			await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
			return

		if self.model.validate_order_amount(amount):
			amount = self.model.sanitize_order_amount(amount)
		else:
			await self.send_message("Please enter a valid amount. Ex.: 123.4567", update, context, query)
			return

		message = await self.model.market_sell_order(market_id, amount)

		message = self.model.beautify(message)
		message = f"Market sell order successfully placed:\n\n{message}"

		await self.send_message(message, update, context, query)

	async def limit_buy_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if context.args:
			market_id = (context.args[0:1] or [None])[0]
			amount = (context.args[1:2] or [None])[0]
			price = (context.args[2:3] or [None])[0]
		elif data:
			market_id = data.get("market_id", None)
			amount = data.get("amount", None)
			price = data.get("price", None)
		else:
			market_id = None
			amount = None
			price = None

		if self.model.validate_market_id(market_id):
			market_id = self.model.sanitize_market_id(market_id)
		else:
			await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
			return

		if self.model.validate_order_amount(amount):
			amount = self.model.sanitize_order_amount(amount)
		else:
			await self.send_message("Please enter a valid amount. Ex.: 123.4567", update, context, query)
			return

		if self.model.validate_order_price(price):
			price = self.model.sanitize_order_price(price)
		else:
			await self.send_message("Please enter a valid price. Ex.: 123.4567", update, context, query)
			return

		message = await self.model.limit_buy_order(market_id, amount, price)

		message = self.model.beautify(message)
		message = f"Limit buy order successfully placed:\n\n{message}"

		await self.send_message(message, update, context, query)

	async def limit_sell_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if context.args:
			market_id = (context.args[0:1] or [None])[0]
			amount = (context.args[1:2] or [None])[0]
			price = (context.args[2:3] or [None])[0]
		elif data:
			market_id = data.get("market_id", None)
			amount = data.get("amount", None)
			price = data.get("price", None)
		else:
			market_id = None
			amount = None
			price = None

		if self.model.validate_market_id(market_id):
			market_id = self.model.sanitize_market_id(market_id)
		else:
			await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
			return

		if self.model.validate_order_amount(amount):
			amount = self.model.sanitize_order_amount(amount)
		else:
			await self.send_message("Please enter a valid amount. Ex.: 123.4567", update, context, query)
			return

		if self.model.validate_order_price(price):
			price = self.model.sanitize_order_price(price)
		else:
			await self.send_message("Please enter a valid price. Ex.: 123.4567", update, context, query)
			return

		message = await self.model.limit_sell_order(market_id, amount, price)

		message = self.model.beautify(message)
		message = f"Limit sell order successfully placed:\n\n{message}"

		await self.send_message(message, update, context, query)

	async def place_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if context.args:
			order_type = (context.args[0:1] or [None])[0]
			order_side = (context.args[1:2] or [None])[0]
			market_id = (context.args[2:3] or [None])[0]
			amount = (context.args[3:4] or [None])[0]
			price = (context.args[4:5] or [None])[0]
		elif data:
			order_type = data.get("order_type", None)
			order_side = data.get("order_side", None)
			market_id = data.get("market_id", None)
			amount = data.get("amount", None)
			price = data.get("price", None)
		else:
			order_type = None
			order_side = None
			market_id = None
			amount = None
			price = None

		if self.model.validate_order_type(order_type):
			order_type = self.model.sanitize_order_type(order_type)
		else:
			await self.send_message("""Please enter a valid order type ("market" or "limit").""", update, context, query)
			return

		if self.model.validate_order_side(order_side):
			order_side = self.model.sanitize_order_side(order_side)
		else:
			await self.send_message("""Please enter a valid order side ("buy" or "sell").""", update, context, query)
			return

		if self.model.validate_market_id(market_id):
			market_id = self.model.sanitize_market_id(market_id)
		else:
			await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
			return

		if self.model.validate_order_amount(amount):
			amount = self.model.sanitize_order_amount(amount)
		else:
			await self.send_message("Please enter a valid amount. Ex.: 123.4567", update, context, query)
			return

		if order_type == "limit":
			if self.model.validate_order_price(price):
				price = self.model.sanitize_order_price(price)
			else:
				await self.send_message("Please enter a valid price. Ex.: 123.4567", update, context, query)
				return

		message = await self.model.place_order(market_id, order_type, order_side, amount, price)

		message = self.model.beautify(message)
		message = f"Order successfully placed:\n\n{message}"

		await self.send_message(message, update, context, query)

	# noinspection PyMethodMayBeStatic,PyUnusedLocal
	async def send_message(self, message: str, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None, query: CallbackQuery = None, parse_mode: str = None, reply_markup = None):
		formatted = message
		max_length = 4096

		# noinspection PyUnusedLocal
		def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery):
			if update:
				if update.message:
					return update.message.chat_id
				elif update.callback_query:
					return update.callback_query.message.chat_id

			return TELEGRAM_CHANNEL_ID

		def get_reply_method(update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery, parse_mode: str = None, reply_markup: Any = None):
			async def query_send(message: str):
				return await query.message.reply_text(message, parse_mode=parse_mode, reply_markup=reply_markup)

			async def update_send(message: str):
				return await update.message.reply_text(message, parse_mode=parse_mode, reply_markup=reply_markup)

			async def context_send(message: str):
				return await context.bot.send_message(get_chat_id(update, context, query), message, parse_mode=parse_mode, reply_markup=reply_markup)

			async def fallback_send(message: str):
				return requests.get(
					url=f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
					params={
						"text": message,
						"chat_id": TELEGRAM_CHANNEL_ID,
						"parse_mode": parse_mode,
						"reply_markup": reply_markup,
					}
				)

			if query and query.message:
				return query_send
			elif update and update.message:
				return update_send
			elif context and context.bot:
				return context_send

			return fallback_send

		reply_method = get_reply_method(update, context, query, parse_mode, reply_markup)

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

	async def get_balance(self, token_id: str):
		balances = await self.get_balances()
		balance = balances.get(token_id)

		return balance

	async def get_balances(self) -> Dict[str, Any]:
		balances = community_exchange.fetch_balance()

		non_zero_balances_keys = {key for key, value in balances.get("total", {}).items() if value > 0}
		non_zero_balances = {key: balances[key] for key in non_zero_balances_keys}

		sorted_balances = OrderedDict(sorted(
			non_zero_balances.items(),
			key=lambda x: (x[0].lower(), -x[1]['total'])
		))

		return sorted_balances

	async def get_open_orders(self, market_id: str):
		response = community_exchange.fetch_open_orders(market_id)

		output = [
			{
				"id": item.get("id"),
				"clientOrderId": item.get("clientOrderId"),
				"symbol": item.get("symbol"),
				"type": item.get("type"),
				"side": item.get("side"),
				"amount": item.get("amount"),
				"price": item.get("price"),
				"filled": item.get("filled"),
				"datetime": item.get("datetime"),
			} for item in response
		]

		return output

	async def market_buy_order(self, market_id: str, amount: float):
		response = community_exchange.create_order(market_id, "market", "buy", amount)

		output = {
			"id": response.get("id"),
			"clientOrderId": response.get("clientOrderId"),
			"symbol": response.get("symbol"),
			"type": response.get("type"),
			"side": response.get("side"),
			"amount": response.get("amount"),
			"status": response.get("status"),
			"datetime": response.get("datetime"),
		}

		return output

	async def market_sell_order(self, market_id: str, amount: float):
		response = community_exchange.create_order(market_id, "market", "sell", amount)

		output = {
			"id": response.get("id"),
			"clientOrderId": response.get("clientOrderId"),
			"symbol": response.get("symbol"),
			"type": response.get("type"),
			"side": response.get("side"),
			"amount": response.get("amount"),
			"status": response.get("status"),
			"datetime": response.get("datetime"),
		}

		return output

	async def limit_buy_order(self, market_id: str, amount: float, price: float):
		response = community_exchange.create_order(market_id, "limit", "buy", amount, price)

		output = {
			"id": response.get("id"),
			"clientOrderId": response.get("clientOrderId"),
			"symbol": response.get("symbol"),
			"type": response.get("type"),
			"side": response.get("side"),
			"amount": response.get("amount"),
			"price": response.get("price"),
			"filled": response.get("filled"),
			"status": response.get("status"),
			"datetime": response.get("datetime"),
		}

		return output

	async def limit_sell_order(self, market_id: str, amount: float, price: float):
		response = community_exchange.create_order(market_id, "limit", "sell", amount, price)

		output = {
			"id": response.get("id"),
			"clientOrderId": response.get("clientOrderId"),
			"symbol": response.get("symbol"),
			"type": response.get("type"),
			"side": response.get("side"),
			"amount": response.get("amount"),
			"price": response.get("price"),
			"filled": response.get("filled"),
			"status": response.get("status"),
			"datetime": response.get("datetime"),
		}

		return output

	async def place_order(self, market: str, order_type: OrderType, order_side: OrderSide, amount: float, price: float = None, stop_loss_price: float = None):
		response = community_exchange.create_order(market, order_type, order_side, amount, price)

		output = {
			"id": response.get("id"),
			"clientOrderId": response.get("clientOrderId"),
			"symbol": response.get("symbol"),
			"type": response.get("type"),
			"side": response.get("side"),
			"amount": response.get("amount"),
			"price": response.get("price"),
			"filled": response.get("filled"),
			"status": response.get("status"),
			"datetime": response.get("datetime"),
		}

		return output

	def __getattr__(self, method_name):
		attribute = getattr(community_exchange, method_name, None)

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
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.CANCEL_ORDER):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.CREATE_ORDER):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.DESCRIBE):
			output = response
			output['apiKey'] = "****"
			output['secret'] = "****"

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.DEPOSIT):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_BALANCE):
			output = response

			if output.get("info"):
				del output["info"]

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_CLOSED_ORDERS):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_CURRENCIES):
			output = {
				key: {
					"id": value.get("id"),
					"numericId": value.get("numericId"),
					"code": value.get("code"),
					"precision": value.get("precision"),
					"type": value.get("type"),
					"name": value.get("name"),
					"active": value.get("active"),
				} for key, value in response.items()
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_MARKETS):
			output = [
				{
					"symbol": item.get("symbol"),
					"base": item.get("base"),
					"quote": item.get("quote"),
				} for item in response
			]

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_MY_TRADES):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_OHLCV):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_OPEN_ORDERS):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_ORDER):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_ORDER_BOOK):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_ORDERS):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_ORDERS_ALL_MARKETS):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_STATUS):
			output = {
				"status": response.get("status"),
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_TICKER):
			output = {
				"symbol": response.get("symbol"),
				"datetime": response.get("datetime"),
				"last": response.get("last"),
				"open": response.get("open"),
				"high": response.get("high"),
				"low": response.get("low"),
				"close": response.get("close"),
				"bid": response.get("bid"),
				"ask": response.get("ask"),
				"change": response.get("change"),
				"percentage": response.get("percentage"),
				"average": response.get("average"),
				"baseVolume": response.get("baseVolume"),
				"quoteVolume": response.get("quoteVolume")
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_TICKERS):
			output = {
				key: {
					"symbol": value.get("symbol"),
					"datetime": value.get("datetime"),
					"last": value.get("last"),
					"open": value.get("open"),
					"high": value.get("high"),
					"low": value.get("low"),
					"close": value.get("close"),
					"bid": value.get("bid"),
					"ask": value.get("ask"),
					"change": value.get("change"),
					"percentage": value.get("percentage"),
					"average": value.get("average"),
					"baseVolume": value.get("baseVolume"),
					"quoteVolume": value.get("quoteVolume")
				} for key, value in response.items()
			}

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_TRADES):
			output = response

			return output
		elif MagicMethod.is_equivalent(method, MagicMethod.FETCH_TRADING_FEE):
			output = response

			if output.get("info"):
				del output["info"]

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


def initialize():
	Telegram.instance().initialize()


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
