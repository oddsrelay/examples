# Changelog

## Unreleased

- `flumine-bookmaker-prices`: UK and Irish bookmakers' win prices beside Betfair's in a flumine strategy. A
  `BackgroundWorker` polls the next races on the raw board with `If-None-Match` and hands each new board to the
  strategy as a `CustomEvent`; races are matched to Betfair markets by start time, and prices to runners by name. It
  places no orders, and the Betfair client is set to paper trading.
- `racing-board`: a price table for the next races on the each-way, extra-place or BOG board, posted to Discord or
  Telegram, with the last `ETag` kept between runs so an unchanged board is a free `304` and no post, and a digest of
  the last post so a table that reads the same is not posted twice.
- The first four examples: `oddsmatcher-50`, `odds-screen`, `conditional-polling` and `csv-export`.
