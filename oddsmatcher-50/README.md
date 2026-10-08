# oddsmatcher-50

An oddsmatcher in about 50 lines of Python. It reads a matched board, pairs each bookmaker back price with
the lowest exchange lay price for the same selection, and sorts the pairs by a rating it calculates. The feed
sends prices and the liquidity behind each lay, never a rating, so the rating is this script's own arithmetic.

## Run

```sh
export ODDSRELAY_KEY="your API key"
python3 main.py --sports tennis
```

| Option | What it does |
|---|---|
| `--board` | `standard` (the default), `2up` or `bog`: the boards whose lay side is a plain list |
| `--sports`, `--bookmakers`, `--exchanges`, `--markets` | Filters, passed to the API as given (comma-separated keys) |
| `--region` | One region code, passed as given |
| `--commission` | Your exchange's commission as a fraction from 0 to 1 (such as `0.02`), used in the rating |
| `--top` | How many rows to print |
| `--max-tokens` | Spend up to this many tokens without asking |

Each line shows the rating, the kick-off, the event, the market and selection, the back offer (bookmaker and
price) and the lay offer (exchange, price and the liquidity available at that price).

## The rating

```
rating = 100 × back × (1 − commission) ÷ (lay − commission)
```

It compares a back price with a lay price once the exchange's commission is taken into account. At 100 the
two prices balance exactly. Above 100 the back price is longer than the lay price once commission is
taken off; below 100 it is shorter.

## Test

```sh
python3 -m unittest -v
```

The test runs `pairs()` and `rating()` on the API's own response examples in `../fixtures`, with no network.
