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
	def _create_database(self, path: Path):
		path.parent.mkdir(parents=True, exist_ok=True)
		path.touch()

	def _initialize_database(self):
		self.mutate(
			"""
				create table user (
					id TEXT	not null,
					exchange_id TEXT not null,
					exchange_environment TEXT not null,
					telegram_id integer	not null,
					exchange_api_key TEXT not null,
					exchange_api_secret TEXT	not null,
					data TEXT,
					constraint user_pk primary key (id)
				);
			"""
		)

		self.mutate(
			"""
				create table user_token (
					token TEXT	not null,
					user_id TEXT not null,
					constraint user_token_pk primary key (token)
				);
			"""
		)

		self.commit()

	def connect(self):
		database_path = Path(properties.get('database.path.absolute'))

		should_initialize_database = False
		if not database_path.exists():
			self._create_database(database_path)
			should_initialize_database = True

		if self.read_write_connection is None:
			try:
				self.read_write_connection = sqlite3.connect(
					str(database_path.absolute()),
					detect_types=sqlite3.PARSE_DECLTYPES,
				)
				self.read_write_connection.row_factory = sqlite3.Row
			except Exception as exception:
				raise exception

		if self.read_only_connection is None:
			try:
				self.read_only_connection = sqlite3.connect(
					f"file:{str(database_path.absolute())}?mode=ro",
					uri=True,
					detect_types=sqlite3.PARSE_DECLTYPES
				)
				self.read_only_connection.row_factory = sqlite3.Row
			except Exception as exception:
				raise exception

		if should_initialize_database:
			self._initialize_database()

	def close(self):
		if self.read_write_connection:
			self.read_write_connection.close()
			self.read_write_connection = None
		if self.read_only_connection:
			self.read_only_connection.close()
			self.read_only_connection = None

	def execute(self, connection_type: ConnectionType, query: str, parameters=None, auto_commit=False):
		connection = self.read_write_connection if connection_type == ConnectionType.READ_WRITE else self.read_only_connection
		cursor = connection.cursor()

		if parameters is None:
			cursor.execute(query)
		elif isinstance(parameters, list) and isinstance(parameters[0], dict):
			cursor.executemany(query, parameters)
		else:
			cursor.execute(query, parameters)

		rows = cursor.fetchall()

		result = [dict(row) for row in rows]

		if auto_commit:
			self.commit()

		return result

	def select_single_value(self, query, parameters=None):
		"""
		Returns the first value from the first row of the query output
		"""
		row = self.select_single(query, parameters)

		if isinstance(row, dict):
			return next(iter(row.values()))
		else:
			return None

	def select_single(self, query, parameters=None):
		"""
		Returns the first row from of query output
		"""
		rows = self.select(query, parameters)

		if isinstance(rows, list) and len(rows) > 0:
			return rows[0]
		else:
			return None

	def select(self, query, parameters=None):
		return self.execute(ConnectionType.READ_ONLY, query, parameters)

	def insert(self, query, parameters=None, auto_commit=False):
		return self.execute(ConnectionType.READ_WRITE, query, parameters, auto_commit)

	def update(self, query, parameters=None, auto_commit=False):
		return self.execute(ConnectionType.READ_WRITE, query, parameters, auto_commit)

	def delete(self, query, parameters=None, auto_commit=False):
		return self.execute(ConnectionType.READ_WRITE, query, parameters, auto_commit)

	def mutate(self, query, parameters=None, auto_commit=False):
		return self.execute(ConnectionType.READ_WRITE, query, parameters, auto_commit)

	def begin(self):
		"""
		Explicitly begin a new transaction.
		"""
		self.read_write_connection.execute("BEGIN TRANSACTION;")

	def commit(self):
		self.read_write_connection.commit()

	def rollback(self):
		self.read_write_connection.rollback()


database: Database = Database.instance()
