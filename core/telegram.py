import os

import json
import requests
import textwrap
from singleton.singleton import ThreadSafeSingleton
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, filters, MessageHandler
from typing import Any
from typing import List

# noinspection PyUnresolvedReferences
import ccxt as sync_ccxt
# noinspection PyUnresolvedReferences
import ccxt.async_support as async_ccxt

from core.constants import constants
from core.decorators import handle_exceptions
from core.model import Model
from core.properties import properties
from core.types import MagicMethod
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, BotCommand, WebAppInfo, \
	KeyboardButton, ReplyKeyboardMarkup

ccxt = sync_ccxt

TELEGRAM_TOKEN: bool = os.getenv("TELEGRAM_TOKEN", properties.get_or_default("telegram.token", None))
TELEGRAM_LISTEN_COMMANDS: bool = os.getenv("TELEGRAM_LISTEN_COMMANDS", properties.get_or_default("telegram.listen_commands", "true")).lower() in ["true", "1"]
EXCHANGE_WEB_APP_URL = os.getenv("EXCHANGE_WEB_APP_URL", properties.get_or_default("exchange.web_app.url", "https://cube.exchange/"))


@handle_exceptions
@ThreadSafeSingleton
class Telegram(object):

	def __init__(self):
		self.model = Model.instance()

	# noinspection PyMethodMayBeStatic
	async def initialize(self):
		self.application = Application.builder().token(TELEGRAM_TOKEN).build()

		commands = [
			BotCommand("start", "| Starts the bot"),
			BotCommand("help", "| Provides help information"),
			BotCommand("balance", "<tokenId> | Get your balance"),
			BotCommand("balances", "| Get all balances"),
			BotCommand("cancel_all_orders", "<marketId> | Cancel all open orders from a market"),
			BotCommand("cancel_order", "<orderId or clientOrderId> | Cancel a specific order from a market"),
			BotCommand("create_order", "<marketId> <limit/market> <buy/sell> <amount> <price> | Place an order"),
			BotCommand("describe", "| Bring all information about the exchange"),
			BotCommand("fetch_balance", "| Fetch all balances from the user"),
			BotCommand("fetch_closed_orders", "<marketId> | Fetch all closed orders from a market"),
			BotCommand("fetch_currencies", "| Fetch all currencies"),
			BotCommand("fetch_deposit_addresses", "<codes> | Fetch the deposit addresses"),
			BotCommand("fetch_deposit", "<depositId> | Fetch a specific deposit from the user"),
			BotCommand("fetch_deposits", "<currencyId> | Fetch all deposits from the user for a specific currency"),
			BotCommand("fetch_markets", "| Fetch all markets"),
			BotCommand("fetch_my_trades", "<marketId> | Fetch all user trades from a market"),
			BotCommand("fetch_ohlcv", "<marketId> | Fetch the OHLCV (open, high, low, close, volume) from a market"),
			BotCommand("fetch_open_orders", "<marketId> | Fetch all open orders from a market"),
			BotCommand("fetch_order", "<orderId or clientOrderId> | Fetch a specific order from a market"),
			BotCommand("fetch_order_book", "<marketId> | Fetch the order book from a market"),
			BotCommand("fetch_orders", "<marketId> | Fetch all orders from a market"),
			BotCommand("fetch_orders_all_markets", "| Fetch all orders from all markets"),
			BotCommand("fetch_status", "| Bring the status of the exchange"),
			BotCommand("fetch_ticker", "<marketId> | Fetch the ticker from a market"),
			BotCommand("fetch_tickers", "| Fetch the tickers from all markets"),
			BotCommand("fetch_trades", "<marketId> | Fetch all trades from a market"),
			BotCommand("fetch_trading_fee", "<marketId> | Fetch the trading fee from a market"),
			BotCommand("fetch_withdrawal", "<withdrawId> | Fetch a specific withdraw from the user"),
			BotCommand("fetch_withdrawals", "<currencyId> | Fetch all withdraws from the user for a specific currency"),
			BotCommand("open_orders", "<marketId> | Get open orders"),
			BotCommand("place_market_buy_order", "<marketId> <amount> | Place a market buy order"),
			BotCommand("place_market_sell_order", "<marketId> <amount> | Place a market sell order"),
			BotCommand("place_limit_buy_order", "<marketId> <amount> <price> | Place a limit buy order"),
			BotCommand("place_limit_sell_order", "<marketId> <amount> <price> | Place a limit sell order"),
			BotCommand("place_order", "<limit/market> <buy/sell> <marketId> <amount> <price> | Place a custom order"),
			BotCommand("set_sandbox_mode", "<true/false> | Enable or disable the sandbox mode"),
			BotCommand("withdraw", "<currencyId> <amount> <destinationAddress> <tag>| Withdraw funds from a currency to an address"),
		]
		await self.application.bot.set_my_commands(commands)

		self.application.add_handler(CommandHandler("start", self.start))
		self.application.add_handler(CommandHandler("help", self.help))
		self.application.add_handler(CommandHandler("balance", self.get_balance))
		self.application.add_handler(CommandHandler("balances", self.get_balances))
		self.application.add_handler(CommandHandler("openOrders", self.get_open_orders))
		self.application.add_handler(CommandHandler("open_orders", self.get_open_orders))
		self.application.add_handler(CommandHandler("placeMarketBuyOrder", self.market_buy_order))
		self.application.add_handler(CommandHandler("place_market_buy_order", self.market_buy_order))
		self.application.add_handler(CommandHandler("placeMarketSellOrder", self.market_sell_order))
		self.application.add_handler(CommandHandler("place_market_sell_order", self.market_sell_order))
		self.application.add_handler(CommandHandler("placeLimitBuyOrder", self.limit_buy_order))
		self.application.add_handler(CommandHandler("place_limit_buy_order", self.limit_buy_order))
		self.application.add_handler(CommandHandler("placeLimitSellOrder", self.limit_sell_order))
		self.application.add_handler(CommandHandler("place_limit_sell_order", self.limit_sell_order))
		self.application.add_handler(CommandHandler("placeOrder", self.place_order))
		self.application.add_handler(CommandHandler("place_order", self.place_order))

		self.application.add_handler(CallbackQueryHandler(self.button_handler))
		self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_handler))
		self.application.add_handler(MessageHandler(filters.COMMAND, self.handle_magic_command_input))

	def run(self):
		if TELEGRAM_LISTEN_COMMANDS:
			self.application.run_polling()

	# noinspection PyMethodMayBeStatic
	def is_admin(self, username) -> bool:
		if TELEGRAM_ADMIN_USERNAMES is None or TELEGRAM_ADMIN_USERNAMES == "" or len(TELEGRAM_ADMIN_USERNAMES) == 0:
			return True
		elif TELEGRAM_ADMIN_USERNAMES and isinstance(TELEGRAM_ADMIN_USERNAMES, List):
			return username in TELEGRAM_ADMIN_USERNAMES

		return False

	async def validate_request(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> bool:
		# noinspection PyBroadException
		try:
			if not self.is_admin(update.message.from_user.username):
				await self.send_message(constants.errors.unauthorized_user)

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

		command = MagicMethod.find(command).value
		command = self.camel_to_snake(command)

		method = getattr(self.model, command, None)

		if not method:
			await self.send_message(f"""Unrecognized command "{command}" for exchange {EXCHANGE_ID}.""", update, context, query)
			return

		message = await method(*positional_args, **named_args)

		message = self.model.beautify(message)

		await self.send_message(message, update, context, query)

	# noinspection PyMethodMayBeStatic
	def camel_to_snake(self, target: str):
		result = [target[0].lower()]
		i = 1
		while i < len(target):
			if target[i].isupper():
				if (i + 1 < len(target) and target[i + 1].isupper()) or (i + 1 == len(target)):
					start = i
					while i + 1 < len(target) and target[i + 1].isupper():
						i += 1
					result.append('_' + target[start:i+1].lower())
				else:
					result.append('_' + target[i].lower())
			else:
				result.append(target[i])
			i += 1

		return ''.join(result)

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
			[KeyboardButton(text=f"{str(EXCHANGE_ID).capitalize()} App", web_app=WebAppInfo(url=EXCHANGE_WEB_APP_URL))],
			[InlineKeyboardButton("Get a Token Balance", callback_data="balance")],
			[InlineKeyboardButton("Get All Balances", callback_data="balances")],
			[InlineKeyboardButton("Get All Open Orders from a Market", callback_data="open_orders")],
			[InlineKeyboardButton("Place a Market Buy Order", callback_data="place_market_buy_order")],
			[InlineKeyboardButton("Place a Market Sell Order", callback_data="place_market_sell_order")],
			[InlineKeyboardButton("Place a Limit Buy Order", callback_data="place_limit_buy_order")],
			[InlineKeyboardButton("Place a Limit Sell Order", callback_data="place_limit_sell_order")],
			[InlineKeyboardButton("Place a Custom Order", callback_data="place_order")],
		]
		inline_keyboard_markup = InlineKeyboardMarkup(command_buttons)

		web_app_keyboard = [
			[KeyboardButton(text=f"{str(EXCHANGE_ID).capitalize()} App", web_app=WebAppInfo(url=EXCHANGE_WEB_APP_URL))]
		]
		reply_keyboard_markup = ReplyKeyboardMarkup(web_app_keyboard, resize_keyboard=True)

		await self.send_message(
			textwrap.dedent(
				f"""
					*🤖 Welcome to {str(EXCHANGE_ID).upper()} Trading Bot! 📈*
					
					*Available commands:*
					
					*/help*
					
					*/balances*
					
					*/openOrders* `<marketId>`
					
					*/placeOrder* `<limit/market> <buy/sell> <marketId> <amount> <price>`
				"""
			),
			update,
			context,
			query,
			parse_mode="Markdown",
			reply_markup=inline_keyboard_markup
		)

		await self.send_message(
			textwrap.dedent(
				"""
					*Click on the button to open the Web App.*
					
					*Type /help to get more information and more advanced commands. Feel free to explore and trade safely!* 🚀
				"""
			),
			update,
			context,
			query,
			parse_mode="Markdown",
			reply_markup=reply_keyboard_markup
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
						*/fetchDepositAddresses*
						*/fetchMarkets*
						*/fetchOHLCV* `<marketId>`
						*/fetchOpenOrders* `<marketId>`
						*/fetchOrder* `<orderId> <marketId>`
						*/fetchOrderBook* `<marketId>`
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
						"chat_id": get_chat_id(update, context, query),
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


telegram = Telegram.instance()
