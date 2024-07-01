from dotmap import DotMap

from core.properties import properties
from core.types import APIResponseStatus, CCXTAPIRequest, CCXTAPIResponse, Environment, Protocol


async def ccxt(request: CCXTAPIRequest) -> CCXTAPIResponse:
	user_id = request.user_id
	exchange_id = request.exchange_id
	exchange_environment = request.exchange_environment if request.exchange_environment else Environment.PRODUCTION
	exchange_protocol = request.exchange_protocol if request.exchange_protocol else Protocol.REST
	exchange_method = request.exchange_method
	exchange_method_parameters = request.exchange_method_parameters

	target = properties.get_or_default(f"""users.{user_id}.exchange.{exchange_id}.{exchange_environment}.{exchange_protocol}""", None)

	response = CCXTAPIResponse()

	if target is not None:
		if hasattr(target, exchange_method):
			attribute = getattr(target, exchange_method)

			if callable(attribute):
				try:
					response.title = f"""{exchange_id}.{exchange_method}"""
					response.message = f"""Successfully executed "{exchange_id}.{exchange_method}(***)"."""
					response.status = APIResponseStatus.SUCCESS
					response.result = DotMap(attribute(**exchange_method_parameters))

					return response
				except Exception as exception:
					response.title = f"""{exchange_id}.{exchange_method}"""
					response.message = f"""An error has occurred when trying to execute "{exchange_id}.{exchange_method}(***)". Error: "{exception}"."""
					response.status = APIResponseStatus.METHOD_EXECUTION_ERROR
					response.result = DotMap({"exception": f"""{exception}"""})

					return response
			else:
				try:
					response.title = f"""{exchange_id}.{exchange_method}"""
					response.message = f"""Successfully got "{exchange_id}.{exchange_method}"."""
					response.status = APIResponseStatus.SUCCESS
					response.result = DotMap({exchange_method: attribute})

					return response
				except Exception as exception:
					response.title = f"""{exchange_id}.{exchange_method}"""
					response.message = f"""An error has occurred when trying to get "{exchange_id}.{exchange_method}". Error: "{exception}"."""
					response.status = APIResponseStatus.ATTRIBUTE_NOT_FOUND_ERROR
					response.result = DotMap({"exception": f"""{exception}"""})

					return response
		else:
			exception = NotImplementedError("Attribute or method not available.")

			response.title = f"""{exchange_id}.{exchange_method}"""
			response.message = f"""An error has occurred when trying to execute "{exchange_id}.{exchange_method}". Error: "{exception}"."""
			response.status = APIResponseStatus.ATTRIBUTE_NOT_AVAILABLE_ERROR
			response.result = DotMap({"exception": f"""{exception}"""})

			return response
	else:
		exception = ValueError(f"""Target exchange not available: "{exchange_id}.{exchange_environment}.{exchange_protocol}".""")

		response.title = f"""{exchange_id}.{exchange_method}"""
		response.message = f"""An error has occurred when trying to execute "{exchange_id}.{exchange_method}". Error: "{exception}"."""
		response.status = APIResponseStatus.EXCHANGE_NOT_AVAILABLE_ERROR
		response.result = DotMap({"exception": f"""{exception}"""})

		return response
