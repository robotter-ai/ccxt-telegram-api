import ccxt
import jsonpickle
import logging
import os
from ccxt.base.types import OrderType, OrderSide
from dotmap import DotMap
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from typing import Any, Dict

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.DEBUG)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
ADMIN_USERNAMES = [os.getenv("TELEGRAM_ADMIN_USERNAME")]

EXCHANGE_NAME = os.getenv("EXCHANGE_ID", "binance")
EXCHANGE_API_KEY = os.getenv("EXCHANGE_API_KEY")
EXCHANGE_API_SECRET = os.getenv("EXCHANGE_API_SECRET")
EXCHANGE_ENVIRONMENT = os.getenv("EXCHANGE_ENVIRONMENT", "production")
EXCHANGE_SUB_ACCOUNT_ID = os.getenv("EXCHANGE_SUB_ACCOUNT_ID")

UNAUTHORIZED_USER_MESSAGE = "Unauthorized user."

exchange = ccxt.binance({
	"apiKey": EXCHANGE_API_KEY,
	"secret": EXCHANGE_API_SECRET,
	"options": {
		"environment": EXCHANGE_ENVIRONMENT,
		"subAccountId": EXCHANGE_SUB_ACCOUNT_ID,
	}
})


class Telegram:

	def __init__(self):
		self.model = Model()

	# noinspection PyMethodMayBeStatic
	def is_admin(self, username):
		return username in ADMIN_USERNAMES

	async def validate_request(self, update: Update, _context: ContextTypes.DEFAULT_TYPE):
		if not self.is_admin(update.message.from_user.username):
			await update.message.reply_text(UNAUTHORIZED_USER_MESSAGE)
			return False

		return True

	async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return

		command_list = [
			"/balances - View all balances",
			"/balance <marketId> - View specific market balance",
			"/marketBuy <marketId> <amount> <price> - Place a market buy order",
			"/marketSell <marketId> <amount> <price> - Place a market sell order",
			"/limitBuy <marketId> <amount> <price> <stopLossPrice> - Place a limit buy order",
			"/limitSell <marketId> <amount> <price> <stopLossPrice> - Place a limit sell order",
			"/place <limit/market> <buy/sell> <marketId> <amount> <price> <stopLossPrice (optional)> - Place a custom order"
		]

		await update.message.reply_text(
			f"Welcome to {EXCHANGE_NAME} trading bot.\nThe available commands are:\n" + "\n".join(command_list)
		)

	async def get_balance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not self.validate_request(update, context):
			return

		market_id = context.args[0]
		balance = await self.model.get_balance(market_id)

		await update.message.reply_text(str(balance))

	async def get_balances(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not self.validate_request(update, context):
			return

		balances = await self.model.get_balances()

		await update.message.reply_text(str(balances))

	async def market_buy_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return

		try:
			market_id, amount = context.args[0], float(context.args[1])
			order = await self.model.market_buy_order(market_id, amount)
			await update.message.reply_text(f"Market Buy Order placed: {dump(order)}")
		except (IndexError, ValueError):
			await update.message.reply_text("Usage: /marketBuy <marketId> <amount>")

	async def market_sell_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount = context.args[0], float(context.args[1])
			order = await self.model.market_sell_order(market_id, amount)
			await update.message.reply_text(f"Market Sell Order placed: {dump(order)}")
		except (IndexError, ValueError):
			await update.message.reply_text("Usage: /marketSell <marketId> <amount>")

	async def limit_buy_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount, price, stop_loss_price = context.args[0], float(context.args[1]), float(context.args[2]), float(context.args[3])
			order = await self.model.limit_buy_order(market_id, amount, price, stop_loss_price)
			await update.message.reply_text(f"Limit Buy Order placed: {dump(order)}")
		except (IndexError, ValueError):
			await update.message.reply_text("Usage: /limitBuy <marketId> <amount> <price> <stopLossPrice>")

	async def limit_sell_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not await self.validate_request(update, context):
			return
		try:
			market_id, amount, price, stop_loss_price = context.args[0], float(context.args[1]), float(context.args[2]), float(context.args[3])
			order = await self.model.limit_sell_order(market_id, amount, price, stop_loss_price)
			await update.message.reply_text(f"Limit Sell Order placed: {dump(order)}")
		except (IndexError, ValueError):
			await update.message.reply_text("Usage: /limitSell <marketId> <amount> <price> <stopLossPrice>")

	async def place_order(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
		if not self.validate_request(update, context):
			return

		arguments = context.args
		if len(arguments) < 5:
			await update.message.reply_text(
				"""Unrecognized command. Usage:\n\n/place <limit/market> <buy/sell> <marketId> <amount> <price> <stopLossPrice (optional)>""")
			return

		if len(arguments) == 5:
			order_type, order_side, market_id, amount, price = arguments[0], arguments[1], arguments[2], arguments[3], arguments[4]
			stop_loss_price = None
		elif len(arguments) == 6:
			order_type, order_side, market_id, amount, price, stop_loss_price = arguments[0], arguments[1], arguments[2], arguments[3], arguments[4], arguments[5]
		else:
			await update.message.reply_text(
				"""Unrecognized command. Usage:\n\n/place <limit/market> <buy/sell> <marketId> <amount> <price> <stopLossPrice (optional)>""")
			return

		# noinspection PyTypeChecker
		order_type: OrderType = str(order_type).lower()
		# noinspection PyTypeChecker
		order_side: OrderSide = str(order_side).lower()

		if order_type not in ["limit", "market"]:
			await update.message.reply_text("""Invalid order type. Allowed values are: limit/market""")
			return

		if order_side not in ["buy", "sell"]:
			await update.message.reply_text("""Invalid order side. Allowed values are: buy/sell""")
			return

		try:
			amount = float(amount)
		except ValueError:
			await update.message.reply_text("""Invalid amount. Ex.: 123.45""")
			return

		try:
			price = float(price)
		except ValueError:
			await update.message.reply_text("""Invalid price. Ex.: 123.45""")
			return

		order = await self.model.place_order(market_id, order_type, order_side, amount, price, stop_loss_price)

		await update.message.reply_text(f"""{dump(order)}""")


# noinspection PyMethodMayBeStatic
class Model:
	async def get_balance(self, market_id: str):
		balances = await self.get_balances()
		balance = balances.get('total', {}).get(market_id, 0)

		return {market_id: balance}

	async def get_balances(self):
		return exchange.fetch_balance()

	async def market_buy_order(self, market_id: str, amount: float):
		return await exchange.create_order(market_id, "market", "buy", amount)

	async def market_sell_order(self, market_id: str, amount: float):
		return await exchange.create_order(market_id, "market", "sell", amount)

	async def limit_buy_order(self, market_id: str, amount: float, price: float, stop_loss_price: float):
		return await exchange.create_order(market_id, "limit", "buy", amount, price, {
			"stopLossPrice": stop_loss_price
		})

	async def limit_sell_order(self, market_id: str, amount: float, price: float, stop_loss_price: float):
		return await exchange.create_order(market_id, "limit", "sell", amount, price, {
			"stopLossPrice": stop_loss_price
		})

	async def place_order(self, market: str, order_type: OrderType, order_side: OrderSide, amount: float, price: float, stop_loss_price: float):
		return exchange.create_order(market, order_type, order_side, amount, price, {
			"stopLossPrice": stop_loss_price
		})


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


def main():
	telegram = Telegram()

	application = Application.builder().token(TELEGRAM_TOKEN).build()

	application.add_handler(CommandHandler("start", telegram.start))
	application.add_handler(CommandHandler("balance", telegram.get_balance))
	application.add_handler(CommandHandler("balances", telegram.get_balances))
	application.add_handler(CommandHandler("marketBuy", telegram.market_buy_order))
	application.add_handler(CommandHandler("marketSell", telegram.market_sell_order))
	application.add_handler(CommandHandler("limitBuy", telegram.limit_buy_order))
	application.add_handler(CommandHandler("limitSell", telegram.limit_sell_order))
	application.add_handler(CommandHandler("place", telegram.place_order))

	application.run_polling()


if __name__ == "__main__":
	main()
