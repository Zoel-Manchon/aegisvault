"""Public-key team sharing (X25519 sealed box) over the vault service."""
import os
import tempfile

import pytest

from ferrovault.adapters.outbound.sharing.sealed_box import (
    generate_keypair, open_sealed)

pytest.importorskip("cryptography")
from ferrovault.container import build_vault_service  # noqa: E402


def _vault(path):
    svc = build_vault_service(path)
    svc.init_vault("pw")
    svc.add_entry("pw", "prod-db", "svc", "postgres://secret-dsn")
    return svc


def test_share_then_receive_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        svc = _vault(os.path.join(d, "v.fv"))
        priv, pub = generate_keypair()               # recipient's keypair
        blob = svc.share_secret("pw", "prod-db", pub)
        assert open_sealed(blob, priv) == "postgres://secret-dsn"


def test_other_recipient_cannot_open():
    with tempfile.TemporaryDirectory() as d:
        svc = _vault(os.path.join(d, "v.fv"))
        _priv, pub = generate_keypair()
        other_priv, _other_pub = generate_keypair()
        blob = svc.share_secret("pw", "prod-db", pub)
        with pytest.raises(Exception):
            open_sealed(blob, other_priv)


def test_share_grant_is_persisted_with_recipient_metadata():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "v.fv")
        svc = _vault(path)
        priv, pub = generate_keypair()

        blob = svc.share_secret("pw", "prod-db", pub, recipient_label="ops@example.com", actor="zoel")
        reopened = build_vault_service(path)
        entry = next(e for e in reopened.list_entries("pw") if e.name == "prod-db")

        assert open_sealed(blob, priv) == "postgres://secret-dsn"
        assert entry.shared_with == ("ops@example.com",)
        assert entry.active_share_count == 1
        assert entry.revoked_share_count == 0
        assert entry.sharing_grants[0]["recipient"] == "ops@example.com"
        assert entry.sharing_grants[0]["created_by"] == "zoel"
        assert entry.sharing_grants[0]["public_key_fingerprint"]


def test_revoke_share_marks_grant_inactive_but_keeps_audit_metadata():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "v.fv")
        svc = _vault(path)
        _priv, pub = generate_keypair()
        svc.share_secret("pw", "prod-db", pub, recipient_label="ops@example.com")

        revoked = svc.revoke_share("pw", "prod-db", "ops@example.com", reason="offboarding", actor="owner")
        entry = next(e for e in svc.list_entries("pw") if e.name == "prod-db")

        assert revoked == 1
        assert entry.shared_with == ()
        assert entry.active_share_count == 0
        assert entry.revoked_share_count == 1
        assert entry.sharing_grants[0]["revoked_by"] == "owner"
        assert entry.sharing_grants[0]["revoke_reason"] == "offboarding"
