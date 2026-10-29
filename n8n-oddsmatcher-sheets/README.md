# n8n-oddsmatcher-sheets

An [n8n](https://n8n.io) workflow that keeps a Google Sheet of UK and Irish bookmaker back prices beside exchange
lay prices, one row per bookmaker price, matched against the sheet on a schedule. It uses n8n's own HTTP Request
node, so there is nothing to install.

Each run first asks the API what the matched board call costs (`quote=true`, which is free). Above
`maxTokensPerRun` the run stops there, with the price in the error. Otherwise it reads the board, then the rows
already in your sheet. Each bookmaker back price is put beside the lowest exchange lay with at least
`minLayAvailable` at that price, and rated: back / lay x 100, and the same after your exchange commission. Pairs
rated at or above `minRating` are added, or updated where the sheet already has their `row_key`. Rows whose
`row_key` is no longer among them are removed: their event has started, a price has gone, or the rating has fallen
below `minRating`. So the sheet shows the board as it stood at the last run, and any column you add yourself (a tick,
a note) stays beside its row for as long as the row is there. Rows the workflow did not write, with no `row_key`, are
left alone.

Each call to the API is tried three times. A call that still fails goes to **Explain the failure**, which stops the
run with the status, the API's error code and request id, and what to do. The sheet is not changed, and the next
scheduled run tries again.

## Use it

1. In n8n, import `oddsmatcher-to-google-sheets.json`.
2. Create a Header Auth credential with Name `x-api-key` and your API key as the Value, and pick it in **Check the
   price** and **Read the matched board**.
3. Type `row_key` in cell A1 of an empty Google Sheet. In **Settings**, set `sheetUrl` to its URL and `sheetName` to
   its tab, then connect Google Sheets in **Read the sheet**, **Remove rows that left the board** and **Add or
   update rows**. The first run adds the other columns.
4. Adjust **Settings**, run the workflow once and check the sheet, then publish it so the schedule runs.

| Setting | What it does |
|---|---|
| `sheetUrl`, `sheetName` | The Google Sheet and the tab the workflow keeps |
| `board` | `standard`, `2up` or `bog`. For `bog`, set `sport` to `horse_racing`, empty `competitions` and set `markets` to `win` |
| `sport` | A sport key as `/v2/sports` lists it (`soccer`); used when `competitions` is empty |
| `competitions` | Competition keys, comma-separated: an event's `competition_key`, as `/v2/sports` lists them |
| `markets` | Market keys, comma-separated (`h2h` is the match result) |
| `bookmakers`, `exchanges` | Venue keys, comma-separated, as `/v2/bookmakers` lists them; every venue if left empty |
| `commissionPercent` | Your exchange commission, for the second rating |
| `minRating` | The lowest rating after commission that is kept |
| `minLayAvailable` | The least money available at the lay price; a lay with less gives way to the next lowest |
| `maxTokensPerRun` | The most one run may spend; a dearer call stops the run before the board is read |

The columns are `row_key`, `checked_at` and `kick_off` (UK time), `competition`, `event`, `market`, `outcome`,
`bookmaker`, `back`, `exchange`, `lay`, `lay_available` (the money available at that lay price), `rating`,
`rating_after_commission`, `back_link` and `lay_link`. Values are written as they are (Cell Format: Let n8n format).

Rows are removed from the bottom of the sheet up, one call to Google per run of neighbouring rows, so a run where many
events have started makes many calls. If Google refuses one (its own limit on writes a minute), the run stops and the
next one picks up from the sheet as it is. Each run spends the call's price, so set the schedule to suit your plan.
The retries and the failure branch were checked on n8n 2.43.7.

## Test

```sh
node --test test.mjs
```

The test runs the workflow's two Code nodes on the API's own response examples in `../fixtures`. No key, no network.
