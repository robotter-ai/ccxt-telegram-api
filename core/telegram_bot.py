import json
import os
import requests
import textwrap
from dotmap import DotMap
from singleton.singleton import ThreadSafeSingleton
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, BotCommand, WebAppInfo, \
	KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, filters, MessageHandler
from typing import Any
from typing import List

# noinspection PyUnresolvedReferences
import ccxt as sync_ccxt
# noinspection PyUnresolvedReferences
import ccxt.async_support as async_ccxt
from core.constants import constants
from core.decorators import handle_exceptions
from core.model import model
from core.properties import properties
from core.types import MagicMethod, Credentials, Protocol, Environment

ccxt = sync_ccxt


EXCHANGE_ID: bool = os.getenv("EXCHANGE_ID", properties.get_or_default("exchange.id", None))
TELEGRAM_TOKEN: bool = os.getenv("TELEGRAM_TOKEN", properties.get_or_default("telegram.token", None))
TELEGRAM_CHAT_ID: bool = os.getenv("TELEGRAM_CHANNEL_ID", properties.get_or_default("telegram.chat_id", None))
TELEGRAM_LISTEN_COMMANDS: bool = os.getenv("TELEGRAM_LISTEN_COMMANDS", properties.get_or_default("telegram.listen_commands", "true")).lower() in ["true", "1"]
EXCHANGE_WEB_APP_URL = os.getenv("EXCHANGE_WEB_APP_URL", properties.get_or_default("exchange.web_app.url", "https://cube.exchange/"))

TELEGRAM_ADMIN_USERNAMES = []
administrator = os.getenv("TELEGRAM_ADMIN_USERNAME", "").strip().replace("@", "")
if administrator:
	TELEGRAM_ADMIN_USERNAMES.append(administrator)
administrators = os.getenv("TELEGRAM_ADMIN_USERNAMES", "").split(",")
administrators = [username.strip().replace("@", "") for username in administrators if username.strip()]
TELEGRAM_ADMIN_USERNAMES = TELEGRAM_ADMIN_USERNAMES + administrators
administrators = properties.get_or_default("telegram.admin.users", [])
administrators = [username.strip().replace("@", "") for username in administrators if username.strip()]
TELEGRAM_ADMIN_USERNAMES = TELEGRAM_ADMIN_USERNAMES + administrators


@handle_exceptions
@ThreadSafeSingleton
class Telegram(object):

	def __init__(self):
		self.model = model

	# noinspection PyMethodMayBeStatic
	async def initialize(self):
		self.application = Application.builder().token(TELEGRAM_TOKEN).build()

		commands = [
			BotCommand("start", "| Starts the bot"),
			BotCommand("help", "| Provides help information"),
			BotCommand("sign_in", "| Sign in the user to enable private operations"),
			BotCommand("sign_out", "| Sign out the user"),
			BotCommand("balance", "<tokenId> | Get your balance"),
			BotCommand("balances", "| Get all balances"),
			BotCommand("cancel_all_orders", "<marketId> | Cancel all open orders from a market"),
			BotCommand("cancel_order", "<orderId or clientOrderId> | Cancel a specific order from a market"),
			BotCommand("create_order", "<marketId> <limit/market> <buy/sell> <amount> <price> | Place an order"),
			BotCommand("describe", "| Bring all information about the exchange"),
			# BotCommand("exchanges", "| List all available exchanges"),
			BotCommand("fetch_balance", "| Fetch all balances from the user"),
			BotCommand("fetch_closed_orders", "<marketId> | Fetch all closed orders from a market"),
			BotCommand("fetch_currencies", "| Fetch all currencies"),
			BotCommand("fetch_deposit_addresses", "<codes> | Fetch the deposit addresses"),
			BotCommand("fetch_deposit", "<depositId> | Fetch a specific deposit from the user"),
			BotCommand("fetch_deposits", "<currencyId> | Fetch all deposits from the user for a specific currency"),
			BotCommand("fetch_markets", "| Fetch all markets"),
			BotCommand("fetch_my_trades", "<marketId> | Fetch all user trades from a market"),
			BotCommand("fetch_ohlcv", "<marketId> | Fetch the OHLCV (open, high, low, close, volume) from a market"),
			BotCommand("fetch_open_order", "<orderId or clientOrderId> <marketId> | Fetch a specific open order from a market"),
			BotCommand("fetch_open_orders", "<marketId> | Fetch all open orders from a market"),
			BotCommand("fetch_order", "<orderId or clientOrderId> <marketId> | Fetch a specific order from a market"),
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
			# BotCommand("strategy", "<start|stop|status> | Start, stop or retrieve the status from the strategy."),
			# BotCommand("switch_exchange", "<exchangeId> | Switch to another exchange"),
			BotCommand("withdraw", "<currencyId> <amount> <destinationAddress> <tag>| Withdraw funds from a currency to an address"),
		]
		await self.application.bot.set_my_commands(commands)

		self.application.add_handler(CommandHandler("start", self.start))
		self.application.add_handler(CommandHandler("help", self.help))
		self.application.add_handler(CommandHandler("signIn", self.sign_in))
		self.application.add_handler(CommandHandler("sign_in", self.sign_in))
		self.application.add_handler(CommandHandler("signOut", self.sign_out))
		self.application.add_handler(CommandHandler("sign_out", self.sign_out))
		self.application.add_handler(CommandHandler("balance", self.get_balance))
		self.application.add_handler(CommandHandler("balances", self.get_balances))
		# self.application.add_handler(CommandHandler("exchanges", self.get_exchanges))
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
		# self.application.add_handler(CommandHandler("strategy", self.strategy))
		# self.application.add_handler(CommandHandler("switchExchange", self.switch_exchange))
		# self.application.add_handler(CommandHandler("switch_exchange", self.switch_exchange))

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

		if data == "sign_in":
			# context.user_data["sign_in"] = {}
			context.user_data["sign_in"] = {
				"exchange_id": properties.get_or_default("exchange.id", "cube"),
				"exchange_environment": properties.get_or_default("exchange.environment", "production"),
			}
			await self.send_message("Signing In", update, context, query)
			await self.send_message("Enter your exchange API key. Ex.: a1aa22be-0aa0-b54a-80c1-fa9e111112c2", update, context, query)
			context.user_data["sign_in_step"] = "ask_exchange_api_key"
		elif data == "sign_out":
			context.user_data["sign_out"] = {}
			await self.send_message("""Are you sure that you want to sign out? Type "confirm" to sign out or "cancel" to abort.""", update, context, query)
			context.user_data["sign_out_step"] = "confirm"
		elif data == "balance":
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

		if "sign_in_step" in data:
			if data["sign_in_step"] == "ask_exchange_id":
				await update.message.delete()
				if self.model.validate_exchange_id(text):
					data["sign_in"]["exchange_id"] = self.model.sanitize_exchange_id(text)
					data["sign_in_step"] = "ask_exchange_environment"
					await self.send_message("""Enter the exchange environment ("production", "staging", "development")""", update, context, query)
				else:
					await self.send_message(f"""Please enter a valid exchange id. Ex.: {properties.get_or_default("exchange.id")}""", update, context, query)
			elif data["sign_in_step"] == "ask_exchange_environment":
				await update.message.delete()
				if self.model.validate_exchange_environment(text):
					data["sign_in"]["exchange_environment"] = self.model.sanitize_exchange_environment(text)
					data["sign_in_step"] = "ask_exchange_api_key"
					await self.send_message("""Enter the exchange API key. Ex.: a1aa22be-0aa0-b54a-80c1-fa9e111112c2""", update, context, query)
				else:
					await self.send_message("""Please enter a valid exchange environment("production", "staging", "development").""", update, context, query)
			elif data["sign_in_step"] == "ask_exchange_api_key":
				await update.message.delete()
				if self.model.validate_exchange_api_key(text):
					data["sign_in"]["exchange_api_key"] = self.model.sanitize_exchange_api_key(text)
					data["sign_in_step"] = "ask_exchange_api_secret"
					await self.send_message("""Enter the exchange API secret. Ex.: abcdef010f6e98a4124e0a08bbf869d3cf1c999999999731fc7de20a9ea001ba""", update, context, query)
				else:
					await self.send_message("""Please enter a valid exchange API key. Ex.: a1aa22be-0aa0-b54a-80c1-fa9e111112c2""", update, context, query)
			elif data["sign_in_step"] == "ask_exchange_api_secret":
				await update.message.delete()
				if self.model.validate_exchange_api_secret(text):
					data["sign_in"]["exchange_api_secret"] = self.model.sanitize_exchange_api_secret(text)
					data["sign_in_step"] = "ask_exchange_options_sub_account_id"
					await self.send_message("""Enter your sub account ID. Ex.: 123""", update, context, query)
				else:
					await self.send_message("""Please enter a valid exchange API secret. Ex.: abcdef010f6e98a4124e0a08bbf869d3cf1c999999999731fc7de20a9ea001ba""", update, context, query)
			elif data["sign_in_step"] == "ask_exchange_options_sub_account_id":
				await update.message.delete()
				if self.model.validate_exchange_options_sub_account_id(text):
					data["sign_in"]["exchange_options"] = {}
					data["sign_in"]["exchange_options"]["sub_account_id"] = self.model.sanitize_exchange_options_sub_account_id(text)
					data["sign_in_step"] = "confirm"
					formatted = self.model.beautify({
						"exchange": data["sign_in"]["exchange_id"],
						"environment": data["sign_in"]["exchange_environment"],
						"api_key": data["sign_in"]["exchange_api_key"],
						"api_secret": data["sign_in"]["exchange_api_secret"],
						"options": data["sign_in"]["exchange_options"],
					})
					# await self.send_message(f"""Review your credentials and type "confirm" to sign in or "cancel" to abort.\n\n{formatted}""", update, context, query)
					await self.send_message(f"""Type "confirm" to sign in or "cancel" to abort.""", update, context, query)
				else:
					await self.send_message("""Please enter a valid sub account id. Ex.: 123""", update, context, query)
			elif data["sign_in_step"] == "confirm":
				await update.message.delete()
				text = text.lower()
				if text == "confirm":
					try:
						await self.sign_in(update, context, query, data["sign_in"])
					finally:
						data.clear()
				elif text.lower() == "cancel":
					data.clear()
					await self.send_message("Sign in cancelled.", update, context, query)
				else:
					await self.send_message("""Please type "confirm" to sign in or "cancel" to abort.""", update, context, query)
		elif data["sign_out_step"] == "confirm":
			text = text.lower()
			if text == "confirm":
				try:
					await self.sign_out(update, context, query)
				finally:
					data.clear()
			elif text.lower() == "cancel":
				data.clear()
				await self.send_message("Sign out cancelled.", update, context, query)
			else:
				await self.send_message("""Please type "confirm" to sign out or "cancel" to abort.""", update, context, query)
		elif "balance_step" in data:
			if data["balance_step"] == "ask_token_id":
				if self.model.validate_token_id(text):
					data["balance"] = self.model.sanitize_token_id(text)
					try:
						await self.get_balance(update, context, query, data)
					finally:
						data.clear()
				else:
					await self.send_message("""Please enter a valid token id ("btc").""", update, context, query)
		elif "open_orders_step" in data:
			if data["open_orders_step"] == "ask_market_id":
				if self.model.validate_market_id(text):
					data["open_orders"] = self.model.sanitize_market_id(text)
					try:
						await self.get_open_orders(update, context, query, data)
					finally:
						data.clear()
				else:
					await self.send_message("""Please enter a valid market id ("btcusdc").""", update, context, query)
		elif "place_market_buy_order_step" in data:
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
		elif "place_market_sell_order_step" in data:
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
		elif "place_limit_buy_order_step" in data:
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
		elif "place_limit_sell_order_step" in data:
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
		elif "place_order_step" in data:
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

		exchange = self.get_user_exchange(update)

		method = getattr(self.model, command, None)

		if not method:
			await self.send_message(f"""Unrecognized command "{command}" for exchange {EXCHANGE_ID}.""", update, context, query)
			return

		message = await method(exchange)(*positional_args, **named_args)

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

	# noinspection PyMethodMayBeStatic
	def get_user_exchange(self, update: Update):
		user_telegram_id = update.message.from_user.id
		exchange_id = properties.get_or_default("exchange.id")
		exchange_environment = Environment.get_by_id(properties.get_or_default(f"exchanges.available.{exchange_id}.environment"))
		exchange_protocol = Protocol.REST

		from core.helpers import get_user_exchange
		exchange = get_user_exchange(user_telegram_id, exchange_id, exchange_environment, exchange_protocol)

		return exchange

	async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		command_buttons = [
			[KeyboardButton(text=f"{str(EXCHANGE_ID).capitalize()} App", web_app=WebAppInfo(url=EXCHANGE_WEB_APP_URL))],
			[InlineKeyboardButton("Sign In", callback_data="sign_in")],
			[InlineKeyboardButton("Sign Out", callback_data="sign_out")],
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
					
					*/signIn*
					*/signOut*
					
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
					
					*ℹ️ Authentication commands:*
						Show this information:
						*- /signIn*
						*- /signOut*
					
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

	async def sign_in(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if context.args:
			await update.message.delete()

			exchange_id = (context.args[0:1] or [None])[0]
			exchange_environment = (context.args[1:2] or [None])[0]
			exchange_api_key = (context.args[2:3] or [None])[0]
			exchange_api_secret = (context.args[3:4] or [None])[0]
			exchange_options_sub_account_id = (context.args[4:5] or [None])[0]
			exchange_options = DotMap({
				"sub_account_id": exchange_options_sub_account_id
			}, _dynamic=False)
		elif data:
			exchange_id = data.get("exchange_id", None)
			exchange_environment = data.get("exchange_environment", None)
			exchange_api_key = data.get("exchange_api_key", None)
			exchange_api_secret = data.get("exchange_api_secret", None)
			exchange_options = data.get("exchange_options", None)
		else:
			exchange_id = None
			exchange_environment = None
			exchange_api_key = None
			exchange_api_secret = None
			exchange_options = None

		if self.model.validate_exchange_id(exchange_id):
			exchange_id = self.model.sanitize_exchange_id(exchange_id)
		else:
			await self.send_message(f"""Please enter a valid exchange ID. Ex.: {properties.get_or_default("exchange.id", "cube")}""", update, context, query)
			return

		if self.model.validate_exchange_environment(exchange_environment):
			exchange_environment = self.model.sanitize_exchange_environment(exchange_environment)
		else:
			await self.send_message("""Please enter a valid exchange environment ("production", "staging", or "development").""", update, context, query)
			return

		if self.model.validate_exchange_api_key(exchange_api_key):
			exchange_api_key = self.model.sanitize_exchange_api_key(exchange_api_key)
		else:
			await self.send_message("""Please enter a valid exchange API key. Ex.: a1aa22be-0aa0-b54a-80c1-fa9e111112c2""", update, context, query)
			return

		if self.model.validate_exchange_api_secret(exchange_api_secret):
			exchange_api_secret = self.model.sanitize_exchange_api_secret(exchange_api_secret)
		else:
			await self.send_message("Please enter a valid exchange API secret. Ex.: abcdef010f6e98a4124e0a08bbf869d3cf1c999999999731fc7de20a9ea001ba", update, context, query)
			return

		if self.model.validate_exchange_options(exchange_options):
			exchange_options: DotMap = self.model.sanitize_exchange_options(exchange_options)
		else:
			await self.send_message("Please enter valid options for the exchange.", update, context, query)
			return

		parameters = {
			"userTelegramId": update.message.from_user.id,
			"jwtToken": None,
			"exchangeId": exchange_id,
			"exchangeEnvironment": exchange_environment,
			"exchangeProtocol": Protocol.REST.value,
			"exchangeApiKey": exchange_api_key,
			"exchangeApiSecret": exchange_api_secret,
			"exchangeOptions": exchange_options.toDict()
		}
		credentials = Credentials(**parameters)

		# message = await self.model.sign_in(credentials)
		# message = self.model.beautify(message)
		# message = f"Successfully signed in:\n\n{message}"

		await self.model.sign_in(credentials)
		message = f"Successfully signed in."

		await self.send_message(message, update, context, query)

	async def sign_out(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		if not await self.validate_request(update, context):
			return

		user_telegram_id = update.message.from_user.id

		# message = await self.model.sign_out(user_telegram_id)
		# message = self.model.beautify(message)
		# message = f"Successfully signed out:\n\n{message}"

		message = f"Successfully signed out."
		await self.model.sign_out(user_telegram_id)

		await self.send_message(message, update, context, query)

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
			exchange = self.get_user_exchange(update)
			token_id = self.model.sanitize_token_id(token_id)
			message = await self.model.get_balance(exchange, token_id)

			message = self.model.beautify(message)
			await self.send_message(message, update, context, query)
		else:
			await self.send_message("""Please enter a valid token id ("btc").""", update, context, query)

	async def get_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None, data: Any = None):
		## Special case, this validation does not apply here because the action is called directly.
		# if not await self.validate_request(update, context):
		# 	return

		exchange = self.get_user_exchange(update)
		message = await self.model.get_balances(exchange)

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
			exchange = self.get_user_exchange(update)
			market_id = self.model.sanitize_market_id(market_id)
			message = await self.model.get_open_orders(exchange, market_id)

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

		exchange = self.get_user_exchange(update)
		message = await self.model.market_buy_order(exchange, market_id, amount)

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

		exchange = self.get_user_exchange(update)
		message = await self.model.market_sell_order(exchange, market_id, amount)

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

		exchange = self.get_user_exchange(update)
		message = await self.model.limit_buy_order(exchange, market_id, amount, price)

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

		exchange = self.get_user_exchange(update)
		message = await self.model.limit_sell_order(exchange, market_id, amount, price)

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

		exchange = self.get_user_exchange(update)
		message = await self.model.place_order(exchange, market_id, order_type, order_side, amount, price)

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
					# noinspection PyUnresolvedReferences
					return update.callback_query.message.chat_id

			return TELEGRAM_CHAT_ID

		def get_reply_method(update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery, parse_mode: str = None, reply_markup: Any = None):
			async def query_send(message: str):
				# noinspection PyUnresolvedReferences
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
