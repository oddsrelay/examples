# OddsRelay examples

Small Python programs that read the [OddsRelay](https://oddsrelay.io) odds API, one folder each.
Python 3.9 or later and nothing else: there are no packages to install.

| Folder | What it shows |
|---|---|
| [oddsmatcher-50](oddsmatcher-50) | Each bookmaker back price on a matched board beside the lowest exchange lay price, sorted by a rating the script calculates. |
| [odds-screen](odds-screen) | The best back price for each selection across every venue on the raw board, and which venues offer it. |
| [conditional-polling](conditional-polling) | Polling a board with `ETag` and `If-None-Match`: an unchanged board comes back as an empty `304 Not Modified` that costs nothing. |
| [csv-export](csv-export) | Any matched board written to CSV, one row per back or lay offer. |

## Run one

```sh
export ODDSRELAY_KEY="your API key"
cd oddsmatcher-50
python3 main.py --sports tennis
```

Every script takes `--help`. The key comes from your OddsRelay account; the [docs](https://oddsrelay.io/docs)
cover keys, routes and parameters.

## What every example does

- Reads the key from `ODDSRELAY_KEY` and sends it as `Authorization: Bearer`. It never goes in a URL and is
  never printed.
- Sends `Accept-Encoding: gzip` and unzips what comes back. Python's `urllib` asks for an uncompressed reply
  unless told otherwise, and the standard, dutching and raw boards refuse that.
- Prices the request first with `quote=true`, which costs nothing. If the request has a price, the script asks
  before spending it; pass `--max-tokens` to set a ceiling and run without the prompt.
- Waits out a `429` for as long as `Retry-After` says, and stops on any other error with the API's error code
  and request id.

The HTTP helper is `api.py`. Each folder keeps an identical copy, so any folder can be lifted out on its own.

## Tests

The tests run each example's logic on the response examples published in the API's OpenAPI file (`fixtures/`).
They make no network calls and need no key.

```sh
for m in */main.py; do (cd "$(dirname "$m")" && python3 -m unittest -v) || break; done
```

## Links

- Docs: https://oddsrelay.io/docs
- OpenAPI file: https://api.oddsrelay.io/v2/openapi.json

## License

[MIT](LICENSE)
