import textwrap
from collections import OrderedDict

import asyncio

import ccxt
import jsonpickle
import logging
import os
from ccxt.base.types import OrderType, OrderSide
from dotmap import DotMap
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, filters, MessageHandler
from telegram.ext._utils.types import FilterDataDict
from typing import Any, Dict, Optional, Union

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHANNEL_ID = os.getenv("TELEGRAM_TELEGRAM_CHANNEL_ID")
TELEGRAM_ADMIN_USERNAMES = [os.getenv("TELEGRAM_ADMIN_USERNAME")]

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
		"subAccountId": EXCHANGE_SUB_ACCOUNT_ID,
	}
})

exchange.set_sandbox_mode(True)


class Telegram:

	def __init__(self):
		self.model = Model()

	# noinspection PyMethodMayBeStatic
	def is_admin(self, username):
		return username in TELEGRAM_ADMIN_USERNAMES

	async def validate_request(self, update: Update, _context: ContextTypes.DEFAULT_TYPE):
		if not self.is_admin(update.message.from_user.username):
			await update.message.reply_text(UNAUTHORIZED_USER_MESSAGE)

			return False

		return True

	# noinspection PyMethodMayBeStatic
	async def send_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE, message: Any, query: CallbackQuery = None):
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
			await self.get_balance(update, context, query)
		elif data == 'balances':
			await self.get_balances(update, context, query)
		elif data == 'place':
			context.user_data['place_order'] = {}
			await context.bot.send_message(
				chat_id=query.message.chat_id,
				text="Enter 'limit' or 'market' for the type of order:"
			)
			context.user_data['place_order_step'] = 'ask_order_type'
		else:
			message = "Unknown command."

			await self.send_message(update, context, message, query)

			return

	async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		user_data = context.user_data
		text = update.message.text

		if 'place_order_step' in user_data:
			if user_data['place_order_step'] == 'ask_order_type':
				if text.lower() in ['limit', 'market']:
					user_data['place_order']['type'] = text.lower()
					user_data['place_order_step'] = 'ask_buy_sell'
					await update.message.reply_text("Enter 'buy' or 'sell':")
				else:
					await update.message.reply_text("Please enter a valid type ('limit' or 'market').")

			elif user_data['place_order_step'] == 'ask_buy_sell':
				if text.lower() in ['buy', 'sell']:
					user_data['place_order']['side'] = text.lower()
					user_data['place_order_step'] = 'ask_market_id'
					await update.message.reply_text("Enter the market ID (e.g., BTC/USD):")
				else:
					await update.message.reply_text("Please enter 'buy' or 'sell'.")

			elif user_data['place_order_step'] == 'ask_market_id':
				user_data['place_order']['market_id'] = text.upper()
				user_data['place_order_step'] = 'ask_amount'
				await update.message.reply_text("Enter the amount:")

			elif user_data['place_order_step'] == 'ask_amount':
				try:
					user_data['place_order']['amount'] = float(text)
					if user_data['place_order']['type'] == 'limit':
						user_data['place_order_step'] = 'ask_price'
						await update.message.reply_text("Enter the price:")
					else:
						user_data['place_order_step'] = 'confirm'
						await update.message.reply_text("Review your order and type 'confirm' to place it or 'cancel' to abort.")
				except ValueError:
					await update.message.reply_text("Please enter a valid amount.")

			elif user_data['place_order_step'] == 'ask_price':
				try:
					user_data['place_order']['price'] = float(text)
					user_data['place_order_step'] = 'ask_stop_loss'
					await update.message.reply_text("Enter the stop loss price (optional, type 'skip' to omit):")
				except ValueError:
					await update.message.reply_text("Please enter a valid price.")

			elif user_data['place_order_step'] == 'ask_stop_loss':
				if text.lower() == 'skip':
					user_data['place_order_step'] = 'confirm'
					await update.message.reply_text("Review your order and type 'confirm' to place it or 'cancel' to abort.")
				else:
					try:
						user_data['place_order']['stop_loss_price'] = float(text)
						user_data['place_order_step'] = 'confirm'
						await update.message.reply_text("Review your order and type 'confirm' to place it or 'cancel' to abort.")
					except ValueError:
						await update.message.reply_text("Please enter a valid stop loss price or type 'skip'.")

			elif user_data['place_order_step'] == 'confirm':
				if text.lower() == 'confirm':
					await self.place_order(update, context, user_data['place_order'])
					user_data.clear()
				elif text.lower() == 'cancel':
					user_data.clear()
					await update.message.reply_text("Order canceled.")
				else:
					await update.message.reply_text("Please type 'confirm' to place the order or 'cancel' to abort.")

		else:
			# Handle other text messages that are not part of the order process
			await update.message.reply_text("Please use the menu to start an action.")

	async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return

		command_buttons = [
			[InlineKeyboardButton("Balances", callback_data="balances")],
			[InlineKeyboardButton("Balance", callback_data="balance")],
			[InlineKeyboardButton("OpenOrders", callback_data="openOrders")],
			[InlineKeyboardButton("MarketBuy", callback_data="marketBuy")],
			[InlineKeyboardButton("MarketSell", callback_data="marketSell")],
			[InlineKeyboardButton("LimitBuy", callback_data="limitBuy")],
			[InlineKeyboardButton("LimitSell", callback_data="limitSell")],
			[InlineKeyboardButton("Place", callback_data="place")],
		]
		reply_markup = InlineKeyboardMarkup(command_buttons)

		await update.message.reply_text(
			textwrap.dedent(
				f"""
					**🤖 Welcome to {str(EXCHANGE_NAME).upper()} Trading Bot! 📈**
					
					Here are the available commands:
					
					*🔍 Query Commands:*
						- `/balances`
							(View all balances)
						
						- `/balance <marketId>`
							(View specific balance from a market)
						
						- `/openOrders <marketId>`
							(Get all open orders from a market)
					
					*🛒 Trading Commands:*
						- `/marketBuy <marketId> <amount> <price>`:
							(Place a market buy order)
						
						- `/marketSell <marketId> <amount> <price>`:
							(Place a market sell order)
						
						- `/limitBuy <marketId> <amount> <price> <stopLossPrice>`:
							(Place a limit buy order)
						
						- `/limitSell <marketId> <amount> <price> <stopLossPrice>`:
							(Place a limit sell order)
						
						- `/place <limit/market> <buy/sell> <marketId> <amount> <price> [<stopLossPrice>]`
							(Place a custom order)
					
					*🔧 Advanced Commands:*
						With this special command you can theoretically try any available CCXT command. Some examples are:
						
							/fetchTicker BTCUSDT
							/fetchTicker symbol=BTCUSDT
						
						- `/<anyCCXTMethod> <arg1Value> <arg2Name>=<arg2Value>`
							(Theoretically any CCXT command)
					
					Feel free to explore and trade safely! 🚀
				"""
			),
			parse_mode="Markdown",
			reply_markup=reply_markup
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

		await self.send_message(update, context, message)

	async def get_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None):
		if not self.validate_request(update, context):
			return

		market_id = context.args[0]
		message = await self.model.get_balance(market_id)

		await self.send_message(update, context, message, query)

	async def get_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE, query: CallbackQuery = None):
		if not self.validate_request(update, context):
			return

		message = await self.model.get_balances()

		await self.send_message(update, context, message, query)

	async def get_open_orders(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not self.validate_request(update, context):
			return

		if len(context.args) == 1:
			market_id = context.args.get(0)
		else:
			market_id = None

		message = await self.model.get_open_orders(market_id)

		await self.send_message(update, context, message)

	async def market_buy_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return

		try:
			market_id, amount = context.args[0], float(context.args[1])
			order = await self.model.market_buy_order(market_id, amount)

			message = f"Market Buy Order placed: {dump(order)}"

			await self.send_message(update, context, message)
		except (IndexError, ValueError):
			await update.message.reply_text("Usage: /marketBuy <marketId> <amount>")

	async def market_sell_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount = context.args[0], float(context.args[1])
			order = await self.model.market_sell_order(market_id, amount)

			message = f"Market Sell Order placed: {dump(order)}"

			await self.send_message(update, context, message)
		except (IndexError, ValueError):
			message = "Usage: /marketSell <marketId> <amount>"

			await self.send_message(update, context, message)

	async def limit_buy_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount, price, stop_loss_price = context.args[0], float(context.args[1]), float(context.args[2]), float(context.args[3])
			order = await self.model.limit_buy_order(market_id, amount, price, stop_loss_price)

			message = f"Limit Buy Order placed: {dump(order)}"

			await self.send_message(update, context, message)
		except (IndexError, ValueError):
			message = "Usage: /limitBuy <marketId> <amount> <price> <stopLossPrice>"

			await self.send_message(update, context, message)

	async def limit_sell_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount, price, stop_loss_price = context.args[0], float(context.args[1]), float(context.args[2]), float(context.args[3])
			order = await self.model.limit_sell_order(market_id, amount, price, stop_loss_price)

			message = f"Limit Sell Order placed: {dump(order)}"

			await self.send_message(update, context, message)
		except (IndexError, ValueError):
			message = "Usage: /limitSell <marketId> <amount> <price> <stopLossPrice>"

			await self.send_message(update, context, message)

	async def place_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not self.validate_request(update, context):
			return

		arguments = context.args
		if len(arguments) < 5:
			message = """Unrecognized command. Usage:\n\n/place <limit/market> <buy/sell> <marketId> <amount> <price> <stopLossPrice (optional)>"""

			await self.send_message(update, context, message)

			return

		if len(arguments) == 5:
			order_type, order_side, market_id, amount, price = arguments[0], arguments[1], arguments[2], arguments[3], arguments[4]
			stop_loss_price = None
		elif len(arguments) == 6:
			order_type, order_side, market_id, amount, price, stop_loss_price = arguments[0], arguments[1], arguments[2], arguments[3], arguments[4], arguments[5]
		else:
			message = """Unrecognized command. Usage:\n\n/place <limit/market> <buy/sell> <marketId> <amount> <price> <stopLossPrice (optional)>"""

			await self.send_message(update, context, message)

			return

		# noinspection PyTypeChecker
		order_type: OrderType = str(order_type).lower()
		# noinspection PyTypeChecker
		order_side: OrderSide = str(order_side).lower()

		if order_type not in ["limit", "market"]:
			message = """Invalid order type. Allowed values are: limit/market"""

			await self.send_message(update, context, message)

			return

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
			price = float(price)
		except ValueError:
			message = """Invalid price. Ex.: 123.45"""
			await self.send_message(update, context, message)

			return

		order = await self.model.place_order(market_id, order_type, order_side, amount, price, stop_loss_price)

		message = f"""{dump(order)}"""

		await self.send_message(update, context, message)


# noinspection PyMethodMayBeStatic
class Model:
	async def get_balance(self, market_id: str):
		balances = await self.get_balances()
		balance = balances.get('total', {}).get(market_id, 0)

		return {market_id: balance}

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

	async def limit_buy_order(self, market_id: str, amount: float, price: float, stop_loss_price: float):
		return exchange.create_order(market_id, "limit", "buy", amount, price, {
			"stopLossPrice": stop_loss_price
		})

	async def limit_sell_order(self, market_id: str, amount: float, price: float, stop_loss_price: float):
		return exchange.create_order(market_id, "limit", "sell", amount, price, {
			"stopLossPrice": stop_loss_price
		})

	async def place_order(self, market: str, order_type: OrderType, order_side: OrderSide, amount: float, price: float = None, stop_loss_price: float = None):
		return exchange.create_order(market, order_type, order_side, amount, price, {
			"stopLossPrice": stop_loss_price
		})

	def __getattr__(self, name):
		attribute = getattr(exchange, name, None)
		if callable(attribute):
			async def method(*args, **kwargs):
				return attribute(*args, **kwargs)
			return method
		return attribute


def dump(target: Any):
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

	print(await model.get_balances())
	print(await model.get_balance('BTC'))
	print(await model.get_open_orders('BTCUSDT'))
	print(await model.market_buy_order('BTCUSDT', 0.00009))
	print(await model.market_sell_order('BTCUSDT', 0.00009))
	print(await model.limit_buy_order('BTCUSDT', 0.001, 50000, 50001))
	print(await model.limit_sell_order('BTCUSDT', 0.00009, 999999.99, 1000000))
	print(await model.place_order('BTCUSDT', 'market', 'buy', 0.00001))
	print(await model.place_order('BTCUSDT', 'limit', 'sell', 0.00001, 999999.99, 1000000))

	print(await model.fetch_balance())
	print(await model.fetch_ticker('BTCUSDT'))


def main():
	telegram = Telegram()

	application = Application.builder().token(TELEGRAM_TOKEN).build()

	application.add_handler(CommandHandler("start", telegram.start))
	application.add_handler(CommandHandler("balance", telegram.get_balance))
	application.add_handler(CommandHandler("balances", telegram.get_balances))
	application.add_handler(CommandHandler("openOrders", telegram.get_open_orders))
	application.add_handler(CommandHandler("marketBuy", telegram.market_buy_order))
	application.add_handler(CommandHandler("marketSell", telegram.market_sell_order))
	application.add_handler(CommandHandler("limitBuy", telegram.limit_buy_order))
	application.add_handler(CommandHandler("limitSell", telegram.limit_sell_order))
	application.add_handler(CommandHandler("place", telegram.place_order))

	application.add_handler(CallbackQueryHandler(telegram.button_handler))

	application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, telegram.handle_text_message))
	application.add_handler(MessageHandler(filters.COMMAND, telegram.magic_command))

	application.run_polling()


if __name__ == "__main__":
	main()
	# asyncio.get_event_loop().run_until_complete(test())
