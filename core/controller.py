from typing import Any

from dotmap import DotMap

from core.constants import constants
from core.properties import properties


def ccxt(options: DotMap) -> DotMap[str, Any]:
	id = options.get("id", None)
	type = options.get("type", constants.ccxt.types.community)
	method = options.get("method", None)
	parameters = options.get("parameters", None)

	target = properties.get_or_default(f"""users.{id}.exchange.{type}""", None)

	if target is not None and method is not None:
		return DotMap(target[method](**parameters))
