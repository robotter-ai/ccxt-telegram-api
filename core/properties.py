import os

import yaml
from singleton.singleton import ThreadSafeSingleton

from core.constants import constants
from core.utils import deep_merge
from core.extensions import DotMap


@ThreadSafeSingleton
class Properties(object):
	def __init__(self):
		self.properties = DotMap({}, _dynamic=False)

	def load(self, app):
		self.load_from_app(app)
		self.load_from_constants()
		self.load_from_configuration_files()
		self.load_from_database()
		self.load_from_environment_variables()
		self.define_extra_properties()

	def load_from_app(self, app):
		self.properties['app'] = app
		self.properties['root_path'] = app.root_path
		self.properties['app_root_path'] = app.root_path
		self.properties['app_instance_path'] = app.root_path

	def load_from_constants(self):
		self.properties = deep_merge(self.properties, constants)

	def load_from_configuration_files(self):
		root_path = self.properties['app_root_path']

		configuration = {}

		with open(os.path.join(root_path, constants.configuration.relative_folder, constants.configuration.main), 'r') as stream:
			target = yaml.safe_load(stream) or {}
			configuration = deep_merge(configuration, target)

		with open(os.path.join(root_path, constants.configuration.relative_folder, constants.configuration.common), 'r') as stream:
			target = yaml.safe_load(stream) or {}
			configuration = deep_merge(configuration, target)

		if os.environ.get('ENVIRONMENT'):
			configuration['environment'] = os.environ['ENVIRONMENT']

		with open(os.path.join(root_path, constants.configuration.relative_folder, constants.configuration.environment[configuration['environment']]), 'r') as stream:
			target = yaml.safe_load(stream) or {}
			configuration = deep_merge(configuration, target)

		self.properties = DotMap(deep_merge(self.properties, configuration), _dynamic=False)

	def load_from_database(self):
		pass

	def load_from_environment_variables(self):
		pass

	def get_or_default_as(self, key, type, default=None):
		# TODO Finish implementation
		raise NotImplemented()

	def get(self, key):
		output = self.get_or_default(key, None)

		if output is None:
			raise ValueError(f'Property with key "{key}" not found.')

		return output

	def get_or_default(self, key, default=None):
		# if key.startswith('public.'):
		# 	try:
		# 		request_parameters = deep_merge(request.args, request.get_json())
		# 	except RuntimeError:
		# 		request_parameters = DotMap({}, _dynamic=False)
		#
		# 	output = request_parameters.safe_deep_get(key)
		# 	if output is not None: return output

		output = self.properties.safe_deep_get(key)
		if output is not None: return output

		modified_key = key.replace('.', '_')
		output = os.environ.get(modified_key, None)
		if output is not None: return output

		modified_key = modified_key.upper()
		output = os.environ.get(modified_key, None)
		if output is not None: return output

		if isinstance(output, DotMap): return default

		return default

	def set(self, key, value):
		try:
			self.properties._dynamic = True
			self.properties.safe_deep_set(key, value)
		finally:
			self.properties._dynamic = False

	def define_extra_properties(self):
		self.set("resources_path", os.path.join(self.get("root_path"), "resources"))
		self.set("resources_configuration_path", os.path.join(self.get("resources_path"), "configuration"))
		self.set("resources_data_path", os.path.join(self.get("resources_path"), "data"))
		self.set("resources_logs_path", os.path.join(self.get("resources_path"), "logs"))
		self.set("resources_studies_path", os.path.join(self.get("resources_path"), "studies"))


properties = Properties.instance()
