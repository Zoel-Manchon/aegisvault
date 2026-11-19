"""Shamir's Secret Sharing over GF(2^8)."""
import os

import pytest

from ferrovault.domain.services.shamir import combine_shares, split_secret


def test_any_k_of_n_reconstructs():
    secret = os.urandom(32)
    shares = split_secret(secret, 5, 3)
    assert combine_shares([shares[0], shares[2], shares[4]]) == secret
    assert combine_shares([shares[1], shares[3], shares[0]]) == secret
    assert combine_shares(shares) == secret            # all shares also work


def test_fewer_than_k_does_not_recover():
    secret = os.urandom(16)
    shares = split_secret(secret, 5, 3)
    assert combine_shares([shares[0], shares[1]]) != secret


def test_threshold_equals_n():
    secret = b"exactly-two-of-two!"
    shares = split_secret(secret, 2, 2)
    assert combine_shares(shares) == secret


def test_invalid_parameters_rejected():
    with pytest.raises(ValueError):
        split_secret(b"x", 3, 5)          # k > n
    with pytest.raises(ValueError):
        combine_shares(["1-aa", "1-bb"])  # duplicate index


def test_shares_carry_their_number_and_a_checksum():
    from ferrovault.domain.services.shamir import parse_share, share_groups
    secret = bytes(range(32))
    shares = split_secret(secret, 5, 3)
    assert [parse_share(s)[0] for s in shares] == [1, 2, 3, 4, 5]
    # 1 index byte + 32 share bytes + 3 checksum bytes = 72 hex characters
    assert all(len(s) == 72 and "-" not in s for s in shares)
    spaced = " ".join(share_groups(shares[1]))          # how the UI shows it
    assert combine_shares([shares[0], spaced, shares[4].upper()]) == secret


def test_a_copying_typo_is_caught_by_the_checksum():
    from ferrovault.domain.services.shamir import parse_share
    share = split_secret(b"secret-key-material", 3, 2)[0]
    typo = share[:10] + ("0" if share[10] != "0" else "1") + share[11:]
    with pytest.raises(ValueError, match="typo"):
        parse_share(typo)
    with pytest.raises(ValueError, match="short"):
        parse_share(share[:6])


def test_legacy_dash_shares_still_combine():
    from ferrovault.domain.services.shamir import parse_share
    secret = b"legacy"
    shares = split_secret(secret, 3, 2)
    legacy = [f"{parse_share(s)[0]}-{parse_share(s)[1].hex()}" for s in shares]
    assert combine_shares(legacy[:2]) == secret
    assert combine_shares([legacy[0], shares[2]]) == secret
