from datetime import datetime
from functools import reduce
from typing import Any, Dict

import jsonpickle
from dateutil.relativedelta import relativedelta
from deepmerge import always_merger
from dotmap import DotMap


def safe_deep_get(self, keys, default=None):
	return reduce(
		lambda dictionary, key:
			dictionary.get(key, default) if isinstance(dictionary, dict)
			else default, keys.split("."), self
	)


def safe_deep_set(self, keys, value):
	keys = keys.split(".")

	last_key = keys.pop()

	current_dict = self

	for key in keys:
		if key not in current_dict or not isinstance(current_dict[key], dict):
			current_dict[key] = {}
		current_dict = current_dict[key]

	current_dict[last_key] = value


def deep_merge(base, next):
	return always_merger.merge(base, next)


def dump(target: Any):
	try:
		if isinstance(target, str):
			return target

		if isinstance(target, DotMap):
			target = target.toDict()

		if isinstance(target, Dict):
			return str(target)

		return jsonpickle.encode(target, unpicklable=True, indent=2)
	except (Exception,):
		return target


def escape_html(text: str) -> str:
	return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&apos;")
