import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

import main

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
EACH_WAY = json.loads((FIXTURES / "v2-odds-type.each_way.json").read_text())["data"]
BOG = json.loads((FIXTURES / "v2-odds-type.bog_bare.json").read_text())  # format=bare: a list, no envelope
QUOTE = json.loads((FIXTURES / "v2-odds-type.quote.json").read_text())
TOKEN = "placeholder-not-a-token"


def local(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(main.UK).strftime("%H:%M %Z")


class TableTest(unittest.TestCase):
    def test_terms(self):
        self.assertEqual(main.terms({"places": 3, "place_fraction": 0.2}), "3pl 1/5")
        self.assertEqual(main.terms({"places": 4, "place_fraction": 0.25}), "4pl 1/4")
        self.assertEqual(main.terms({"bookmaker": "betfred", "price": 4.0}), "")  # a win-only board

    def test_each_way_race(self):
        lines = main.race(EACH_WAY[0], 10).splitlines()
        self.assertEqual(lines[0], f"Illawarra Grange {local(EACH_WAY[0]['commence_time'])}")
        self.assertEqual(lines[1].split(), ["Albert", "Palais", "2.7", "kwiff", "3pl", "1/5", "lay", "3.25", "(22)"])

    def test_bog_race_lists_every_book_at_the_best_price_and_the_lowest_lay(self):
        line = main.race(BOG[0], 10).splitlines()[1]
        self.assertIn("4.0  ladbrokes, betfred  lay 4.3 (17)", line)

    def test_one_line_per_runner_however_it_is_spelled(self):
        event = json.loads(json.dumps(BOG[0]))
        outcomes = event["markets"][0]["outcomes"]
        outcomes.insert(0, {"name": "BASSRAH", "back": [{"bookmaker": "coral", "price": 4.5, "link": None}],
                            "lay": [{"exchange": "smarkets", "price": 4.2, "available": 9.5, "link": None}]})
        outcomes.append({"name": "Bass'rah", "back": [{"bookmaker": "bet365", "price": 4.5, "link": None}], "lay": []})
        lines = main.race(event, 10).splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[1].split(), ["Bassrah", "4.5", "coral,", "bet365", "lay", "4.2", "(10)"])

    def test_runners_shortest_price_first_and_capped(self):
        event = json.loads(json.dumps(BOG[0]))
        outcomes = event["markets"][0]["outcomes"]
        for name, price in (("Longshot", 21.0), ("Favourite", 2.5), ("No Price", None)):
            outcomes.append({"name": name, "back": [{"bookmaker": "betfred", "price": price, "link": None}], "lay": []})
        lines = main.race(event, 2).splitlines()
        self.assertEqual([line.split()[0] for line in lines[1:]], ["Favourite", "Bassrah"])

    def test_more_than_two_books_are_counted(self):
        event = json.loads(json.dumps(BOG[0]))
        back = event["markets"][0]["outcomes"][0]["back"]
        back += [{"bookmaker": book, "price": 4.0, "link": None} for book in ("coral", "bet365")]
        self.assertIn("ladbrokes, betfred +2  lay", main.race(event, 10))

    def test_message_is_cut_to_fit_one_post(self):
        text = main.message(BOG * 60, 10)
        self.assertLessEqual(len(text), main.MAX_CHARS)
        self.assertIn("more races", text)
        self.assertEqual(main.message(BOG, 10), main.race(BOG[0], 10))


@mock.patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "", "TELEGRAM_BOT_TOKEN": "", "TELEGRAM_CHAT_ID": ""})
class SendTest(unittest.TestCase):
    def test_discord(self):
        with mock.patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": f"https://discord.com/api/webhooks/1/{TOKEN}\n"}), \
                mock.patch("main.urlopen") as urlopen:
            main.send("Ayr 13:30 BST")
        req = urlopen.call_args[0][0]
        self.assertEqual(req.full_url, f"https://discord.com/api/webhooks/1/{TOKEN}")
        self.assertTrue(req.get_header("User-agent").startswith("DiscordBot ("))
        body = json.loads(req.data)
        self.assertEqual(body, {"content": "```\nAyr 13:30 BST\n```", "allowed_mentions": {"parse": []}})

    def test_telegram_escapes_html(self):
        env = {"TELEGRAM_BOT_TOKEN": TOKEN, "TELEGRAM_CHAT_ID": "@racing_prices"}
        with mock.patch.dict(os.environ, env), mock.patch("main.urlopen") as urlopen:
            main.send("Fish & Chips <3>")
        req = urlopen.call_args[0][0]
        self.assertEqual(req.full_url, f"https://api.telegram.org/bot{TOKEN}/sendMessage")
        self.assertEqual(json.loads(req.data), {"chat_id": "@racing_prices", "parse_mode": "HTML",
                                                "text": "<pre>Fish &amp; Chips &lt;3&gt;</pre>"})

    def test_a_refusal_never_names_the_url(self):
        refused = HTTPError("u", 404, "", None, io.BytesIO(b'{"message": "Unknown Webhook", "code": 10015}'))
        with mock.patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": f"https://discord.com/api/webhooks/1/{TOKEN}"}), \
                mock.patch("main.urlopen", side_effect=refused), self.assertRaises(SystemExit) as stop:
            main.send("x")
        self.assertIn("HTTP 404", str(stop.exception))
        self.assertNotIn(TOKEN, str(stop.exception))

    def test_no_destination_stops(self):
        with mock.patch("main.urlopen") as urlopen:
            self.assertRaises(SystemExit, main.send, "x")
        urlopen.assert_not_called()


class MainTest(unittest.TestCase):
    def run_main(self, replies, *argv):
        """main() with get() faked: the quote call answers QUOTE, each data call the next of `replies`."""
        sent = []

        def fake_get(path, params, headers=None):
            sent.append((params.get("quote"), (headers or {}).get("If-None-Match")))
            return (200, {}, QUOTE) if params.get("quote") else replies.pop(0)
        with mock.patch.object(main, "get", fake_get), mock.patch.object(main, "send") as send, \
                mock.patch("sys.argv", ["main.py", "--state", self.state, *argv]), \
                mock.patch("sys.stdin", io.StringIO()), redirect_stdout(io.StringIO()) as out, \
                redirect_stderr(io.StringIO()):
            main.main()
        return sent, send, out.getvalue()

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.state = os.path.join(self.dir.name, "etag")

    def tearDown(self):
        self.dir.cleanup()

    def test_posts_then_a_304_sends_nothing(self):
        sent, send, _ = self.run_main([(200, {"ETag": '"c1-gz"'}, BOG)])
        self.assertEqual(sent, [("true", None), (None, None)])  # the quote first
        send.assert_called_once_with(main.race(BOG[0], 10))
        self.assertEqual(Path(self.state).read_text(), '"c1-gz"')
        sent, send, out = self.run_main([(304, {"ETag": '"c1-gz"'}, None)])
        self.assertEqual(sent[1], (None, '"c1-gz"'))
        send.assert_not_called()
        self.assertIn("unchanged", out)

    def test_dry_run_prints_and_keeps_no_etag(self):
        sent, send, out = self.run_main([(200, {"ETag": '"c1-gz"'}, BOG)], "--dry-run")
        send.assert_not_called()
        self.assertIn("Bassrah", out)
        self.assertFalse(Path(self.state).exists())
        Path(self.state).write_text('"c1-gz"')  # after a real post, a dry run still asks for the whole board
        sent, _, out = self.run_main([(200, {"ETag": '"c1-gz"'}, BOG)], "--dry-run")
        self.assertEqual(sent[1], (None, None))
        self.assertIn("Bassrah", out)

    def test_an_empty_window_sends_nothing(self):
        _, send, out = self.run_main([(200, {"ETag": '"c0-gz"'}, [])])
        send.assert_not_called()
        self.assertIn("no races", out)

    def test_a_priced_quote_with_no_ceiling_spends_nothing(self):
        def fake_get(path, params, headers=None):
            self.assertEqual(params.get("quote"), "true")
            return 200, {}, {"cost": 3, "remaining": None, "rate_card": "2026-09"}
        with mock.patch.object(main, "get", fake_get), mock.patch("sys.argv", ["main.py"]), \
                mock.patch("sys.stdin", io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertRaises(SystemExit, main.main)

    def test_the_request(self):
        def fake_get(path, params, headers=None):
            self.assertEqual(path, "/v2/odds/each-way")
            self.assertEqual((params["sports"], params["format"], params["bookmakers"]),
                             ("horse_racing", "bare", "bet365,betfred"))
            start = datetime.fromisoformat(params["commenceTimeFrom"])
            end = datetime.fromisoformat(params["commenceTimeTo"])
            self.assertEqual((end - start).total_seconds(), 2 * 3600)
            return (200, {}, QUOTE) if params.get("quote") else (200, {}, [])
        with mock.patch.object(main, "get", fake_get), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()), \
                mock.patch("sys.argv", ["main.py", "--hours", "2", "--bookmakers", "bet365,betfred"]):
            main.main()


if __name__ == "__main__":
    unittest.main()
