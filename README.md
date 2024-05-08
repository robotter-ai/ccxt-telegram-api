# CCXT Telegram BOT

This is a Telegram bot for CCXT that enable the users to do various operations like fetching balances,
placing and cancelling orders, fetching open orders, and virtually all methods that CCXT supports.

## Installation

Cloning the repository and installing the dependencies:

```bash
git clone https://github.com/yourtrading-ai/ccxt-telegram-bot.git
cd ccxt-telegram-bot

pip install -r requirements.txt
```

For each user, it is needed to export the following environment variables:

```bash
export EXCHANGE_API_KEY="<User's Cube API Key>" # For example: "00000000-0000-0000-0000-000000000000"
export EXCHANGE_API_SECRET="<User's Cube API Secret>" # For example: "0000000000000000000000000000000000000000000000000000000000000000"
export EXCHANGE_SUB_ACCOUNT_ID="<User's Cube Sub-account Id>" # For example: "100"

export TELEGRAM_ADMIN_USERNAMES= "<User's Telegram Admin Usernames>" # For example: "@MyTelegramUser" or "@MyTelegramUser1,@MyTelegramUser2"
export TELEGRAM_TOKEN="<User's Telegram Bot Token>" # For example: "0000000000:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
export TELEGRAM_CHANNEL_ID="<User's Telegram Channel Id>" # For example: "-100000000000"
```

Some other possible environment variables are:

```text
EXCHANGE_ID="<Exchange Id>" # The default is "cube", but any other one supported on CCXT can be used, for example: "binance", "coinbase", etc.
EXCHANGE_ENVIRONMENT="<Exchange environment>" # The default is "production". Possible values are: "staging" or "production"
TELEGRAM_LISTEN_COMMANDS=<Activate or not telegram> # The default is `true`. Possible values are `true` or `false`
RUN_INTEGRATION_TESTS=<Run or not integration tests> # The default is `false`. Possible values are `true` or `false`
```

Because CCXT is only available through a fork for now, you need to install it manually:

```bash
cd .. # Go back to the parent directory
git clone https://github.com/yourtrading-ai/ccxt.git
cd ccxt

npm install
npm run build

cd python
pip uninstall ccxt -y # This is going to uninstall the original ccxt package
pip install -e . # This is going to install the ccxt package locally
```

After that we can turn on the Telegram bot with:

```bash
cd ../../ccxt-telegram-bot
python app.py
```
