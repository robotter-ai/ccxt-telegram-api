import inspect
import logging
import traceback
from pathlib import Path
from singleton.singleton import ThreadSafeSingleton
from typing import Any

from core.properties import properties
from core.telegram_bot import telegram
from core.utils import dump, escape_html


@ThreadSafeSingleton
class Logger(object):

	def __init__(self):
		self.level = properties.get('logging.level')
		self.levels = properties.get('logging.levels')
		self.telegram_level: bool = properties.get('telegram.level')
		self.use_telegram: bool = properties.get('logging.use_telegram')

		directory = properties.get('logging.directory')
		Path(directory).mkdir(parents=True, exist_ok=True)

		format = properties.get('logging.format')

		logger = logging.getLogger()
		logger.setLevel(logging.DEBUG)

		for level in self.levels:
			file_handler = logging.FileHandler(f'{directory}/{str(logging.getLevelName(level)).lower()}.log', mode='a')
			file_handler.setLevel(level)

			# Create a filter to only log messages of a specific level
			class SpecificLevelFilter(logging.Filter):
				def __init__(self, level):
					super().__init__()
					self.__level = level

				def filter(self, logRecord):
					return logRecord.levelno == self.__level

			file_handler.addFilter(SpecificLevelFilter(level))
			file_handler.setFormatter(logging.Formatter(format))
			logger.addHandler(file_handler)

		file_handler = logging.FileHandler(f'{directory}/all.log', mode='a')
		file_handler.setLevel(logging.DEBUG)
		file_handler.setFormatter(logging.Formatter(format))
		logger.addHandler(file_handler)

		stream_handler = logging.StreamHandler()
		stream_handler.setFormatter(logging.Formatter(format))
		stream_handler.setLevel(self.level)
		logger.addHandler(stream_handler)

	def debug(self, message: str = "", object: Any = None, prefix: str = "", frame: Any = None):
		self.log(logging.DEBUG, message, object, prefix, frame)

	def info(self, message: str = "", object: Any = None, prefix: str = "", frame: Any = None):
		self.log(logging.INFO, message, object, prefix, frame)

	def warning(self, message: str = "", object: Any = None, prefix: str = "", frame: Any = None):
		self.log(logging.WARNING, message, object, prefix, frame)

	def error(self, message: str = "", object: Any = None, prefix: str = "", frame: Any = None):
		self.log(logging.ERROR, message, object, prefix, frame)

	def critical(self, message: str = "", object: Any = None, prefix: str = "", frame: Any = None):
		self.log(logging.CRITICAL, message, object, prefix, frame)

	def log(self, level: int, message: str = "", object: Any = None, prefix: str = "", frame: Any = None):
		if not frame:
			frame = inspect.currentframe().f_back

		filename = frame.f_code.co_filename.removeprefix(f"""{properties.get("root_path")}/""")
		line_number = frame.f_lineno
		function_name = frame.f_code.co_name

		if object:
			message = f'{message}:\n{dump(object)}'

		message = f"{prefix} {filename}:{line_number} {function_name}: {message}"

		logging.log(level, message)

		if self.use_telegram and level >= self.level and level >= self.telegram_level:
			if level >= logging.ERROR and not "/cc " in message:
				message += f"\n/cc {telegram.admins}"

			message = escape_html(message)

			telegram.send(message)

	def ignore_exception(self, exception: Exception, prefix: str = "", frame=inspect.currentframe().f_back):
		formatted_exception = traceback.format_exception(type(exception), exception, exception.__traceback__)
		formatted_exception = "\n".join(formatted_exception)

		message = f"""Ignored exception: {type(exception).__name__} {str(exception)}:\n{formatted_exception}"""

		self.log(logging.ERROR, prefix=prefix, message=message, frame=frame)


logger = Logger.instance()
