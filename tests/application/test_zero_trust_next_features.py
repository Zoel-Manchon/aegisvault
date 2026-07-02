import json

from ferrovault.application.services.directory import DirectoryPrincipal, IdentityDirectory
from ferrovault.application.services.policy import PolicyEngine
from ferrovault.application.services.policy_pack import PolicyRule
from ferrovault.application.services.settings import VaultSettings


def test_policy_pack_blocks_matching_context_only():
    rule = PolicyRule(
        rule_id="critical-copy",
        name="Critical copy requires verified MFA",
        actions=("copy_secret",),
        team_vaults=("Production",),
        require_mfa=True,
        reason="production needs MFA",
    ).to_dict()
    engine = PolicyEngine(VaultSettings(policy_rules=(rule,), require_reveal_before_copy=False, require_mfa_for_high_sensitivity=False))

    blocked = engine.evaluate("copy_secret", {"team_vault": "Production", "mfa_verified": False})
    allowed = engine.evaluate("copy_secret", {"team_vault": "Personal", "mfa_verified": False})

    assert not blocked.allowed
    assert blocked.code == "policy_pack_denied"
    assert allowed.allowed


def test_identity_directory_upsert_and_trusted_devices():
    directory = IdentityDirectory()
    directory = directory.upsert(DirectoryPrincipal(
        label="Ops", email="ops@example.com", role="admin",
        groups=("ops", "security"), trusted_devices=("ops-laptop", "yubikey-host"),
    ))

    principal = directory.list()[0]

    assert principal.email == "ops@example.com"
    assert principal.role == "admin"
    assert directory.trusted_device_ids() == ("ops-laptop", "yubikey-host")


def test_settings_json_roundtrip_preserves_policy_pack_lists_as_tuples(tmp_path):
    from ferrovault.application.services.settings import JsonSettingsStore

    settings = VaultSettings(policy_rules=(PolicyRule(
        rule_id="prod-share", name="No prod share", actions=("share_secret",), team_vaults=("Production",),
    ).to_dict(),))
    path = tmp_path / "settings.json"
    JsonSettingsStore(path).save(settings)

    loaded = JsonSettingsStore(path).load()

    assert loaded.policy_rules == settings.normalized().policy_rules
    assert json.loads(path.read_text())["policy_rules"][0]["team_vaults"] == ["Production"]
