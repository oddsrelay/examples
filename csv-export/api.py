"""The small HTTP helper every example here shares. Each folder keeps an identical copy, so any
folder runs on its own with nothing but the Python standard library."""
from __future__ import annotations

import gzip
import json
import os
import sys
import time
from http.client import HTTPMessage
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

API = "https://api.oddsrelay.io"


def get(path: str, params: dict, headers: dict | None = None) -> tuple[int, HTTPMessage, Any]:
    """GET one route with gzip: (status, headers, decoded JSON or None). Waits out 429s, exits on errors."""
    key = os.environ.get("ODDSRELAY_KEY")
    if not key:
        sys.exit("set ODDSRELAY_KEY to your API key")
    query = urlencode({k: v for k, v in params.items() if v is not None})
    for _ in range(3):
        req = Request(f"{API}{path}" + (f"?{query}" if query else ""), headers={
            "Authorization": f"Bearer {key}", "Accept-Encoding": "gzip", **(headers or {})})
        try:
            with urlopen(req, timeout=30) as res:
                status, hdrs, body = res.status, res.headers, res.read()
        except HTTPError as err:  # urllib raises for 304 and for every 4xx and 5xx
            status, hdrs, body = err.code, err.headers, err.read()
        except URLError as err:
            sys.exit(f"could not reach {API}: {err.reason}")
        if body and hdrs.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        if status == 429:  # rate-limited: the reply says how long to wait
            time.sleep(int(hdrs.get("Retry-After", "1")))
            continue
        if status >= 400:
            error = json.loads(body).get("error", {}) if body[:1] == b"{" else {}
            sys.exit(f"HTTP {status} {error.get('code', '')}: {error.get('message', '')} "
                     f"(request id {error.get('request_id', '-')})")
        return status, hdrs, json.loads(body) if body else None
    sys.exit("still rate-limited after 3 tries")


def afford(quote: dict, max_tokens: int | None) -> bool:
    """True when a quoted price is fine: free, within --max-tokens, or confirmed at the prompt."""
    print(f"quote: {quote['cost']} tokens ({quote['remaining']} left)", file=sys.stderr)
    if quote["cost"] == 0 or (max_tokens is not None and quote["cost"] <= max_tokens):
        return True
    if max_tokens is None and sys.stdin.isatty():
        return input("fetch it? [y/N] ").strip().lower() == "y"
    return False
