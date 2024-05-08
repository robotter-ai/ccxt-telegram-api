from singleton.singleton import ThreadSafeSingleton
from typing import Dict

import json

import os

# noinspection PyUnresolvedReferences
import ccxt as sync_ccxt
# noinspection PyUnresolvedReferences
import ccxt.async_support as async_ccxt
from ccxt import Exchange as CommunityExchange
from ccxt.async_support import Exchange as ProExchange


@ThreadSafeSingleton
class IntegrationTests:
	def __init__(self):
		from app import Model, Telegram

		self.use_sandbox_mode = True
		self.market_symbols = ['tsoltusdc', 'tbtctusdc']
		self.market_ids = ['200047', '200005']
		self.order_sides = ['buy', 'sell']
		self.order_types = ['limit', 'market']
		self.client_order_id = 1712612349538
		self.exchange_order_id = '5341481585'
		self.community_exchange: CommunityExchange = None
		self.pro_exchange: ProExchange = None
		self.model: Model = None
		self.telegram: Telegram = None

	def initialize(self, community_exchange: CommunityExchange, pro_exchange: ProExchange, telegram, model):
		self.community_exchange = community_exchange
		self.pro_exchange = pro_exchange
		self.telegram = telegram
		self.model = model

	async def run(self):
		try:
			print("begin")

			# self.create_community_exchange()
			# self.create_pro_exchange()

			# self.get_all_exchanges()
			# self.load_markets()
			# self.fetch_currencies()
			# self.fetch_markets()
			# self.fetch_trading_fee()

			# self.create_order()
			# self.create_order(self.order_sides[1])
			# self.create_order(order_type=self.order_types[1])
			# self.create_order(self.order_sides[1], self.order_types[1])

			# self.cancel_order()
			# self.fetch_balance()
			# self.fetch_raw_order()
			# self.fetch_order()
			# self.fetch_open_orders()
			# self.fetch_orders()
			# self.fetch_raw_orders()
			# self.fetch_order_book()
			# self.fetch_ticker()
			# self.fetch_tickers()
			# self.cancel_all_orders()
			# self.fetch_ohlcv()
			# self.fetch_trades()
			# self.fetch_my_trades()
			# self.fetch_closed_orders()
			# self.fetch_status()
			# self.deposit()
			# self.withdraw()
			# self.watch_order_book()

			# print(await self.model.get_balances())
			# print(await self.model.get_balance("BTC"))
			# print(await self.model.get_open_orders("BTCUSDT"))
			# print(await self.model.market_buy_order("BTCUSDT", 0.00009))
			# print(await self.model.market_sell_order("BTCUSDT", 0.00009))
			# print(await self.model.limit_buy_order("BTCUSDT", 0.001, 20000))
			# print(await self.model.limit_sell_order("BTCUSDT", 0.00009, 99999))
			# print(await self.model.place_order("BTCUSDT", "market", "buy", 0.0001))
			# print(await self.model.place_order("BTCUSDT", "limit", "sell", 0.00009, 99999))

			# print(await self.model.fetch_markets())
			# print(await self.model.fetch_balance())
			# print(await self.model.fetch_ticker("BTCUSDT"))
			# print(await self.model.fetch_tickers())
			# print(await self.model.fetch_orders("BTCUSDT"))
			# print(await self.model.fetch_currencies())
			# print(await self.model.cancel_all_orders("BTCUSDT"))
			# print(await self.model.create_order("BTCUSDT", "market", "buy", 0.0001))
			# print(await self.model.fetch_closed_orders("BTCUSDT"))
			# print(await self.model.fetch_currencies())
			# print(await self.model.fetch_balance())

			# await self.place_order(None, None, {
			# 	"type": "market",
			# 	"side": "buy",
			# 	"market_id": "BTCUSDT",
			# 	"amount": 0.00009
			# })

			# await self.place_order(None, None, {
			# 	"type": "limit",
			# 	"side": "sell",
			# 	"market_id": "BTCUSDT",
			# 	"amount": 0.00009,
			# 	"price": 99999
			# })

			print("end")
		finally:
			# self.community_exchange.close()
			pass

	def log(self, target):
		if isinstance(target, Dict):
			print(json.dumps(target, indent=2))
		else:
			print(str(target))

	def get_all_exchanges(self):
		exchanges = sync_ccxt.exchanges
		self.log(exchanges)

	def create_community_exchange(self):
		self.community_exchange = getattr(sync_ccxt, self.exchange_id)()
		self.community_exchange.api_key = os.getenv('API_KEY')
		self.community_exchange.secret = os.getenv('API_SECRET')
		if self.use_sandbox_mode:
			self.community_exchange.set_sandbox_mode(True)
		# self.community_exchange.options['subaccountId'] = self.sub_account_id

	def create_pro_exchange(self):
		self.pro_exchange = getattr(sync_ccxt.pro, self.exchange_id)()
		self.pro_exchange.api_key = os.getenv('API_KEY')
		self.pro_exchange.secret = os.getenv('API_SECRET')
		if self.use_sandbox_mode:
			self.community_exchange.set_sandbox_mode(True)
		# self.pro_exchange.options['subaccountId'] = self.sub_account_id

	def load_markets(self):
		response = self.community_exchange.load_markets()
		self.log(response)

	def fetch_markets(self):
		response = self.community_exchange.fetch_markets()
		self.log(response)

	def fetch_currencies(self):
		response = self.community_exchange.fetch_currencies()
		self.log(response)

	def fetch_ticker(self):
		response = self.community_exchange.fetch_ticker(self.market_symbols[0])
		self.log(response)

	def fetch_tickers(self):
		response = self.community_exchange.fetch_tickers(self.market_symbols)
		self.log(response)

	def fetch_order_book(self):
		response = self.community_exchange.fetch_order_book(self.market_symbols[0])
		self.log(response)

	def fetch_ohlcv(self):
		response = self.community_exchange.fetch_ohlcv(self.market_symbols[0])
		self.log(response)

	def fetch_trades(self):
		response = self.community_exchange.fetch_trades(self.market_symbols[0])
		self.log(response)

	def fetch_balance(self):
		response = self.community_exchange.fetch_balance()
		self.log(response)

	def create_order(self, side='buy', order_type='limit'):
		response = None
		if order_type == 'limit':
			if side == 'buy':
				price = 130.0
			else:
				price = 160.0
			response = self.community_exchange.create_order(
				self.market_symbols[0], order_type, side, 0.1, price,
				{
					'requestId': 1,
					'selfTradePrevention': 0,
					'postOnly': 0,
					'timeInForce': 1,
					'cancelOnDisconnect': False
				}
			)
		if order_type == 'market':
			response = self.community_exchange.create_order(
				symbol=self.market_symbols[0],
				type=order_type,
				side=side,
				amount=0.1,
				params={
					'requestId': 1,
					'selfTradePrevention': 0,
					'postOnly': 0,
					'timeInForce': 1,
					'cancelOnDisconnect': False
				}
			)
		self.log(response)

	def cancel_order(self):
		response = self.community_exchange.cancel_order(self.exchange_order_id, self.market_symbols[0], {'requestId': 1})
		self.log(response)

	def cancel_all_orders(self):
		response = self.community_exchange.cancel_all_orders(self.market_symbols[0], {
			'requestId': 1,
		})
		self.log(response)

	def fetch_raw_order(self):
		response = self.community_exchange.fetch_raw_order(self.exchange_order_id, self.market_symbols[0], {
		})
		self.log(response)

	def fetch_order(self):
		response = self.community_exchange.fetch_order(self.exchange_order_id, self.market_symbols[0], {
		})
		self.log(response)

	def fetch_orders(self):
		response = self.community_exchange.fetch_orders(self.market_symbols[0], None, None, {
		})
		self.log(response)

	def fetch_raw_orders(self):
		response = self.community_exchange.fetch_raw_orders()
		self.log(response)

	def fetch_open_orders(self):
		response = self.community_exchange.fetch_open_orders(self.market_symbols[0], None, None, {
		})
		self.log(response)

	def fetch_closed_orders(self):
		pass

	def fetch_my_trades(self):
		pass

	def deposit(self):
		pass

	def withdraw(self):
		response = self.community_exchange.withdraw()
		self.log(response)

	def fetch_trading_fee(self):
		response = self.community_exchange.fetch_trading_fee(self.market_symbols[0])
		self.log(response)

	def fetch_status(self):
		response = self.community_exchange.fetch_status()
		self.log(response)

	def watch_order_book(self):
		response = self.pro_exchange.watch_order_book(self.market_symbols[0])
		self.log(response)

	def parse_order(self):
		pass
