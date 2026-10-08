import json
import unittest
from pathlib import Path

import main

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


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
        self.assertEqual(main.best_prices(event), {("h2h", "Natsuki Yoshimoto"): (1.75, ["betfair_exchange"])})


if __name__ == "__main__":
    unittest.main()
