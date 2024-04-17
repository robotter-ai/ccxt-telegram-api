const { Telegraf, Markup } = require('telegraf');
const ccxt = require('ccxt');
require('dotenv').config();

const TELEGRAM_TOKEN = process.env.TELEGRAM_TOKEN;
const EXCHANGE_NAME = process.env.EXCHANGE_ID || 'binance';
const EXCHANGE_API_KEY = process.env.EXCHANGE_API_KEY;
const EXCHANGE_API_SECRET = process.env.EXCHANGE_API_SECRET;
const EXCHANGE_ENVIRONMENT = process.env.EXCHANGE_ENVIRONMENT || 'production';
const EXCHANGE_SUB_ACCOUNT_ID = process.env.EXCHANGE_SUB_ACCOUNT_ID;
const TELEGRAM_ADMIN_USERNAMES = [process.env.TELEGRAM_ADMIN_USERNAME];
const UNAUTHORIZED_USER_MESSAGE = "Unauthorized user.";

const exchangeClass = ccxt[EXCHANGE_NAME];
const exchange = new exchangeClass({
    apiKey: EXCHANGE_API_KEY,
    secret: EXCHANGE_API_SECRET,
    options: {
        environment: EXCHANGE_ENVIRONMENT,
        subAccountId: EXCHANGE_SUB_ACCOUNT_ID,
    }
});

exchange.setSandboxMode(true);

const bot = new Telegraf(TELEGRAM_TOKEN);

// Utility functions
const isAdmin = (username) => TELEGRAM_ADMIN_USERNAMES.includes(username);
const beautify = (json) => JSON.stringify(json, null, 2);

// Middleware
bot.use(async (ctx, next) => {
    if (!ctx.update.message || !isAdmin(ctx.update.message.from.username)) {
        ctx.reply(UNAUTHORIZED_USER_MESSAGE);
        return;
    }
    await next();
});

// Start command
bot.start(async (ctx) => {
    const commandButtons = Markup.inlineKeyboard([
        [Markup.button.callback("Get a Token Balance", "balance")],
        [Markup.button.callback("Get All Balances", "balances")],
        [Markup.button.callback("Get All Open Orders from a Market", "open_orders")],
        [Markup.button.callback("Place a Custom Order", "place_order")],
    ]);

    await ctx.replyWithMarkdown(`
        **🤖 Welcome to ${EXCHANGE_NAME.toUpperCase()} Trading Bot! 📈**
        
        Type /help to get more information.
        Feel free to explore and trade safely! 🚀
    `, { reply_markup: commandButtons });
});

// Help command
bot.help(async (ctx) => {
    await ctx.replyWithMarkdown(`
        **🤖 Welcome to ${EXCHANGE_NAME.toUpperCase()} Trading Bot! 📈**
        
        Here's what you can do with this bot. Use the commands to interact:
        
        - /balance <token>
        - /balances
        - /openOrders <marketId>
        - /placeOrder <limit/market> <buy/sell> <marketId> <amount> <price>
        
        Type a command to proceed!
    `);
});

// Command handlers
bot.command('balance', async (ctx) => {
    const token = ctx.message.text.split(' ')[1];
    if (!token) {
        ctx.reply("Please provide a token ID. Ex: /balance BTC");
        return;
    }
    const balance = await exchange.fetchBalance();
    ctx.replyWithMarkdown(`*Balance for ${token}:*\n\n${beautify(balance.total[token] || 0)}`);
});

bot.command('balances', async (ctx) => {
    const balance = await exchange.fetchBalance();
    ctx.replyWithMarkdown(`*All Balances:*\n\n${beautify(balance.total)}`);
});

bot.command('openOrders', async (ctx) => {
    const marketId = ctx.message.text.split(' ')[1];
    if (!marketId) {
        ctx.reply("Please provide a market ID. Ex: /openOrders BTC/USD");
        return;
    }
    const orders = await exchange.fetchOpenOrders(marketId);
    ctx.replyWithMarkdown(`*Open Orders for ${marketId}:*\n\n${beautify(orders)}`);
});

bot.command('placeOrder', async (ctx) => {
    const parts = ctx.message.text.split(' ');
    if (parts.length < 6) {
        ctx.reply("Usage: /placeOrder <limit/market> <buy/sell> <marketId> <amount> <price>");
        return;
    }
    const [_, orderType, orderSide, marketId, amount, price] = parts;
    const result = await exchange.createOrder(marketId, orderType, orderSide, parseFloat(amount), parseFloat(price));
    ctx.replyWithMarkdown(`*Order Placed:*\n\n${beautify(result)}`);
});

// Handle callbacks from inline keyboards
bot.action('balance', async (ctx) => {
    ctx.reply("Send me the token ID. Example: BTC");
});

bot.action('balances', async (ctx) => {
    const balance = await exchange.fetchBalance();
    ctx.replyWithMarkdown(`*All Balances:*\n\n${beautify(balance.total)}`);
});

bot.action('open_orders', async (ctx) => {
    ctx.reply("Send me the market ID. Example: BTC/USD");
});

bot.action('place_order', async (ctx) => {
    ctx.reply("Usage: /placeOrder <limit/market> <buy/sell> <marketId> <amount> <price>");
});

// Error handling
bot.catch((err, ctx) => {
    console.error(`Error for ${ctx.updateType}`, err);
    ctx.reply(`An error occurred: ${err.message}`);
});

bot.launch();
