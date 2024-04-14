import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters, CallbackContext
)
from core.tradeexcutor import TradeExecutor
from util import formatter


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.DEBUG)

# Constants remain unchanged
TRADE_SELECT, SHORT_TRADE, LONG_TRADE, OPEN_ORDERS, FREE_BALANCE = range(5)
CANCEL_ORD, PROCESS_ORD_CANCEL = range(5, 7)
COIN_NAME, PERCENT_CHANGE, AMOUNT, PRICE, PROCESS_TRADE = range(7, 12)
CONFIRM, CANCEL, END_CONVERSATION = range(12, 15)


class TelegramBot:
    def __init__(self, token: str, channel_id: str, trade_executor: TradeExecutor):
        self.application = Application.builder().token(token).build()
        self.trade_executor = trade_executor
        self.exchange = self.trade_executor.exchange
        self.channel_id = channel_id
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

    async def process_trade_selection(self, update: Update, context: CallbackContext) -> int:
        query = update.callback_query
        await query.answer()
        selection = int(query.data)

        if selection == FREE_BALANCE:
            balance = self.exchange.free_balance

            msg = "You don't have any available balance" if len(balance) == 0 \
                else f"Your available balance:\n{formatter.format_balance(balance)}"

            await self.application.bot.edit_message_text(text=msg,
                                  chat_id=query.message.chat_id,
                                  message_id=query.message.message_id)
            return END_CONVERSATION

        # Handling based on selection
        return END_CONVERSATION

    def build_conversation_handler(self) -> ConversationHandler:
        return ConversationHandler(
            entry_points=[CommandHandler('trade', self.show_options)],
            states={
                TRADE_SELECT: [CallbackQueryHandler(self.process_trade_selection)],
                # Add other states and their handlers here
            },
            fallbacks=[CommandHandler('start', self.show_help)],
        )

    async def handle_error(self, update: object, context: CallbackContext) -> None:
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
