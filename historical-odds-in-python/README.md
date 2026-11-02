# historical-odds-in-python

Prints one bookmaker's price changes for one event over a window, how many moves it made, and any recording gaps
the API lists, so you can tell a flat price from a stretch with nothing recorded.

## Run

```sh
export ODDSRELAY_KEY="your API key"
python3 main.py or_evt_2d7dd94b072d --bookmaker bet365 --from 2026-10-24T11:00:00Z --to 2026-10-24T15:00:00Z
```

| Option | What it does |
|---|---|
| `--bookmaker` | One bookmaker key, such as `bet365` (required) |
| `--from`, `--to` | The window, ISO 8601, at most 24 hours apart (required) |
| `--market` | One market key; `h2h` by default |
| `--outcome` | One outcome's name; every outcome when left out |
| `--max-tokens` | Spend up to this many tokens a page without asking |

The key must include the Historical odds product. `GET /v2/events` and `GET /v2/historical/closing` give you event ids.

## Test

```sh
python3 -m unittest -v
```

The test runs `main()` on the API contract's own example of the route, with `get()` faked and no network.
