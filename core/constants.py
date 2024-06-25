from dotmap import DotMap
from enum import Enum

from core.types import SystemStatus

constants = DotMap({
	"id": "ccxt-telegram-bot",
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
}, _dynamic=False)
