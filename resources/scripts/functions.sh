#!/bin/bash

kill_processes_and_subprocesses() {
	local app="$1"
	local target_pids parent_pids child_pids

	target_pids=$(grep -l "\bAPP=$app\b" /proc/*/environ | cut -d/ -f3 || true)

	if [ ! -z "$target_pids" ]; then
		parent_pids=$(echo "$target_pids" | grep -o -E '([0-9]+)' | tr "\n" " ")

		for parent_pid in $parent_pids; do
			child_pids=$(pstree -p $parent_pid | grep -o -E '([0-9]+)' | tr "\n" " ")

			kill -9 $parent_pid 2>/dev/null || true

			for child_pid in $child_pids; do
				kill -9 $child_pid 2>/dev/null || true
			done
		done
	fi
}

update_ccxt() {
	source ~/.bashrc

	cd ~/ccxt

	git add .
	git stash
	git pull
	# git stash apply
	ccxt_rebuild
}

update_api() {
	source ~/.bashrc

	cd ~/api

	git add .
	git stash
	git pull
	git stash apply

	pip uninstall ccxt ccxt-robotter -y
	pip install -r requirements.txt
}

update_frontend() {
	source ~/.bashrc

	cd ~/frontend

	git add .
	git stash
	git pull
	git stash apply
	npm install
}

update() {
	source ~/.bashrc

	# update_ccxt
	update_api
	update_frontend
}

stop() {
#	stop_ssh
	stop_api
	stop_frontend
}

stop_ssh() {
	service ssh stop
}

stop_api() {
	kill_processes_and_subprocesses api
}

stop_frontend() {
	kill_processes_and_subprocesses frontend
}

restart_ssh() {
	source ~/.bashrc

	service ssh restart
	sleep 2
}

restart_api() {
	cd ~/api

	stop_api
	mkdir -p ~/logs
	nohup bash -c 'APP=api python app.py' > ~/logs/api.log 2>&1 &
}

restart_frontend() {
	cd ~/frontend

	stop_frontend
	mkdir -p ~/logs
	nohup bash -c 'APP=frontend npm run dev' > ~/logs/frontend.log 2>&1 &
}

log_frontend() {
	tail -f ~/logs/api.log
}

log_api() {
	tail -f ~/logs/api.log
}

log_all() {
	tail -f ~/logs/api.log ~/logs/api.log
}

restart() {
	source ~/.bashrc

	# restart_ssh
	restart_api
	restart_frontend

	cd ~
}

full_update() {
	update
	restart
	log_all
}

ccxt_activate_environment() {
	local environment=${ccxt_conda_environment:-cube}

	conda activate $environment
}

ccxt_hide() {
	ccxt_activate_environment

	git unhide-all
	git unhide-untracked
	git hide
	git hide-untracked

	git unhide ts/src/cube.ts
	git unhide ts/src/abstract/cube.ts
	git unhide ts/src/pro/cube.ts

	git unhide js/src/cube.js
	git unhide js/src/cube.d.ts
	git unhide js/src/abstract/cube.js
	git unhide js/src/abstract/cube.d.ts
	git unhide js/src/pro/cube.js
	git unhide js/src/pro/cube.d.ts

	git unhide python/ccxt/cube.py
	git unhide python/ccxt/abstract/cube.py
	git unhide python/ccxt/pro/cube.py

	git unhide python/ccxt/async_support/cube.py
	git unhide python/ccxt/async_support/abstract/cube.py
	git unhide python/ccxt/async_support/pro/cube.py

	git unhide php/cube.php
	git unhide php/abstract/cube.php
	git unhide php/pro/cube.php

	git unhide php/async/cube.php
	git unhide php/async/abstract/cube.php
	git unhide php/async/pro/cube.php

	git unhide cs/ccxt/api/cube.cs
	git unhide cs/ccxt/wrappers/cube.cs
	git unhide cs/ccxt/exchanges/cube.cs

	git unhide python/package.json

	git unhide temporary
}

ccxt_install() {
	ccxt_activate_environment

	npm install
}

ccxt_lint() {
	ccxt_activate_environment

	npm run lint ts/src/cube.ts
}

ccxt_transpile() {
	ccxt_activate_environment

	./build/transpile.sh cube
}

ccxt_build() {
	ccxt_activate_environment

	npm run build
}

ccxt_cleanup() {
	ccxt_activate_environment

	./cleanup.sh
}

ccxt_test() {
	ccxt_activate_environment

	node js/src/test/test.js cube --verbose
}

ccxt_rebuild() {
	ccxt_activate_environment

	ccxt_cleanup
	ccxt_install
	ccxt_lint
	ccxt_transpile
	ccxt_build
}

ccxt_full_rebuild() {
	ccxt_activate_environment

#	git reset --hard HEAD
	ccxt_cleanup
#	conda activate ccxt
	pip install tox
	composer install
	ccxt_install
#	ccxt_lint
#	ccxt_transpile
	ccxt_build
#	cd python
#	pip install -e .
}
