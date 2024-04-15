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

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHANNEL_ID = os.environ.get("TELEGRAM_CHANNEL_ID")
ADMIN_USERNAMES = [os.environ.get("TELEGRAM_ADMIN_USERNAME")]

EXCHANGE_NAME = os.environ.get("EXCHANGE_ID")
EXCHANGE_API_KEY = os.environ.get("EXCHANGE_API_KEY")
EXCHANGE_API_SECRET = os.environ.get("EXCHANGE_API_SECRET")
EXCHANGE_ENVIRONMENT = os.environ.get("EXCHANGE_ENVIRONMENT")
EXCHANGE_SUB_ACCOUNT_ID = os.environ.get("EXCHANGE_SUB_ACCOUNT_ID")

UNAUTHORIZED_USER_MESSAGE = """Unauthorized user."""

exchange = ccxt.binance({
	"apiKey": EXCHANGE_API_KEY,
	"secret": EXCHANGE_API_SECRET,
	"options": {
		"environment": EXCHANGE_ENVIRONMENT,
		"subAccountId": EXCHANGE_SUB_ACCOUNT_ID,
	}
})


def is_admin(username):
	return username in ADMIN_USERNAMES


async def start(update: Update, _context: ContextTypes.DEFAULT_TYPE):
	if not is_admin(update.message.from_user.username):
		await update.message.reply_text(UNAUTHORIZED_USER_MESSAGE)
		return


async def fetch_balances(update: Update, _context: ContextTypes.DEFAULT_TYPE):
	if not is_admin(update.message.from_user.username):
		await update.message.reply_text(UNAUTHORIZED_USER_MESSAGE)
		return

	balances = exchange.fetch_balance()

	await update.message.reply_text(dump(balances))


async def place_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
	if not is_admin(update.message.from_user.username):
		await update.message.reply_text(UNAUTHORIZED_USER_MESSAGE)
		return

	arguments = context.args
	if len(arguments) < 5:
		await update.message.reply_text("Usage: /place <limit/market> <buy/sell> <marketId> <amount> <price>")
		return

	order_type, order_side, market, amount, price = arguments[0], arguments[1], arguments[2], arguments[3], arguments[4]
	order_type: OrderType = str(order_type).lower()
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

	order = exchange.create_order(market, order_type, order_side, amount, price)

	await update.message.reply_text(f"""{dump(order)}""")


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
	application = Application.builder().token(TELEGRAM_TOKEN).build()

	application.add_handler(CommandHandler("start", start))
	application.add_handler(CommandHandler("balances", fetch_balances))
	application.add_handler(CommandHandler("place", place_order))

	application.run_polling()


if __name__ == "__main__":
	main()
