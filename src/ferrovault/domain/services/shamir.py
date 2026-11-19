"""Shamir's Secret Sharing over GF(2^8) - split a secret into N shares of
which any K reconstruct it, while any K-1 reveal nothing.

Byte-wise sharing in the AES field (0x11b), the same construction HashiCorp
Vault and `ssss` use. Pure domain logic, no I/O.

A share is written as plain hexadecimal (shown in groups of four): one byte
with the share number, the share bytes and a 3-byte checksum, so a typo made
while copying it by hand is caught before any reconstruction is attempted.
Shares from older versions ("<x>-<hex>", no checksum) are still accepted.
"""
from __future__ import annotations

import hashlib
import secrets

_CHECK_LEN = 3
_CHECK_TAG = b"aegisvault-shamir-share-v2"

# --- GF(2^8) arithmetic ------------------------------------------------------
_EXP = [0] * 512
_LOG = [0] * 256


def _xtime(a: int) -> int:
    a <<= 1
    if a & 0x100:
        a ^= 0x11B
    return a & 0xFF


def _init_tables():
    a = 1
    for i in range(255):
        _EXP[i] = a
        _LOG[a] = i
        a ^= _xtime(a)                 # multiply by generator 3
    for i in range(255, 512):
        _EXP[i] = _EXP[i - 255]


_init_tables()


def _mul(a: int, b: int) -> int:
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _inv(a: int) -> int:
    return _EXP[255 - _LOG[a]]


def _eval(coeffs: list, x: int) -> int:
    y = 0
    for c in reversed(coeffs):         # Horner's method in GF(256)
        y = _mul(y, x) ^ c
    return y


# --- public API --------------------------------------------------------------
def validate_split(n: int, k: int) -> None:
    """K-of-N must satisfy 2 <= k <= n <= 255.

    k = 1 would hand out the whole recovery key in every share, so it is
    refused: a "share" must reveal nothing on its own.
    """
    if not (isinstance(n, int) and isinstance(k, int)):
        raise ValueError("shares and threshold must be integers")
    if not 2 <= k <= n <= 255:
        raise ValueError("require 2 <= k <= n <= 255")


def split_secret(secret: bytes, n: int, k: int) -> list:
    validate_split(n, k)
    if not secret:
        raise ValueError("cannot split an empty secret")
    xs = list(range(1, n + 1))
    shares = {x: bytearray() for x in xs}
    for byte in secret:
        coeffs = [byte] + [secrets.randbelow(256) for _ in range(k - 1)]
        for x in xs:
            shares[x].append(_eval(coeffs, x))
    return [format_share(x, bytes(buf)) for x, buf in shares.items()]


def _checksum(body: bytes) -> bytes:
    return hashlib.sha256(_CHECK_TAG + body).digest()[:_CHECK_LEN]


def format_share(x: int, data: bytes) -> str:
    """Share number + share bytes + checksum, as lower-case hex."""
    body = bytes([x]) + bytes(data)
    return (body + _checksum(body)).hex()


def share_groups(share: str, size: int = 4) -> list:
    """The share in upper-case groups of ``size`` characters, for display."""
    text = "".join(str(share).split()).upper()
    return [text[i:i + size] for i in range(0, len(text), size)]


def parse_share(share: str) -> tuple:
    """A share -> ``(x, bytes)``; raises ValueError on anything else.

    Accepts the checksummed hex form (spaces and case are ignored) and the
    older ``"<x>-<hex>"`` form.
    """
    text = "".join(str(share).split())
    if "-" not in text:
        try:
            raw = bytes.fromhex(text)
        except ValueError as exc:
            raise ValueError("a share is made of hexadecimal groups (0-9, A-F)") from exc
        if len(raw) < 2 + _CHECK_LEN:
            raise ValueError("this share is too short: a group is missing")
        body, check = raw[:-_CHECK_LEN], raw[-_CHECK_LEN:]
        if _checksum(body) != check:
            raise ValueError("this share has a typo: its checksum does not match")
        x = body[0]
        if not 1 <= x <= 255:
            raise ValueError(f"share index {x} is outside 1..255")
        return x, body[1:]
    x_str, sep, hex_str = text.partition("-")
    if not sep or not x_str.isdigit() or not hex_str:
        raise ValueError("a share looks like 3-9c02… (index, dash, hex)")
    x = int(x_str)
    if not 1 <= x <= 255:
        raise ValueError(f"share index {x} is outside 1..255")
    try:
        data = bytes.fromhex(hex_str)
    except ValueError as exc:
        raise ValueError(f"share {x} is not valid hex") from exc
    if not data:
        raise ValueError(f"share {x} is empty")
    return x, data


def combine_shares(share_strings: list) -> bytes:
    points = [parse_share(s) for s in share_strings if str(s).strip()]
    if len(points) < 2:
        raise ValueError("at least two shares are needed")
    if len({x for x, _ in points}) != len(points):
        raise ValueError("duplicate share indices")
    if len({len(y) for _, y in points}) != 1:
        raise ValueError("the shares have different lengths: they come from different splits")

    length = len(points[0][1])
    out = bytearray(length)
    for pos in range(length):
        secret_byte = 0
        for i, (xi, yi) in enumerate(points):
            basis = 1
            for j, (xj, _) in enumerate(points):
                if i == j:
                    continue
                basis = _mul(basis, _mul(xj, _inv(xj ^ xi)))
            secret_byte ^= _mul(yi[pos], basis)
        out[pos] = secret_byte
    return bytes(out)
