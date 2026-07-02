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
