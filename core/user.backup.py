# from dotmap import DotMap
# from fastapi import Response
# from starlette.requests import Request
# from typing import Optional, Any
#
# from ccxt import Exchange as RESTExchange, async_support as async_ccxt
# from ccxt.async_support import Exchange as WebSocketExchange
# from core.constants import constants
# from core.cypher import cypher
# from core.database import database
# from core.helpers import ccxt
# from core.properties import properties
# from core.types import Credentials, Protocol
#
#
# def get_user(request: Request | Credentials, response: Response) -> DotMap[str, Any]:
# 	pass
#
#
# def insert_user(request: Credentials, response: Response) -> DotMap[str, Any]:
# 	pass
#
#
# def update_user(request: Credentials) -> DotMap[str, Any]:
# 	parameters = await extract_all_parameters(request)
#
# 	token = extract_jwt_token(parameters)
#
# 	user = get_user(token)
#
# 	token_expiration_delta = datetime.timedelta(
# 		seconds=properties.get_or_default("server.authentication.cookie.maxAge", constants.authentication.cookie.maxAge)
# 	)
# 	token = create_jwt_token(
# 		data={"sub": str(user.id)}, expires_delta=token_expiration_delta
# 	)
#
# 	response.set_cookie(
# 		key="token",
# 		value=f"Bearer {token}",
# 		httponly=properties.get_or_default("server.authentication.cookie.httpOnly", constants.authentication.cookie.httpOnly),
# 		secure=properties.get_or_default("server.authentication.cookie.secure", constants.authentication.cookie.secure),
# 		samesite=properties.get_or_default("server.authentication.cookie.sameSite", constants.authentication.cookie.sameSite),
# 		max_age=properties.get_or_default("server.authentication.cookie.maxAge", constants.authentication.cookie.maxAge),
# 		path=properties.get_or_default("server.authentication.cookie.path", constants.authentication.cookie.path),
# 		domain=properties.get_or_default("server.authentication.cookie.domain", constants.authentication.cookie.domain),
# 	)
#
# 	return {"token": token, "type": constants.authentication.jwt.token.type}
#
#
# def insert_or_update_user(request: Credentials, response: Response) -> DotMap[str, Any]:
# 	credentials: Credentials = request
#
# 	token_expiration_delta = datetime.timedelta(
# 		seconds=properties.get_or_default("server.authentication.cookie.maxAge", constants.authentication.cookie.maxAge)
# 	)
# 	token = create_jwt_token(
# 		data={
# 			"sub": credentials.id
# 		},
# 		expires_delta=token_expiration_delta
# 	)
#
# 	response.set_cookie(
# 		key="token",
# 		value=f"Bearer {token}",
# 		httponly=properties.get_or_default("server.authentication.cookie.httpOnly", constants.authentication.cookie.httpOnly),
# 		secure=properties.get_or_default("server.authentication.cookie.secure", constants.authentication.cookie.secure),
# 		samesite=properties.get_or_default("server.authentication.cookie.sameSite", constants.authentication.cookie.sameSite),
# 		max_age=properties.get_or_default("server.authentication.cookie.maxAge", constants.authentication.cookie.maxAge),
# 		path=properties.get_or_default("server.authentication.cookie.path", constants.authentication.cookie.path),
# 		domain=properties.get_or_default("server.authentication.cookie.domain", constants.authentication.cookie.domain),
# 	)
#
# 	credentials.jwtToken = token
#
# 	update_user(credentials)
#
# 	return {"token": token, "type": constants.authentication.jwt.token.type}
#
#
# def get_user(request: Request, response: Response) -> DotMap[str, Any]:
# 	pass
#
#
# def delete_user(request: Request, response: Response) -> DotMap[str, Any]:
# 	parameters = await extract_all_parameters(request)
#
# 	token = extract_jwt_token(parameters)
#
# 	response.delete_cookie(key="token")
#
# 	delete_user(token)
#
# 	return {"message": "Successfully signed out."}
#
#
# def get_user(id_or_user_telegram_id_or_jwt_token: str | int) -> Optional[DotMap[str, Any]]:
# 	user = properties.get_or_default(f"""users.{id}""", None)
#
# 	if not user:
# 		user_id = properties.get_or_default(f"""telegram.ids.{id_or_user_telegram_id_or_jwt_token}""")
# 		user = properties.get_or_default(f"""users.{user_id}""", None)
#
# 	if not user:
# 		user_id = properties.get_or_default(f"""tokens.{id_or_user_telegram_id_or_jwt_token}""")
# 		user = properties.get_or_default(f"""users.{user_id}""", None)
#
# 	if user:
# 		return DotMap(user, _dynamic=False)
#
# 	return None
#
#
# def update_user(credentials: Credentials) -> DotMap[str, Any]:
# 	user_exists = database.select_single_value("""SELECT EXISTS(SELECT 1 FROM user WHERE id = :id);""", {"id": credentials.id})
#
# 	if not user_exists:
# 		database.insert(
# 			"""
# 				INSERT INTO
# 					user
# 						(id, exchange_id, exchange_environment, telegram_id, api_key, api_secret, sub_account_id, data)
# 					VALUES
# 						(:id, :exchange_id, :exchange_environment, :telegram_id, :api_key, :api_secret, :sub_account_id, :data)
# 			""", {
# 				"id": credentials.id,
# 				"exchange_id": credentials.exchangeId,
# 				"exchange_environment": credentials.exchangeEnvironment,
# 				"telegram_id": cypher.encrypt(credentials.userTelegramId),
# 				"api_key": cypher.encrypt(credentials.exchangeApiKey),
# 				"api_secret": cypher.encrypt(credentials.exchangeApiSecret),
# 				"sub_account_id": cypher.encrypt(credentials.exchangeOptions.get("subAccountId") if credentials.exchangeOptions else ""),
# 				"data": str({
# 					"favorites": {
# 						"tokens": [],
# 						"markets": []
# 					}
# 				}),
# 			},
# 			True
# 		)
# 		user = database.select_single("select * from user where id = :id", {"id": credentials.id})
#
# 		print(user)
#
# 	rest_exchange: RESTExchange = getattr(ccxt, credentials.exchangeId)({
# 		"apiKey": credentials.exchangeApiKey,
# 		"secret": credentials.exchangeApiSecret,
# 		"options": {
# 			"environment": credentials.exchangeEnvironment,
# 			"subaccountId": credentials.exchangeOptions.get("subAccountId"),
# 		}
# 	})
#
# 	websocket_exchange: WebSocketExchange = getattr(async_ccxt, credentials.exchangeId)({
# 		"apiKey": credentials.exchangeApiKey,
# 		"secret": credentials.exchangeApiSecret,
# 		"options": {
# 			"environment": credentials.exchangeEnvironment,
# 			"subaccountId": credentials.exchangeOptions.get("subaccountid"),
# 		}
# 	})
#
# 	if credentials.exchangeEnvironment != constants.environments.production:
# 		rest_exchange.set_sandbox_mode(True)
# 		websocket_exchange.set_sandbox_mode(True)
#
# 	rest_exchange.fetch_markets()
# 	rest_exchange.fetch_currencies()
#
# 	properties.set(f"""users.{credentials.id}.id""", credentials.id)
# 	properties.set(f"""users.{credentials.id}.exchange.{credentials.exchangeId}.{credentials.exchangeEnvironment}.credentials""", credentials)
# 	properties.set(f"""users.{credentials.id}.exchange.{credentials.exchangeId}.{credentials.exchangeEnvironment}.{Protocol.REST.value}""", rest_exchange)
# 	properties.set(f"""users.{credentials.id}.exchange.{credentials.exchangeId}.{credentials.exchangeEnvironment}.{Protocol.WebSocket.value}""", websocket_exchange)
#
# 	properties.set(f"""telegram.ids.{credentials.userTelegramId}""", credentials.id)
# 	properties.set(f"""tokens.{credentials.jwtToken}""", credentials.id)
#
# 	return properties.get_or_default(f"""users.{credentials.id}""")
#
#
# def delete_user(idOrJwtToken: str):
# 	user = get_user(idOrJwtToken)
#
# 	if user:
# 		properties.set(f"""users.{user.id}""", None)
#
# 	# properties.set(f"""telegram.ids.{userTelegramId}""", None)
# 	# properties.set(f"""tokens.{jwtToken}""", None)
