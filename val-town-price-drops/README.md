# val-town-price-drops

A [Val Town](https://www.val.town) val that tells you when a UK or Irish bookmaker's price drops by a percentage
you set, by email or on a webhook (Discord, Slack or any URL that takes a JSON POST). It runs on a schedule on Val
Town, so there is nothing to host. `alert.ts` is the whole val.

The val is public on Val Town: [oddsrelay/uk-price-drop-alert](https://www.val.town/x/oddsrelay/uk-price-drop-alert).

Each run first asks the API what the raw board read costs (`quote=true`, which is free). Above `MAX_TOKENS_PER_RUN`
it reads nothing and the run fails with the price. Otherwise it reads up to 250 events, soonest kick-off first, and
compares each bookmaker price with the one stored at the last run, in the val's own blob storage. Every drop of
`DROP_PERCENT` or more goes out in one message, biggest first, and each drop is sent once. Prices are forgotten once
their event starts. Exchange prices are left out.

## Use it

1. Remix the val on Val Town, or make your own: create a val, add a file with a Cron trigger (the `+` button at
   the top right of the val editor, then `CRON`) and paste `alert.ts` over its starter code.
2. Get a key: sign up at [app.oddsrelay.io/signup](https://app.oddsrelay.io/signup) and copy your key from the
   dashboard. Free gives you 50,000 tokens for 14 days from sign-up, with no card, then no tokens until you choose a plan, on the same key.
3. In the val's left sidebar, open Environment variables and add `ODDSRELAY_KEY` with your key. Never put the key
   in the code: anyone can read a public val's code, but not its environment variables.
4. Alerts come by email to your Val Town account's address (Val Town's free plan sends email only to you). To get
   them on Discord, Slack or another webhook instead, add the webhook's address as `ALERT_WEBHOOK_URL`.
5. Change the settings at the top of `alert.ts` if you like, then click Run. The first run stores the prices and
   sends a "Watching" message, which also shows that your email or webhook works.
6. Set the schedule in the cron trigger's settings, within what your Val Town plan allows. Each run spends the
   read's price, so set it to suit your OddsRelay plan too.

| Setting | What it does |
|---|---|
| `SPORTS` | Sport or competition keys, comma-separated, as `/v2/sports` lists them |
| `MARKETS` | Market keys, comma-separated (`h2h` is the match result) |
| `BOOKMAKERS` | Bookmaker keys, comma-separated, as `/v2/bookmakers` lists them |
| `DROP_PERCENT` | The smallest drop sent, as a percentage of the price at the last run |
| `MAX_TOKENS_PER_RUN` | The most one run may spend: a dearer read is not made, and the run fails with its price |

A run that fails (the cap, a refused key, a webhook that says no) shows as an error in the val's logs and sends
nothing.

## Test

In the [examples repo](https://github.com/oddsrelay/examples), `node --test test.mjs` in this folder runs the val on
the API's own raw-board example in `../fixtures`, with Val Town's blob storage and email stood in for. No key, no
network. It needs Node 22.18 or later, which runs TypeScript as it is.
