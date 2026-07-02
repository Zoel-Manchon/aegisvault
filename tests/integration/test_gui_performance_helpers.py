from __future__ import annotations

from ferrovault.adapters.inbound.gui.performance import StartupProfiler


def test_startup_profiler_is_noop_when_disabled(capsys):
    profiler = StartupProfiler(enabled=False)
    profiler.mark("ignored")
    with profiler.span("ignored-span"):
        pass
    assert capsys.readouterr().out == ""


def test_favicon_network_fetch_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("AEGISVAULT_FETCH_FAVICONS", raising=False)
    from ferrovault.adapters.inbound.gui.favicon_policy import network_favicons_enabled

    assert network_favicons_enabled() is False


def test_favicon_network_fetch_is_opt_in(monkeypatch):
    monkeypatch.setenv("AEGISVAULT_FETCH_FAVICONS", "1")
    from ferrovault.adapters.inbound.gui.favicon_policy import network_favicons_enabled

    assert network_favicons_enabled() is True
