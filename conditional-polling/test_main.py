import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import main

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
BOARD = json.loads((FIXTURES / "v2-odds-type.standard_filtered.json").read_text())


class PollingTest(unittest.TestCase):
    def test_max_age(self):
        self.assertEqual(main.max_age({"Cache-Control": "private, max-age=7, must-revalidate"}), 7)
        self.assertEqual(main.max_age({"Cache-Control": "no-store"}), 0)
        self.assertEqual(main.max_age({}), 0)

    def test_the_etag_goes_back_and_304s_keep_it(self):
        replies = iter([
            (200, {"ETag": '"c1-gz"', "Cache-Control": "max-age=7", "X-Tokens-Cost": "3"}, BOARD),
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
        self.assertIn("304 not modified", lines[1])
        self.assertIn("events 1", lines[0])


if __name__ == "__main__":
    unittest.main()
