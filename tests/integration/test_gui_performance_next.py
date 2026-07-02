from ferrovault.adapters.inbound.gui.favicon_policy import (
    background_favicon_prefetch_enabled,
    favicon_prefetch_limit,
    network_favicons_enabled,
)
from ferrovault.adapters.inbound.gui.performance import background_health_warmup_enabled
from ferrovault.adapters.inbound.gui.view_models.command_palette import DEFAULT_ACTIONS


def test_favicon_prefetch_env_flags(monkeypatch):
    monkeypatch.delenv("AEGISVAULT_PREFETCH_FAVICONS", raising=False)
    monkeypatch.delenv("AEGISVAULT_FETCH_FAVICONS", raising=False)
    assert not background_favicon_prefetch_enabled()
    assert not network_favicons_enabled()

    monkeypatch.setenv("AEGISVAULT_PREFETCH_FAVICONS", "1")
    monkeypatch.setenv("AEGISVAULT_FETCH_FAVICONS", "true")
    assert background_favicon_prefetch_enabled()
    assert network_favicons_enabled()


def test_favicon_prefetch_limit_is_bounded(monkeypatch):
    monkeypatch.setenv("AEGISVAULT_FAVICON_PREFETCH_LIMIT", "999999")
    assert favicon_prefetch_limit() == 500
    monkeypatch.setenv("AEGISVAULT_FAVICON_PREFETCH_LIMIT", "bad")
    assert favicon_prefetch_limit(12) == 12


def test_background_health_warmup_can_be_disabled(monkeypatch):
    monkeypatch.delenv("AEGISVAULT_DISABLE_HEALTH_WARMUP", raising=False)
    assert background_health_warmup_enabled()
    monkeypatch.setenv("AEGISVAULT_DISABLE_HEALTH_WARMUP", "yes")
    assert not background_health_warmup_enabled()


def test_quick_guide_is_in_command_palette():
    ids = {action.id for action in DEFAULT_ACTIONS}
    assert "action:guide" in ids
