from dataclasses import dataclass, field

import pytest

pytest.importorskip("cryptography")

from ferrovault.adapters.inbound.gui.sharing_controller import SharingWorkflowController
from ferrovault.adapters.outbound.sharing.sealed_box import generate_keypair


@dataclass
class EntryStub:
    name: str
    secret: str = "secret"
    deleted: bool = False
    sharing_grants: tuple[dict, ...] = ()


class SessionStub:
    def __init__(self):
        self._entries = [EntryStub("prod-db")]
        self.added = []

    def entries(self):
        return list(self._entries)

    def share_public_key(self, name, recipient, public_key, actor="local-admin"):
        grant = {
            "grant_id": "grant-1",
            "recipient": recipient,
            "public_key_fingerprint": public_key[:12],
            "created_at": "2026-07-01T00:00:00+00:00",
            "created_by": actor,
            "sealed_blob": "sealed-payload",
        }
        entry = next(e for e in self._entries if e.name == name)
        entry.sharing_grants = entry.sharing_grants + (grant,)
        return grant

    def revoke_share(self, name, match, reason="", actor="local-admin"):
        entry = next(e for e in self._entries if e.name == name)
        revoked = 0
        grants = []
        for grant in entry.sharing_grants:
            if not grant.get("revoked_at") and match in {grant.get("grant_id"), grant.get("recipient"), grant.get("public_key_fingerprint")}:
                grant = dict(grant, revoked_at="2026-07-01T01:00:00+00:00", revoked_by=actor, revoke_reason=reason)
                revoked += 1
            grants.append(grant)
        entry.sharing_grants = tuple(grants)
        return revoked

    def add(self, **kwargs):
        self.added.append(kwargs)


def test_sharing_controller_creates_registry_and_revokes_grants():
    _priv, pub = generate_keypair()
    session = SessionStub()
    controller = SharingWorkflowController(session, actor="zoel")

    result = controller.create_grant("prod-db", "ops@example.com", pub)
    active, revoked = controller.grant_counts()
    rows = controller.grant_rows()

    assert "grant id: grant-1" in result.display_text
    assert active == 1 and revoked == 0
    assert rows[0].state == "ACTIVE"
    assert rows[0].revoke_match == "grant-1"

    count = controller.revoke_grant("prod-db", "grant-1", "offboarding")
    active, revoked = controller.grant_counts()

    assert count == 1
    assert active == 0 and revoked == 1
    assert controller.grant_rows()[0].revoke_reason == "offboarding"


def test_sharing_controller_applies_policy_callback_before_share():
    _priv, pub = generate_keypair()
    controller = SharingWorkflowController(SessionStub(), authorize_share=lambda _name: (False, "blocked by test policy"))

    with pytest.raises(PermissionError, match="blocked by test policy"):
        controller.create_grant("prod-db", "ops@example.com", pub)


def test_sharing_controller_can_save_received_secret():
    session = SessionStub()
    controller = SharingWorkflowController(session, actor="zoel")

    controller.save_received_secret(name="shared-api", username="svc", secret="token", url="https://example.com")

    saved = session.added[0]
    assert saved["name"] == "shared-api"
    assert saved["category"] == "Received"
    assert saved["tags"] == ("received", "shared")


def test_sealed_blob_text_extraction():
    assert SharingWorkflowController.sealed_blob_only("metadata\n\nabc.def") == "abc.def"
    assert SharingWorkflowController.sealed_blob_only("abc.def") == "abc.def"
