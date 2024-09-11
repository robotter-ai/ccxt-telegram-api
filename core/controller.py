import traceback

from core.properties import properties
from core.types import APIResponseStatus, CCXTAPIRequest, CCXTAPIResponse, Environment, Protocol


async def ccxt(request: CCXTAPIRequest) -> CCXTAPIResponse:
	user_id = request.user_id
	exchange_id = request.exchange_id
	exchange_environment = request.exchange_environment if request.exchange_environment else Environment.PRODUCTION.value
	exchange_protocol = request.exchange_protocol if request.exchange_protocol else Protocol.REST.value
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
					response.status_code = response.status.http_code
					if exchange_method_parameters is None:
						response.result = attribute()
					else:
						response.result = attribute(**exchange_method_parameters.toDict())

					return response
				except Exception as exception:
					return handle_method_call_exception(exception, exchange_method, exchange_id)
			else:
				try:
					response.title = f"""{exchange_id}.{exchange_method}"""
					response.message = f"""Successfully got "{exchange_id}.{exchange_method}"."""
					response.status = APIResponseStatus.SUCCESS
					response.status_code = response.status.http_code
					response.result = {exchange_method: attribute}

					return response
				except Exception as exception:
					full_stack_trace = traceback.format_exc()
					response.title = f"""{exchange_id}.{exchange_method}"""
					response.message = f"""An error has occurred when trying to get "{exchange_id}.{exchange_method}". Error: "{exception}"."""
					response.status = APIResponseStatus.ATTRIBUTE_NOT_FOUND_ERROR
					response.status_code = response.status.http_code
					response.result = {
						"exception": f"""{exception}""",
						"stack_trace": full_stack_trace
					}

					return response
		else:
			exception = NotImplementedError("Attribute or method not available.")

			response.title = f"""{exchange_id}.{exchange_method}"""
			response.message = f"""An error has occurred when trying to execute "{exchange_id}.{exchange_method}". Error: "{exception}"."""
			response.status = APIResponseStatus.ATTRIBUTE_NOT_AVAILABLE_ERROR
			response.status_code = response.status.http_code
			response.result = {"exception": f"""{exception}"""}

			return response
	else:
		exception = ValueError(f"""Target exchange not available: "{exchange_id}.{exchange_environment}.{exchange_protocol}".""")

		response.title = f"""{exchange_id}.{exchange_method}"""
		response.message = f"""An error has occurred when trying to execute "{exchange_id}.{exchange_method}". Error: "{exception}"."""
		response.status = APIResponseStatus.EXCHANGE_NOT_AVAILABLE_ERROR
		response.status_code = response.status.http_code
		response.result = {"exception": f"""{exception}"""}

		return response


def handle_method_call_exception(exception: Exception, exchange_method: str, exchange_id: str) -> CCXTAPIResponse:
	response = CCXTAPIResponse()
	exchange_method = exchange_method.lower()
	full_stack_trace = traceback.format_exc()
	response.title = f"""{exchange_id}.{exchange_method}"""

	if exchange_method == 'create_order':
		response.message = handle_create_order_exception_message(exception)
		response.status = APIResponseStatus.METHOD_EXECUTION_ERROR
	elif exchange_method == 'cancel_order':
		response.message = handle_cancel_order_exception_message(exception)
		response.status = APIResponseStatus.METHOD_EXECUTION_ERROR
	else:
		response.message = f"""An error has occurred when trying to execute "{exchange_id}.{exchange_method}(***)". Error: "{exception}"."""
		response.status = APIResponseStatus.METHOD_EXECUTION_ERROR

	response.status_code = response.status.http_code
	response.result = {
		"exception": str(exception),
		"stack_trace": full_stack_trace
	}

	return response


def handle_create_order_exception_message(exception: Exception) -> str:
	message = str(exception)

	return f'Failed to create order: {message}'

	# if 'OrderType was not recognized' in message:
	# 	return 'Failed to create order: Order type not recognized.'
	# elif 'Unclassified error occurred.' in message:
	# 	return 'Failed to create order: Unclassified error occurred.'
	# elif 'OrderSide was not recognized' in message:
	# 	return 'Failed to create order: Order side not recognized.'
	# elif 'Invalid quantity: Quantity was zero.' in message:
	# 	return 'Failed to create order: Quantity cannot be zero.'
	# elif 'Invalid market ID' in message:
	# 	return 'Failed to create order: The specified market ID does not exist.'
	# elif 'Duplicate order ID' in message:
	# 	return 'Failed to create order: Duplicate order ID for this subaccount.'
	# elif 'Invalid side specified.' in message:
	# 	return 'Failed to create order: Invalid order side specified.'
	# elif 'Invalid time in force specified.' in message:
	# 	return 'Failed to create order: Invalid time in force specified.'
	# elif 'Invalid order type specified.' in message:
	# 	return 'Failed to create order: Invalid order type specified.'
	# elif 'Invalid post-only flag specified.' in message:
	# 	return 'Failed to create order: Invalid post-only flag specified.'
	# elif 'Invalid self-trade prevention specified.' in message:
	# 	return 'Failed to create order: Invalid self-trade prevention specified.'
	# elif 'Unknown trader: Internal error with subaccount positions.' in message:
	# 	return 'Failed to create order: Unknown trader issue with subaccount positions.'
	# elif 'Price should not be specified for market or market limit orders.' in message:
	# 	return 'Failed to create order: Price should not be specified for market orders.'
	# elif 'Post-only with market order is not allowed.' in message:
	# 	return 'Failed to create order: Post-only with market order is not allowed.'
	# elif 'Post-only with invalid time in force.' in message:
	# 	return 'Failed to create order: Post-only with invalid time in force.'
	# elif 'Exceeded spot position limits.' in message:
	# 	return 'Failed to create order: Order exceeds spot position limits.'
	# elif 'No opposing resting orders to trade against.' in message:
	# 	return 'Failed to create order: No opposing resting orders to trade against.'
	# elif 'Post-only order would have crossed and traded.' in message:
	# 	return 'Failed to create order: Post-only order would have crossed and traded.'
	# elif 'Fill or kill (FOK) order was not fully fillable.' in message:
	# 	return 'Failed to create order: Fill or kill order was not fully fillable.'
	# elif 'Only order cancellations are accepted at this time.' in message:
	# 	return 'Failed to create order: Only order cancellations are accepted at this time.'
	# elif 'Protection price would not trade for market-with-protection orders.' in message:
	# 	return 'Failed to create order: Protection price would not trade for market-with-protection orders.'
	# elif 'Market orders cannot be placed because there is no internal reference price.' in message:
	# 	return 'Failed to create order: Market orders cannot be placed because there is no internal reference price.'
	# elif 'Slippage too high: The order would trade beyond allowed protection levels.' in message:
	# 	return 'Failed to create order: Slippage too high, exceeds protection levels.'
	# elif 'Outside price band: Bid price is too low or ask price is too high.' in message:
	# 	return 'Failed to create order: Price is outside the allowable band.'


def handle_cancel_order_exception_message(exception: Exception) -> str:
	message = str(exception)

	return f'Failed to cancel order: {message}'

	# # Rej
	# if 'Order cancellation rejected for clientOrderId' in message:
	# 	if 'Invalid market ID' in message:
	# 		return 'Failed to cancel order: Invalid market ID provided.'
	# 	elif 'Order not found' in message:
	# 		return 'Failed to cancel order: The specified client order ID does not exist for the corresponding market ID and subaccount ID.'
	# 	elif 'Unclassified error occurred' in message:
	# 		return 'Failed to cancel order: An unclassified error occurred.'
	#
	# # Ack
	# if 'Order canceled due to disconnection' in message:
	# 	return 'Order was canceled due to disconnection.'
	# elif 'Order was requested to be canceled' in message:
	# 	return 'Order was successfully requested to be canceled.'
	# elif 'Immediate or cancel (IOC) order was not fully filled' in message:
	# 	return 'Order was canceled because it was an IOC that could not be fully filled.'
	# elif 'A resting order was canceled due to self-trade prevention (STP).' in message:
	# 	return 'A resting order was canceled due to self-trade prevention (STP).'
	# elif 'An aggressing order was canceled due to self-trade prevention (STP).' in message:
	# 	return 'An aggressing order was canceled due to self-trade prevention (STP).'
	# elif 'Order was covered by a mass-cancel request.' in message:
	# 	return 'Order was covered by a mass-cancel request.'
	# elif 'Order was canceled because asset position limits would be otherwise breached' in message:
	# 	return 'Order was canceled because it would breach asset position limits.'
	#
	# return f'Failed to cancel order: {message}'
