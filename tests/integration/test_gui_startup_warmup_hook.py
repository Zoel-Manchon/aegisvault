from pathlib import Path


def test_main_window_health_warmup_hook_exists():
    source = Path("src/ferrovault/adapters/inbound/gui/main_window.py").read_text()
    assert "QTimer.singleShot(900, self._start_background_health_warmup)" in source
    assert "def _start_background_health_warmup(self):" in source


def test_health_warmup_hook_respects_disable_env():
    source = Path("src/ferrovault/adapters/inbound/gui/main_window.py").read_text()
    method = source.split("def _start_background_health_warmup(self):", 1)[1].split("def _schedule_filter", 1)[0]
    assert "background_health_warmup_enabled" in method
    assert "return" in method
    assert "start_health_scan" in method
