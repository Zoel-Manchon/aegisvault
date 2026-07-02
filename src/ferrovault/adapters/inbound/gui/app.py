"""GUI entry point: wires Qt to the vault service and runs the app.

Inbound (driving) adapter, exactly like cli.py - it builds the same
VaultService from the composition root and drives it. Launch with
`aegisvault-gui` or `python -m ferrovault.adapters.inbound.gui.app`. Legacy `snekrust-gui` still works.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from .branding import ORG_NAME, PRODUCT_NAME
from .performance import StartupProfiler


def _load_fonts(app: QApplication) -> None:
    """Prefer the bundled UI font, then fall back to high-quality system fonts."""
    family = None
    for ttf in (Path(__file__).parent / "fonts").glob("*.ttf"):
        fid = QFontDatabase.addApplicationFont(str(ttf))
        families = QFontDatabase.applicationFontFamilies(fid)
        if families:
            family = families[0]
            break

    font = QFont(family or "Segoe UI Variable", 10)
    font.setHintingPreference(QFont.PreferFullHinting)
    app.setFont(font)


def _pump(app: QApplication) -> None:
    """Let the splash/progress window repaint between expensive startup phases."""
    app.processEvents()


def main(argv: list | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--qml" in argv:
        argv = [a for a in argv if a != "--qml"]
        from .qml_app import main as qml_main
        return qml_main(argv)

    vault_path = "vault.fv"
    if "--vault" in argv:
        vault_path = argv[argv.index("--vault") + 1]

    profiler = StartupProfiler()

    with profiler.span("QApplication"):
        app = QApplication(argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(ORG_NAME)

    with profiler.span("fonts"):
        _load_fonts(app)

    from .theme import STYLESHEET
    with profiler.span("stylesheet"):
        app.setStyleSheet(STYLESHEET)

    def service_factory():
        from ....container import build_vault_service
        with profiler.span("service"):
            return build_vault_service(vault_path)

    # Keep the pre-unlock path light. The main window imports most of the GUI
    # stack, so defer it until the user has successfully unlocked the vault.
    from .unlock_dialog import UnlockDialog
    unlock = UnlockDialog(service_factory, vault_path, profiler=profiler)
    profiler.mark("unlock-dialog-ready")
    if not unlock.exec() or unlock.session is None:
        return 0
    profiler.mark("vault-unlocked")

    from .splash import StartupSplash
    splash = StartupSplash(subtitle="Loading secure workspace…")
    splash.show()
    _pump(app)

    splash.set_status("Loading persistent desktop settings…")
    _pump(app)
    with profiler.span("settings-store-import"):
        from ....application.services.settings import JsonSettingsStore

    splash.set_status("Loading workspace components…")
    _pump(app)
    with profiler.span("main-window-import"):
        from .main_window import MainWindow

    splash.set_status("Rendering vault interface…")
    _pump(app)
    with profiler.span("main-window-build"):
        window = MainWindow(unlock.session, app.clipboard(), JsonSettingsStore())

    splash.set_status("Ready.")
    window.show()
    profiler.mark("main-window-shown")
    QTimer.singleShot(180, splash.close)
    profiler.mark("event-loop")
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
