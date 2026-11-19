"""Background GUI workers for expensive optional work.

The main startup path should only unlock, hydrate metadata, and render. Anything
that can wait—full password-health analysis, favicon warming, later sync/agent
checks—belongs here so Qt remains responsive.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal, Slot

from .favicon_policy import (
    background_favicon_prefetch_enabled,
    favicon_prefetch_limit,
    network_favicons_enabled,
)


@dataclass(frozen=True)
class WorkerResult:
    """Small structured result emitted by background workers."""

    ok: bool
    payload: Any = None
    error: str = ""


# Owners without a parent are kept here until their result is delivered:
# otherwise a caller that drops the return value of run_task() would lose it.
_UNPARENTED: set = set()


class _WorkerThread(QObject):
    """Small owner object that keeps a QThread and worker alive.

    The result is delivered through ``_deliver``, a slot of this object, which
    lives on the GUI thread: Qt then queues the call there. Connecting the
    worker's signal straight to a plain function would run it on the worker
    thread, and touching widgets from there crashes Qt.

    The QThread itself belongs to the application, not to ``parent``: Qt
    aborts the process when a running QThread is destroyed, which is what
    would happen if the window that started a key derivation or a health
    scan were closed mid-task. Closing that window deletes this owner, so the
    result is dropped instead of reaching a dead widget.
    """

    def __init__(self, worker: QObject, run_slot, on_finished, parent: QObject | None = None):
        super().__init__(parent)
        self._on_finished = on_finished
        if parent is None:
            _UNPARENTED.add(self)
        self.thread = QThread(QCoreApplication.instance())
        self.worker = worker
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(run_slot)
        worker.finished.connect(self._deliver)
        worker.finished.connect(self.thread.quit)
        worker.finished.connect(worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.deleteLater)

    @Slot(object)
    def _deliver(self, result) -> None:
        try:
            self._on_finished(result)
        finally:
            _UNPARENTED.discard(self)

    def start(self) -> None:
        self.thread.start()


class TaskWorker(QObject):
    """Run one callable outside the GUI thread (key derivation, re-sealing)."""

    finished = Signal(object)

    def __init__(self, fn):
        super().__init__()
        self._fn = fn

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(WorkerResult(True, self._fn()))
        except Exception as exc:  # noqa: BLE001 - handed to the GUI, which explains it
            self.finished.emit(WorkerResult(False, payload=exc, error=str(exc) or exc.__class__.__name__))
        finally:
            self._fn = None


def wait_for_workers(timeout_ms: int = 10_000) -> None:
    """Let running workers finish before the application object goes away."""
    app = QCoreApplication.instance()
    if app is None:
        return
    for thread in app.findChildren(QThread):
        try:
            if thread.isRunning():
                thread.wait(timeout_ms)
        except RuntimeError:
            pass  # already deleted


def run_task(fn, on_finished, *, parent: QObject | None = None) -> "_WorkerThread":
    """Run ``fn()`` on a QThread; ``on_finished(WorkerResult)`` runs on the GUI thread."""
    worker = TaskWorker(fn)
    owner = _WorkerThread(worker, worker.run, on_finished, parent)
    owner.start()
    return owner


class HealthScanWorker(QObject):
    """Run the full password health analyzer outside the GUI thread."""

    finished = Signal(object)

    def __init__(self, session, breach_checker=None, old_after_days: int | None = None):
        super().__init__()
        self._session = session
        self._breach_checker = breach_checker
        self._old_after_days = old_after_days

    def run(self) -> None:
        try:
            report = self._session.health_report(self._breach_checker, old_after_days=self._old_after_days)
            self.finished.emit(WorkerResult(True, report))
        except Exception as exc:  # noqa: BLE001 - surfaced to the GUI as status text
            self.finished.emit(WorkerResult(False, error=str(exc)))


class FaviconPrefetchWorker(QObject):
    """Warm favicon cache files in the background.

    It never creates QPixmap/QIcon objects; those stay on the GUI thread.
    """

    finished = Signal(object)

    def __init__(self, urls: Iterable[str], *, limit: int | None = None, fetch: bool | None = None):
        super().__init__()
        self._urls = tuple(urls)
        self._limit = favicon_prefetch_limit() if limit is None else limit
        self._fetch = network_favicons_enabled() if fetch is None else fetch

    def run(self) -> None:
        try:
            from .favicons import prefetch_favicon_files

            self.finished.emit(WorkerResult(True, prefetch_favicon_files(
                self._urls,
                limit=self._limit,
                fetch=self._fetch,
            )))
        except Exception as exc:  # noqa: BLE001
            self.finished.emit(WorkerResult(False, error=str(exc)))


def start_health_scan(session, on_finished, *, breach_checker=None, parent: QObject | None = None,
                      old_after_days: int | None = None) -> _WorkerThread:
    worker = HealthScanWorker(session, breach_checker, old_after_days)
    owner = _WorkerThread(worker, worker.run, on_finished, parent)
    owner.start()
    return owner


def start_favicon_prefetch(urls: Iterable[str], on_finished=None, *, parent: QObject | None = None) -> _WorkerThread | None:
    """Start favicon cache warmup only when explicitly enabled.

    Default behavior remains offline/instant. Set AEGISVAULT_PREFETCH_FAVICONS=1
    to warm local cache and AEGISVAULT_FETCH_FAVICONS=1 to allow network fetches.
    """

    if not background_favicon_prefetch_enabled():
        return None

    def _noop(_result):
        return None

    worker = FaviconPrefetchWorker(tuple(urls))
    owner = _WorkerThread(worker, worker.run, on_finished or _noop, parent)
    owner.start()
    return owner
