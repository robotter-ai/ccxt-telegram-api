import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, CallbackContext
)
from telegram.ext.filters import BaseFilter, Text

from core.tradeexcutor import TradeExecutor
from model.longtrade import LongTrade
from model.shorttrade import ShortTrade
from util import formatter

TRADE_SELECT = "trade_select"
SHORT_TRADE = "short_trade"
LONG_TRADE = "long_trade"
OPEN_ORDERS = "open_orders"
FREE_BALANCE = "free_balance"

CANCEL_ORD = "cancel_order"
PROCESS_ORD_CANCEL = "process_ord_cancel"

COIN_NAME = "coin_name"
PERCENT_CHANGE = "percent_select"
AMOUNT = "amount"
PRICE = "price"
PROCESS_TRADE = "process_trade"

CONFIRM = "confirm"
CANCEL = "cancel"
END_CONVERSATION = ConversationHandler.END

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)

# Constants remain unchanged
TRADE_SELECT, SHORT_TRADE, LONG_TRADE, OPEN_ORDERS, FREE_BALANCE = range(5)
CANCEL_ORD, PROCESS_ORD_CANCEL = range(5, 7)
COIN_NAME, PERCENT_CHANGE, AMOUNT, PRICE, PROCESS_TRADE = range(7, 12)
CONFIRM, CANCEL, END_CONVERSATION = range(12, 15)


class TelegramBot:
    class PrivateUserFiler(BaseFilter):
        def __init__(self, user_id):
            super.__init__(user_id)
            self.user_id = int(user_id)

        def filter(self, message):
            return message.from_user.id == self.user_id

    def __init__(self, token: str, channel_id: str, allowed_user_id, trade_executor: TradeExecutor):
        self.application = Application.builder().token(token).build()
        self.trade_executor = trade_executor
        self.exchange = self.trade_executor.exchange
        self.channel_id = channel_id
        # self.private_filter = self.PrivateUserFiler(allowed_user_id)
        self._prepare()

    def _prepare(self):
        self.application.add_handler(CommandHandler('start', self.show_help))
        self.application.add_handler(self.build_conversation_handler())
        self.application.add_error_handler(self.handle_error)

    async def show_help(self, update: Update, context: CallbackContext) -> None:
        await update.message.reply_text('Type /trade to show options')

    async def show_options(self, update: Update, context: CallbackContext) -> int:
        button_list = [
            [InlineKeyboardButton("Short trade", callback_data=str(SHORT_TRADE)),
             InlineKeyboardButton("Long trade", callback_data=str(LONG_TRADE))],
            [InlineKeyboardButton("Open orders", callback_data=str(OPEN_ORDERS)),
             InlineKeyboardButton("Available balance", callback_data=str(FREE_BALANCE))]
        ]

        await update.message.reply_text("Trade options:", reply_markup=InlineKeyboardMarkup(button_list))
        return TRADE_SELECT

    async def process_trade_selection(self, update: Update, user_data: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        selection = str(query.data)

        if selection == OPEN_ORDERS:
            orders = self.exchange.fetch_open_orders()

            if len(orders) == 0:
                self.application.bot.edit_message_text(text="You don't have open orders",
                                      chat_id=query.message.chat_id,
                                      message_id=query.message.message_id)
                return END_CONVERSATION

            # show the option to cancel active orders
            keyboard = [
                [InlineKeyboardButton("Ok", callback_data=CONFIRM),
                 InlineKeyboardButton("Cancel order", callback_data=CANCEL)]
            ]

            self.application.bot.edit_message_text(text=formatter.format_open_orders(orders),
                                  chat_id=query.message.chat_id,
                                  message_id=query.message.message_id,
                                  reply_markup=InlineKeyboardMarkup(keyboard))

            # attach opened orders, so that we can cancel by index
            user_data[OPEN_ORDERS] = orders
            return CANCEL_ORD
        elif selection == FREE_BALANCE:
            balance = self.exchange.free_balance

            msg = "You don't have any available balance" if len(balance) == 0 \
                else f"Your available balance:\n{formatter.format_balance(balance)}"

            await self.application.bot.edit_message_text(text=msg,
                                  chat_id=query.message.chat_id,
                                  message_id=query.message.message_id)
            return END_CONVERSATION

        user_data[TRADE_SELECT] = selection
        await self.application.bot.edit_message_text(text=f'Enter coin name for {selection}',
                              chat_id=query.message.chat_id,
                              message_id=query.message.message_id)
        return COIN_NAME

    def cancel_order(self, bot, update):
        query = update.callback_query

        if query.data == CANCEL:
            query.message.reply_text('Enter order index to cancel: ')
            return PROCESS_ORD_CANCEL

        self.show_help(bot, update)
        return END_CONVERSATION

    def process_order_cancel(self, bot, update, user_data):
        idx = int(update.message.text)
        order = user_data[OPEN_ORDERS][idx]
        self.exchange.cancel_order(order['id'])
        update.message.reply_text(f'Canceled order: {formatter.format_order(order)}')
        return END_CONVERSATION

    def process_coin_name(self, bot, update, user_data):
        user_data[COIN_NAME] = update.message.text.upper()
        update.message.reply_text(f'What amount of {user_data[COIN_NAME]}')
        return AMOUNT

    def process_amount(self, bot, update, user_data):
        user_data[AMOUNT] = float(update.message.text)
        update.message.reply_text(f'What % change for {user_data[AMOUNT]} {user_data[COIN_NAME]}')
        return PERCENT_CHANGE

    def process_percent(self, bot, update, user_data):
        user_data[PERCENT_CHANGE] = float(update.message.text)
        update.message.reply_text(f'What price for 1 unit of {user_data[COIN_NAME]}')
        return PRICE

    def process_price(self, bot, update, user_data):
        user_data[PRICE] = float(update.message.text)

        keyboard = [
            [InlineKeyboardButton("Confirm", callback_data=CONFIRM),
             InlineKeyboardButton("Cancel", callback_data=CANCEL)]
        ]

        update.message.reply_text(f"Confirm the trade: '{TelegramBot.build_trade(user_data)}'",
                                  reply_markup=InlineKeyboardMarkup(keyboard))

        return PROCESS_TRADE

    def process_trade(self, bot, update, user_data):
        query = update.callback_query

        if query.data == CONFIRM:
            trade = TelegramBot.build_trade(user_data)
            self._execute_trade(trade)
            update.callback_query.message.reply_text(f'Scheduled: {trade}')
        else:
            self.show_help(bot, update)

        return END_CONVERSATION

    async def handle_error(self, update: object, context: CallbackContext) -> None:
        logging.warning('Update "%s" caused error "%s"', update, context.error)

    def build_conversation_handler(self) -> ConversationHandler:
        entry_handler = CommandHandler('trade', callback=self.show_options)
        # entry_handler = CommandHandler('trade', filters=self.private_filter, callback=self.show_options)
        conversation_handler = ConversationHandler(
            entry_points=[entry_handler],
            fallbacks=[entry_handler],
            states={
                TRADE_SELECT: [CallbackQueryHandler(self.process_trade_selection)],
                CANCEL_ORD: [CallbackQueryHandler(self.cancel_order)],
                PROCESS_ORD_CANCEL: [MessageHandler(filters=Text, callback=self.process_order_cancel)],
                COIN_NAME: [MessageHandler(filters=Text, callback=self.process_coin_name)],
                AMOUNT: [MessageHandler(Text, callback=self.process_amount)],
                PERCENT_CHANGE: [MessageHandler(Text, callback=self.process_percent)],
                PRICE: [MessageHandler(Text, callback=self.process_price)],
                PROCESS_TRADE: [CallbackQueryHandler(self.process_trade)],
            },
        )
        return conversation_handler

        # return ConversationHandler(
        #     entry_points=[CommandHandler('trade', self.show_options, filters=self.private_filter)],
        #     states={
        #         TRADE_SELECT: [CallbackQueryHandler(self.process_trade_selection)],
        #         # Add other states and their handlers here
        #     },
        #     fallbacks=[CommandHandler('start', self.show_help)],
        # )

    def start_bot(self) -> None:
        self.application.run_polling()

    def _execute_trade(self, trade):
        loop = asyncio.new_event_loop()
        task = loop.create_task(self.trade_executor.execute_trade(trade))
        loop.run_until_complete(task)

    @staticmethod
    def build_trade(user_data):
        current_trade = user_data[TRADE_SELECT]
        price = user_data[PRICE]
        coin_name = user_data[COIN_NAME]
        amount = user_data[AMOUNT]
        percent_change = user_data[PERCENT_CHANGE]

        if current_trade == LONG_TRADE:
            return LongTrade(price, coin_name, amount, percent_change)
        elif current_trade == SHORT_TRADE:
            return ShortTrade(price, coin_name, amount, percent_change)
        else:
            raise NotImplementedError
