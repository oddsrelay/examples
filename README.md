# OddsRelay examples

Small Python programs that read the [OddsRelay](https://oddsrelay.io) odds API, one folder each.
Python 3.9 or later and nothing else: there are no packages to install. The one exception is
flumine-bookmaker-prices, which runs inside flumine (Python 3.10 or later). The three `n8n-` folders hold
[n8n](https://n8n.io) workflows instead, built on n8n's own HTTP Request node: import the JSON file into n8n.

| Folder | What it shows |
|---|---|
| [oddsmatcher-50](oddsmatcher-50) | Each bookmaker back price on a matched board beside the lowest exchange lay price, sorted by a rating the script calculates. |
| [odds-screen](odds-screen) | The best back price for each selection across every venue on the raw board, and which venues offer it. |
| [conditional-polling](conditional-polling) | Polling a board with `ETag` and `If-None-Match`: an unchanged board comes back as an empty `304 Not Modified` that costs nothing. |
| [csv-export](csv-export) | Any matched board written to CSV, one row per back or lay offer. |
| [racing-board](racing-board) | The next races' prices from a racing board, posted to a Discord channel or a Telegram chat, and only when the board has changed. |
| [flumine-bookmaker-prices](flumine-bookmaker-prices) | UK and Irish bookmakers' win prices beside Betfair's in a [flumine](https://github.com/betcode-org/flumine) strategy: a background worker polls the raw board and hands each new board to the strategy. |
| [n8n-oddsmatcher-sheets](n8n-oddsmatcher-sheets) | An n8n workflow that keeps a Google Sheet of bookmaker back prices beside the lowest exchange lay, rated: on a schedule it adds new rows, updates the ones it wrote before and removes those that have left the board. |
| [n8n-back-lay-log-sheets](n8n-back-lay-log-sheets) | An n8n workflow that logs close back and lay pairs to Google Sheets, with a new row only when a pair is new or one of its prices has moved since its last row. |
| [n8n-price-moves-telegram](n8n-price-moves-telegram) | An n8n workflow that sends a Telegram message when a bookmaker's price moves past a threshold you set, comparing each check with the last. |

## Get a key

Sign up at [app.oddsrelay.io/signup](https://app.oddsrelay.io/signup) and copy your key from the dashboard.
Free gives you 50,000 tokens for 14 days from sign-up, with no card, then no tokens until you choose a plan, on the same key. [Plans and token prices](https://oddsrelay.io/pricing).

## Run one

```sh
export ODDSRELAY_KEY="your API key"
cd oddsmatcher-50
python3 main.py --sports tennis
```

Every script takes `--help`. The [docs](https://oddsrelay.io/docs) cover routes and parameters.

## What every example does

- Reads the key from `ODDSRELAY_KEY` and sends it as `Authorization: Bearer`. It never goes in a URL and is
  never printed.
- Sends `Accept-Encoding: gzip` and unzips what comes back. Python's `urllib` asks for an uncompressed reply
  unless told otherwise, and the standard, dutching and raw boards refuse that.
- Prices the request first with `quote=true`, which costs nothing. If the request has a price, the script asks
  before spending it; pass `--max-tokens` to set a ceiling and run without the prompt.
- Waits out a `429` for as long as `Retry-After` says, and stops on any other error with the API's error code
  and request id. flumine-bookmaker-prices runs as a long-lived worker instead: it logs the error, clears its
  bookmaker prices and polls again.

The HTTP helper is `api.py`. Each folder keeps an identical copy, so any folder can be lifted out on its own.
The n8n workflows keep the key in an n8n Header Auth credential (`x-api-key`) and price each call with
`quote=true` before they read, stopping above the cap set in their Settings node. The two Google Sheets
workflows also try a failed call three times, then stop with the API's error code and request id.

## Tests

The tests run each example's logic on the response examples published in the API's OpenAPI file (`fixtures/`).
They make no network calls and need no key. The flumine example's tests are skipped unless flumine is installed
(`pip install -r flumine-bookmaker-prices/requirements.txt`).

```sh
for m in */main.py; do (cd "$(dirname "$m")" && python3 -m unittest -v) || break; done
for t in */test.mjs; do node --test "$t" || break; done
```

The second line runs the n8n workflows' Code nodes on the same fixtures (Node.js 18 or later).

## More from OddsRelay

- [oddsrelay-python](https://github.com/oddsrelay/oddsrelay-python): the Python client, `pip install oddsrelay`
- [oddsrelay-js](https://github.com/oddsrelay/oddsrelay-js): the JavaScript and TypeScript client, `npm install oddsrelay`
- [oddsrelay-r](https://github.com/oddsrelay/oddsrelay-r): the R client
- [oddsrelay-mcp](https://github.com/oddsrelay/oddsrelay-mcp): an MCP server that gives Claude, Cursor and other AI assistants read access, with a token cap
- [oddsrelay-sheets](https://github.com/oddsrelay/oddsrelay-sheets): formulas and a template spreadsheet for Google Sheets
- [Libraries and tools](https://oddsrelay.io/docs/libraries), the [docs](https://oddsrelay.io/docs), the [API reference](https://oddsrelay.io/docs/reference) and the [OpenAPI file](https://api.oddsrelay.io/v2/openapi.json)
- Contact: hello@oddsrelay.io

## License

[MIT](LICENSE)
