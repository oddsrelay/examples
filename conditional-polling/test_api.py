"""Tests for api.py, the helper every folder carries an identical copy of. No network: urlopen is replaced."""
import gzip
import io
import os
import unittest
from http.client import HTTPMessage
from pathlib import Path
from unittest import mock
from urllib.error import HTTPError

import api

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"
KEY = "placeholder-not-a-key"


def message(**headers) -> HTTPMessage:
    msg = HTTPMessage()
    for name, value in headers.items():
        msg[name.replace("_", "-")] = value
    return msg


class Reply(io.BytesIO):
    def __init__(self, status: int, headers: HTTPMessage, body: bytes):
        super().__init__(body)
        self.status, self.headers = status, headers


def refusal(status: int, body: bytes = b"", **headers) -> HTTPError:
    return HTTPError(api.API, status, "", message(**headers), io.BytesIO(body))


@mock.patch.dict(os.environ, {"ODDSRELAY_KEY": KEY})
class GetTest(unittest.TestCase):
    def test_asks_for_gzip_and_decompresses(self):
        body = (FIXTURES / "v2-odds-type.standard_filtered.json").read_bytes()
        reply = Reply(200, message(Content_Encoding="gzip", ETag='"c1-gz"'), gzip.compress(body))
        with mock.patch("api.urlopen", return_value=reply) as urlopen:
            status, headers, board = api.get("/v2/odds/standard", {"sports": "tennis", "markets": None})
        request = urlopen.call_args[0][0]
        self.assertEqual(request.full_url, "https://api.oddsrelay.io/v2/odds/standard?sports=tennis")
        self.assertEqual(request.get_header("Accept-encoding"), "gzip")
        self.assertEqual(request.get_header("Authorization"), f"Bearer {KEY}")
        self.assertEqual((status, headers["ETag"], board["meta"]["feed_type"]), (200, '"c1-gz"', "standard"))

    def test_304_has_no_body(self):
        with mock.patch("api.urlopen", side_effect=refusal(304, ETag='"c1-gz"')) as urlopen:
            status, headers, board = api.get("/v2/odds/standard", {}, {"If-None-Match": '"c1-gz"'})
        self.assertEqual(urlopen.call_args[0][0].get_header("If-none-match"), '"c1-gz"')
        self.assertEqual((status, board), (304, None))

    def test_429_waits_for_retry_after(self):
        replies = [refusal(429, Retry_After="2"), Reply(200, message(), b"[]")]
        with mock.patch("api.urlopen", side_effect=replies), mock.patch("api.time.sleep") as sleep:
            self.assertEqual(api.get("/v2/odds/standard", {})[2], [])
        sleep.assert_called_once_with(2)

    def test_429_gives_up_after_three_tries_without_a_last_wait(self):
        replies = [refusal(429, Retry_After="2") for _ in range(4)]
        with mock.patch("api.urlopen", side_effect=replies) as urlopen, mock.patch("api.time.sleep") as sleep:
            self.assertRaises(SystemExit, api.get, "/v2/odds/standard", {})
        self.assertEqual((urlopen.call_count, sleep.call_count), (3, 2))

    def test_a_pasted_newline_is_stripped_from_the_key(self):
        with mock.patch.dict(os.environ, {"ODDSRELAY_KEY": f"{KEY}\r\n"}), \
                mock.patch("api.urlopen", return_value=Reply(200, message(), b"[]")) as urlopen:
            api.get("/v2/odds/standard", {})
        self.assertEqual(urlopen.call_args[0][0].get_header("Authorization"), f"Bearer {KEY}")

    def test_errors_exit_with_the_code_and_request_id_never_the_key(self):
        body = (FIXTURES / "error-401.invalid_api_key.json").read_bytes()
        with mock.patch("api.urlopen", side_effect=refusal(401, body)), self.assertRaises(SystemExit) as stop:
            api.get("/v2/odds/standard", {})
        self.assertIn("HTTP 401 invalid_api_key", str(stop.exception))
        self.assertIn("or_req_", str(stop.exception))
        self.assertNotIn(KEY, str(stop.exception))

    def test_a_missing_key_stops_before_any_request(self):
        with mock.patch.dict(os.environ, {"ODDSRELAY_KEY": ""}), mock.patch("api.urlopen") as urlopen:
            self.assertRaises(SystemExit, api.get, "/v2/odds/standard", {})
        urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
