# racing-board

Posts a price table for the next races to a Discord channel or a Telegram chat. It reads one racing board
(`each-way`, `extra-place` or `bog`) and, for each race, prints every runner's best back price, the bookmakers
offering it with their each-way terms, and the lowest exchange lay for the win with the liquidity available at
that price. It posts prices only: no selections and no advice.

It keeps the last post's `ETag` in a small file and sends it back as `If-None-Match` on the next run. When the
board has not changed, the API answers `304 Not Modified`, which costs nothing, and nothing is posted. That makes
it safe to run from a scheduler such as cron. It asks for `format=bare`, the event list without the envelope,
because the envelope's `meta` times would change the `ETag` with every new board.

The `ETag` labels the whole board, so it also moves when something the table does not show changes, such as a place
lay or a price below the best. The file therefore also keeps a digest of the last post's text, and a table that
reads the same as the last one is not posted again.

## Run

```sh
export ODDSRELAY_KEY="your API key"
python3 main.py --dry-run
```

`--dry-run` prints the table and posts nothing. To post, set one destination, then run without it:

```sh
# Discord: Server Settings, Integrations, Webhooks, then Copy Webhook URL
export DISCORD_WEBHOOK_URL="the webhook URL"

# or Telegram: a bot from @BotFather, added to your channel as an administrator that can post messages
export TELEGRAM_BOT_TOKEN="the bot's token"
export TELEGRAM_CHAT_ID="@your_channel"

python3 main.py --max-tokens <the quoted price>
```

The webhook URL and the bot token are both secrets: anyone holding one can post as your bot. Keep them in the
environment, never in the script, and the script never prints them, not even in an error.

| Option | What it does |
|---|---|
| `--board` | `each-way` (the default), `extra-place` or `bog` |
| `--hours` | Races starting within this many hours from now (default 1) |
| `--bookmakers` | Bookmaker keys, comma-separated, as `/v2/bookmakers` lists them; all of them if left out |
| `--runners` | Most runners shown per race, shortest price first (default 10) |
| `--max-tokens` | Spend up to this many tokens without asking |
| `--state` | The file that keeps the last post's `ETag` and a digest of its text (default `.racing-board-etag`) |
| `--dry-run` | Print the table instead of posting it, ignoring the saved `ETag`, and save nothing |

The quote at the start prices the call and costs nothing. On the racing boards a call costs the same whatever
you filter, so `--bookmakers` does not change the price: it trims the table, and a narrower board changes less
often, so more runs end in a free `304`.

## What a line shows

```
Ayr 13:30 BST
Bassrah               4.0  ladbrokes, betfred  lay 4.3 (17)
```

The race heading is the course and the start time in UK time (UTC on a machine with no time zone data). Each runner
line gives the best back price, the bookmakers offering it (after the second, `+N` counts the rest) and, on the
each-way boards, each one's terms (`3pl 1/5`: three places at a fifth of the odds). Then the lowest win lay on the
exchanges, and in brackets the liquidity available at it. Runner names that differ only in case or punctuation are
shown as one runner.

One message holds as many races as fit in Discord's 2,000 characters; a note counts the races left out. Prices
are decimal, as the API sends them.

## Test

```sh
python3 -m unittest -v
```

The tests build the table from the API's own response examples in `../fixtures` and check the Discord and
Telegram requests, the `304` path and the quote, with the network replaced. No key, no network.
