# flumine-bookmaker-prices

UK and Irish bookmakers' win prices beside Betfair's own, inside a [flumine](https://github.com/betcode-org/flumine)
strategy.

A flumine `BackgroundWorker` polls the OddsRelay raw board for the next horse races, and a `CustomEvent` hands each
new board to the strategy on flumine's main thread, so the strategy needs no locks. For each GB and Irish win market
that starts within `--minutes`, the strategy keeps every runner's bookmaker prices in `market.context["bookmakers"]`,
as `{selection_id: {bookmaker: price}}`, and prints the best of them beside Betfair's best back and lay.

It places no orders. `on_prices()` is where your own logic would read the prices: it runs on every Betfair update to a
market the strategy is watching (open, not in play, starting within `--minutes`), once the first board and flumine's
runner names are in. The Betfair client is set to paper trading, so an order you add is simulated until you change that.

## Run

flumine needs Python 3.10 or later.

```sh
pip install -r requirements.txt
export ODDSRELAY_KEY="your API key"
export BETFAIR_USERNAME="your Betfair username"
export BETFAIR_PASSWORD="your Betfair password"
export BETFAIR_APP_KEY="your Betfair app key"
python3 main.py
```

Set `BETFAIR_CERTS` to the folder holding your Betfair API certificate to log in with it; without it, the login is
interactive. The [betfairlightweight](https://github.com/betcode-org/betfair) docs cover both.

| Option | What it does |
|---|---|
| `--minutes` | Show win markets starting within this many minutes (default 10) |
| `--races` | How many of the next races each poll fetches, 1 to 250 (default 30) |
| `--bookmakers` | Bookmaker keys, comma-separated, as `/v2/bookmakers` lists them; all of them if left out |
| `--every` | Seconds between polls of the board (default 30, your choice) |
| `--max-tokens` | Stop polling if a changed board costs more than this; needed for a run with no terminal |

The quote at the start prices one poll and costs nothing, and without `--max-tokens` you are asked about it whenever it
costs anything. The raw board comes in start-time order and a page is priced on the races it holds, so `--races` keeps
each poll small. Each poll sends the last `ETag` back as `If-None-Match`: an unchanged board is a `304` that costs
nothing. A changed one costs its own price, which moves with the prices its races hold, and each reply's `X-Tokens-Cost`
says what it cost. A poll that fails can still have been charged: a `500` after a spend reads `X-Tokens-Cost` 0, and the
spend stands. With `--max-tokens`, a changed board that costs more stops polling and clears the bookmaker prices (that
board is paid for, then dropped). Without it, nothing caps the polls after the start, so pass it for a long run.

## How it fits together

- `poll()` is the worker's function. It runs on the worker's own thread, so it never touches the strategy: it puts
  each new board on flumine's handler queue as a `CustomEvent`, and flumine calls `BookmakerPrices.new_board()` on
  its main thread, where `process_market_book()` runs too.
- A race on the board is a market's race when the two start within `WINDOW` seconds of each other. Its prices are
  then matched to the market's runners by name, compared without case, punctuation or a country suffix such as
  `(IRE)`, so no course names are needed, and a race the board lists twice merges into one.
- The exchanges' own prices on the board are left out (`/v2/bookmakers` marks them `is_exchange`): Betfair's side
  comes from flumine.
- If a poll fails, whatever the error, it is logged and the strategy's bookmaker prices are cleared, so it never
  reads stale ones. The next good poll fetches the whole board again.
- The board is pre-match, so a market that has turned in play is left alone.

## What a table shows

```
Kempton 18:00 GMT  1.262474543
Alpha Star          back   4.2  lay   4.3 | bookmakers 4.33 (william_hill)
Bravo Lad           back     -  lay     - | bookmakers 6.5 (bet365)
Charlie Boy         back     -  lay     - | bookmakers -
```

The heading is the course, the off in UK time and the Betfair market id. Each runner line gives Betfair's best back
and lay, then the best bookmaker price and the bookmakers offering it (after the second, `+N` counts the rest). A
market's table is printed once for each new board. Prices are decimal.

## Test

```sh
pip install -r requirements.txt
python3 -m unittest -v
```

The tests run `poll()` through flumine's own `BackgroundWorker` with the reply stubbed, hand the board over through
flumine's custom event handling, and process a market built from betfairlightweight's resources. They also read the
raw board examples in `../fixtures`. No key, no network and no Betfair login. Without flumine they are skipped.
