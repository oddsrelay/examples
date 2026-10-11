"""Post a price table for the next races on a racing board to a Discord channel or a Telegram chat.

For each race: every runner's best back price, the bookmakers offering it (with their each-way terms on
the each-way and extra-place boards) and the lowest exchange lay for the win. Prices only, no advice.
The last post's ETag goes back as If-None-Match, so an unchanged board is a free 304 and nothing is sent.

Run: ODDSRELAY_KEY=<your key> python3 main.py --dry-run
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from fractions import Fraction
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from api import afford, get

try:
    from zoneinfo import ZoneInfo
    UK = ZoneInfo("Europe/London")
except KeyError:  # no time zone data on this machine (Windows without the tzdata package): show UTC
    UK = timezone.utc
MAX_CHARS = 1990  # Discord's limit is 2000 characters with the code fence, Telegram's 4096: one cut fits both


def terms(offer: dict) -> str:
    """An offer's each-way terms, such as '3pl 1/5', or '' on a board without them."""
    if not offer.get("places") or not offer.get("place_fraction"):
        return ""
    return f"{offer['places']}pl {Fraction(offer['place_fraction']).limit_denominator(10)}"


def race(event: dict, runners: int) -> str:
    """One race: a heading, then a line per runner with a priced back offer, shortest price first."""
    start = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00")).astimezone(UK)
    field: dict[str, dict] = {}
    for outcome in (o for market in event["markets"] for o in market["outcomes"]):
        # One line per runner: names that differ only in case or punctuation are folded together.
        runner = field.setdefault(re.sub(r"[^a-z0-9]", "", outcome["name"].lower()),
                                  {"name": outcome["name"], "back": [], "lay": []})
        if runner["name"].isupper():
            runner["name"] = outcome["name"]
        lay = outcome.get("lay") or []
        runner["back"] += [b for b in outcome["back"] if b.get("price")]
        runner["lay"] += [o for o in (lay.get("win") or [] if isinstance(lay, dict) else lay) if o.get("price")]
    rows = []
    for runner in (r for r in field.values() if r["back"]):
        best = max(b["price"] for b in runner["back"])
        books = list(dict.fromkeys(f"{b['bookmaker']} {terms(b)}".rstrip()
                                   for b in runner["back"] if b["price"] == best))
        lay = min(runner["lay"], key=lambda o: o["price"], default=None)
        rows.append((best, f"{runner['name'][:18]:<18} {best:>6}  {', '.join(books[:2])}"
                     + (f" +{len(books) - 2}" if len(books) > 2 else "")
                     + (f"  lay {lay['price']} ({lay.get('available') or 0:.0f})" if lay else "")))
    return "\n".join([f"{event.get('venue') or event['event_id']} {start:%H:%M %Z}"]
                     + [line for _, line in sorted(rows)[:runners]])


def message(events: list[dict], runners: int) -> str:
    """Every race in start order, cut before the first one that would pass MAX_CHARS."""
    timed = sorted((e for e in events if e.get("commence_time")), key=lambda e: e["commence_time"])
    blocks = [race(e, runners) for e in timed]
    text = ""
    for n, block in enumerate(blocks):
        more = f"(+{len(blocks) - n} more races: narrow --hours or --bookmakers)"
        if len(text) + len(block) + len(more) > MAX_CHARS:
            return text + more
        text += block + "\n\n"
    return text.rstrip()


def send(text: str) -> None:
    """Post to Discord (DISCORD_WEBHOOK_URL) or Telegram (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)."""
    hook, bot, chat = (os.environ.get(name, "").strip()
                       for name in ("DISCORD_WEBHOOK_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"))
    if hook:  # Discord asks for a User-Agent in this form; parse [] stops any @mention pinging the channel
        url, headers = hook, {"User-Agent": "DiscordBot (https://github.com/oddsrelay/examples, 1)"}
        body = {"content": f"```\n{text}\n```", "allowed_mentions": {"parse": []}}
    elif bot and chat:
        url, headers = f"https://api.telegram.org/bot{bot}/sendMessage", {}
        body = {"chat_id": chat, "parse_mode": "HTML", "text": f"<pre>{html.escape(text, quote=False)}</pre>"}
    else:
        sys.exit("set DISCORD_WEBHOOK_URL, or TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID, or pass --dry-run")
    req = Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers})
    try:  # error messages never name the URL: it carries the webhook's or the bot's token
        urlopen(req, timeout=30).close()
    except HTTPError as err:
        sys.exit(f"the post was refused: HTTP {err.code} {err.read()[:200].decode(errors='replace')}")
    except URLError as err:
        sys.exit(f"could not post: {err.reason}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Post the next races' prices to Discord or Telegram.")
    ap.add_argument("--board", choices=["each-way", "extra-place", "bog"], default="each-way")
    ap.add_argument("--hours", type=float, default=1, help="races starting within this many hours")
    ap.add_argument("--bookmakers", help="comma-separated bookmaker keys (all of them if left out)")
    ap.add_argument("--runners", type=int, default=10, help="most runners shown per race")
    ap.add_argument("--max-tokens", type=int, help="spend up to this many tokens without asking")
    ap.add_argument("--state", default=".racing-board-etag", help="file that keeps the last post's ETag")
    ap.add_argument("--dry-run", action="store_true", help="print the table instead of posting it")
    args = ap.parse_args()
    now = datetime.now(timezone.utc).replace(microsecond=0)
    path, params = f"/v2/odds/{args.board}", {
        "sports": "horse_racing", "bookmakers": args.bookmakers, "format": "bare",  # bare: the ETag follows the events
        "commenceTimeFrom": now.isoformat(), "commenceTimeTo": (now + timedelta(hours=args.hours)).isoformat()}
    if not afford(get(path, {**params, "quote": "true"})[2], args.max_tokens):
        sys.exit("not fetched: pass --max-tokens to allow this price")
    state = Path(args.state)
    etag = state.read_text().strip() if state.exists() and not args.dry_run else ""  # a dry run always prints
    status, headers, events = get(path, params, {"If-None-Match": etag} if etag else None)
    if status == 304 or not events:
        print("nothing sent: " + ("unchanged since the last post" if status == 304 else "no races in the window"))
        return
    text = message(events, args.runners)
    if args.dry_run:
        print(text)
        return
    send(text)
    state.write_text(headers.get("ETag") or "")


if __name__ == "__main__":
    main()
