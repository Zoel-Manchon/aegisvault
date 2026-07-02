"""Experimental Qt Quick/QML command-center entry point.

This does not replace the production Qt Widgets GUI yet.  It proves the QML
migration path for motion-heavy surfaces: command palette, animated security
score, and live audit stream.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtQml import QQmlApplicationEngine

from .branding import ORG_NAME, PRODUCT_NAME
from .performance import StartupProfiler


def main(argv: list | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    vault_path = "vault.fv"
    if "--vault" in argv:
        vault_path = argv[argv.index("--vault") + 1]

    profiler = StartupProfiler()
    with profiler.span("QApplication"):
        app = QApplication(argv)
    app.setApplicationName(f"{PRODUCT_NAME} QML")
    app.setOrganizationName(ORG_NAME)

    from ....container import build_vault_service
    from .unlock_dialog import UnlockDialog
    from .qml_bridge import QmlVaultBridge

    with profiler.span("service"):
        service = build_vault_service(vault_path)
    unlock = UnlockDialog(service, vault_path, profiler=profiler)
    if not unlock.exec() or unlock.session is None:
        return 0
    profiler.mark("vault-unlocked")

    bridge = QmlVaultBridge(unlock.session)
    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("vaultBridge", bridge)
    qml_path = Path(__file__).parent / "qml" / "AegisVaultCommandCenter.qml"
    with profiler.span("qml-engine"):
        engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
