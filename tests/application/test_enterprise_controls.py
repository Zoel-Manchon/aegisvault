from dataclasses import dataclass

from ferrovault.application.services.enterprise import EnterpriseIdentity, RbacEngine, ADMIN, AUDITOR, MEMBER, READONLY
from ferrovault.application.services.identity import OidcClaimMapper, ScimDirectory
from ferrovault.application.services.policy import PolicyEngine
from ferrovault.application.services.rotation import RotationPlanner
from ferrovault.application.services.settings import VaultSettings
from ferrovault.application.services.siem import MemorySiemSink, SiemStreamer, normalize_blocks


def test_rbac_blocks_export_for_member_but_allows_auditor():
    rbac = RbacEngine()

    blocked = rbac.evaluate("export_audit", EnterpriseIdentity(role=MEMBER))
    allowed = rbac.evaluate("export_audit", EnterpriseIdentity(role=AUDITOR))

    assert not blocked.allowed
    assert blocked.code == "role_forbidden"
    assert allowed.allowed


def test_policy_blocks_sensitive_action_from_untrusted_device():
    engine = PolicyEngine(VaultSettings(
        enterprise_role=ADMIN,
        local_device_id="laptop-2",
        trusted_device_ids=("laptop-1",),
        require_trusted_device=True,
    ))

    decision = engine.evaluate("copy_secret", {"revealed": True, "device_id": "laptop-2"})

    assert not decision.allowed
    assert decision.code == "untrusted_device"


def test_policy_requires_mfa_for_high_sensitivity():
    engine = PolicyEngine(VaultSettings(
        enterprise_role=ADMIN,
        require_mfa_for_high_sensitivity=True,
    ))

    decision = engine.evaluate("reveal_secret", {"sensitivity": "critical", "mfa_verified": False})

    assert not decision.allowed
    assert decision.code == "mfa_required"


def test_oidc_claim_mapper_maps_enterprise_role_and_mfa():
    identity = OidcClaimMapper(allowed_domains=("example.com",)).map_claims({
        "sub": "u-123",
        "email": "admin@example.com",
        "name": "Ada Admin",
        "roles": ["vault_admin", "platform"],
        "groups": ["platform"],
        "amr": ["pwd", "mfa"],
    })

    assert identity.user_id == "u-123"
    assert identity.role == ADMIN
    assert identity.mfa_verified


def test_scim_directory_upsert_deactivate_and_identity():
    directory = ScimDirectory()
    user = directory.upsert_user({
        "id": "u-1",
        "userName": "ops@example.com",
        "displayName": "Ops User",
        "active": True,
        "role": "readonly",
        "groups": [{"display": "ops"}],
        "emails": [{"value": "ops@example.com"}],
    })

    identity = directory.identity_for(user.id)
    inactive = directory.deactivate_user(user.id)

    assert identity.role == READONLY
    assert identity.groups == ("ops",)
    assert not inactive.active


@dataclass(frozen=True)
class EntryLike:
    name: str
    created_at: str
    updated_at: str = ""
    last_rotated_at: str = ""
    rotation_interval_days: int = 90
    sensitivity: str = "standard"
    deleted: bool = False


def test_rotation_planner_flags_overdue_and_due_soon():
    findings = RotationPlanner().analyze((
        EntryLike("db-root", "2026-01-01T00:00:00+00:00", rotation_interval_days=30, sensitivity="critical"),
        EntryLike("api-token", "2026-06-06T00:00:00+00:00", rotation_interval_days=30),
    ), now_iso="2026-07-01T00:00:00+00:00")

    by_name = {f.entry_name: f for f in findings}
    assert by_name["db-root"].status == "overdue"
    assert by_name["db-root"].severity == "critical"
    assert by_name["api-token"].status == "due_soon"


def test_siem_streamer_normalizes_and_writes_events():
    @dataclass(frozen=True)
    class Block:
        index: int
        timestamp: str
        action: str
        detail: str
        prev_hash: str
        hash: str

    blocks = (Block(0, "2026-07-01T00:00:00+00:00", "init", "vault created", "0", "abc"),)
    sink = MemorySiemSink()

    count = SiemStreamer(sink).stream(blocks)
    events = normalize_blocks(blocks)

    assert count == 1
    assert sink.events == list(events)
    assert sink.events[0].event_type == "init"
