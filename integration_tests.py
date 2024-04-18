from typing import Dict

import json

import os
import ccxt


class IntegrationTests:
	def __init__(self):
		self.use_sandbox_mode = True
		self.market_symbols = ['tsoltusdc', 'tbtctusdc']
		self.market_ids = ['200047', '200005']
		self.client_order_id = 1712612349538
		self.exchange_order_id = '5328155590'
		self.community_exchange = None
		self.pro_exchange = None

	async def run(self):
		try:
			# await self.create_community_exchange()
			# await self.create_pro_exchange()

			# await self.get_all_exchanges()
			# await self.load_markets()
			# await self.fetch_currencies()
			# await self.fetch_markets()
			await self.fetch_trading_fee()
			# await self.create_order()
			# await self.cancel_order()
			# await self.fetch_balance()
			# await self.fetch_raw_order()
			# await self.fetch_order()
			# await self.fetch_open_orders()
			# await self.fetch_orders()
			# await self.fetch_orders_all_markets()
			# await self.fetch_order_book()
			# await self.fetch_ticker()
			# await self.fetch_tickers()
			# await self.cancel_all_orders()
			# await self.fetch_orders()
			# await self.fetch_ohlcv()
			# await self.fetch_trades()
			# await self.fetch_my_trades()
			# await self.fetch_closed_orders()
			# await self.fetch_status()
			# await self.deposit()
			# await self.withdraw()
			# await self.watch_order_book()
			# await self.parse_order()
		finally:
			await self.community_exchange.close()

	def log(self, target):
		if isinstance(target, Dict):
			print(json.dumps(target, indent=2))
		else:
			print(str(target))

	async def get_all_exchanges(self):
		exchanges = ccxt.exchanges
		self.log(exchanges)

	async def create_community_exchange(self):
		self.community_exchange = getattr(ccxt, self.exchange_id)()
		self.community_exchange.api_key = os.getenv('API_KEY')
		self.community_exchange.secret = os.getenv('API_SECRET')
		if self.use_sandbox_mode:
			self.community_exchange.set_sandbox_mode(True)
		self.community_exchange.options['subaccountId'] = self.sub_account_id

	async def create_pro_exchange(self):
		self.pro_exchange = getattr(ccxt.pro, self.exchange_id)()
		self.pro_exchange.api_key = os.getenv('API_KEY')
		self.pro_exchange.secret = os.getenv('API_SECRET')
		if self.use_sandbox_mode:
			self.community_exchange.set_sandbox_mode(True)
		self.pro_exchange.options['subaccountId'] = self.sub_account_id

	async def load_markets(self):
		response = await self.community_exchange.load_markets()
		self.log(response)

	async def fetch_markets(self):
		response = await self.community_exchange.fetch_markets()
		self.log(response)

	async def fetch_currencies(self):
		response = await self.community_exchange.fetch_currencies()
		self.log(response)

	async def fetch_ticker(self):
		response = await self.community_exchange.fetch_ticker(self.market_symbols[0])
		self.log(response)

	async def fetch_tickers(self):
		response = await self.community_exchange.fetch_tickers(self.market_symbols)
		self.log(response)

	async def fetch_order_book(self):
		response = await self.community_exchange.fetch_order_book(self.market_symbols[0])
		self.log(response)

	async def fetch_ohlcv(self):
		response = await self.community_exchange.fetch_ohlcv()
		self.log(response)

	async def fetch_trades(self):
		response = await self.community_exchange.fetch_trades(self.market_symbols[0])
		self.log(response)

	async def fetch_balance(self):
		response = await self.community_exchange.fetch_balance()
		self.log(response)

	async def create_order(self):
		response = await self.community_exchange.create_order(
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

	async def cancel_order(self):
		response = await self.community_exchange.cancel_order(self.exchange_order_id, self.market_symbols[0], {'requestId': 1})
		self.log(response)

	async def cancel_all_orders(self):
		response = await self.community_exchange.cancel_all_orders(self.market_symbols[0], {
			'subaccountId': self.sub_account_id,
			'requestId': 1,
		})
		self.log(response)

	async def fetch_raw_order(self):
		response = await self.community_exchange.fetch_raw_order(self.exchange_order_id, self.market_symbols[0], {
			'subAccountId': self.sub_account_id
		})
		self.log(response)

	async def fetch_order(self):
		response = await self.community_exchange.fetch_order(self.exchange_order_id, self.market_symbols[0], {
			'subAccountId': self.sub_account_id
		})
		self.log(response)

	async def fetch_orders(self):
		response = await self.community_exchange.fetch_orders(self.market_symbols[0], None, None, {
			'subAccountId': self.sub_account_id
		})
		self.log(response)

	async def fetch_orders_all_markets(self):
		response = await self.community_exchange.fetch_orders_all_markets(None, None, {
			'subAccountId': self.sub_account_id
		})
		self.log(response)

	async def fetch_open_orders(self):
		response = await self.community_exchange.fetch_open_orders(self.market_symbols[0], None, None, {
			'subAccountId': self.sub_account_id
		})
		self.log(response)

	async def fetch_closed_orders(self):
		pass

	async def fetch_my_trades(self):
		pass

	async def deposit(self):
		pass

	async def withdraw(self):
		response = await self.community_exchange.withdraw()
		self.log(response)

	async def fetch_trading_fee(self):
		response = await self.community_exchange.fetch_trading_fee(self.market_symbols[0])
		self.log(response)

	async def fetch_status(self):
		pass

	async def watch_order_book(self):
		response = await self.pro_exchange.watch_order_book(self.market_symbols[0])
		self.log(response)

	async def parse_order(self):
		pass
