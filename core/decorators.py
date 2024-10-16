import asyncio
import logging
import traceback
from functools import wraps


def sync_handle_exceptions(method):

	@wraps(method)
	def wrapper(*args, **kwargs):
		try:
			return method(*args, **kwargs)
		except Exception as exception:
			try:
				from core.telegram_bot import telegram
				asyncio.get_event_loop().run_until_complete(
					telegram.send_message(
						str(exception)
					)
				)
			except Exception as telegram_exception:
				logging.error(traceback.format_exception(telegram_exception))

			raise

	return wrapper


def async_handle_exceptions(method):

	@wraps(method)
	async def wrapper(*args, **kwargs):
		try:
			return await method(*args, **kwargs)
		except Exception as exception:
			try:
				from core.telegram_bot import telegram
				await telegram.send_message(str(exception))
			except Exception as telegram_exception:
				logging.error(traceback.format_exception(telegram_exception))

			raise

	return wrapper


def handle_exceptions(cls):
	is_singleton = 'instance' in cls.__dict__

	original_instance_method = None

	if is_singleton:
		original_instance_method = cls.instance

	for attr, method in list(cls.__dict__.items()):
		if callable(method) and method != original_instance_method:
			if asyncio.iscoroutinefunction(method):
				setattr(cls, attr, async_handle_exceptions(method))
			else:
				setattr(cls, attr, sync_handle_exceptions(method))

	if is_singleton and original_instance_method:
		cls.instance = staticmethod(sync_handle_exceptions(original_instance_method))

	return cls
