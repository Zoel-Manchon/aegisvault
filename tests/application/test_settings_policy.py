from ferrovault.application.services.policy import PolicyEngine
from ferrovault.application.services.settings import JsonSettingsStore, VaultSettings


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "settings.json"
    store = JsonSettingsStore(path)
    original = VaultSettings(
        clipboard_clear_seconds=7,
        auto_lock_seconds=60,
        require_reveal_before_copy=False,
        show_health_sidebar=False,
        enterprise_sync_enabled=True,
        policy_enforcement_enabled=True,
        require_totp_for_shared=False,
        block_export_when_audit_broken=False,
    )
    store.save(original)

    loaded = store.load()

    assert loaded == original.normalized()


def test_policy_requires_reveal_before_copy():
    engine = PolicyEngine(VaultSettings(require_reveal_before_copy=True))

    blocked = engine.evaluate("copy_secret", {"revealed": False})
    allowed = engine.evaluate("copy_secret", {"revealed": True})

    assert not blocked.allowed
    assert blocked.code == "reveal_required"
    assert allowed.allowed


def test_policy_blocks_sharing_without_totp_when_enabled():
    engine = PolicyEngine(VaultSettings(require_totp_for_shared=True))

    blocked = engine.evaluate("share_secret", {"has_totp": False})
    allowed = engine.evaluate("share_secret", {"has_totp": True})

    assert not blocked.allowed
    assert blocked.code == "totp_required"
    assert allowed.allowed


def test_policy_can_run_in_monitor_mode():
    engine = PolicyEngine(VaultSettings(policy_enforcement_enabled=False))

    assert engine.evaluate("copy_secret", {"revealed": False}).allowed
    assert engine.evaluate("share_secret", {"has_totp": False}).allowed
    assert engine.evaluate("export_audit", {"audit_ok": False}).allowed
