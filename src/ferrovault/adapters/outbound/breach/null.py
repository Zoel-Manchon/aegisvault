"""Offline BreachChecker: reports nothing breached (default, no network)."""
from __future__ import annotations


class NullBreachChecker:
    def check(self, name_to_password: dict) -> dict:
        return {}
