"""MasterKey value object: the derived symmetric key, wipeable and redacted."""
from __future__ import annotations


class MasterKey:
    __slots__ = ("_key",)

    def __init__(self, key: bytes):
        self._key = bytearray(key)

    @property
    def bytes(self) -> bytes:
        return bytes(self._key)

    def wipe(self) -> None:
        """Best-effort zeroization of the key buffer."""
        for i in range(len(self._key)):
            self._key[i] = 0

    def __len__(self) -> int:
        return len(self._key)

    def __repr__(self) -> str:
        return "MasterKey(***)"
