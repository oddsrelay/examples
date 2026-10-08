"""An oddsmatcher in about 50 lines: each bookmaker back price on a matched board beside the
lowest exchange lay price, sorted by a rating this script calculates (the feed sends no rating).

Run: ODDSRELAY_KEY=<your key> python3 main.py --sports tennis
"""
from __future__ import annotations

import argparse
import sys
from typing import Iterator

from api import afford, get

FILTERS = ("region", "sports", "bookmakers", "exchanges", "markets")


def rating(back: float, lay: float, commission: float) -> float:
    """100 x back x (1 - commission) / (lay - commission): 100 means the two prices balance exactly."""
    return 100 * back * (1 - commission) / (lay - commission)


def label(event: dict) -> str:
    if event.get("home_team"):
        return f"{event['home_team']} v {event.get('away_team')}"
    return event.get("event_name") or event.get("venue") or event["event_id"]


def pairs(events: list[dict], commission: float) -> Iterator[tuple]:
    """(rating, event, market, outcome, back offer, lay offer) for every priced back offer."""
    for event in events:
        for market in event["markets"]:
            for outcome in market["outcomes"]:
                # Lays come in price order, so lays[0] is the lowest on offer.
                lays = [lay for lay in outcome.get("lay") or [] if lay.get("price")]
                if not lays or lays[0]["price"] <= commission:
                    continue
                lay = lays[0]
                for back in outcome["back"]:
                    if back.get("price"):
                        score = rating(back["price"], lay["price"], commission)
                        yield score, event, market, outcome, back, lay


def main() -> None:
    ap = argparse.ArgumentParser(description="Rate every back and lay pair on a matched board.")
    ap.add_argument("--board", choices=["standard", "2up", "bog"], default="standard")
    for name in FILTERS:
        ap.add_argument(f"--{name}", help="one region code" if name == "region" else "comma-separated keys")
    ap.add_argument("--commission", type=float, default=0.0, help="your exchange commission, as a fraction")
    ap.add_argument("--top", type=int, default=20, help="how many rows to print")
    ap.add_argument("--max-tokens", type=int, help="spend up to this many tokens without asking")
    args = ap.parse_args()
    if not 0 <= args.commission < 1:
        ap.error("--commission is a fraction from 0 to 1, such as 0.02")
    path, params = f"/v2/odds/{args.board}", {name: getattr(args, name) for name in FILTERS}
    if not afford(get(path, {**params, "quote": "true"})[2], args.max_tokens):
        sys.exit("not fetched: narrow the filters, or pass --max-tokens")
    rows = sorted(pairs(get(path, params)[2]["data"], args.commission), key=lambda row: row[0], reverse=True)
    for score, event, market, outcome, back, lay in rows[: args.top]:
        selection = outcome["name"] + (f" {outcome['point']}" if outcome.get("point") is not None else "")
        print(f"{score:6.1f}  {event['commence_time']}  {label(event)}  {market['key']}  {selection}"
              f"  back {back['bookmaker']} {back['price']}  lay {lay['exchange']} {lay['price']}"
              f" ({lay.get('available')} available)")


if __name__ == "__main__":
    main()
