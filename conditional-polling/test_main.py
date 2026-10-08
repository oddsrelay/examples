import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

import main

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
BOARD = json.loads((FIXTURES / "v2-odds-type.standard_filtered.json").read_text())["data"]  # format=bare
QUOTE = json.loads((FIXTURES / "v2-odds-type.quote.json").read_text())


def run(sent: list, quote: dict, *argv: str) -> None:
    """main() with get() faked and one poll: the quote call answers `quote`, the poll the fixture board."""
    def fake_get(path, params, headers=None):
        sent.append((params.get("quote"), params.get("format")))
        return 200, {}, quote if params.get("quote") else BOARD
    with mock.patch.object(main, "get", fake_get), \
            mock.patch("sys.argv", ["main.py", "--polls", "1", *argv]), \
            mock.patch("sys.stdin", StringIO()), redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        main.main()


class PollingTest(unittest.TestCase):
    def test_max_age(self):
        self.assertEqual(main.max_age({"Cache-Control": "private, max-age=7, must-revalidate"}), 7)
        self.assertEqual(main.max_age({"Cache-Control": "no-store"}), 0)
        self.assertEqual(main.max_age({}), 0)

    def test_the_etag_goes_back_and_304s_keep_it(self):
        replies = iter([
            (200, {"ETag": '"c1-gz"', "Cache-Control": "max-age=7", "X-Tokens-Cost": "3",
                   "X-Processed-At": "2026-09-17T02:20:57.271Z"}, BOARD),
            (304, {"ETag": '"c1-gz"', "Cache-Control": "max-age=7", "X-Tokens-Cost": "0"}, None),
            (200, {"ETag": '"c2-gz"', "X-Tokens-Cost": "3"}, BOARD),
            (304, {"ETag": '"c2-gz"', "X-Tokens-Cost": "0"}, None),
        ])
        sent, slept = [], []

        def fetch(headers):
            sent.append(headers)
            return next(replies)

        with redirect_stdout(StringIO()) as out:
            main.poll(fetch, polls=4, every=1, sleep=slept.append)
        self.assertEqual(sent, [{}, {"If-None-Match": '"c1-gz"'}, {"If-None-Match": '"c1-gz"'},
                                {"If-None-Match": '"c2-gz"'}])
        self.assertEqual(slept, [7, 7, 1])  # the longer of --every and max-age, none after the last poll
        lines = out.getvalue().splitlines()
        self.assertIn("304, unchanged", lines[1])
        self.assertIn("events 1, processed at 2026-09-17T02:20:57.271Z", lines[0])

    def test_main_quotes_before_it_spends(self):
        sent = []
        run(sent, QUOTE)
        self.assertEqual(sent, [("true", "bare"), (None, "bare")])
        sent = []  # a priced quote, no --max-tokens and no terminal to ask at: nothing is spent
        self.assertRaises(SystemExit, run, sent, {"cost": 3, "remaining": None, "rate_card": "2026-09"})
        self.assertEqual(sent, [("true", "bare")])


if __name__ == "__main__":
    unittest.main()
