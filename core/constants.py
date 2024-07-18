from dotmap import DotMap

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
	"errors": {
		"unauthorized_user": "Unauthorized user.",
	 	"sign_in_required": "You need to sign in to perform this operation."
	},
	"default": {
		"exchange": {
			"id": "cube",
			"web_app": {
				"url": "https://cube.exchange/"
			}
		}
	}
}, _dynamic=False)
