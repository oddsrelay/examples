# csv-export

Writes any matched board to CSV, one row per offer: each bookmaker back offer and each exchange lay offer,
with the event, market and selection repeated on every row, ready for a spreadsheet or `pandas.read_csv`.

## Run

```sh
export ODDSRELAY_KEY="your API key"
python3 main.py --board each-way --out each-way.csv
```

| Option | What it does |
|---|---|
| `--board` | Any matched board: `standard` (the default), `2up`, `dutching`, `each-way`, `extra-place`, `bog` |
| `--sports`, `--bookmakers`, `--exchanges`, `--markets`, `--region` | Filters, passed to the API as given (comma-separated keys) |
| `--out` | The file to write; `board.csv` by default |
| `--max-tokens` | Spend up to this many tokens without asking |

## Columns

`event_id`, `commence_time`, `sport_key`, `event`, `market`, `selection`, `point`, `side`, `venue`, `price`,
`available`, `places`, `place_fraction`, `dutch_id`, `link`.

`side` is `back` or `lay`. On the each-way and extra-place boards the lay side is two sets of rows,
`lay_win` and `lay_place`. Dutching has no lay side, and its rows carry the `dutch_id` that groups them.
A field an offer does not have is an empty cell.

## Test

```sh
python3 -m unittest -v
```

The test runs `rows()` and `write_csv()` on the API's own response examples in `../fixtures`, with no network.
