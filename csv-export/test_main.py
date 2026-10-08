import csv
import io
import json
import tempfile
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


class CsvExportTest(unittest.TestCase):
    def test_standard_board(self):
        board = load("v2-odds-type.standard_filtered.json")["data"]
        rows = list(main.rows(board))
        self.assertEqual([(r["side"], r["venue"], r["price"]) for r in rows],
                         [("back", "william_hill", 2.9), ("lay", "betfair_exchange", 3.45)])
        self.assertEqual(rows[1]["available"], 175.0)
        self.assertEqual(rows[0]["event"], f"{board[0]['home_team']} v {board[0]['away_team']}")

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
        count = main.write_csv(load("v2-odds-type.bog_bare.json"), out)  # format=bare: a list, no envelope
        out.seek(0)
        table = list(csv.DictReader(out))
        self.assertEqual(count, 4)
        self.assertEqual(len(table), 4)
        self.assertEqual(list(table[0]), main.FIELDS)
        self.assertEqual((table[3]["side"], table[3]["venue"], table[3]["price"]), ("lay", "smarkets", "4.4"))
        self.assertEqual(table[0]["point"], "")  # absent fields are empty cells


    def test_main_quotes_before_it_spends(self):
        with tempfile.TemporaryDirectory() as folder:
            out = str(Path(folder) / "board.csv")
            sent = []
            board = load("v2-odds-type.standard_filtered.json")
            run(sent, load("v2-odds-type.quote.json"), board, "--out", out)
            self.assertEqual(sent, ["true", None])
            self.assertEqual(len(Path(out).read_text().splitlines()), 3)  # the header and two offers
            sent = []  # a priced quote, no --max-tokens and no terminal to ask at: nothing is spent
            priced = {"cost": 50, "remaining": None, "rate_card": "2026-09"}
            self.assertRaises(SystemExit, run, sent, priced, None, "--out", out + ".2")
            self.assertEqual(sent, ["true"])


if __name__ == "__main__":
    unittest.main()
