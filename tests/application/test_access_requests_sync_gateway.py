import os
import tempfile

import pytest

from ferrovault.application.services.access_requests import AccessRequestQueue
from ferrovault.application.services.directory import DirectoryPrincipal, IdentityDirectory
from ferrovault.application.services.sync_gateway import ZeroTrustSyncGateway
from ferrovault.container import build_vault_service
from ferrovault.adapters.outbound.sharing.sealed_box import generate_keypair

pytest.importorskip("cryptography")


def _vault(path):
    svc = build_vault_service(path)
    svc.init_vault("pw")
    svc.add_entry("pw", "prod-db", "svc", "postgres://secret-dsn")
    return svc


def test_access_request_queue_creates_and_decides_requests():
    queue = AccessRequestQueue().create(
        entry_name="prod-db",
        requester="ops@example.com",
        action="reveal_secret",
        reason="incident response",
        created_at="2026-07-01T10:00:00+00:00",
    )
    request = queue.list()[0]

    assert queue.pending_count() == 1
    assert queue.pending_for_entry("prod-db")[0].requester == "ops@example.com"

    queue = queue.decide(
        request.request_id,
        approved=True,
        decided_by="owner",
        decided_at="2026-07-01T10:05:00+00:00",
        reason="approved for IR window",
    )

    decided = queue.list()[0]
    assert queue.pending_count() == 0
    assert decided.status == "approved"
    assert decided.decided_by == "owner"


def test_zero_trust_sync_gateway_delivers_only_to_trusted_active_directory_principal():
    with tempfile.TemporaryDirectory() as d:
        svc = _vault(os.path.join(d, "v.fv"))
        _priv, pub = generate_keypair()
        svc.share_secret("pw", "prod-db", pub, recipient_label="ops@example.com")
        entry = next(e for e in svc.list_entries("pw") if e.name == "prod-db")
        directory = IdentityDirectory([
            DirectoryPrincipal(label="Ops", email="ops@example.com", public_key=pub, trusted_devices=("laptop-1",))
        ])

        allowed = ZeroTrustSyncGateway(directory).evaluate([entry], device_id="laptop-1")[0]
        blocked = ZeroTrustSyncGateway(directory).evaluate([entry], device_id="unknown-device")[0]

        assert allowed.allowed is True
        assert allowed.sealed_blob
        assert blocked.allowed is False
        assert "not trusted" in blocked.reason


def test_zero_trust_sync_gateway_blocks_revoked_grants():
    with tempfile.TemporaryDirectory() as d:
        svc = _vault(os.path.join(d, "v.fv"))
        _priv, pub = generate_keypair()
        svc.share_secret("pw", "prod-db", pub, recipient_label="ops@example.com")
        svc.revoke_share("pw", "prod-db", "ops@example.com", reason="offboarding")
        entry = next(e for e in svc.list_entries("pw") if e.name == "prod-db")
        directory = IdentityDirectory([
            DirectoryPrincipal(label="Ops", email="ops@example.com", public_key=pub, trusted_devices=("laptop-1",))
        ])

        decision = ZeroTrustSyncGateway(directory).evaluate([entry], device_id="laptop-1")[0]

        assert decision.allowed is False
        assert decision.sealed_blob == ""
        assert decision.reason == "grant revoked"
