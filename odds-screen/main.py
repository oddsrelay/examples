"""An odds screen: the best back price for each selection across every venue on the raw board,
and which venues offer it.

Run: ODDSRELAY_KEY=<your key> python3 main.py --sports tennis
"""
from __future__ import annotations

import argparse
import sys

from api import afford, get

FILTERS = ("region", "sports", "bookmakers", "markets", "limit", "cursor")


def best_prices(event: dict) -> dict[tuple[str, str], tuple[float, list[str]]]:
    """{(market, selection): (best back price, venues offering it)} for one raw event."""
    best: dict[tuple[str, str], tuple[float, list[str]]] = {}
    for venue in event["bookmakers"]:
        for market in venue["markets"]:
            for outcome in market["outcomes"]:
                # A bookmaker sends price; an exchange quoting both sides sends back_price.
                price = outcome.get("price") or outcome.get("back_price")
                if not price:
                    continue
                key = (market["key"], outcome["name"])
                top, venues = best.get(key, (0.0, []))
                if price > top:
                    best[key] = (price, [venue["key"]])
                elif price == top:
                    venues.append(venue["key"])
    return best


def main() -> None:
    ap = argparse.ArgumentParser(description="Best back price per selection on the raw board.")
    for name in ("region", "sports", "bookmakers"):
        ap.add_argument(f"--{name}", help="comma-separated keys, as the API lists them")
    ap.add_argument("--markets", default="h2h", help="comma-separated market keys")
    ap.add_argument("--limit", type=int, help="events in the page")
    ap.add_argument("--cursor", help="the cursor printed by the run before")
    ap.add_argument("--max-tokens", type=int, help="spend up to this many tokens without asking")
    args = ap.parse_args()
    params = {name: getattr(args, name) for name in FILTERS}
    if not afford(get("/v2/odds/raw", {**params, "quote": "true"})[2], args.max_tokens):
        sys.exit("not fetched: narrow the filters, or pass --max-tokens")
    page = get("/v2/odds/raw", params)[2]
    for event in page["data"]:
        name = f"{event['home_team']} v {event['away_team']}" if event.get("home_team") else event["id"]
        print(f"\n{event['commence_time']}  {name}  ({event['sport_title']})")
        for (market, selection), (price, venues) in sorted(best_prices(event).items()):
            print(f"  {market:<14} {selection:<30} {price:>7}  {', '.join(venues)}")
    if page["meta"].get("next_cursor"):
        print(f"\nnext page: --cursor {page['meta']['next_cursor']}", file=sys.stderr)


if __name__ == "__main__":
    main()
