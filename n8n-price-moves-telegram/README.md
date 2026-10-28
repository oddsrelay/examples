# n8n-price-moves-telegram

An [n8n](https://n8n.io) workflow that sends a Telegram message when a UK or Irish bookmaker's price moves past a
threshold you set. It uses n8n's own HTTP Request node, so there is nothing to install.

Each run first asks the API what the raw board call costs (`quote=true`, which is free). Above `maxTokensPerRun`
the run stops there, with the price in the error. Otherwise it reads the prices of up to 250 events, soonest
kick-off first, and compares each bookmaker price with the one stored on an earlier check. Every move at or past
`moveThresholdPercent` goes out in one message, biggest first. A check with no moves sends nothing, and a move is
sent once.

The stored prices live in the workflow's static data, so there is no database to set up, and they are dropped once
their event starts. n8n saves static data only on runs the schedule starts after the workflow is published. The
first of those, like every manual run, stores the prices and sends a "Watching" message instead of moves.

## Use it

1. In n8n, import `price-moves-to-telegram.json`.
2. Create a Header Auth credential with Name `x-api-key` and your API key as the Value, and pick it in **Check the
   price** and **Read bookmaker prices**.
3. Create a bot with @BotFather and add its token as a Telegram credential in **Send to Telegram**. Send the bot a
   message first: a bot cannot start a chat.
4. In **Settings**, set `telegramChatId`. Run the workflow once and check that the Watching message arrives, then
   publish it so the schedule runs.

| Setting | What it does |
|---|---|
| `sports` | Sport or competition keys, comma-separated, as `/v2/sports` lists them |
| `markets` | Market keys, comma-separated (`h2h` is the match result) |
| `bookmakers` | Venue keys, comma-separated, as `/v2/bookmakers` lists them; an exchange here is watched on its back price |
| `moveThresholdPercent` | The smallest move, as a percentage of the earlier price, that is sent |
| `maxTokensPerRun` | The most one run may spend; a dearer call stops the run before the prices are read |
| `telegramChatId` | The chat to post to: your own chat with the bot, or a group the bot belongs to |

Telegram gets three tries per message. A message that still fails is not sent again, because its prices are
already stored, and the run shows as failed in n8n's Executions list. Each run spends the call's price, so set the
schedule to suit your plan.

## Test

```sh
node --test test.mjs
```

The test runs the workflow's Code node on the API's own raw-board example in `../fixtures`. No key, no network.
