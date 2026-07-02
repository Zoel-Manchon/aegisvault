"""Secret value object: a sensitive string that refuses to leak itself.

Redacts in repr/str/logs, compares in constant time, and is the only type the
domain uses to carry credentials. True memory zeroization happens in the Rust
core (the `zeroize` crate); in pure Python this is best-effort, which the code
is honest about rather than pretending otherwise.
"""
from __future__ import annotations

import hmac


class Secret:
    __slots__ = ("_value",)

    def __init__(self, value: str | bytes):
        if isinstance(value, str):
            value = value.encode("utf-8")
        self._value = bytes(value)

    def reveal(self) -> str:
        return self._value.decode("utf-8")

    def reveal_bytes(self) -> bytes:
        return self._value

    def __eq__(self, other) -> bool:
        if not isinstance(other, Secret):
            return NotImplemented
        return hmac.compare_digest(self._value, other._value)

    def __hash__(self) -> int:
        return 0  # secrets must not be distinguishable by hash

    def __repr__(self) -> str:
        return "Secret(***)"

    def __str__(self) -> str:
        return "***"
