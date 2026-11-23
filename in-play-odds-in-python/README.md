# in-play-odds-in-python

Follows one football event from before kick-off into play: each read prints the time, whether the event is in play
(`in_play`), and every venue's price on the match result (`h2h`) market. The event keeps its id at kick-off, so the
same loop keeps reading it.

## Run

```sh
export ODDSRELAY_KEY="your API key"
python3 main.py
python3 main.py --event or_evt_0123456789ab --every 60 --polls 30 --max-tokens 50
```

| Option | What it does |
|---|---|
| `--event` | One event id; left out, the first football event on the raw board |
| `--region` | One region code; `uk` when left out |
| `--every` | Seconds between reads; 60 by default |
| `--polls` | How many reads before it stops; 30 by default |
| `--max-tokens` | Spend up to this many tokens a call without asking |

## Test

```sh
python3 -m unittest -v
```

The test runs `main()` on the contract's raw example with `get()` faked and no network.
