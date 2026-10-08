import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

import main
from api import afford

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


class OddsmatcherTest(unittest.TestCase):
    def test_rating(self):
        self.assertAlmostEqual(main.rating(2.0, 2.0, 0.0), 100.0)
        self.assertAlmostEqual(main.rating(3.0, 3.1, 0.02), 100 * 3.0 * 0.98 / 3.08)

    def test_standard_board(self):
        rows = list(main.pairs(load("v2-odds-type.standard_filtered.json")["data"], 0.0))
        self.assertEqual(len(rows), 1)
        score, event, market, outcome, back, lay = rows[0]
        self.assertAlmostEqual(score, 100 * 2.9 / 3.45)
        self.assertEqual((market["key"], outcome["name"]), ("h2h", "Sijia Wei"))
        self.assertEqual((back["bookmaker"], lay["exchange"]), ("william_hill", "betfair_exchange"))
        self.assertEqual(main.label(event), "Sijia Wei v Zhuoxuan Bai")

    def test_every_back_offer_meets_the_lowest_lay(self):
        rows = list(main.pairs(load("v2-odds-type.bog_bare.json"), 0.0))  # format=bare: a list, no envelope
        self.assertEqual([row[4]["bookmaker"] for row in rows], ["ladbrokes", "betfred"])
        self.assertEqual({row[5]["price"] for row in rows}, {4.3})
        self.assertEqual(main.label(rows[0][1]), "Ayr")

    def test_outcomes_without_a_lay_are_skipped(self):
        self.assertEqual(list(main.pairs(load("v2-odds-type.dutching_filtered.json")["data"], 0.0)), [])

    def test_unpriced_offers_are_skipped(self):
        board = load("v2-odds-type.standard_filtered.json")["data"]
        outcome = board[0]["markets"][0]["outcomes"][0]
        outcome["lay"][0]["price"] = None
        self.assertEqual(list(main.pairs(board, 0.0)), [])
        outcome["lay"][0]["price"], outcome["back"][0]["price"] = 3.45, None
        self.assertEqual(list(main.pairs(board, 0.0)), [])

    def test_afford(self):
        priced = {"cost": 50, "remaining": 1000, "rate_card": "2026-09"}
        with redirect_stderr(io.StringIO()):
            self.assertTrue(afford(load("v2-odds-type.quote.json"), None))  # a free quote needs no ceiling
            self.assertTrue(afford(priced, 50))
            self.assertFalse(afford(priced, 49))

    def test_main_quotes_before_it_spends(self):
        sent = []
        run(sent, load("v2-odds-type.quote.json"), load("v2-odds-type.standard_filtered.json"))
        self.assertEqual(sent, ["true", None])
        sent = []  # a priced quote, no --max-tokens and no terminal to ask at: nothing is spent
        priced = {"cost": 50, "remaining": None, "rate_card": "2026-09"}
        self.assertRaises(SystemExit, run, sent, priced, None)
        self.assertEqual(sent, ["true"])

    def test_commission_must_be_a_fraction(self):
        sent = []
        self.assertRaises(SystemExit, run, sent, {}, None, "--commission", "5")
        self.assertEqual(sent, [])  # refused before any request


if __name__ == "__main__":
    unittest.main()
