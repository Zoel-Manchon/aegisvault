"""Merkle root: a single fingerprint of the whole vault's contents.

Hash the entries pairwise up a binary tree; the root changes if any entry
changes. Same construction Bitcoin uses to commit to a block's transactions.
Here it gives the vault a compact, verifiable state fingerprint.
"""
from __future__ import annotations

import hashlib


def _h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def merkle_root(leaves: list) -> str:
    if not leaves:
        return "0" * 64
    level = [_h(leaf if isinstance(leaf, bytes) else leaf.encode("utf-8"))
             for leaf in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])          # duplicate the last (Bitcoin-style)
        level = [_h(level[i] + level[i + 1]) for i in range(0, len(level), 2)]
    return level[0].hex()
