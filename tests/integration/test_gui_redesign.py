"""Behaviour of the redesigned GUI that protects the user (offscreen Qt).

Unlock throttling, wiping typed passwords, discarding a cancelled unlock, the
master-password floor on create, workers that outlive their window, the
command palette's search rules and the stylesheet rules that keep disabled
destructive buttons from looking clickable.
"""
import os
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")
pytest.importorskip("cryptography")

from PySide6.QtCore import QEvent                                               # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QWidget                      # noqa: E402

from ferrovault.adapters.outbound.clock.system_clock import SystemClock          # noqa: E402
from ferrovault.adapters.outbound.crypto.aesgcm_cipher import AesGcmCipher       # noqa: E402
from ferrovault.adapters.outbound.crypto.scrypt_kdf import ScryptKeyDerivation    # noqa: E402
from ferrovault.adapters.outbound.storage.file_repository import FileVaultRepository  # noqa: E402
from ferrovault.application.services.settings import VaultSettings                # noqa: E402
from ferrovault.application.services.vault_service import VaultService            # noqa: E402

_app = QApplication.instance() or QApplication([])

from ferrovault.adapters.inbound.gui.background import run_task, wait_for_workers  # noqa: E402
from ferrovault.adapters.inbound.gui.components.kit import mono_font             # noqa: E402
from ferrovault.adapters.inbound.gui.fmt import starter_rule_text               # noqa: E402
from ferrovault.adapters.inbound.gui.screens import palette                       # noqa: E402
from ferrovault.adapters.inbound.gui.screens.unlock import (                      # noqa: E402
    FAILS_BEFORE_WAIT, UnlockWindow, _params_text, lock_message,
)
from ferrovault.adapters.inbound.gui.theme import STYLESHEET                       # noqa: E402

GOOD = "tinta marfil cobre lince 1984"


def _factory(path):
    return VaultService(FileVaultRepository(path), ScryptKeyDerivation(), AesGcmCipher(), SystemClock())


def _wait(cond, timeout=30.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        _app.processEvents()
        if cond():
            return True
        time.sleep(0.01)
    return False


def _window(path, **kwargs):
    window = UnlockWindow(VaultSettings(), path, service_factory=_factory, **kwargs)
    window.show()
    _app.processEvents()
    return window


@pytest.fixture
def vault_path(tmp_path):
    path = str(tmp_path / "personal.avault")
    service = _factory(path)
    service.init_vault(GOOD)
    return path


# ---- unlock ---------------------------------------------------------------------------------
def test_wrong_passwords_are_counted_and_then_throttled(vault_path):
    window = _window(vault_path)
    opened = []
    window.unlocked.connect(lambda *args: opened.append(args))
    for attempt in range(1, FAILS_BEFORE_WAIT + 1):
        window._password.setText(f"wrong-{attempt}")
        window._unlock()
        assert window._password.text() == "", "the typed password must leave the field once submitted"
        assert _wait(lambda: not window._busy)
        assert window._fails == attempt
    assert not opened
    assert not window._go.isEnabled()
    assert window._go.label_text().startswith("Espera")
    window._password.setText(GOOD)
    window._unlock()
    assert not window._busy, "no attempt may start while the wait runs"
    window._wait_until = 0.0
    window._update_wait()
    window._password.setText(GOOD)
    window._unlock()
    assert _wait(lambda: opened)
    session, path, created = opened[0]
    assert path == vault_path and created is False
    session.lock()
    window.close()


def test_a_cancelled_unlock_is_discarded_and_its_session_locked(vault_path):
    window = _window(vault_path)
    opened = []
    window.unlocked.connect(lambda *args: opened.append(args))
    arrived = []
    original = window._finished

    def spy(result, mode):
        arrived.append(result)
        original(result, mode)

    window._finished = spy
    window._password.setText(GOOD)
    window._unlock()
    window._cancel()
    assert not window._busy and window._mode == "open"
    assert _wait(lambda: arrived)
    assert not opened, "a cancelled unlock must not open the vault"
    assert arrived[0].ok and arrived[0].payload[0].is_locked
    window.close()


def test_create_needs_a_strong_repeated_password_and_the_acknowledgement(tmp_path):
    target = tmp_path / "nueva.avault"
    window = _window(target)
    assert window._mode == "create"
    window._new_folder = tmp_path
    window._new_name.setText("nueva.avault")
    window._new.password.setText("verano2019")
    window._new.confirm.setText("verano2019")
    window._understood.setChecked(True)
    assert not window._go.isEnabled(), "a weak master password must be refused"
    window._new.password.setText(GOOD)
    window._new.confirm.setText(GOOD + "x")
    assert not window._go.isEnabled(), "the repeat must match"
    window._new.confirm.setText(GOOD)
    window._understood.setChecked(False)
    assert not window._go.isEnabled(), "the user must acknowledge there is no reset"
    window._understood.setChecked(True)
    assert window._go.isEnabled()
    created = []
    window.unlocked.connect(lambda *args: created.append(args))
    window._create()
    assert window._new.password.text() == "" and window._new.confirm.text() == ""
    assert _wait(lambda: created)
    session, path, was_created = created[0]
    assert was_created and os.path.isfile(path)
    session.lock()
    window.close()


def test_lock_messages_and_kdf_parameters_read_well():
    assert lock_message("idle") == "Se bloqueó por inactividad."
    assert lock_message("manual", clipboard_cleared=True).endswith("Portapapeles vaciado.")
    assert lock_message("screen-lock") != lock_message("unknown-reason")
    assert _params_text({"kdf": "Argon2id", "params": "Argon2id · m=256 MiB · t=3 · p=4"}) == \
        "m = 256 MiB · t = 3 · p = 4"


# ---- workers ---------------------------------------------------------------------------------
def test_a_worker_outlives_the_window_that_started_it():
    owner = QWidget()
    calls = []
    run_task(lambda: time.sleep(0.2) or "done", calls.append, parent=owner)
    owner.deleteLater()            # the window closes while the task runs
    QApplication.sendPostedEvents(None, QEvent.DeferredDelete)   # what the event loop would do
    wait_for_workers(5000)         # no "QThread destroyed while running" abort
    _wait(lambda: False, timeout=0.1)
    assert calls == [], "a result must not reach a widget that is gone"


def test_a_worker_reports_failures_with_the_exception():
    results = []

    def boom():
        raise ValueError("mal")

    run_task(boom, results.append)
    assert _wait(lambda: results)
    assert results[0].ok is False and isinstance(results[0].payload, ValueError)


# ---- command palette ----------------------------------------------------------------------------
class _View:
    def __init__(self, name, username="", updated_at="2026-01-01", deleted=False):
        self.name, self.username, self.updated_at, self.deleted = name, username, updated_at, deleted
        self.url, self.kind, self.category, self.tags = "", "login", "", ()


def test_palette_search_ignores_case_and_accents_and_never_lists_the_trash():
    views = [_View("Bóveda familiar"), _View("GitHub", "ana"), _View("Vieja", deleted=True)]
    entries = palette.entry_commands(views)
    assert [c.label for c in entries] == ["Bóveda familiar", "GitHub"] or \
        {c.label for c in entries} == {"Bóveda familiar", "GitHub"}
    acts = palette.actions("dark")
    hits = palette.search(entries, acts, "BOVEDA")
    assert hits and hits[0].label == "Bóveda familiar"
    only_actions = palette.search(entries, acts, ">")
    assert only_actions and all(c.command_id != "entry" for c in only_actions)
    first = palette.search(entries, acts, "")
    assert sum(c.command_id == "entry" for c in first) <= palette.RECENT


def test_palette_caps_entry_results():
    views = [_View(f"Cuenta {i}") for i in range(30)]
    hits = palette.search(palette.entry_commands(views), palette.actions("dark"), "cuenta")
    assert sum(c.command_id == "entry" for c in hits) == palette.MAX_ENTRIES


# ---- stylesheet ---------------------------------------------------------------------------------
def test_disabled_destructive_buttons_have_their_own_look():
    for kind in ("danger", "dangerSolid", "primary", "ghost"):
        assert f"QPushButton#{kind}:disabled" in STYLESHEET


def test_explicit_font_sizes_survive_the_stylesheet():
    host = QWidget()
    host.setStyleSheet(STYLESHEET)
    tile = QLabel("9AB1", host)
    tile.setFont(mono_font(16, 500))
    host.show()
    _app.processEvents()
    assert tile.font().pixelSize() == 16
    host.close()


def test_starter_policy_rules_are_shown_in_spanish_unless_renamed():
    assert starter_rule_text("Critical audit export guard") == "Sin exportar auditoría de lo crítico"
    assert starter_rule_text("Mi regla") == "Mi regla"
    assert starter_rule_text("") == ""
