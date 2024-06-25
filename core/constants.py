from dotmap import DotMap
from enum import Enum

from core.types import SystemStatus

constants = DotMap({
	"id": "fun-client",
	"configuration": {
		"main": "main.yml",
		"common": "common.yml",
		"environment": {
			"development": "development.yml",
			"staging": "staging.yml",
			"production": "production.yml"
		},
		"relative_folder": "resources/configuration",
	},
	"environments": {
		"development": "development",
		"staging": "staging",
		"production": "production"
	},
	"authentication": {
		"jwt": {
			"algorithm": "HS256",
			"token": {
				"type": "bearer",
				"expiration": 30  # in minutes
			}
		}
	},
	"services": {
		"status": {
			"task": "services.status",
			"delay": 500,  # in ms
			"current": None,
			"default": {
				"fun-frontend": SystemStatus.UNKNOWN,
				"filebrowser": SystemStatus.UNKNOWN,
				"fun-client": SystemStatus.UNKNOWN,
				"hb-client": SystemStatus.UNKNOWN,
				"hb-gateway": SystemStatus.UNKNOWN
			}
		}
	}
}, _dynamic=False)


class KujiraConnectorSpecification(Enum):
	CONNECTOR = "kujira"
	CHAIN = "kujira"
	NETWORK = ["mainnet", "testnet"]
	TRADING_TYPE = "CLOB_SPOT"
	CHAIN_TYPE = "KUJIRA"
	ADDITIONAL_SPENDERS = []
	ADDITIONAL_PROMPT_VALUES = {'accountId': '0'}
	CHAIN_NETWORKS = ["kujira_mainnet", "kujira_testnet"]
	TOKENS = ["KUJI", "USK"]


chains_connector_specification = {
	"KUJIRA": KujiraConnectorSpecification
}

