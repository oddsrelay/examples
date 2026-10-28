# n8n-oddsmatcher-sheets

An [n8n](https://n8n.io) workflow that keeps a Google Sheet of UK and Irish bookmaker back prices beside exchange
lay prices, one row per bookmaker price, refreshed on a schedule. It uses n8n's own HTTP Request node, so there is
nothing to install.

Each run first asks the API what the matched board call costs (`quote=true`, which is free). Above
`maxTokensPerRun` the run stops there, with the price in the error. Otherwise it reads the board, puts each
bookmaker back price beside the lowest exchange lay for the same outcome, rates the pair (back / lay x 100, and the
same after your exchange commission) and adds or updates the rows in your sheet, matched on `row_key`.

Rows are never deleted. A row whose `checked_at` is older than the latest run has left the board: its event has
started, or one of its prices has gone. Filter on `checked_at`, or clear the sheet below row 1 now and then.

## Use it

1. In n8n, import `oddsmatcher-to-google-sheets.json`.
2. Create a Header Auth credential with Name `x-api-key` and your API key as the Value, and pick it in **Check the
   price** and **Read the matched board**.
3. Type `row_key` in cell A1 of an empty Google Sheet. In **Add or update rows**, connect Google Sheets and choose
   that file and sheet. Column to match on should then read `row_key`; the first run adds the other columns.
4. Adjust **Settings**, run the workflow once and check the sheet, then publish it so the schedule runs.

| Setting | What it does |
|---|---|
| `board` | `standard`, `2up` or `bog`. For `bog`, set `sports` to `horse_racing` and `markets` to `win` |
| `sports` | Sport or competition keys, comma-separated, as `/v2/sports` lists them |
| `markets` | Market keys, comma-separated (`h2h` is the match result) |
| `bookmakers`, `exchanges` | Venue keys, comma-separated, as `/v2/bookmakers` lists them; every venue if left empty |
| `commissionPercent` | Your exchange commission, for the second rating |
| `maxTokensPerRun` | The most one run may spend; a dearer call stops the run before the board is read |

The columns are `row_key`, `checked_at` and `kick_off` (UK time), `competition`, `event`, `market`, `outcome`,
`bookmaker`, `back`, `exchange`, `lay`, `lay_available` (the money available at that lay price), `rating`,
`rating_after_commission`, `back_link` and `lay_link`. Each run spends the call's price, so set the schedule to
suit your plan.

## Test

```sh
node --test test.mjs
```

The test runs the workflow's Code node on the API's own response examples in `../fixtures`. No key, no network.
