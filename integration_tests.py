from typing import Dict

import json

import os
import ccxt
# import ccxt.async_support as ccxt


class IntegrationTests:
	def __init__(self):
		self.use_sandbox_mode = True
		self.market_symbols = ['tsoltusdc', 'tbtctusdc']
		self.market_ids = ['200047', '200005']
		self.client_order_id = 1712612349538
		self.exchange_order_id = '5328155590'
		self.community_exchange = None
		self.pro_exchange = None

	def run(self):
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
			# self.cancel_order()
			# self.fetch_balance()
			# self.fetch_raw_order()
			# self.fetch_order()
			# self.fetch_open_orders()
			# self.fetch_orders()
			# self.fetch_orders_all_markets()
			# self.fetch_order_book()
			# self.fetch_ticker()
			# self.fetch_tickers()
			# self.cancel_all_orders()
			# self.fetch_orders()
			# self.fetch_ohlcv()
			# self.fetch_trades()
			# self.fetch_my_trades()
			# self.fetch_closed_orders()
			# self.fetch_status()
			# self.deposit()
			# self.withdraw()
			# self.watch_order_book()
			# self.parse_order()

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
		exchanges = ccxt.exchanges
		self.log(exchanges)

	def create_community_exchange(self):
		self.community_exchange = getattr(ccxt, self.exchange_id)()
		self.community_exchange.api_key = os.getenv('API_KEY')
		self.community_exchange.secret = os.getenv('API_SECRET')
		if self.use_sandbox_mode:
			self.community_exchange.set_sandbox_mode(True)
		self.community_exchange.options['subaccountId'] = self.sub_account_id

	def create_pro_exchange(self):
		self.pro_exchange = getattr(ccxt.pro, self.exchange_id)()
		self.pro_exchange.api_key = os.getenv('API_KEY')
		self.pro_exchange.secret = os.getenv('API_SECRET')
		if self.use_sandbox_mode:
			self.community_exchange.set_sandbox_mode(True)
		self.pro_exchange.options['subaccountId'] = self.sub_account_id

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
		response = self.community_exchange.fetch_ohlcv()
		self.log(response)

	def fetch_trades(self):
		response = self.community_exchange.fetch_trades(self.market_symbols[0])
		self.log(response)

	def fetch_balance(self):
		response = self.community_exchange.fetch_balance()
		self.log(response)

	def create_order(self):
		response = self.community_exchange.create_order(
			self.market_symbols[0], 'limit', 'buy', 0.1, 125.0,
			{
				'requestId': 1,
				'subaccountId': self.sub_account_id,
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
			'subaccountId': self.sub_account_id,
			'requestId': 1,
		})
		self.log(response)

	def fetch_raw_order(self):
		response = self.community_exchange.fetch_raw_order(self.exchange_order_id, self.market_symbols[0], {
			'subAccountId': self.sub_account_id
		})
		self.log(response)

	def fetch_order(self):
		response = self.community_exchange.fetch_order(self.exchange_order_id, self.market_symbols[0], {
			'subAccountId': self.sub_account_id
		})
		self.log(response)

	def fetch_orders(self):
		response = self.community_exchange.fetch_orders(self.market_symbols[0], None, None, {
			'subAccountId': self.sub_account_id
		})
		self.log(response)

	def fetch_orders_all_markets(self):
		response = self.community_exchange.fetch_orders_all_markets(None, None, {
			'subAccountId': self.sub_account_id
		})
		self.log(response)

	def fetch_open_orders(self):
		response = self.community_exchange.fetch_open_orders(self.market_symbols[0], None, None, {
			'subAccountId': self.sub_account_id
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
		pass

	def watch_order_book(self):
		response = self.pro_exchange.watch_order_book(self.market_symbols[0])
		self.log(response)

	def parse_order(self):
		pass
