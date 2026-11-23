import copy
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import main

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = next(p for p in (os.path.join(HERE, "..", "fixtures"), os.path.join(HERE, "fixtures")) if os.path.isdir(p))
PAGE = json.load(open(os.path.join(FIXTURES, "v2-odds-raw.page.json")))
QUOTE = json.load(open(os.path.join(FIXTURES, "v2-odds-type.quote.json")))
EVENT = PAGE["data"][0]


def state(in_play):
    event = copy.deepcopy(EVENT)
    event["in_play"] = in_play
    return event


def run(events, *flags, quote=QUOTE):
    """main() with get() faked: quote calls answer `quote`, the raw board answers the fixture page, event reads take
    `events` in turn. time.sleep is faked too."""
    sent, left, out = [], list(events), io.StringIO()

    def fake_get(path, params, headers=None):
        sent.append((path, params))
        if params.get("quote"):
            return 200, {}, quote
        if path == "/v2/odds/raw":
            return 200, {}, PAGE
        return 200, {}, left.pop(0)
    argv = ["main.py", *flags]
    with mock.patch.object(main, "get", fake_get), mock.patch("sys.argv", argv), mock.patch("time.sleep"), \
            mock.patch("sys.stdin", io.StringIO()), redirect_stdout(out), redirect_stderr(io.StringIO()):
        main.main()
    return out.getvalue().splitlines(), sent


class InPlayTest(unittest.TestCase):
    def test_reports_the_turn_into_play_once_with_the_same_id(self):
        lines, sent = run([state(False), state(True), state(True)], "--polls", "3")
        turns = [line for line in lines if "gone in play" in line]
        self.assertEqual(len(turns), 1)
        self.assertTrue(turns[0].endswith(f"still {EVENT['id']}"))
        self.assertEqual(sum("in_play=True" in line for line in lines), 2)
        self.assertEqual(sent[-1][0], f"/v2/odds/event/{EVENT['id']}")
        self.assertEqual(sent[-1][1]["inPlay"], "include")

    def test_prices_line_names_every_venue_on_h2h(self):
        lines, _ = run([state(False)], "--polls", "1")
        self.assertIn("bet600: Natsuki Yoshimoto 1.7, Tiana Tian Deng 2.0", lines[0])
        self.assertNotIn("correct_score", lines[0])

    def test_already_in_play_has_no_turn(self):
        lines, _ = run([state(True), state(True)], "--event", EVENT["id"], "--polls", "2")
        self.assertFalse(any("gone in play" in line for line in lines))

    def test_refuses_over_the_ceiling_before_any_data_call(self):
        with self.assertRaises(SystemExit):
            run([], "--max-tokens", "5", quote={"cost": 40, "remaining": 1000})


if __name__ == "__main__":
    unittest.main()
