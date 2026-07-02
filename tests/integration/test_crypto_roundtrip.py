"""Integration: the real scrypt + AES-GCM adapters through a file repository."""
import os
import tempfile

import pytest

from ferrovault.adapters.outbound.clock.system_clock import SystemClock
from ferrovault.adapters.outbound.crypto.scrypt_kdf import ScryptKeyDerivation
from ferrovault.adapters.outbound.storage.file_repository import FileVaultRepository
from ferrovault.application.errors import AuthenticationError
from ferrovault.application.services.vault_service import VaultService
from ferrovault.domain.value_objects.kdf_params import KdfParams

cryptography = pytest.importorskip("cryptography")
from ferrovault.adapters.outbound.crypto.aesgcm_cipher import AesGcmCipher  # noqa: E402


def _service(path):
    return VaultService(FileVaultRepository(path), ScryptKeyDerivation(),
                        AesGcmCipher(), SystemClock(), kdf_factory=KdfParams.scrypt)


def test_real_crypto_roundtrip_on_disk():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "vault.fv")
        svc = _service(path)
        svc.init_vault("master-pass-1")
        svc.add_entry("master-pass-1", "aws", "root", "AKIA-SECRET")
        # A brand-new service instance reads it straight off disk.
        assert _service(path).get_secret("master-pass-1", "aws") == "AKIA-SECRET"


def test_tampered_or_wrong_password_is_rejected():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "vault.fv")
        svc = _service(path)
        svc.init_vault("master-pass-1")
        with pytest.raises(AuthenticationError):
            _service(path).get_secret("WRONG", "aws")


def test_audit_chain_persists_and_verifies_across_reload():
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "vault.fv")
        svc = _service(path)
        svc.init_vault("pw")
        svc.add_entry("pw", "github", "octocat", "s3cr3t")
        svc.add_entry("pw", "aws", "root", "key")
        # A fresh service reads the persisted ledger and verifies the chain.
        verdict, root, head = _service(path).verify_integrity("pw")
        assert verdict.ok
        blocks = _service(path).audit_log("pw")
        assert [b.action for b in blocks] == ["init", "add", "add"]
        assert len(root) == 64 and len(head) == 64
