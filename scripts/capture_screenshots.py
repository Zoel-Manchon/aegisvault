"""Regenerate the README screenshots in docs/screenshots from a throwaway vault.

    python scripts/capture_screenshots.py

Everything runs offscreen (no window appears) on a temporary vault filled with
made-up entries and people, so no real secret can end up in a picture, and the
settings folder is sandboxed so the user's own preferences are never read or
written. Each dialog is drawn over its dimmed window, the way it looks in the
app. The dark set is captured first; the light-theme shot runs in a second
process because the palette is fixed when the theme module is imported.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from datetime import timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "screenshots"
LIGHT = "--light" in sys.argv
SANDBOX = Path(tempfile.mkdtemp(prefix="aegisvault-shots-"))

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["AEGISVAULT_THEME"] = "light" if LIGHT else "dark"
os.environ["APPDATA"] = str(SANDBOX / "appdata")
os.environ["LOCALAPPDATA"] = str(SANDBOX / "localappdata")
os.environ["XDG_CONFIG_HOME"] = str(SANDBOX / "config")
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPoint  # noqa: E402
from PySide6.QtGui import QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

app = QApplication(["aegisvault-screenshots"])

from ferrovault.adapters.inbound.gui.theme import application_stylesheet  # noqa: E402
from ferrovault.adapters.inbound.gui.typography import load_fonts  # noqa: E402

load_fonts(app)
app.setStyleSheet(application_stylesheet())

from ferrovault.adapters.inbound.gui.main_window import MainWindow  # noqa: E402
from ferrovault.adapters.outbound.sharing.sealed_box import generate_keypair  # noqa: E402
from ferrovault.application.services.directory import DirectoryPrincipal, IdentityDirectory  # noqa: E402
from ferrovault.application.services.settings import MemorySettingsStore, VaultSettings  # noqa: E402
from ferrovault.container import build_vault_service  # noqa: E402

PASSWORD = "tinta marfil cobre lince 1984"   # protects a vault that is deleted afterwards


def pump(seconds: float = 0.3) -> None:
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.01)


def _cut_short(widget) -> list:
    return [lbl for lbl in widget.findChildren(QLabel)
            if lbl.isVisible() and lbl.text() and not lbl.wordWrap() and lbl.width() < lbl.sizeHint().width() - 1]


def settle(*widgets, timeout: float = 3.0) -> None:
    """Let layouts catch up with the last text changes before grabbing.

    grab() paints at once, while a label that just got longer is resized on a
    later turn of the event loop; on screen the layout always runs first.
    """
    pump(0.3)
    end = time.monotonic() + timeout
    while time.monotonic() < end and any(_cut_short(widget) for widget in widgets):
        pump(0.05)


def save(pixmap, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pixmap.toImage().save(str(OUT / f"{name}.png"), "PNG", 0)   # 0 = smallest file
    print(f"docs/screenshots/{name}.png")


def over_window(window, dialog, name: str, prepare=None) -> None:
    """The dialog and the scrim it lays over its window, as one picture."""
    dialog.show()
    pump()
    if prepare is not None:
        prepare(dialog)
    settle(window, dialog)
    base = window.grab()
    shot = dialog.grab()
    offset = dialog.mapToGlobal(QPoint(0, 0)) - window.mapToGlobal(QPoint(0, 0))
    if not base.rect().contains(offset):
        offset = QPoint((base.width() - shot.width()) // 2, (base.height() - shot.height()) // 2)
    painter = QPainter(base)
    painter.drawPixmap(offset, shot)
    painter.end()
    save(base, name)
    dialog.done(0) if hasattr(dialog, "done") else dialog.close()
    pump(0.1)


def sample_vault(path: Path):
    service = build_vault_service(str(path))
    service.init_vault(PASSWORD)
    session = service.unlock(PASSWORD)
    session.add("GitHub", "ana.ruiz@estudio.dev", "vX9#qL2m!Tz7@wR4kP8e", url="https://github.com",
                category="Trabajo", totp="JBSWY3DPEHPK3PXP", tags=("desarrollo", "sso"))
    session.add("GitLab interno", "ana", "verano2019", url="https://gitlab.estudio.dev", category="Trabajo")
    session.add("Jira", "ana.ruiz", "verano2019", url="https://estudio.atlassian.net", category="Trabajo")
    session.add("Hotmail antiguo", "ana_r@hotmail.com", "ana1985", url="https://outlook.live.com",
                category="Personal")
    # deliberately no vendor prefix: a realistic-looking key would trip secret scanners
    session.add("Stripe · API", "acct_live", "demo_key_7Hk2Pq9xLm3vR8sT4wQ1nB6c", category="Trabajo",
                kind="api_key")
    session.add("Dropbox", "ana@estudio.dev", "Kq8!mZ2#pL9@xW4r", url="https://dropbox.com", category="Personal")
    session.add("Wifi casa", "", "Router: casa-5G\nClave: 7Hk2-Pq9x-Lm3v", kind="note", category="Personal")
    session.toggle_favorite("GitHub")
    _private, luis = generate_keypair()
    session.share_public_key("GitHub", "Luis Gómez", luis, actor="Ana Ruiz", expires_in=timedelta(days=7))
    directory = IdentityDirectory(()).upsert(
        DirectoryPrincipal(label="Luis Gómez", email="luis@estudio.dev", public_key=luis, role="member"))
    directory = directory.upsert(DirectoryPrincipal(label="Marta Ruiz", email="marta@estudio.dev",
                                                    public_key=generate_keypair()[1], role="admin"))
    settings = VaultSettings(recipient_directory=tuple(directory.to_list()),
                             enterprise_display_name="Ana Ruiz", enterprise_role="owner")
    return service, session, settings


def capture_dark(path: Path) -> None:
    from ferrovault.adapters.inbound.gui.screens.palette import CommandPalette
    from ferrovault.adapters.inbound.gui.screens.shamir import EnrollShamirDialog
    from ferrovault.adapters.inbound.gui.screens.share import ShareDialog
    from ferrovault.adapters.inbound.gui.screens.unlock import UnlockWindow

    service, session, settings = sample_vault(path)
    window = MainWindow(session, app.clipboard(), MemorySettingsStore(settings), vault_path=str(path))
    window.resize(1440, 900)
    window.show()
    pump(0.6)
    window.list.setCurrentRow(0)
    settle(window)
    save(window.grab(), "vault")

    views = session.entries()
    github = next(view for view in views if view.name == "GitHub")
    over_window(window, CommandPalette(window, views, lambda *_: None), "palette",
                lambda palette: palette.search.setText("git"))
    over_window(window, ShareDialog(session, github, window._settings, window), "share")
    over_window(window, EnrollShamirDialog(session, "personal", window), "shamir")

    window._open_health()
    settle(window)
    save(window.grab(), "health")
    window._open_audit(verify=True)
    settle(window)
    save(window.grab(), "audit")
    window.lock_now("manual")
    window.close()
    pump(0.1)

    front = UnlockWindow(VaultSettings(), path)
    front.resize(1200, 780)
    front.show()
    settle(front)
    save(front.grab(), "unlock")
    front.close()


def capture_light(path: Path) -> None:
    _service, session, settings = sample_vault(path)
    window = MainWindow(session, app.clipboard(), MemorySettingsStore(settings), vault_path=str(path))
    window.resize(1440, 900)
    window.show()
    pump(0.6)
    window.list.setCurrentRow(0)
    settle(window)
    save(window.grab(), "vault-light")
    window.lock_now("manual")
    window.close()


def main() -> int:
    vault = SANDBOX / "vaults" / "personal.avault"
    vault.parent.mkdir(parents=True)
    if LIGHT:
        capture_light(vault)
        return 0
    capture_dark(vault)
    return subprocess.run([sys.executable, __file__, "--light"]).returncode


if __name__ == "__main__":
    try:
        code = main()
    finally:
        for widget in QApplication.topLevelWidgets():   # see gui/app.py: never leave windows to shutdown
            widget.deleteLater()
        from PySide6.QtCore import QEvent
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        import shutil
        shutil.rmtree(SANDBOX, ignore_errors=True)       # the throwaway vault and settings
    raise SystemExit(code)
