"""GUI entry point: splash → unlock (or create) → workspace, and back on lock.

Inbound (driving) adapter, exactly like cli.py: it builds the same
VaultService from the composition root and drives it. Launch with
``aegisvault-gui`` or ``python -m ferrovault.adapters.inbound.gui.app``.
``--vault PATH`` opens a given file; ``--qml`` starts the experimental QML shell
where Qt Quick is installed (the Windows .exe leaves it out and opens the regular window).
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from PySide6.QtCore import QEvent, QRect, Qt, QTimer
from PySide6.QtWidgets import QApplication, QWidget

from .branding import ORG_NAME, PRODUCT_NAME
from .performance import StartupProfiler

SPLASH_MIN_S = 0.35
FRONT_SIZE = (1200, 780)
SHELL_SIZE = (1440, 900)
APP_USER_MODEL_ID = "AegisVault.Desktop"


def _choose_theme(app: QApplication, theme: str) -> None:
    """theme.py fixes the palette when it is imported, so decide it first."""
    if os.environ.get("AEGISVAULT_THEME"):
        return
    mode = (theme or "dark").strip().lower()
    if mode == "system":
        try:
            mode = "light" if app.styleHints().colorScheme() == Qt.ColorScheme.Light else "dark"
        except AttributeError:
            mode = "dark"
    os.environ["AEGISVAULT_THEME"] = mode if mode in ("dark", "light") else "dark"


def _match_window_frame(app: QApplication) -> None:
    """Title bars in the app's theme rather than the Windows one (Qt 6.8+)."""
    light = os.environ.get("AEGISVAULT_THEME", "dark").strip().lower() == "light"
    try:
        app.styleHints().setColorScheme(Qt.ColorScheme.Light if light else Qt.ColorScheme.Dark)
    except AttributeError:
        pass  # older Qt: the frame keeps following the Windows setting


def _place(window: QWidget, size: tuple[int, int], around: QRect | None = None) -> None:
    """Size a top-level window to fit the screen and centre it (on ``around`` if given)."""
    screen = window.screen() or QApplication.primaryScreen()
    area = screen.availableGeometry() if screen is not None else QRect(0, 0, *size)
    width = min(size[0], area.width() - 40)
    height = min(size[1], area.height() - 40)
    window.resize(max(width, window.minimumWidth()), max(height, window.minimumHeight()))
    centre = around.center() if around is not None else area.center()
    frame = window.frameGeometry()
    frame.moveCenter(centre)
    x = min(max(frame.left(), area.left()), max(area.left(), area.right() - frame.width()))
    y = min(max(frame.top(), area.top()), max(area.top(), area.bottom() - frame.height()))
    window.move(x, y)


class _Controller:
    """Owns the one visible window and swaps it on unlock and on lock."""

    def __init__(self, app: QApplication, store, profiler: StartupProfiler):
        self.app = app
        self.store = store
        self.profiler = profiler
        self.front = None   # UnlockWindow
        self.shell = None   # MainWindow

    # ---- front door ---------------------------------------------------------------
    def show_unlock(self, path: str | Path | None, message: str = "", around: QRect | None = None,
                    choose: bool = False) -> None:
        from .screens.unlock import UnlockWindow
        settings = self.store.load()
        window = UnlockWindow(settings, path, message=message)
        window.setMinimumSize(980, 640)
        window.unlocked.connect(self._on_unlocked)
        _place(window, FRONT_SIZE, around)
        window.show()
        window.raise_()
        window.activateWindow()
        self.front = window
        if choose:
            QTimer.singleShot(0, window.choose_file)

    def _on_unlocked(self, session, path: str, created: bool) -> None:
        self.profiler.mark("vault-unlocked")
        settings = self.store.load()
        if settings.last_vault_path != path:
            from dataclasses import replace
            try:
                self.store.save(replace(settings, last_vault_path=path))
            except OSError:
                pass  # remembering the path is a convenience, never a reason to fail
        with self.profiler.span("main-window-build"):
            from .main_window import MainWindow
            shell = MainWindow(session, self.app.clipboard(), self.store, vault_path=path)
        shell.on_locked = self._on_locked
        front, self.front = self.front, None
        chain_ok = getattr(front, "chain_ok", True)
        _place(shell, SHELL_SIZE, front.frameGeometry() if front is not None else None)
        shell.show()
        shell.raise_()
        shell.activateWindow()
        self.shell = shell
        self.profiler.mark("main-window-shown")
        if front is not None:
            front.close()
            front.deleteLater()
        if not chain_ok:
            shell._toasts.show(
                "La cadena de auditoría no cuadra", "Alguien o algo modificó el historial de este archivo.",
                tone="danger", icon_name="link-broken", action_text="Ver auditoría",
                on_action=lambda: shell._open_audit(verify=True), timeout_ms=60000, key="chain-broken")
        if created:
            QTimer.singleShot(700, lambda: self._offer_shamir(shell))

    @staticmethod
    def _offer_shamir(shell) -> None:
        try:
            shell._toasts.show(
                "Bóveda creada", "Si olvidas la contraseña, solo los fragmentos Shamir la abren.",
                tone="success", icon_name="shamir", action_text="Crear fragmentos",
                on_action=shell._enroll_recovery, timeout_ms=30000, key="shamir-offer")
        except RuntimeError:
            pass  # the window locked before the offer appeared

    def _on_locked(self, reason: str) -> None:
        from .screens.unlock import lock_message
        shell, self.shell = self.shell, None
        if shell is None:
            return
        _reason, cleared = getattr(shell, "_last_lock", (reason, False))
        path = getattr(shell, "_vault_path", "") or None
        self.show_unlock(path, lock_message(reason, cleared), around=shell.frameGeometry(),
                         choose=(reason == "switch"))
        shell.on_locked = None
        shell.close()
        shell.deleteLater()

    def shutdown(self) -> None:
        """On quit, make sure no key outlives the process's last event."""
        shell, self.shell = self.shell, None
        if shell is not None:
            shell.on_locked = None
            try:
                shell.lock_now("quit")
            except RuntimeError:
                pass
        from .background import wait_for_workers
        wait_for_workers()


def _set_windows_app_id() -> None:
    """Group the windows under AegisVault on the taskbar instead of under python.exe."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except (AttributeError, OSError):
        pass  # cosmetic: an older shell simply keeps the default grouping


def _start_path(argv: list[str], settings) -> Path:
    from .screens.unlock import default_vault_path
    if "--vault" in argv:
        index = argv.index("--vault")
        if index + 1 < len(argv):
            return Path(argv[index + 1]).expanduser()
    last = (settings.last_vault_path or "").strip()
    if last and Path(last).is_file():
        return Path(last)
    return default_vault_path()


def main(argv: list | None = None) -> int:
    argv = list(sys.argv if argv is None else argv)
    if "--qml" in argv:
        argv = [a for a in argv if a != "--qml"]
        try:
            from .qml_app import main as qml_main
        except ImportError:
            qml_main = None  # builds without Qt Quick (the Windows .exe) open the regular window
        if qml_main is not None:
            return qml_main(argv)

    _set_windows_app_id()
    profiler = StartupProfiler()
    with profiler.span("QApplication"):
        app = QApplication(argv)
    app.setApplicationName(PRODUCT_NAME)
    app.setOrganizationName(ORG_NAME)
    from .app_icon import app_icon
    app.setWindowIcon(app_icon())

    from ....application.services.settings import JsonSettingsStore
    store = JsonSettingsStore()
    settings = store.load()
    _choose_theme(app, settings.theme)
    _match_window_frame(app)

    with profiler.span("fonts"):
        from .typography import load_fonts
        load_fonts(app)
    with profiler.span("stylesheet"):
        from .focus_ring import FocusRingFilter
        from .theme import application_stylesheet
        app.setStyleSheet(application_stylesheet())
        app.installEventFilter(FocusRingFilter(app))

    from .... import __version__
    from .screens.unlock import Splash, run_startup_checks
    path = _start_path(argv, settings)
    started = time.monotonic()
    splash = Splash(__version__, offline=not settings.breach_check_online)
    splash.setMinimumSize(980, 640)
    _place(splash, FRONT_SIZE)
    splash.show()
    app.processEvents()
    facts = run_startup_checks(splash, path, app.processEvents)
    profiler.mark("splash-checks")

    controller = _Controller(app, store, profiler)
    app.aboutToQuit.connect(controller.shutdown)

    def leave_splash() -> None:
        controller.show_unlock(path, facts.get("problem", ""), around=splash.frameGeometry())
        splash.close()
        splash.deleteLater()
        profiler.mark("unlock-ready")

    QTimer.singleShot(max(0, int((SPLASH_MIN_S - (time.monotonic() - started)) * 1000)), leave_splash)
    profiler.mark("event-loop")
    code = app.exec()
    controller.front = controller.shell = None
    _destroy_windows()
    return code


def _destroy_windows() -> None:
    """Delete every window while Qt and Python are both still fully alive.

    Left to interpreter shutdown, a closed window could be destroyed after the
    QApplication it belongs to, and the process crashed on exit about half the
    time. A crash is worse than untidy here: it can leave a memory dump behind.
    """
    for widget in QApplication.topLevelWidgets():
        widget.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


if __name__ == "__main__":
    raise SystemExit(main())
