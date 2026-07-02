"""Background GUI workers for expensive optional work.

The main startup path should only unlock, hydrate metadata, and render. Anything
that can wait—full password-health analysis, favicon warming, later sync/agent
checks—belongs here so Qt remains responsive.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, QThread, Signal

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


class _WorkerThread(QObject):
    """Small owner object that keeps a QThread and worker alive."""

    def __init__(self, worker: QObject, run_slot, on_finished, parent: QObject | None = None):
        super().__init__(parent)
        self.thread = QThread(parent)
        self.worker = worker
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(run_slot)
        worker.finished.connect(on_finished)
        worker.finished.connect(self.thread.quit)
        worker.finished.connect(worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.deleteLater)

    def start(self) -> None:
        self.thread.start()


class HealthScanWorker(QObject):
    """Run the full password health analyzer outside the GUI thread."""

    finished = Signal(object)

    def __init__(self, session, breach_checker=None):
        super().__init__()
        self._session = session
        self._breach_checker = breach_checker

    def run(self) -> None:
        try:
            self.finished.emit(WorkerResult(True, self._session.health_report(self._breach_checker)))
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


def start_health_scan(session, on_finished, *, breach_checker=None, parent: QObject | None = None) -> _WorkerThread:
    worker = HealthScanWorker(session, breach_checker)
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
