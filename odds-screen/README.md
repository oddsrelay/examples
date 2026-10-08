# odds-screen

Reads a page of the raw board (each bookmaker's and exchange's own prices, event by event) and prints, for
every event, the best back price for each selection and the venues offering it. A tie lists every venue at
that price.

## Run

```sh
export ODDSRELAY_KEY="your API key"
python3 main.py --sports tennis
```

| Option | What it does |
|---|---|
| `--sports`, `--bookmakers`, `--region` | Filters, passed to the API as given (comma-separated keys) |
| `--markets` | Market keys; `h2h` by default |
| `--limit` | Events in the page |
| `--cursor` | Read the next page: the script prints the cursor when there is one |
| `--max-tokens` | Spend up to this many tokens without asking |

The raw board keeps each venue's own selection names, so a selection two venues spell differently shows as
two rows. The matched boards line those names up.

A cursor expires, so read the next page soon after the one before it.

## Test

```sh
python3 -m unittest -v
```

The test runs `best_prices()` on the API's own response examples in `../fixtures`, with no network.
