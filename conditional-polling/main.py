"""Poll a matched board politely: return the last ETag as If-None-Match, and an unchanged board
comes back as an empty 304 Not Modified that costs nothing. It asks for format=bare, because the
envelope's meta times would change the ETag with every new board. Waits at least the reply's
Cache-Control max-age between polls, and api.get waits out any 429 for as long as Retry-After says.

Run: ODDSRELAY_KEY=<your key> python3 main.py --sports tennis
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from typing import Any, Callable

from api import afford, get

FILTERS = ("region", "sports", "bookmakers", "exchanges", "markets")
BOARDS = ["standard", "2up", "dutching", "each-way", "extra-place", "bog"]


def max_age(headers: Any) -> int:
    """The max-age in a reply's Cache-Control header, or 0."""
    found = re.search(r"max-age=(\d+)", headers.get("Cache-Control") or "")
    return int(found.group(1)) if found else 0


def poll(fetch: Callable[[dict], tuple[int, Any, Any]], polls: int, every: float,
         sleep: Callable[[float], None] = time.sleep) -> None:
    """Make `polls` conditional requests through fetch(headers), sleeping between them."""
    etag = None
    for n in range(1, polls + 1):
        status, headers, board = fetch({"If-None-Match": etag} if etag else {})
        cost = headers.get("X-Tokens-Cost")
        if status == 304:
            print(f"poll {n}: 304, unchanged since the last poll (cost {cost})")
        else:
            etag = headers.get("ETag")
            print(f"poll {n}: {status}, events {len(board)}, "
                  f"processed at {headers.get('X-Processed-At')} (cost {cost})")
        if n < polls:
            sleep(max(every, max_age(headers)))


def main() -> None:
    ap = argparse.ArgumentParser(description="Poll a matched board with If-None-Match.")
    ap.add_argument("--board", choices=BOARDS, default="standard")
    for name in FILTERS:
        ap.add_argument(f"--{name}", help="one region code" if name == "region" else "comma-separated keys")
    ap.add_argument("--every", type=float, default=30, help="seconds between polls (your choice)")
    ap.add_argument("--polls", type=int, default=5, help="how many requests to make")
    ap.add_argument("--max-tokens", type=int, help="tokens a changed board may cost without asking")
    args = ap.parse_args()
    path, params = f"/v2/odds/{args.board}", {name: getattr(args, name) for name in FILTERS}
    params["format"] = "bare"  # the event list alone, so the ETag moves only when the events do
    if not afford(get(path, {**params, "quote": "true"})[2], args.max_tokens):
        sys.exit("not fetched: narrow the filters, or pass --max-tokens")
    poll(lambda headers: get(path, params, headers), args.polls, args.every)


if __name__ == "__main__":
    main()
