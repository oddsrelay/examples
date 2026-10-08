"""A matched board to CSV: one row per offer, back and lay, ready for a spreadsheet or pandas.

Run: ODDSRELAY_KEY=<your key> python3 main.py --board each-way --out each-way.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from typing import IO, Iterator

from api import afford, get

FILTERS = ("region", "sports", "bookmakers", "exchanges", "markets")
BOARDS = ["standard", "2up", "dutching", "each-way", "extra-place", "bog"]
OFFER = ["price", "available", "places", "place_fraction", "dutch_id", "link"]
FIELDS = ["event_id", "commence_time", "sport_key", "event", "market", "selection", "point", "side", "venue",
          *OFFER]


def rows(events: list[dict]) -> Iterator[dict]:
    """One dict per offer. side is back, lay, or (each-way, extra-place) lay_win and lay_place."""
    for event in events:
        name = (f"{event['home_team']} v {event.get('away_team')}" if event.get("home_team")
                else event.get("event_name") or event.get("venue"))
        for market in event["markets"]:
            for outcome in market["outcomes"]:
                lay = outcome.get("lay") or []  # a list, a {win, place} object, or absent on dutching
                lays = {f"lay_{k}": v for k, v in lay.items()} if isinstance(lay, dict) else {"lay": lay}
                sides = {"back": outcome["back"], **lays}
                for side, offers in sides.items():
                    for offer in offers:
                        yield {"event_id": event["event_id"], "commence_time": event["commence_time"],
                               "sport_key": event["sport_key"], "event": name, "market": market["key"],
                               "selection": outcome["name"], "point": outcome.get("point"), "side": side,
                               "venue": offer.get("bookmaker") or offer.get("exchange"),
                               **{field: offer.get(field) for field in OFFER}}


def write_csv(events: list[dict], out: IO[str]) -> int:
    """Write the board's offers to out as CSV; returns the number of rows."""
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    writer.writeheader()
    count = 0
    for count, row in enumerate(rows(events), 1):
        writer.writerow(row)
    return count


def main() -> None:
    ap = argparse.ArgumentParser(description="Write a matched board to CSV, one row per offer.")
    ap.add_argument("--board", choices=BOARDS, default="standard")
    for name in FILTERS:
        ap.add_argument(f"--{name}", help="comma-separated keys, as the API lists them")
    ap.add_argument("--out", default="board.csv", help="the CSV file to write")
    ap.add_argument("--max-tokens", type=int, help="spend up to this many tokens without asking")
    args = ap.parse_args()
    path, params = f"/v2/odds/{args.board}", {name: getattr(args, name) for name in FILTERS}
    if not afford(get(path, {**params, "quote": "true"})[2], args.max_tokens):
        sys.exit("not fetched: narrow the filters, or pass --max-tokens")
    board = get(path, params)[2]
    with open(args.out, "w", newline="", encoding="utf-8") as out:
        print(f"{write_csv(board['data'], out)} rows written to {args.out}")


if __name__ == "__main__":
    main()
