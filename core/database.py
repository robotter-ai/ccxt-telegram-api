from sqlite3 import Connection
import sqlite3
from enum import Enum
from pathlib import Path
from singleton.singleton import Singleton
from core.properties import properties


class ConnectionType(Enum):
	READ_WRITE = 0,
	READ_ONLY = 1


@Singleton
class Database(object):
	def __init__(self):
		# noinspection PyTypeChecker
		self.read_write_connection: Connection = None
		# noinspection PyTypeChecker
		self.read_only_connection: Connection = None
		self.connect()

	# noinspection PyMethodMayBeStatic
	def _initialize_database(self, path: Path):
		path.parent.mkdir(parents=True, exist_ok=True)
		path.touch()

	def connect(self):
		database_path = Path(properties.get('database.path.absolute'))

		if not database_path.exists():
			self._initialize_database(database_path)

		if self.read_write_connection is None:
			try:
				self.read_write_connection = sqlite3.connect(
					str(database_path.absolute()),
					detect_types=sqlite3.PARSE_DECLTYPES,
					isolation_level=None
				)
				self.read_write_connection.row_factory = sqlite3.Row
			except Exception as exception:
				raise exception

		if self.read_only_connection is None:
			try:
				self.read_only_connection = sqlite3.connect(
					f"file:{str(database_path.absolute())}?immutable=1",
					uri=True,
					detect_types=sqlite3.PARSE_DECLTYPES
				)
				self.read_only_connection.row_factory = sqlite3.Row
			except Exception as exception:
				raise exception

	def close(self):
		if self.read_write_connection:
			self.read_write_connection.close()
			self.read_write_connection = None
		if self.read_only_connection:
			self.read_only_connection.close()
			self.read_only_connection = None

	def execute(self, connection_type: ConnectionType, query: str, parameters=None):
		connection = self.read_write_connection if connection_type == ConnectionType.READ_WRITE else self.read_only_connection
		cursor = connection.cursor()

		if parameters is None:
			cursor.execute(query)
		elif isinstance(parameters, list) and isinstance(parameters[0], dict):
			cursor.executemany(query, parameters)
		else:
			cursor.execute(query, parameters)

		rows = cursor.fetchall()

		return [dict(row) for row in rows]

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

	def commit(self):
		self.read_write_connection.commit()

	def rollback(self):
		self.read_write_connection.rollback()


database = Database.instance()
