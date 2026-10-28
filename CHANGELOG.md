# Changelog

## Unreleased

- `val-town-price-drops`: a Val Town cron val in TypeScript that keeps the last price of each bookmaker outcome
  in the val's blob storage and sends the drops of `DROP_PERCENT` or more since the last run in one message, by
  email or to a webhook (`ALERT_WEBHOOK_URL`). The key comes from the val's environment variables, and a free
  `quote=true` price check against `MAX_TOKENS_PER_RUN` comes before each read.
- `n8n-oddsmatcher-sheets` and `n8n-price-moves-telegram`: two n8n workflows on the HTTP Request node, with
  the key in a Header Auth credential and a free `quote=true` price check against a cap before each read. The
  first adds or updates one Google Sheets row per bookmaker back price beside the lowest exchange lay, rated
  with and without commission, matched on `row_key`. The second keeps the last price of each outcome in the
  workflow's static data and sends the moves at or past a threshold to Telegram in one message.
- `flumine-bookmaker-prices`: UK and Irish bookmakers' win prices beside Betfair's in a flumine strategy. A
  `BackgroundWorker` polls the next races on the raw board with `If-None-Match` and hands each new board to the
  strategy as a `CustomEvent`; races are matched to Betfair markets by start time, and prices to runners by name. It
  places no orders, and the Betfair client is set to paper trading.
- `racing-board`: a price table for the next races on the each-way, extra-place or BOG board, posted to Discord or
  Telegram, with the last `ETag` kept between runs so an unchanged board is a free `304` and no post, and a digest of
  the last post so a table that reads the same is not posted twice.
- The first four examples: `oddsmatcher-50`, `odds-screen`, `conditional-polling` and `csv-export`.
