import json
import unittest
from pathlib import Path

import main
from api import afford

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


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
        rows = list(main.pairs(load("v2-odds-type.bog_bare.json"), 0.0))  # format=bare: the data array alone
        self.assertEqual([row[4]["bookmaker"] for row in rows], ["ladbrokes", "betfred"])
        self.assertEqual({row[5]["price"] for row in rows}, {4.3})
        self.assertEqual(main.label(rows[0][1]), "Ayr")

    def test_outcomes_without_a_lay_are_skipped(self):
        self.assertEqual(list(main.pairs(load("v2-odds-type.dutching_filtered.json")["data"], 0.0)), [])

    def test_unpriced_offers_are_skipped(self):
        board = load("v2-odds-type.standard_filtered.json")["data"]
        board[0]["markets"][0]["outcomes"][0]["lay"][0]["price"] = None
        self.assertEqual(list(main.pairs(board, 0.0)), [])

    def test_afford(self):
        self.assertTrue(afford(load("v2-odds-type.quote.json"), None))  # a free quote needs no ceiling
        priced = {"cost": 50, "remaining": 1000, "rate_card": "2026-09"}
        self.assertTrue(afford(priced, 50))
        self.assertFalse(afford(priced, 49))


if __name__ == "__main__":
    unittest.main()
