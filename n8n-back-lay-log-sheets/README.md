# n8n-back-lay-log-sheets

An [n8n](https://n8n.io) workflow that keeps a log, in Google Sheets, of UK and Irish bookmaker back prices that sit
close to exchange lay prices, and of how those prices move. It uses n8n's own HTTP Request node, so there is nothing
to install.

Each run first asks the API what the Standard matched board call costs (`quote=true`, which is free). Above
`maxTokensPerRun` the run stops there, with the price in the error. Otherwise it reads the board, then the rows
already in your sheet. Each bookmaker back price is put beside the lowest exchange lay with at least
`minLayAvailable` at that price, and rated: back / lay x 100, and the same after your exchange commission. A pair
rated at or above `minRating` gets a new row when the sheet has none for it, or when its back or lay price has moved
by `minMovePercent` or more since its last row. `change` says which (`new` or `moved`), and `back_before` and
`lay_before` hold the prices of that last row. A run that finds nothing new writes nothing, so repeat runs add no
duplicates.

Each call to the API is tried three times. A call that still fails goes to **Explain the failure**, which stops the
run with the status, the API's error code and request id, and what to do. The sheet is not changed, and the next
scheduled run tries again.

## Use it

1. In n8n, import `back-lay-log-to-google-sheets.json`.
2. Create a Header Auth credential with Name `x-api-key` and your API key as the Value, and pick it in **Check the
   price** and **Read the matched board**.
3. Make an empty Google Sheet. In **Settings**, set `sheetUrl` to its URL and `sheetName` to its tab, then connect
   Google Sheets in **Read the log** and **Add the new rows**. The first run writes the column names.
4. Run the workflow once and check the sheet, then publish it so the schedule runs.

| Setting | What it does |
|---|---|
| `sheetUrl`, `sheetName` | The Google Sheet and the tab that hold the log |
| `sport` | A sport key as `/v2/sports` lists it (`soccer`); used when `competitions` is empty |
| `competitions` | Competition keys, comma-separated: an event's `competition_key`, as `/v2/sports` lists them |
| `markets` | Market keys, comma-separated (`h2h` is the match result) |
| `bookmakers`, `exchanges` | Venue keys, comma-separated, as `/v2/bookmakers` lists them; every venue if left empty |
| `commissionPercent` | Your exchange commission, for the second rating |
| `minRating` | The lowest rating after commission that is logged |
| `minLayAvailable` | The least money available at the lay price; a lay with less gives way to the next lowest |
| `minMovePercent` | How far a back or lay price must move from the pair's last row to be logged again; 0 logs every change |
| `maxTokensPerRun` | The most one run may spend; a dearer call stops the run before the board is read |

The columns are `checked_at` and `kick_off` (UK time), `competition`, `event`, `market`, `outcome`, `bookmaker`,
`back`, `exchange`, `lay`, `lay_available` (the money available at that lay price), `rating`,
`rating_after_commission`, `change`, `back_before`, `lay_before` and `pair_key` (event, market, outcome and
bookmaker: what a row is matched on). Values are written as they are (Cell Format: Let n8n format), so the times stay
text that sorts in order. A pair's last row is the one with the latest `checked_at`, so the sheet can be sorted or
filtered freely.

Each run reads the whole sheet, and the log only grows: move old rows to another tab now and then. Each run also
spends the call's price, so set the schedule to suit your plan. The retries and the failure branch were checked on
n8n 2.43.7.

## Test

```sh
node --test test.mjs
```

The test runs the workflow's two Code nodes on the API's own response examples in `../fixtures`. No key, no network.
