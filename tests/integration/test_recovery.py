"""Shamir recovery + password rotation over the real crypto stack."""
import os
import tempfile

import pytest

from ferrovault.adapters.outbound.clock.system_clock import SystemClock
from ferrovault.adapters.outbound.crypto.scrypt_kdf import ScryptKeyDerivation
from ferrovault.adapters.outbound.storage.file_repository import FileVaultRepository
from ferrovault.application.errors import AuthenticationError
from ferrovault.application.services.vault_service import VaultService

pytest.importorskip("cryptography")
from ferrovault.adapters.outbound.crypto.aesgcm_cipher import AesGcmCipher  # noqa: E402


def _svc(path):
    return VaultService(FileVaultRepository(path), ScryptKeyDerivation(),
                        AesGcmCipher(), SystemClock())


def _prepared(path):
    _svc(path).init_vault("orig")
    _svc(path).add_entry("orig", "github", "octocat", "s3cr3t")
    return _svc(path).enroll_recovery("orig", 5, 3)


def test_recover_resets_password_and_keeps_data():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "v.fv")
        shares = _prepared(path)
        _svc(path).recover([shares[0], shares[2], shares[4]], "new")
        assert _svc(path).get_secret("new", "github") == "s3cr3t"
        with pytest.raises(AuthenticationError):
            _svc(path).get_secret("orig", "github")


def test_shares_survive_rotation():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "v.fv")
        shares = _prepared(path)
        _svc(path).rotate("orig", "rotated")
        assert _svc(path).get_secret("rotated", "github") == "s3cr3t"
        # same shares still reconstruct access after the password changed
        _svc(path).recover([shares[1], shares[3], shares[0]], "final")
        assert _svc(path).get_secret("final", "github") == "s3cr3t"


def test_too_few_shares_rejected():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "v.fv")
        shares = _prepared(path)
        with pytest.raises(AuthenticationError):
            _svc(path).recover([shares[0], shares[1]], "x")
