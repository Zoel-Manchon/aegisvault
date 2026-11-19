"""Shared chrome for the full-window pages (health, audit, settings).

Each page has the "‹ Bóveda / Página" breadcrumb, its own lock pill (the main
window keeps it in sync with the auto-lock countdown) and "Bloquear ahora".
Esc goes back to the vault.
"""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QFrame, QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from ..components.kit import Button, Card, LockPill, label
from ..design.tokens import TOPBAR_H


class Page(QWidget):
    """Breadcrumb header + scrollable content area."""

    def __init__(self, crumb: str, callbacks: dict[str, Callable], *, scroll: bool = True,
                 margins=(56, 28, 56, 32), spacing: int = 20):
        super().__init__()
        self.setObjectName("page")
        self._callbacks = callbacks
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        header = QFrame()
        header.setObjectName("pageHeader")
        header.setFixedHeight(TOPBAR_H)
        row = QHBoxLayout(header)
        row.setContentsMargins(16, 0, 12, 0)
        row.setSpacing(10)
        self.back_btn = Button("Bóveda", "nav", "chevron-left", on_click=callbacks["back"],
                               tooltip="Volver a la bóveda (Esc)")
        row.addWidget(self.back_btn)
        row.addWidget(label("/", "tertiary"))
        row.addWidget(label(crumb, "bodyStrong"))
        row.addStretch(1)
        self.header_actions = QHBoxLayout()
        self.header_actions.setSpacing(8)
        row.addLayout(self.header_actions)
        self.lock_pill = LockPill()
        row.addWidget(self.lock_pill)
        row.addWidget(Button("Bloquear ahora", "secondary", "lock", on_click=callbacks["lock"],
                             tooltip="Bloquear ahora (Ctrl+L)"))
        col.addWidget(header)

        self.inner = QWidget()
        self.inner.setObjectName("page")
        self.content = QVBoxLayout(self.inner)
        self.content.setContentsMargins(*margins)
        self.content.setSpacing(spacing)
        if scroll:
            area = QScrollArea()
            area.setObjectName("plain")
            area.setWidgetResizable(True)
            area.setFrameShape(QFrame.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(self.inner)
            col.addWidget(area, 1)
        else:
            col.addWidget(self.inner, 1)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=callbacks["back"])


def kv_row(key: str, value: str, mono: bool = True) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(12)
    row.addWidget(label(key, "secondary"))
    row.addStretch(1)
    row.addWidget(label(value, "monoBody" if mono else "body"))
    return row


def section_card(title: str, subtitle: str = "", right: QWidget | None = None) -> Card:
    card = Card(title, right=right, name="cardSunken", margins=(20, 18, 20, 18), spacing=12)
    if subtitle:
        card.add(label(subtitle, "secondary", wrap=True))
    return card
