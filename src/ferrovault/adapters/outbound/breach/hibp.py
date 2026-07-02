"""BreachChecker backed by HaveIBeenPwned's Pwned Passwords range API.

Uses k-anonymity: the password is SHA-1'd locally and only the first 5 hex
characters of the digest are sent. The API returns all suffixes sharing that
prefix; we match locally. The password never leaves the machine.
"""
from __future__ import annotations

import hashlib
import urllib.request

_RANGE = "https://api.pwnedpasswords.com/range/"


class HibpBreachChecker:
    def check(self, name_to_password: dict) -> dict:
        # de-dupe identical passwords so we hit the API once each
        by_pw: dict = {}
        for name, pw in name_to_password.items():
            by_pw.setdefault(pw, []).append(name)

        result: dict = {}
        cache: dict = {}
        for pw, names in by_pw.items():
            count = self._count(pw, cache)
            if count:
                for name in names:
                    result[name] = count
        return result

    def _count(self, password: str, cache: dict) -> int:
        digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
        prefix, suffix = digest[:5], digest[5:]
        table = cache.get(prefix)
        if table is None:
            req = urllib.request.Request(
                _RANGE + prefix, headers={"Add-Padding": "true",
                                          "User-Agent": "ferrovault"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8")
            table = {}
            for line in body.splitlines():
                suf, _, cnt = line.partition(":")
                table[suf.strip()] = int(cnt)
            cache[prefix] = table
        return table.get(suffix, 0)
