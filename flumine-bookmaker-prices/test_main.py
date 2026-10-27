import importlib.util
import io
import json
import os
import queue
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

if importlib.util.find_spec("flumine") is None:  # flumine needs Python 3.10 or later: pip install -r requirements.txt
    raise unittest.SkipTest("flumine is not installed")

from betfairlightweight.resources import MarketBook, MarketCatalogue
from betfairlightweight.resources.streamingresources import MarketDefinition
from flumine import Flumine
from flumine.markets.market import Market
from flumine.worker import BackgroundWorker

import main

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
EXCHANGES = {"betfair_exchange", "smarkets", "matchbook"}  # what /v2/bookmakers marks is_exchange
START = datetime(2026, 10, 27, 18, 0, tzinfo=timezone.utc)
# One race in the raw board's shape (trimmed): the same race listed twice, a name in capitals with a country suffix,
# a missing price, and an exchange, which quotes back and lay instead of a price.
BOARD = [
    {"id": "or_evt_a", "sport_key": "horse_racing", "commence_time": "2026-10-27T18:00:00Z", "bookmakers": [
        {"key": "bet365", "markets": [{"key": "outright_winner", "outcomes": [
            {"name": "Alpha Star", "price": 4.0}, {"name": "Bravo Lad", "price": 6.5}]}]},
        {"key": "betfair_exchange", "markets": [{"key": "outright_winner", "outcomes": [
            {"name": "Alpha Star", "back_price": 4.8, "lay_price": 4.9, "available": 187.32}]}]}]},
    {"id": "or_evt_b", "sport_key": "horse_racing", "commence_time": "2026-10-27T18:01:00Z", "bookmakers": [
        {"key": "william_hill", "markets": [{"key": "outright_winner", "outcomes": [
            {"name": "ALPHA STAR (IRE)", "price": 4.33}, {"name": "Bravo Lad", "price": None}]}]}]},
]


def betfair_market(framework, names=("Alpha Star", "Bravo Lad", "Charlie Boy")) -> Market:
    """A flumine Market built from betfairlightweight's own resources. Its prices are made up."""
    when = START.strftime("%Y-%m-%dT%H:%M:%S.000Z")  # Betfair's time format
    catalogue = MarketCatalogue(
        marketId="1.262474543", marketName="Win", marketStartTime=when,
        event={"id": "1", "name": "Kempton", "venue": "Kempton", "openDate": when, "timezone": "Europe/London"},
        runners=[{"selectionId": 101 + n, "runnerName": name, "handicap": 0, "sortPriority": n + 1}
                 for n, name in enumerate(names)])
    definition = MarketDefinition(
        betDelay=0, bettingType="ODDS", bspMarket=True, bspReconciled=False, complete=True, crossMatching=True,
        discountAllowed=True, eventId="1", eventTypeId="7", inPlay=False, marketBaseRate=5.0, marketTime=when,
        numberOfActiveRunners=len(names), numberOfWinners=1, persistenceEnabled=True, regulators="MR_INT",
        runnersVoidable=False, status="OPEN", timezone="Europe/London", turnInPlayEnabled=True, version=1, runners=[],
        venue="Kempton", countryCode="GB", marketType="WIN")
    ladder = {"availableToBack": [{"price": 4.2, "size": 30.0}], "availableToLay": [{"price": 4.3, "size": 12.0}]}
    book = MarketBook(marketId="1.262474543", status="OPEN", inplay=False, market_definition=definition, runners=[
        {"selectionId": 101 + n, "status": "ACTIVE", "handicap": 0,
         "ex": ladder if n == 0 else {"availableToBack": [], "availableToLay": []}} for n in range(len(names))])
    return Market(framework, "1.262474543", book, catalogue)


class MatchTest(unittest.TestCase):
    def test_key_ignores_case_punctuation_and_a_country_suffix(self):
        self.assertEqual(main.key("ALPHA STAR (IRE)"), main.key("Alpha Star"))
        self.assertEqual(main.key("Einstein's Ghost"), main.key("Einsteins Ghost"))

    def test_prices_of_the_race_beside_the_market(self):
        prices = main.bookmaker_prices(BOARD, START, EXCHANGES)
        self.assertEqual(prices, {"alphastar": {"bet365": 4.0, "william_hill": 4.33}, "bravolad": {"bet365": 6.5}})

    def test_no_prices_from_a_race_at_another_time(self):
        self.assertEqual(main.bookmaker_prices(BOARD, START + timedelta(minutes=12), EXCHANGES), {})

    def test_the_contract_example_and_an_exchange_that_quotes_a_plain_price(self):
        event = json.loads((FIXTURES / "v2-odds-raw.page.json").read_text())["data"][0]
        start = datetime.fromisoformat(event["commence_time"].replace("Z", "+00:00"))
        venue = event["bookmakers"][0]
        outcome = venue["markets"][0]["outcomes"][0]
        prices = main.bookmaker_prices([event], start, EXCHANGES)
        self.assertEqual(prices[main.key(outcome["name"])][venue["key"]], outcome["price"])
        linked = json.loads((FIXTURES / "v2-odds-raw.exchange_with_link.json").read_text())["data"]
        start = datetime.fromisoformat(linked[0]["commence_time"].replace("Z", "+00:00"))
        self.assertEqual(main.bookmaker_prices(linked, start, EXCHANGES), {})  # only Betfair quotes it

    def test_market_books_it_looks_at(self):
        strategy = main.BookmakerPrices(minutes=10)
        soon, later = SimpleNamespace(seconds_to_start=300), SimpleNamespace(seconds_to_start=3600)
        self.assertTrue(strategy.check_market_book(soon, SimpleNamespace(status="OPEN", inplay=False)))
        self.assertFalse(strategy.check_market_book(soon, SimpleNamespace(status="OPEN", inplay=True)))
        self.assertFalse(strategy.check_market_book(soon, SimpleNamespace(status="SUSPENDED", inplay=False)))
        self.assertFalse(strategy.check_market_book(later, SimpleNamespace(status="OPEN", inplay=False)))


class PollTest(unittest.TestCase):
    def setUp(self):
        self.flumine = SimpleNamespace(handler_queue=queue.Queue())
        self.strategy, self.context = main.BookmakerPrices(), {}

    def poll(self, *replies, **kwargs):
        with mock.patch("main.get", side_effect=replies) as get:
            main.poll(self.context, self.flumine, self.strategy, {"sports": "horse_racing"}, **kwargs)
        return get.call_args[0]

    def test_a_new_board_is_queued_and_its_etag_sent_back(self):
        self.poll((200, {"ETag": '"v1"'}, BOARD))
        event = self.flumine.handler_queue.get_nowait()
        self.assertIs(event.event, BOARD)
        self.assertEqual(event.callback, self.strategy.new_board)
        self.assertEqual(self.poll((304, {}, None))[2], {"If-None-Match": '"v1"'})
        self.assertTrue(self.flumine.handler_queue.empty())  # unchanged: nothing to hand over

    def test_an_error_clears_the_prices_once_then_the_whole_board_is_fetched(self):
        self.poll((200, {"ETag": '"v1"'}, BOARD))
        self.flumine.handler_queue.get_nowait()
        for _ in range(2):
            with self.assertLogs("main", "ERROR"):
                self.poll(SystemExit("HTTP 402 insufficient_tokens"))
        self.assertIsNone(self.flumine.handler_queue.get_nowait().event)
        self.assertTrue(self.flumine.handler_queue.empty())  # cleared once, not on every failed poll
        self.assertIsNone(self.poll((200, {"ETag": '"v2"'}, BOARD))[2])  # no If-None-Match after an error

    def test_any_error_clears_the_prices(self):
        for error in (TimeoutError("The read operation timed out"), json.JSONDecodeError("Expecting value", "", 0)):
            with self.subTest(error=type(error).__name__):
                self.poll((200, {"ETag": '"v1"'}, BOARD))
                self.flumine.handler_queue.get_nowait()
                with self.assertLogs("main", "ERROR"):
                    self.poll(error)
                self.assertIsNone(self.flumine.handler_queue.get_nowait().event)

    def test_a_board_over_the_limit_stops_polling(self):
        self.poll((200, {"ETag": '"v1"', "X-Tokens-Cost": "3"}, BOARD), max_tokens=3)
        self.assertIs(self.flumine.handler_queue.get_nowait().event, BOARD)  # within the limit
        with self.assertLogs("main", "ERROR"):
            self.poll((200, {"ETag": '"v2"', "X-Tokens-Cost": "4"}, BOARD), max_tokens=3)
        self.assertIsNone(self.flumine.handler_queue.get_nowait().event)  # over it: the prices are cleared
        with mock.patch("main.get") as get:
            main.poll(self.context, self.flumine, self.strategy, {}, max_tokens=3)
        get.assert_not_called()  # and nothing more is fetched

    def test_without_a_limit_polling_never_stops(self):
        for n, cost in enumerate(("1", "500", "100000")):  # no --max-tokens: a changed board of any cost
            self.poll((200, {"ETag": f'"v{n}"', "X-Tokens-Cost": cost}, BOARD), max_tokens=None)  # is fetched
            self.assertIs(self.flumine.handler_queue.get_nowait().event, BOARD)  # and handed over
        self.assertNotIn("stopped", self.context)


class DryRunTest(unittest.TestCase):
    """The whole path with a stubbed reply: flumine's own BackgroundWorker runs poll, flumine hands the board to the
    strategy as its main loop would, and a market built from betfairlightweight's resources is processed."""

    def setUp(self):
        self.framework, self.strategy = Flumine(), main.BookmakerPrices(minutes=10, exchanges=EXCHANGES)
        self.market = betfair_market(self.framework)
        self.worker = BackgroundWorker(self.framework, main.poll, interval=None,  # None: one call per run()
                                       func_kwargs={"strategy": self.strategy, "params": {}})

    def deliver(self, reply):
        with mock.patch("main.get", side_effect=[reply]):  # a reply, or an exception to raise
            self.worker.run()  # on this thread, keeping the worker's context (its ETag) between calls
        self.framework._process_custom_event(self.framework.handler_queue.get_nowait())

    def process(self):
        with redirect_stdout(io.StringIO()) as out:
            if self.strategy.check_market_book(self.market, self.market.market_book):
                self.strategy.process_market_book(self.market, self.market.market_book)
        return out.getvalue()

    def test_nothing_before_the_first_board(self):
        self.assertEqual(self.process(), "")

    def test_the_board_beside_betfair(self):
        self.deliver((200, {"ETag": '"v1"'}, BOARD))
        self.assertEqual(self.process().splitlines(), [
            f"Kempton {START.astimezone(main.UK):%H:%M %Z}  1.262474543",
            "Alpha Star          back   4.2  lay   4.3 | bookmakers 4.33 (william_hill)",
            "Bravo Lad           back     -  lay     - | bookmakers 6.5 (bet365)",
            "Charlie Boy         back     -  lay     - | bookmakers -"])
        self.assertEqual(self.market.context["bookmakers"],
                         {101: {"bet365": 4.0, "william_hill": 4.33}, 102: {"bet365": 6.5}, 103: {}})
        self.assertEqual(self.process(), "")  # the same board is shown once

    def test_your_logic_runs_on_every_betfair_update(self):
        with mock.patch.object(self.strategy, "on_prices") as on_prices:
            self.process()
            self.assertEqual(on_prices.call_count, 0)  # no board yet
            self.deliver((200, {"ETag": '"v1"'}, BOARD))
            for _ in range(3):
                self.process()
        self.assertEqual(on_prices.call_count, 3)  # once a board is in, every update, not once per board

    def test_a_failed_poll_clears_the_market(self):
        for error in (SystemExit("could not reach the API"), TimeoutError("The read operation timed out")):
            with self.subTest(error=type(error).__name__):
                self.deliver((200, {"ETag": '"v1"'}, BOARD))
                self.process()
                with self.assertLogs("main", "ERROR"):
                    self.deliver(error)
                self.assertEqual(self.process().count("bookmakers -"), 3)
                self.assertEqual(self.market.context["bookmakers"], {101: {}, 102: {}, 103: {}})


class MainTest(unittest.TestCase):
    def test_a_run_with_no_terminal_needs_max_tokens(self):
        env = {"BETFAIR_USERNAME": "u", "BETFAIR_PASSWORD": "p", "BETFAIR_APP_KEY": "k"}
        with mock.patch.dict(os.environ, env), mock.patch("sys.argv", ["main.py"]), \
                mock.patch("sys.stdin") as stdin, mock.patch("main.get") as get:
            stdin.isatty.return_value = False
            with self.assertRaises(SystemExit):
                main.main()
        get.assert_not_called()  # stopped before even the free quote

    def test_a_quote_over_max_tokens_is_not_fetched(self):
        env = {"BETFAIR_USERNAME": "u", "BETFAIR_PASSWORD": "p", "BETFAIR_APP_KEY": "k"}
        with mock.patch.dict(os.environ, env), mock.patch("sys.argv", ["main.py", "--max-tokens", "3"]), \
                mock.patch("main.get", return_value=(200, {}, {"cost": 4, "remaining": 10})) as get, \
                redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as stop:
            main.main()
        self.assertEqual(str(stop.exception), "not fetched: the quote is over --max-tokens")
        get.assert_called_once()  # the free quote, and nothing after it


if __name__ == "__main__":
    unittest.main()
