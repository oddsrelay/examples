"""UK and Irish bookmakers' win prices beside Betfair's own, inside a flumine strategy.

A flumine BackgroundWorker polls the OddsRelay raw board for the next horse races and hands each new board to the
strategy as a CustomEvent, so the strategy reads it on flumine's main thread and needs no locks. For each GB and IE
win market about to start, the strategy keeps every runner's bookmaker prices in market.context["bookmakers"] and
prints the best of them beside Betfair's best back and lay. It places no orders: on_prices is where your own logic
reads them. It runs on every Betfair update to a market the strategy is watching (open, not in play, starting within
--minutes), once the first board and flumine's runner names are in.

Run: ODDSRELAY_KEY=<your key> BETFAIR_USERNAME=<...> BETFAIR_PASSWORD=<...> BETFAIR_APP_KEY=<...> python3 main.py
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import sys
from datetime import datetime, timezone

import betfairlightweight
from betfairlightweight.filters import streaming_market_data_filter, streaming_market_filter
from flumine import BaseStrategy, Flumine, clients
from flumine.events.events import CustomEvent
from flumine.streams.betfairmarketstream import BetfairMarketStream
from flumine.utils import get_price
from flumine.worker import BackgroundWorker

from api import afford, get

try:
    from zoneinfo import ZoneInfo
    UK = ZoneInfo("Europe/London")
except KeyError:  # no time zone data on this machine (Windows without the tzdata package): show UTC
    UK = timezone.utc
PATH = "/v2/odds/raw"  # every venue's price for every runner, races in start-time order
WINDOW = 600  # seconds: a race on the board is a Betfair market's race only if it starts this close to it
logger = logging.getLogger(__name__)


def key(name: str) -> str:
    """A runner's name as both sides can match it: no country suffix such as (IRE), no case, no punctuation."""
    return re.sub(r"[^a-z0-9]", "", re.sub(r"\s*\([A-Z]{2,3}\)\s*$", "", name).lower())


def bookmaker_prices(board: list[dict], start: datetime, exchanges: set[str]) -> dict[str, dict[str, float]]:
    """{runner key: {bookmaker: price}} from the races on the board that start within WINDOW of start. Matching
    on start time and runner names needs no course names, and a race the board lists twice merges into one."""
    prices = {}
    for event in board:
        when = event.get("commence_time")
        if not when or abs((datetime.fromisoformat(when.replace("Z", "+00:00")) - start).total_seconds()) > WINDOW:
            continue
        for venue in (v for v in event["bookmakers"] if v["key"] not in exchanges):  # Betfair's side comes from flumine
            for outcome in (o for market in venue["markets"] for o in market["outcomes"] if o.get("price")):
                prices.setdefault(key(outcome["name"]), {})[venue["key"]] = outcome["price"]
    return prices


def table(market, market_book, names: dict[int, str]) -> str:
    """A heading, then a line per runner: Betfair's best back and lay, the best bookmaker price and who offers it."""
    start = market.market_start_datetime.astimezone(UK)
    lines = [f"{market.venue or ''} {start:%H:%M %Z}  {market.market_id}".strip()]
    for runner in (r for r in market_book.runners if r.status == "ACTIVE"):
        books = market.context["bookmakers"].get(runner.selection_id) or {}
        best = max(books.values(), default=None)
        at_best = [book for book, price in books.items() if price == best]
        more = f" +{len(at_best) - 2}" if len(at_best) > 2 else ""
        bookmakers = f"{best} ({', '.join(at_best[:2])}{more})" if books else "-"
        name = names.get(runner.selection_id, str(runner.selection_id))[:18]
        back, lay = get_price(runner.ex.available_to_back, 0), get_price(runner.ex.available_to_lay, 0)
        lines.append(f"{name:<18}  back {back or '-':>5}  lay {lay or '-':>5} | bookmakers {bookmakers}")
    return "\n".join(lines)


class BookmakerPrices(BaseStrategy):
    """Each runner's bookmaker prices beside its Betfair prices, for win markets about to start. Places no orders."""

    def __init__(self, *args, minutes: float = 10, exchanges: set[str] = frozenset(), **kwargs):
        super().__init__(*args, **kwargs)
        self.minutes, self.exchanges, self.board, self.version = minutes, exchanges, None, 0

    def new_board(self, flumine, event: CustomEvent) -> None:
        """The CustomEvent's callback, on flumine's main thread: the newest board, or None after a failed poll."""
        self.board, self.version = event.event, self.version + 1

    def check_market_book(self, market, market_book) -> bool:
        # The board is pre-match, so a market that has turned in play is left alone.
        return market_book.status == "OPEN" and not market_book.inplay and market.seconds_to_start < self.minutes * 60

    def process_market_book(self, market, market_book) -> None:
        if market.market_catalogue and market.context.get("oddsrelay_version", 0) != self.version:
            # A board this market has not seen (None after a failed poll): match it to the runners, show it once.
            market.context["oddsrelay_version"] = self.version
            prices = bookmaker_prices(self.board or [], market.market_start_datetime, self.exchanges)
            names = {runner.selection_id: runner.runner_name for runner in market.market_catalogue.runners}
            market.context["bookmakers"] = {sid: prices.get(key(name), {}) for sid, name in names.items()}
            print(table(market, market_book, names), flush=True)
        if "bookmakers" in market.context:  # not before the first board, or before flumine has the runner names
            self.on_prices(market, market_book)

    def on_prices(self, market, market_book) -> None:
        """Your own logic goes here, with the latest board's prices in market.context["bookmakers"]
        ({selection_id: {bookmaker: price}}) beside Betfair's in market_book. It runs on every Betfair update to a
        market the strategy is watching (open, not in play, starting within --minutes), once the first board and
        flumine's runner names are in."""


def poll(context: dict, flumine, strategy: BookmakerPrices, params: dict, max_tokens: int | None = None) -> None:
    """The worker's function, on the worker's own thread: fetch the board only when it has changed (an unchanged
    board is a 304 that costs nothing) and queue it for the strategy, never touching the strategy from here."""
    if context.get("stopped"):
        return
    try:
        status, headers, board = get(PATH, params, {"If-None-Match": context["etag"]} if context.get("etag") else None)
        cost = int(headers.get("X-Tokens-Cost") or 0)  # a changed board's price moves with the prices its races hold
    except (SystemExit, Exception) as err:  # api.get exits on an API error; a cut connection or a bad body raises
        logger.error("bookmaker prices not updated: %s", str(err) or type(err).__name__)
        if not context.pop("etag", None):  # no board held, or already cleared after an earlier error
            return
        status, headers, board, cost = 0, {}, None, 0  # clear the strategy's prices rather than leave stale ones
    if max_tokens is not None and cost > max_tokens:
        logger.error("a changed board cost %s tokens, over the %s allowed: polling stopped (see --max-tokens)",
                     cost, max_tokens)
        context["stopped"], board = True, None  # paid for, but no more polls follow: clear rather than go stale
    if status != 304:
        context["etag"] = headers.get("ETag")  # None after an error, so the next poll fetches the whole board
        flumine.handler_queue.put(CustomEvent(board, strategy.new_board))


def main() -> None:
    ap = argparse.ArgumentParser(description="UK and Irish bookmakers' win prices beside Betfair's, in flumine.")
    ap.add_argument("--minutes", type=float, default=10, help="show win markets starting within this many minutes")
    ap.add_argument("--races", type=int, default=30, help="how many of the next races each poll fetches (1 to 250)")
    ap.add_argument("--bookmakers", help="comma-separated bookmaker keys (all of them if left out)")
    ap.add_argument("--every", type=float, default=30, help="seconds between polls of the board (your choice)")
    ap.add_argument("--max-tokens", type=int, help="stop polling if a changed board costs more than this")
    args = ap.parse_args()
    missing = [name for name in ("BETFAIR_USERNAME", "BETFAIR_PASSWORD", "BETFAIR_APP_KEY") if not os.environ.get(name)]
    if missing:
        sys.exit(f"set {', '.join(missing)}")
    if args.max_tokens is None and not sys.stdin.isatty():  # nobody to ask, and nothing would cap the polls
        sys.exit("pass --max-tokens: this run has no terminal to ask at")
    # The board is in start-time order and a page is priced on the races it holds, so `limit` keeps a poll small.
    params = {"sports": "horse_racing", "markets": "outright_winner", "bookmakers": args.bookmakers,
              "limit": args.races, "format": "bare"}  # bare: the ETag follows the races alone
    if not afford(get(PATH, {**params, "quote": "true"})[2], args.max_tokens):
        sys.exit("not fetched: the quote is over --max-tokens" if args.max_tokens is not None
                 else "not fetched: pass --max-tokens to allow this price")
    exchanges = {venue["key"] for venue in get("/v2/bookmakers", {"format": "bare"})[2] if venue["is_exchange"]}
    logging.basicConfig(level=logging.WARNING)
    certs = os.environ.get("BETFAIR_CERTS")  # the folder holding your API certificate; without it, interactive login
    trading = betfairlightweight.APIClient(os.environ["BETFAIR_USERNAME"], os.environ["BETFAIR_PASSWORD"],
                                           app_key=os.environ["BETFAIR_APP_KEY"], certs=certs)
    # Paper trading: an order you add to the strategy is simulated until you change this.
    framework = Flumine(client=clients.BetfairClient(trading, interactive_login=not certs, paper_trade=True))
    strategy = BookmakerPrices(minutes=args.minutes, exchanges=exchanges, stream=BetfairMarketStream(
        market_filter=streaming_market_filter(event_type_ids=["7"], country_codes=["GB", "IE"], market_types=["WIN"]),
        market_data_filter=streaming_market_data_filter(fields=["EX_BEST_OFFERS", "EX_MARKET_DEF"], ladder_levels=1)))
    framework.add_strategy(strategy)
    framework.add_worker(BackgroundWorker(framework, poll, interval=args.every,
                                          func_kwargs={"strategy": strategy, "params": params,
                                                       "max_tokens": args.max_tokens}))
    framework.run()


if __name__ == "__main__":
    main()
