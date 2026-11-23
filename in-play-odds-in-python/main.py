"""Follow one football event from before kick-off into play: each read prints the time, whether
the event is in play, and every venue's back price on the match result (h2h) market.

Run: ODDSRELAY_KEY=<your key> python3 main.py
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone

from api import afford, get

MARKET = "h2h"


def first_event(region: str, max_tokens: int | None) -> str:
    """The id of the first football event on the raw board, in play or not."""
    params = {"region": region, "sports": "soccer", "markets": MARKET, "inPlay": "include", "limit": 1}
    if not afford(get("/v2/odds/raw", {**params, "quote": "true"})[2], max_tokens):
        sys.exit("not fetched: pass --max-tokens, or --event with an id you already have")
    events = get("/v2/odds/raw", params)[2]["data"]
    if not events:
        sys.exit("no football event on the board right now")
    return events[0]["id"]


def prices(event: dict) -> str:
    """'venue: outcome price, outcome price' for every venue quoting the market."""
    parts = []
    for venue in event["bookmakers"]:
        for market in venue["markets"]:
            if market["key"] == MARKET:
                quotes = [f"{o['name']} {o.get('price') or o.get('back_price')}" for o in market["outcomes"]]
                parts.append(f"{venue['key']}: " + ", ".join(quotes))
    return " | ".join(parts) or "no venue quotes this market now"


def main() -> None:
    ap = argparse.ArgumentParser(description="Follow one football event into play.")
    ap.add_argument("--event", help="an event id; left out, the first football event on the raw board")
    ap.add_argument("--region", default="uk", help="one region code")
    ap.add_argument("--every", type=int, default=60, help="seconds between reads")
    ap.add_argument("--polls", type=int, default=30, help="how many reads before it stops")
    ap.add_argument("--max-tokens", type=int, help="spend up to this many tokens a call without asking")
    args = ap.parse_args()
    event_id = args.event or first_event(args.region, args.max_tokens)
    path, params = f"/v2/odds/event/{event_id}", {"region": args.region, "inPlay": "include"}
    if not afford(get(path, {**params, "quote": "true"})[2], args.max_tokens):
        sys.exit("not fetched: pass --max-tokens to set a ceiling for each read")
    was_in_play = None
    for n in range(args.polls):
        event = get(path, params)[2]
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        in_play = event.get("in_play", False)
        if in_play and was_in_play is False:
            print(f"{now}  gone in play: {event['home_team']} v {event['away_team']}, still {event['id']}")
        was_in_play = in_play
        print(f"{now}  in_play={in_play}  {prices(event)}")
        if n < args.polls - 1:
            time.sleep(args.every)


if __name__ == "__main__":
    main()
