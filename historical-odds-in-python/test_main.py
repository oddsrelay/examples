import io
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

import main

FROM, TO = "2026-10-16T19:00:00Z", "2026-10-16T19:45:00Z"


def row(ts, outcome, price=None, **extra):
    base = {"timestamp": ts, "event_id": "or_evt_da71d5873e85", "bookmaker": "bet365", "market": "h2h",
            "outcome": outcome, **extra}
    return {**base, "price": price} if price is not None else base


# The contract's own example of the route: the price at `from`, then one change.
EXAMPLE = [row("2026-10-16T18:59:58.120Z", "Arsenal", 2.2), row("2026-10-16T19:12:03.441Z", "Arsenal", 2.1)]


def page(rows, cursor=None, gaps=()):
    return {"meta": {"next_cursor": cursor, "gaps": list(gaps)}, "data": rows}


def run(pages, *flags, quote=None):
    """main() with get() faked: the quote call answers `quote`, data calls take `pages` in turn."""
    sent, left, out = [], list(pages), io.StringIO()

    def fake_get(path, params, headers=None):
        sent.append(params)
        if params.get("quote"):
            return 200, {}, quote or {"cost": 100, "remaining": "unlimited"}
        return 200, {}, left.pop(0)
    argv = ["main.py", "or_evt_da71d5873e85", "--bookmaker", "bet365", "--from", FROM, "--to", TO, *flags]
    with mock.patch.object(main, "get", fake_get), mock.patch("sys.argv", argv), \
            mock.patch("sys.stdin", io.StringIO()), redirect_stdout(out), redirect_stderr(io.StringIO()):
        main.main()
    return out.getvalue().splitlines(), sent


class HistoricalMovesTest(unittest.TestCase):
    def test_contract_example_is_one_move(self):
        lines, _ = run([page(EXAMPLE)], "--max-tokens", "100")
        self.assertEqual(lines, ["2026-10-16T18:59:58.120Z  Arsenal  2.2", "2026-10-16T19:12:03.441Z  Arsenal  2.1",
                                 "1 moves"])

    def test_refuses_over_the_ceiling_with_no_data_call(self):
        with self.assertRaises(SystemExit):
            run([page(EXAMPLE)], "--max-tokens", "10")

    def test_follows_the_cursor_and_lists_gaps(self):
        gap = {"timestamp": "2026-10-16T19:20:00Z", "why": None}
        lines, sent = run([page(EXAMPLE[:1], "next"), page(EXAMPLE[1:], gaps=[gap])], "--max-tokens", "100")
        self.assertEqual(sent[-1]["cursor"], "next")
        self.assertEqual(lines[-2:], ["1 moves", "recording gap at 2026-10-16T19:20:00Z: no reason given"])

    def test_a_return_after_leaving_is_not_a_move(self):
        rows = [EXAMPLE[0], row("2026-10-16T19:01:00Z", "Arsenal", removed=True), row("2026-10-16T19:02:00Z", "Arsenal", 2.1)]
        lines, _ = run([page(rows)], "--max-tokens", "100")
        self.assertIn("2026-10-16T19:01:00Z  Arsenal  left the board", lines)
        self.assertEqual(lines[-1], "0 moves")

    def test_outcome_filter_and_same_name_kept_apart_by_index(self):
        rows = [row("t1", "Over", 1.8), row("t1", "Over", 2.0, index=1), row("t2", "Over", 1.9), row("t2", "Under", 1.9)]
        lines, _ = run([page(rows)], "--outcome", "Over", "--max-tokens", "100")
        self.assertEqual(lines, ["t1  Over  1.8", "t1  Over (2)  2.0", "t2  Over  1.9", "1 moves"])


if __name__ == "__main__":
    unittest.main()
