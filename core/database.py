from sqlite3 import Connection

import sqlite3
from enum import Enum
from singleton.singleton import Singleton

from properties import properties


class ConnectionType(Enum):
	READ_WRITE = 0,
	READ_ONLY = 1


# noinspection PyUnusedLocal
def plain_row_factory(cursor, row):
	return row[0]


@Singleton
class Database(object):
	def __init__(self):
		self.read_write_connection: Connection
		self.read_only_connection: Connection
		self.connect()

	def close(self):
		if self.read_write_connection:
			self.read_write_connection.close()
			# noinspection PyAttributeOutsideInit
			self.read_write_connection = None
		if self.read_only_connection:
			self.read_only_connection.close()
			# noinspection PyAttributeOutsideInit
			self.read_only_connection = None

	def connect(self):
		if self.read_write_connection is None:
			try:
				# noinspection PyAttributeOutsideInit
				self.read_write_connection = sqlite3.connect(
					properties.get('database.sqlite.path'),
					detect_types=sqlite3.PARSE_DECLTYPES
				)
				self.read_write_connection.row_factory = sqlite3.Row
			except Exception as exception:
				raise exception

		if self.read_only_connection is None:
			try:
				# noinspection PyAttributeOutsideInit
				self.read_only_connection = sqlite3.connect(
					f"file:{properties.get('database.sqlite.path')}?immutable=1",
					uri=True,
					detect_types=sqlite3.PARSE_DECLTYPES
				)
				self.read_only_connection.row_factory = sqlite3.Row
			except Exception as exception:
				raise exception

	def execute(self, connection_type: ConnectionType, query: str, parameters=None):
		if connection_type == ConnectionType.READ_WRITE:
			connection = self.read_write_connection
		elif connection_type == ConnectionType.READ_ONLY:
			connection = self.read_only_connection
		else:
			raise ValueError("[Error] invalid connection type")

		cursor = connection.cursor()

		if parameters is not None and isinstance(parameters, list) and isinstance(parameters[0], dict):
			cursor.executemany(query, parameters)
		else:
			cursor.execute(query, parameters)

		return cursor.fetchall()

	def select_single(self, query, parameters=None):
		return self.execute(ConnectionType.READ_ONLY, query, parameters)[0]

	def select(self, query, parameters=None):
		return self.execute(ConnectionType.READ_ONLY, query, parameters)

	def insert(self, query, parameters=None):
		return self.execute(ConnectionType.READ_WRITE, query, parameters)

	def update(self, query, parameters=None):
		return self.execute(ConnectionType.READ_WRITE, query, parameters)

	def delete(self, query, parameters=None):
		return self.execute(ConnectionType.READ_WRITE, query, parameters)

	def mutate(self, query, parameters=None):
		return self.execute(ConnectionType.READ_WRITE, query, parameters)

	def plain_row_factory(self):
		self.read_only_connection.row_factory = plain_row_factory
		self.read_write_connection.row_factory = plain_row_factory

	def normal_row_factory(self):
		self.read_only_connection.row_factory = sqlite3.Row
		self.read_write_connection.row_factory = sqlite3.Row

	def commit(self):
		self.read_write_connection.commit()

	def rollback(self):
		self.read_write_connection.rollback()
