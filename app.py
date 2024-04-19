from collections import OrderedDict

import ccxt
# import ccxt.async_support as ccxt
import jsonpickle
import logging
import os
import textwrap
import traceback
import asyncio
from ccxt.base.types import OrderType, OrderSide
from dotmap import DotMap
from functools import wraps
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, filters, MessageHandler
from typing import Any, Dict

from integration_tests import IntegrationTests

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

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

exchange_class = getattr(ccxt, EXCHANGE_NAME)
exchange = exchange_class({
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
			print(exception)

			raise

	return wrapper


def async_handle_exceptions(method):
	@wraps(method)
	async def wrapper(*args, **kwargs):
		try:
			return await method(*args, **kwargs)
		except Exception as exception:
			print(f"O erro é {exception}")

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
class Telegram:

	def __init__(self):
		self.model = Model()

	# noinspection PyMethodMayBeStatic
	def is_admin(self, username):
		return username in TELEGRAM_ADMIN_USERNAMES

	async def validate_request(self, update: Update, _context: ContextTypes.DEFAULT_TYPE):
		try:
			if not self.is_admin(update.message.from_user.username):
				await update.message.reply_text(UNAUTHORIZED_USER_MESSAGE)

				return False

			return True
		except Exception as exception:
			return True

	# noinspection PyMethodMayBeStatic
	async def send_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message: Any, _query: CallbackQuery = None):
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

	async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		query = update.callback_query
		await query.answer()
		data = query.data

		if data == 'balance':
			context.user_data['balance'] = ""
			await context.bot.send_message(
				chat_id=query.message.chat_id,
				text="Enter the token id. Ex: BTC"
			)
			context.user_data['balance_step'] = 'ask_token_id'
		elif data == 'balances':
			await self.get_balances(update, context, query)
		elif data == 'open_orders':
			context.user_data['open_orders'] = ""
			await context.bot.send_message(
				chat_id=query.message.chat_id,
				text="Enter the market id. Ex: BTCUSDT"
			)
			context.user_data['open_orders_step'] = 'ask_market_id'
		elif data == 'place_order':
			context.user_data['place_order'] = {}
			await context.bot.send_message(
				chat_id=query.message.chat_id,
				text="Enter the order type. Ex: market; limit"
			)
			context.user_data['place_order_step'] = 'ask_order_type'
		else:
			message = "Unknown command."

			await self.send_message(update, context, message, query)

			return

	async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		user_data = context.user_data
		text = update.message.text

		if 'balance_step' in user_data:
			if user_data['balance_step'] == 'ask_token_id':
				user_data['balance'] = text.upper()
				await self.get_balance(update, context)
				user_data.clear()
		if 'open_orders_step' in user_data:
			if user_data['open_orders_step'] == 'ask_market_id':
				user_data['open_orders'] = text.upper().replace("/", "")
				await self.get_open_orders(update, context)
				user_data.clear()
		if 'place_order_step' in user_data:
			if user_data['place_order_step'] == 'ask_order_type':
				if text.lower() in ['limit', 'market']:
					user_data['place_order']['type'] = text.lower()
					user_data['place_order_step'] = 'ask_order_side'
					await update.message.reply_text("Enter the order side. Ex.: buy; sell")
				else:
					await update.message.reply_text("Please enter a valid order type ('market' or 'limit').")
			elif user_data['place_order_step'] == 'ask_order_side':
				if text.lower() in ['buy', 'sell']:
					user_data['place_order']['side'] = text.lower()
					user_data['place_order_step'] = 'ask_market_id'
					await update.message.reply_text("Enter the market symbol/ID. Ex.: BTCUSDT")
				else:
					await update.message.reply_text("Please enter the order side ('buy' or 'sell').")
			elif user_data['place_order_step'] == 'ask_market_id':
				user_data['place_order']['market_id'] = text.upper().replace("/", "")
				user_data['place_order_step'] = 'ask_amount'
				await update.message.reply_text("Enter the amount. Ex.: 123.4567")
			elif user_data['place_order_step'] == 'ask_amount':
				try:
					user_data['place_order']['amount'] = float(text)
					if user_data['place_order']['type'] == 'limit':
						user_data['place_order_step'] = 'ask_price'
						await update.message.reply_text("Enter the price. Ex.: 123.4567")
					else:
						user_data['place_order_step'] = 'confirm'
						formatted = self.beautify(user_data["place_order"])
						await update.message.reply_text(f"Review your order and type 'confirm' to place it or 'cancel' to abort.\n\n{formatted}")
				except Exception as e:
					await update.message.reply_text("Please enter a valid amount. Ex.: 123.4567")
					raise e
			elif user_data['place_order_step'] == 'ask_price':
				try:
					user_data['place_order']['price'] = float(text)
					user_data['place_order_step'] = 'confirm'
					formatted = self.beautify(user_data["place_order"])
					await update.message.reply_text(f"Review your order and type 'confirm' to place it or 'cancel' to abort.\n\n{formatted}")
				except Exception as e:
					await update.message.reply_text("Please enter a valid price. Ex.: 123.4567")
					raise e
			elif user_data['place_order_step'] == 'confirm':
				try:
					if text.lower() == 'confirm':
						await self.place_order(update, context, user_data['place_order'])
						user_data.clear()
					elif text.lower() == 'cancel':
						user_data.clear()
						await update.message.reply_text("Order canceled.")
					else:
						await update.message.reply_text("Please type 'confirm' to place the order or 'cancel' to abort.")
				except Exception as e:
					await update.message.reply_text(f"{e}")
					raise e
		else:
			# Handle other text messages that are not part of the order process
			await update.message.reply_text("Please use /start for the menu.")

	async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return

		command_buttons = [
			[InlineKeyboardButton("Get a Token Balance", callback_data="balance")],
			[InlineKeyboardButton("Get All Balances", callback_data="balances")],
			[InlineKeyboardButton("Getl All Open Orders from a Market", callback_data="open_orders")],
			# [InlineKeyboardButton("Place a Market Buy Order", callback_data="market_buy_order")],
			# [InlineKeyboardButton("Place a Market Sell Order", callback_data="market_sell_order")],
			# [InlineKeyboardButton("Place a Limit Buy Order", callback_data="limit_buy_order")],
			# [InlineKeyboardButton("Place a Limit Sell Order", callback_data="limit_sell_order")],
			[InlineKeyboardButton("Place a Custom Order", callback_data="place_order")],
		]
		reply_markup = InlineKeyboardMarkup(command_buttons)

		await update.message.reply_text(
			textwrap.dedent(
				f"""
					*🤖 Welcome to {str(EXCHANGE_NAME).upper()} Trading Bot! 📈*
					
										*Available commands:*
					
					*/help*
					
					*/balances*
					
					*/balance* `<marketId>`
					
					*/openOrders* `<tokenId>`
					
					*/marketBuyOrder* `<marketId> <amount> <price>`
					
					*/marketSellOrder* `<marketId> <amount> <price>`
					
					*/limitBuyOrder* `<marketId> <amount> <price>`
					
					*/limitSellOrder* `<marketId> <amount> <price>`
					
					*/placeOrder* `<limit/market> <buy/sell> <marketId> <amount> <price>`
					
					
								*Type /help to get more information.
								Feel free to explore and trade safely!* 🚀
				"""
			),
			parse_mode="Markdown",
			reply_markup=reply_markup
		)

	async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return
		await update.message.reply_text(
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
						*- /marketBuyOrder* `<marketId> <amount> <price>`
						Place a market sell order:
						*- /marketSellOrder* `<marketId> <amount> <price>`
						Place a limit buy order:
						*- /limitBuyOrder* `<marketId> <amount> <price>`
						Place a limit sell order:
						*- /limitSellOrder* `<marketId> <amount> <price>`
						Place a custom order:
						*- /placeOrder* `<limit/market> <buy/sell> <marketId> <amount> <price>`
					
					*🔧 Advanced Commands:*
						With this special command you can theoretically try any available CCXT command. Some examples are:
						
							*/fetchTicker* `BTCUSDT`
							*/fetchTicker* `symbol=BTCUSDT`
						
						Magic Trick:
						*- /anyCCXTMethod* `<arg1Value> <arg2Name>=<arg2Value>`
							(Where <anyCCXTMethod> Theoretically can be any CCXT command)
							
					
					*Feel free to explore and trade safely!* 🚀
				"""
			),
			parse_mode="Markdown",
		)

	async def magic_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return

		text = update.message.text
		command, *args = text.lstrip('/').split(maxsplit=1)
		args = args[0] if args else ""

		positional_args = []
		named_args = {}

		tokens = args.split()
		for token in tokens:
			if '=' in token:
				key, value = token.split('=', 1)
				named_args[key] = value
			else:
				positional_args.append(token)

		message = await getattr(self.model, command)(*positional_args, **named_args)
		message = self.beautify(message)

		await self.send_message(update, context, message)

	async def get_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None):
		if not await self.validate_request(update, context):
			return

		try:
			token_id = context.args[0] if context.args else context.user_data['balance']
			message = await self.model.get_balance(token_id)
			message = self.beautify(message)

			await self.send_message(update, context, message, query)
		except Exception as e:
			await update.message.reply_text("Usage: /balance <marketId>")
			raise e

	async def get_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None):
		if not await self.validate_request(update, context):
			return

		message = await self.model.get_balances()
		message = self.beautify(message)

		await self.send_message(update, context, message, query)

	async def get_open_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return
		try:
			market_id = context.args[0] if context.args else context.user_data['open_orders']
			message = await self.model.get_open_orders(market_id)
			if not len(message):
				message = "No orders"
			else:
				message = self.beautify(message)

			await self.send_message(update, context, message)
		except Exception as e:
			await update.message.reply_text("Usage: /openOrders <marketId>")
			raise e

	async def market_buy_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return

		try:
			market_id, amount = context.args[0], float(context.args[1])
			message = await self.model.market_buy_order(market_id, amount)
			message = self.beautify(message)
			message = f"Market Buy Order placed:\n{message}"

			await self.send_message(update, context, message)
		except Exception as e:
			await update.message.reply_text("Usage: /marketBuyOrder <marketId> <amount> <price>")
			raise e

	async def market_sell_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount = context.args[0], float(context.args[1])
			message = await self.model.market_sell_order(market_id, amount)
			message = self.beautify(message)
			message = f"Market Sell Order placed:\n{message}"

			await self.send_message(update, context, message)
		except Exception as e:
			await update.message.reply_text("Usage: /marketSellOrder <marketId> <amount> <price>")
			raise e

	async def limit_buy_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount, price = context.args[0], float(context.args[1]), float(context.args[2])
			message = await self.model.limit_buy_order(market_id, amount, price)
			message = self.beautify(message)
			message = f"Limit Buy Order placed:\n{message}"

			await self.send_message(update, context, message)
		except Exception as e:
			await update.message.reply_text("Usage: /limitBuyOrder <marketId> <amount> <price>")
			raise e

	async def limit_sell_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount, price = context.args[0], float(context.args[1]), float(context.args[2])
			message = await self.model.limit_sell_order(market_id, amount, price)
			message = self.beautify(message)
			message = f"Limit Sell Order placed:\n{message}"

			await self.send_message(update, context, message)
		except Exception as e:
			await update.message.reply_text("Usage: /limitSellOrder <marketId> <amount> <price>")
			raise e

	async def place_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE, order: Dict[str, Any] = None):
		if not await self.validate_request(update, context):
			return

		order_type, order_side, market_id, amount, price = (None, None, None, None, None)

		if order:
			if len(order.values()) == 4:
				order_type, order_side, market_id, amount = order.values()
			elif len(order.values()) == 5:
				order_type, order_side, market_id, amount, price = order.values()
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
				await update.message.reply_text("""Invalid order type. Allowed values are: limit/market""")
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
		message = self.beautify(message)
		message = f"Order placed:\n\n{message}"

		await self.send_message(update, context, message)

	def beautify(self, target: Any, indent=0) -> str:
		if isinstance(target, dict):
			result = ""
			for key, value in target.items():
				result += '  ' * indent + str(key) + ':'
				if isinstance(value, (dict, list)):
					result += "\n" + self.beautify(value, indent + 1)
				else:
					result += ' ' + str(value) + "\n"
			return result
		elif isinstance(target, list):
			result = ""
			for index, item in enumerate(target):
				result += '  ' * indent + f"-"
				if isinstance(item, (dict, list)):
					result += "\n" + self.beautify(item, indent + 1)
				else:
					result += ' ' + str(item) + "\n"
			return result
		else:
			return '  ' * indent + str(target) + "\n"

	async def handle_exception(self, update: Update, context: ContextTypes.DEFAULT_TYPE, exception: Exception):
		formatted_exception = traceback.format_exception(exception)

		await update.message.reply_text(
			textwrap.dedent(
				f"""
					An exception occurred while executing this operation. Type /start to see the menu again.
					
					{formatted_exception}
				"""
			)
		)


# noinspection PyMethodMayBeStatic
@handle_exceptions
class Model:
	async def get_balance(self, token_id: str):
		balances = await self.get_balances()
		balance = balances.get('total', {}).get(token_id.upper(), 0)

		return {token_id.upper(): balance}

	async def get_balances(self):
		balances = exchange.fetch_balance()

		non_zero_balances = {k: v for k, v in balances.get('total', {}).items() if v > 0}

		sorted_balances = OrderedDict(sorted(non_zero_balances.items(), key=lambda x: x[1], reverse=True))

		return {'total': sorted_balances}

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
	model = Model()
	telegram = Telegram()
	tests = IntegrationTests()

	tests.community_exchange = exchange
	tests.run()

	# print(await model.get_balances())
	# print(await model.get_balance('BTC'))
	# print(await model.get_open_orders('BTCUSDT'))
	# print(await model.market_buy_order('BTCUSDT', 0.00009))
	# print(await model.market_sell_order('BTCUSDT', 0.00009))
	# print(await model.limit_buy_order('BTCUSDT', 0.001, 20000))
	# print(await model.limit_sell_order('BTCUSDT', 0.00009, 99999))
	# print(await model.place_order('BTCUSDT', 'market', 'buy', 0.0001))
	# print(await model.place_order('BTCUSDT', 'limit', 'sell', 0.00009, 99999))

	# print(await model.fetch_markets())
	# print(await model.fetch_balance())
	# print(await model.fetch_ticker('BTCUSDT'))

	# await telegram.place_order(None, None, {
	# 	"type": "market",
	# 	"side": "buy",
	# 	"market_id": "BTCUSDT",
	# 	"amount": 0.00009
	# })

	# await telegram.place_order(None, None, {
	# 	"type": "limit",
	# 	"side": "sell",
	# 	"market_id": "BTCUSDT",
	# 	"amount": 0.00009,
	# 	"price": 99999
	# })


def main():
	telegram = Telegram()

	application = Application.builder().token(TELEGRAM_TOKEN).build()

	application.add_handler(CommandHandler("start", telegram.start))
	application.add_handler(CommandHandler("help", telegram.help))
	application.add_handler(CommandHandler("balance", telegram.get_balance))
	application.add_handler(CommandHandler("balances", telegram.get_balances))
	application.add_handler(CommandHandler("openOrders", telegram.get_open_orders))
	application.add_handler(CommandHandler("marketBuyOrder", telegram.market_buy_order))
	application.add_handler(CommandHandler("marketSellOrder", telegram.market_sell_order))
	application.add_handler(CommandHandler("limitBuyOrder", telegram.limit_buy_order))
	application.add_handler(CommandHandler("limitSellOrder", telegram.limit_sell_order))
	application.add_handler(CommandHandler("placeOrder", telegram.place_order))

	application.add_handler(CallbackQueryHandler(telegram.button_handler))

	application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram.handle_text_message))
	application.add_handler(MessageHandler(filters.COMMAND, telegram.magic_command))

	application.run_polling()


if __name__ == "__main__":
	import asyncio
	asyncio.get_event_loop().run_until_complete(test())

	main()
