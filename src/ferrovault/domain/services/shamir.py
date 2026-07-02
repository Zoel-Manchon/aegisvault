"""Shamir's Secret Sharing over GF(2^8) - split a secret into N shares of
which any K reconstruct it, while any K-1 reveal nothing.

Byte-wise sharing in the AES field (0x11b), the same construction HashiCorp
Vault and `ssss` use. Pure domain logic, no I/O. A share is serialised as
"<x>-<hex>" so it is easy to copy, store, and hand out.
"""
from __future__ import annotations

import secrets

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
def split_secret(secret: bytes, n: int, k: int) -> list:
    if not 1 <= k <= n <= 255:
        raise ValueError("require 1 <= k <= n <= 255")
    xs = list(range(1, n + 1))
    shares = {x: bytearray() for x in xs}
    for byte in secret:
        coeffs = [byte] + [secrets.randbelow(256) for _ in range(k - 1)]
        for x in xs:
            shares[x].append(_eval(coeffs, x))
    return [f"{x}-{bytes(buf).hex()}" for x, buf in shares.items()]


def combine_shares(share_strings: list) -> bytes:
    points = []
    for s in share_strings:
        x_str, hex_str = s.strip().split("-", 1)
        points.append((int(x_str), bytes.fromhex(hex_str)))
    if len({x for x, _ in points}) != len(points):
        raise ValueError("duplicate share indices")

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
