import csv
import io
import json
import unittest
from pathlib import Path

import main

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


def load(name: str):
    return json.loads((FIXTURES / name).read_text())


class CsvExportTest(unittest.TestCase):
    def test_standard_board(self):
        rows = list(main.rows(load("v2-odds-type.standard_filtered.json")["data"]))
        self.assertEqual([(r["side"], r["venue"], r["price"]) for r in rows],
                         [("back", "william_hill", 2.9), ("lay", "betfair_exchange", 3.45)])
        self.assertEqual(rows[1]["available"], 175.0)
        self.assertEqual(rows[0]["event"], "Sijia Wei v Zhuoxuan Bai")

    def test_each_way_board_splits_the_lay_object(self):
        rows = list(main.rows(load("v2-odds-type.each_way.json")["data"]))
        self.assertEqual([r["side"] for r in rows], ["back", "lay_win", "lay_place"])
        self.assertEqual((rows[0]["places"], rows[0]["place_fraction"]), (3, 0.2))
        self.assertEqual(rows[2]["places"], 3)
        self.assertEqual(rows[0]["event"], "Illawarra Grange")

    def test_dutching_board_has_no_lay(self):
        rows = list(main.rows(load("v2-odds-type.dutching_filtered.json")["data"]))
        self.assertEqual({r["side"] for r in rows}, {"back"})
        self.assertEqual({r["dutch_id"] for r in rows}, {"b8d7916c"})

    def test_write_csv(self):
        out = io.StringIO()
        count = main.write_csv(load("v2-odds-type.bog_bare.json"), out)  # format=bare: the data array alone
        out.seek(0)
        table = list(csv.DictReader(out))
        self.assertEqual(count, 4)
        self.assertEqual(len(table), 4)
        self.assertEqual(list(table[0]), main.FIELDS)
        self.assertEqual((table[3]["side"], table[3]["venue"], table[3]["price"]), ("lay", "smarkets", "4.4"))
        self.assertEqual(table[0]["point"], "")  # absent fields are empty cells


if __name__ == "__main__":
    unittest.main()
