# conditional-polling

Polls a matched board the polite way. Every data reply carries an `ETag`. The script sends it back as
`If-None-Match`, and when the board has not changed the API answers `304 Not Modified` with no body, which
costs nothing. A changed board answers `200` with the new board and its token cost.

It asks for `format=bare`, the event list without the envelope. The envelope's `meta` carries times that change
with every new board, so its `ETag` would change too, and a `304` would hardly ever come back.

Polite also means waiting. Between polls the script waits for `--every` or the reply's `Cache-Control: max-age`,
whichever is longer, and it waits out any `429` for as long as `Retry-After` says.

## Run

```sh
export ODDSRELAY_KEY="your API key"
python3 main.py --sports tennis
```

| Option | What it does |
|---|---|
| `--board` | Any matched board: `standard` (the default), `2up`, `dutching`, `each-way`, `extra-place`, `bog` |
| `--sports`, `--bookmakers`, `--exchanges`, `--markets` | Filters, passed to the API as given (comma-separated keys) |
| `--region` | One region code, passed as given |
| `--every` | Seconds between polls, your choice |
| `--polls` | How many requests to make |
| `--max-tokens` | What a changed board may cost without asking |

The quote at the start prices one changed board. Each poll prints its status, the events on the board, the
board time from the `X-Processed-At` header and the `X-Tokens-Cost` header.

## Test

```sh
python3 -m unittest -v
```

`test_main.py` runs the polling loop against canned replies. `test_api.py` checks the shared helper: gzip,
the `304`, the `429` wait, and that an error names its code and request id but never the key. No network.
