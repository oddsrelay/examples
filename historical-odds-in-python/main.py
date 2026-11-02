"""One bookmaker's price changes for one event over a window, with the recording gaps.

Run: ODDSRELAY_KEY=<your key> python3 main.py <event id> --bookmaker bet365 --from <time> --to <time>
"""
from __future__ import annotations

import argparse
import sys
from typing import Iterator

from api import afford, get


def pages(path: str, params: dict) -> Iterator[dict]:
    """Every page of the window, following next_cursor until it is null."""
    cursor = None
    while True:
        page = get(path, {**params, "cursor": cursor})[2]
        yield page
        cursor = page["meta"]["next_cursor"]
        if cursor is None:
            return


def report(rows: list[dict], outcome: str | None) -> int:
    """Print a line per row, in order, and return how many rows moved a price the code already held."""
    held: dict[tuple, float | None] = {}
    moves = 0
    for row in rows:
        if outcome and row["outcome"] != outcome:
            continue
        key = (row["outcome"], row.get("index", 0))
        name = f"{row['outcome']} ({key[1] + 1})" if key[1] else str(row["outcome"])
        if row.get("removed"):
            print(f"{row['timestamp']}  {name}  left the board")
            held[key] = None
            continue
        if held.get(key) is not None and row["price"] != held[key]:
            moves += 1
        print(f"{row['timestamp']}  {name}  {row['price']}")
        held[key] = row["price"]
    return moves


def main() -> None:
    ap = argparse.ArgumentParser(description="Print one bookmaker's price changes for one event.")
    ap.add_argument("event_id")
    ap.add_argument("--bookmaker", required=True, help="one bookmaker key, such as bet365")
    ap.add_argument("--from", dest="start", required=True, help="the window's start, ISO 8601")
    ap.add_argument("--to", dest="end", required=True, help="the window's end, at most 24 hours later")
    ap.add_argument("--market", default="h2h", help="one market key")
    ap.add_argument("--outcome", help="one outcome's name; every outcome when left out")
    ap.add_argument("--max-tokens", type=int, help="spend up to this many tokens a page without asking")
    args = ap.parse_args()
    path = f"/v2/historical/events/{args.event_id}/odds"
    params = {"from": args.start, "to": args.end, "bookmakers": args.bookmaker, "markets": args.market}
    if not afford(get(path, {**params, "quote": "true"})[2], args.max_tokens):
        sys.exit("not fetched: pass --max-tokens, or say yes at the prompt")
    rows, gaps = [], []
    for page in pages(path, params):
        rows += page["data"]
        gaps += page["meta"]["gaps"]
    print(f"{report(rows, args.outcome)} moves")
    for gap in gaps:
        print(f"recording gap at {gap['timestamp']}: {gap.get('why') or 'no reason given'}")


if __name__ == "__main__":
    main()
