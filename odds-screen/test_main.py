import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import main

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


def run(sent: list, quote: dict, board, *argv: str) -> None:
    """main() with get() faked: the quote call answers `quote`, the data call `board`."""
    def fake_get(path, params, headers=None):
        sent.append(params.get("quote"))
        return 200, {}, quote if params.get("quote") else board
    with mock.patch.object(main, "get", fake_get), mock.patch("sys.argv", ["main.py", *argv]), \
            mock.patch("sys.stdin", io.StringIO()), redirect_stdout(io.StringIO()), \
            redirect_stderr(io.StringIO()):
        main.main()


class OddsScreenTest(unittest.TestCase):
    def setUp(self):
        self.event = load("v2-odds-raw.page.json")["data"][0]

    def test_a_tie_lists_every_venue(self):
        best = main.best_prices(self.event)
        self.assertEqual(best[("h2h", "Natsuki Yoshimoto")], (1.7, ["bet600", "betgoodwin"]))
        self.assertEqual(best[("correct_score", "1 - 2")], (4.75, ["bet600", "betgoodwin"]))

    def test_the_highest_price_takes_the_row(self):
        self.event["bookmakers"][1]["markets"][0]["outcomes"][1]["price"] = 2.1
        self.assertEqual(main.best_prices(self.event)[("h2h", "Tiana Tian Deng")], (2.1, ["betgoodwin"]))

    def test_exchange_back_price_and_missing_prices(self):
        event = load("v2-odds-raw.exchange_with_link.json")["data"][0]
        outcomes = event["bookmakers"][0]["markets"][0]["outcomes"]
        outcomes[0] = {"name": "Natsuki Yoshimoto", "back_price": 1.75, "lay_price": 1.8, "available": 10.0}
        outcomes[1]["price"] = None
        self.assertEqual(main.best_prices(event),
                         {("h2h", "Natsuki Yoshimoto"): (1.75, ["betfair_exchange"])})

    def test_main_quotes_before_it_spends(self):
        sent = []
        run(sent, load("v2-odds-type.quote.json"), load("v2-odds-raw.page.json"))
        self.assertEqual(sent, ["true", None])
        sent = []  # a priced quote, no --max-tokens and no terminal to ask at: nothing is spent
        priced = {"cost": 50, "remaining": None, "rate_card": "2026-09"}
        self.assertRaises(SystemExit, run, sent, priced, None)
        self.assertEqual(sent, ["true"])


if __name__ == "__main__":
    unittest.main()
