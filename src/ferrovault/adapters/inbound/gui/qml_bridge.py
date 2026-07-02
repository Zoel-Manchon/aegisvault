"""Bridge objects for the experimental Qt Quick/QML command center."""
from __future__ import annotations

from dataclasses import asdict

from PySide6.QtCore import QObject, Property, Signal, Slot

from .view_models.audit_stream import IncrementalAuditStream
from .view_models.command_palette import DEFAULT_ACTIONS, build_command_index, search_commands
from .view_models.security_score import build_security_score


class QmlVaultBridge(QObject):
    changed = Signal()
    auditChanged = Signal()

    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._session = session
        self._entries = tuple(session.entries())
        self._audit = IncrementalAuditStream()
        self._selected = ""
        self._last_secret = ""
        self.refresh()

    @Slot()
    def refresh(self) -> None:
        self._entries = tuple(self._session.entries())
        self._rotation = tuple(self._session.rotation_report())
        self._score = build_security_score(self._entries, self._rotation)
        self._audit_snapshot = self._audit.update(self._session.audit_log())
        self.changed.emit()
        if self._audit_snapshot.new_count:
            self.auditChanged.emit()

    @Property(int, notify=changed)
    def score(self) -> int:
        return int(self._score.score)

    @Property(str, notify=changed)
    def grade(self) -> str:
        return self._score.grade

    @Property(int, notify=changed)
    def totalEntries(self) -> int:
        return int(self._score.total)

    @Property(int, notify=changed)
    def twofaPercent(self) -> int:
        return int(self._score.twofa_percent)

    @Property(int, notify=changed)
    def activeGrants(self) -> int:
        return int(self._score.active_grants)

    @Property(int, notify=changed)
    def overdueRotations(self) -> int:
        return int(self._score.overdue_rotations)

    @Property(str, notify=changed)
    def selectedEntry(self) -> str:
        return self._selected

    @Slot(str, result='QVariantList')
    def commands(self, query: str):
        idx = build_command_index(self._entries, DEFAULT_ACTIONS)
        return [asdict(c) for c in search_commands(idx, query, limit=14)]

    @Slot(result='QVariantList')
    def entries(self):
        return [
            {
                "name": e.name,
                "username": getattr(e, "username", ""),
                "category": getattr(e, "category", "") or getattr(e, "team_vault", ""),
                "url": getattr(e, "url", ""),
                "favorite": bool(getattr(e, "favorite", False)),
                "twofa": bool(getattr(e, "has_totp", False)),
            }
            for e in self._entries if not getattr(e, "deleted", False)
        ]

    @Slot(result='QVariantList')
    def auditEvents(self):
        return list(self._audit_snapshot.as_dicts())[-80:]

    @Slot(str)
    def selectCommand(self, command_id: str) -> None:
        if command_id.startswith("entry:"):
            self._selected = command_id.split(":", 1)[1]
            self._last_secret = ""
            self.changed.emit()

    @Slot(str, result=str)
    def reveal(self, name: str) -> str:
        if not name:
            return ""
        self._last_secret = self._session.reveal(name)
        return self._last_secret
