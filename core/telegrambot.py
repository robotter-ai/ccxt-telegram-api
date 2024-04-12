import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, CallbackContext
)
from core.tradeexcutor import TradeExecutor
from util import formatter

# Constants remain unchanged
TRADE_SELECT, SHORT_TRADE, LONG_TRADE, OPEN_ORDERS, FREE_BALANCE = range(5)
CANCEL_ORD, PROCESS_ORD_CANCEL = range(5, 7)
COIN_NAME, PERCENT_CHANGE, AMOUNT, PRICE, PROCESS_TRADE = range(7, 12)
CONFIRM, CANCEL, END_CONVERSATION = range(12, 15)


class TelegramBot:
    def __init__(self, token: str, allowed_user_id, trade_executor: TradeExecutor):
        self.application = Application.builder().token(token).build()
        self.trade_executor = trade_executor
        self.exchange = self.trade_executor.exchange
        # self.private_filter = filters.User(user_id=int(allowed_user_id))
        self._prepare()

    def _prepare(self):
        self.application.add_handler(CommandHandler('start', self.show_help))
        # self.application.add_handler(CommandHandler('start', self.show_help, filters=self.private_filter))
        self.application.add_handler(self.build_conversation_handler())
        self.application.add_error_handler(self.handle_error)

    def show_help(self, update: Update, context: CallbackContext) -> None:
        update.message.reply_text('Type /trade to show options')

    def show_options(self, update: Update, context: CallbackContext) -> int:
        button_list = [
            [InlineKeyboardButton("Short trade", callback_data=str(SHORT_TRADE)),
             InlineKeyboardButton("Long trade", callback_data=str(LONG_TRADE))],
            [InlineKeyboardButton("Open orders", callback_data=str(OPEN_ORDERS)),
             InlineKeyboardButton("Available balance", callback_data=str(FREE_BALANCE))],
        ]
        update.message.reply_text("Trade options:", reply_markup=InlineKeyboardMarkup(button_list))
        return TRADE_SELECT

    def process_trade_selection(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        query.answer()
        selection = int(query.data)

        if selection == OPEN_ORDERS:
            # Handle orders here
            pass
        elif selection == FREE_BALANCE:
            # Handle balance here
            pass

        # Additional logic based on selection
        return END_CONVERSATION

    def build_conversation_handler(self) -> ConversationHandler:
        return ConversationHandler(
            entry_points=[CommandHandler('trade', self.show_options)],
            # entry_points=[CommandHandler('trade', self.show_options, filters=self.private_filter)],
            states={
                TRADE_SELECT: [CallbackQueryHandler(self.process_trade_selection)],
                # Add other states and their handlers here
            },
            fallbacks=[CommandHandler('start', self.show_help)],
            # fallbacks=[CommandHandler('start', self.show_help, filters=self.private_filter)],
        )

    def handle_error(self, update: object, context: CallbackContext) -> None:
        logging.warning('Update "%s" caused error "%s"', update, context.error)

    def start_bot(self) -> None:
        self.application.run_polling()

    async def _execute_trade(self, trade) -> None:
        # Implement the trade execution asynchronously
        pass

    @staticmethod
    def build_trade(user_data) -> object:
        # Return a trade object based on user_data
        pass
