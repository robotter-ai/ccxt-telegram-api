FROM ubuntu:latest
CMD ["tail", "-f", "/dev/null"]

ARG ROOT_PASSWORD
ARG USER_CUBE_PASSWORD
ARG TZ=${TZ:-Etc/GMT}
ARG CCXT_REPOSITORY_URL=${CCXT_REPOSITORY_URL:-https://github.com/yourtrading-ai/ccxt.git}
ARG CCXT_TELEGRAM_BOT_REPOSITORY_BRANCH=${CCXT_TELEGRAM_BOT_REPOSITORY_BRANCH:-production}
ARG CCXT_TELEGRAM_BOT_REPOSITORY_URL=${CCXT_TELEGRAM_BOT_REPOSITORY_URL:-https://github.com/yourtrading-ai/ccxt-telegram-bot.git}
ARG EXCHANGE_API_KEY
ARG EXCHANGE_API_SECRET
ARG EXCHANGE_SUB_ACCOUNT_ID
ARG TELEGRAM_ADMIN_USERNAMES
ARG TELEGRAM_TOKEN
ARG TELEGRAM_CHANNEL_ID

ENV EXCHANGE_API_KEY="$EXCHANGE_API_KEY"
ENV EXCHANGE_API_SECRET="$EXCHANGE_API_SECRET"
ENV EXCHANGE_SUB_ACCOUNT_ID="$EXCHANGE_SUB_ACCOUNT_ID"
ENV TELEGRAM_ADMIN_USERNAMES="$TELEGRAM_ADMIN_USERNAMES"
ENV TELEGRAM_TOKEN="$TELEGRAM_TOKEN"
ENV TELEGRAM_CHANNEL_ID="$TELEGRAM_CHANNEL_ID"

RUN <<-EOF
	set -ex
	# ADDING USER CUBE
	useradd -m -d /home/cube cube -p "$USER_CUBE_PASSWORD"
	chsh -s /bin/bash cube

    # GRANTING ROOT PERMISSIONS TO USER CUBE
    apt update && apt install --no-install-recommends -y \
    sudo \
    curl \
    git \
    openssh-client \
    python3 \
    python3-pip \
    python3-dev \
    php \
    php-bcmath \
    php-curl \
    php-gmp \
    && usermod -aG sudo cube
    php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');"
    php -r "if (hash_file('sha384', 'composer-setup.php') === 'dac665fdc30fdd8ec78b38b9800061b4150413ff2e3b6f88543c636f7cd84f6db9189d43a81e5503cda447da73c7e5b6') { echo 'Installer verified'; } else { echo 'Installer corrupt'; unlink('composer-setup.php'); } echo PHP_EOL;"
    php composer-setup.php --install-dir=/usr/local/bin
    mv /usr/local/bin/composer.phar /usr/local/bin/composer
    php -r "unlink('composer-setup.php');"

	set +ex
EOF

RUN rm /usr/bin/sh && ln -s /bin/bash /usr/bin/sh

USER cube
WORKDIR /home/cube

RUN :> /home/cube/.bashrc



RUN git -c http.sslVerify=false clone -b $CCXT_TELEGRAM_BOT_REPOSITORY_BRANCH $CCXT_TELEGRAM_BOT_REPOSITORY_URL

RUN <<-EOF
	set -ex
	ARCHITECTURE="$(uname -m)"

	case $(uname | tr '[:upper:]' '[:lower:]') in
		linux*)
			OS="Linux"
			FILE_EXTENSION="sh"
			case $(uname -r	| tr '[:upper:]' '[:lower:]') in
			*raspi*)
				IS_RASPBERRY="TRUE"
				;;
			*)
				IS_RASPBERRY="FALSE"
				;;
			esac
			;;
		darwin*)
			OS="MacOSX"
			FILE_EXTENSION="sh"
			;;
		msys*)
			OS="Windows"
			FILE_EXTENSION="exe"
			;;
		*)
			echo "Unrecognized OS"
			exit 1
			;;
	esac

	echo "export ARCHITECTURE=$ARCHITECTURE" >> /home/cube/.bashrc
	echo "export OS=$OS" >> /home/cube/.bashrc
	echo "export FILE_EXTENSION=$FILE_EXTENSION" >> /home/cube/.bashrc
	echo "export IS_RASPBERRY=$IS_RASPBERRY" >> /home/cube/.bashrc

	if [ "$ARCHITECTURE" == "aarch64" ]
	then
		echo "export ARCHITECTURE_SUFFIX=\"-$ARCHITECTURE\"" >> /home/cube/.bashrc
		MINICONDA_VERSION="Mambaforge-$(uname)-$(uname -m).sh"
		MINICONDA_URL="https://github.com/conda-forge/miniforge/releases/latest/download/$MINICONDA_VERSION"
		ln -s /home/cube/mambaforge /home/cube/miniconda3
	else
		MINICONDA_VERSION="Miniconda3-py38_4.10.3-$OS-$ARCHITECTURE.$FILE_EXTENSION"
		MINICONDA_URL="https://repo.anaconda.com/miniconda/$MINICONDA_VERSION"
	fi

	curl -L "$MINICONDA_URL" -o "/home/cube/miniconda.$MINICONDA_EXTENSION"
	/bin/bash "/home/cube/miniconda.$MINICONDA_EXTENSION" -b
	rm "/home/cube/miniconda.$MINICONDA_EXTENSION"

	echo 'export PATH=/home/cube/miniconda3/bin:$PATH' >> /home/cube/.bashrc
	source /home/cube/.bashrc

	conda update -n base -c conda-forge conda -y
	conda clean -tipy

	echo "export MINICONDA_VERSION=$MINICONDA_VERSION" >> /home/cube/.bashrc
	echo "export MINICONDA_URL=$MINICONDA_URL" >> /home/cube/.bashrc

	conda init
	conda update conda -y
    conda install python -y
    conda install pip -y
    pip install --upgrade pip
    conda create -n ccxt-telegram-bot -y python=3.11
    echo "cd /home/cube/ccxt-telegram-bot" >> /home/cube/.bashrc
    echo "conda activate ccxt-telegram-bot" >> /home/cube/.bashrc
    source /home/cube/.bashrc
    conda activate ccxt-telegram-bot
    conda install pip -y
    cd /home/cube/ccxt-telegram-bot
    pip install -r requirements.txt
    pip install tox

	set +ex
EOF

RUN <<-EOF
	set -ex

	source /home/cube/.bashrc

	curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash

	export NVM_DIR="$([ -z "${XDG_CONFIG_HOME-}" ] && printf %s "${HOME}/.nvm" || printf %s "${XDG_CONFIG_HOME}/nvm")"
	[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh" # This loads nvm

	nvm install --lts
	nvm cache clear

#	if [ ! "$ARCHITECTURE" == "aarch64" ]
#	then
#		npm install --unsafe-perm --only=production -g @celo/celocli@1.0.3
#	fi

	npm install --global yarn
	npm cache clean --force

	rm -rf /home/cube/.cache
	cd /home/cube
	git clone $CCXT_REPOSITORY_URL
	cd ccxt

	npm install
	composer update
	composer install
	npm run build
	cd python
	pip uninstall ccxt -y # This is going to uninstall the original ccxt package
	pip install -e . # This is going to install the ccxt package locally
	cd /home/cube/ccxt-telegram-bot


	set +ex
EOF