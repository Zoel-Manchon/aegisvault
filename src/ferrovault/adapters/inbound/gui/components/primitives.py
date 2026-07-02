"""Reusable QtWidgets primitives for the AegisVault desktop UI."""
from __future__ import annotations

from collections.abc import Iterable
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from ..icons import icon
from ..theme import ACCENT, ACCENT_2, MUTED, TEXT


def clear_layout(layout) -> None:
    """Delete all widgets from a Qt layout safely."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.deleteLater()


def caption(text: str, *, align: Qt.AlignmentFlag | None = None) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("mono")
    if align is not None:
        label.setAlignment(align)
    return label


class MetricCard(QFrame):
    """Small dashboard metric with consistent spacing and typography."""

    def __init__(self, label: str, value: str, helper: str, *, tone: str = "neutral"):
        super().__init__()
        self.setObjectName("metricTile")
        self.setProperty("tone", tone)
        self.setMinimumHeight(78)
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(4)
        cap = caption(label)
        number = QLabel(value)
        number.setObjectName("metricValue")
        note = QLabel(helper)
        note.setObjectName("smallMuted")
        note.setWordWrap(True)
        box.addWidget(cap)
        box.addWidget(number)
        box.addWidget(note)


class Pill(QLabel):
    """Rounded status badge."""

    def __init__(self, text: str, tone: str = "neutral"):
        super().__init__(text)
        self.setObjectName("ztPill")
        self.setProperty("tone", tone)
        self.setAlignment(Qt.AlignCenter)


class SectionHeader(QFrame):
    """Compact section heading used inside dashboards and dialogs."""

    def __init__(self, title: str, helper: str = ""):
        super().__init__()
        self.setObjectName("sectionHeader")
        box = QVBoxLayout(self)
        box.setContentsMargins(2, 4, 2, 4)
        box.setSpacing(2)
        h = QLabel(title)
        h.setObjectName("h2")
        box.addWidget(h)
        if helper:
            p = QLabel(helper)
            p.setObjectName("smallMuted")
            p.setWordWrap(True)
            box.addWidget(p)


class SummaryCard(QFrame):
    """Reusable text-card for operational summaries."""

    def __init__(self, title: str, lines: Iterable[str], *, minimum_height: int = 142):
        super().__init__()
        self.setObjectName("ztSummaryCard")
        self.setMinimumHeight(minimum_height)
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(8)
        h = QLabel(title)
        h.setObjectName("h2")
        box.addWidget(h)
        for line in tuple(lines)[:5]:
            p = QLabel(f"• {line}")
            p.setObjectName("smallMuted")
            p.setWordWrap(True)
            box.addWidget(p)
        box.addStretch()


class EmptyHint(QFrame):
    """Consistent empty state callout."""

    def __init__(self, title: str, body: str):
        super().__init__()
        self.setObjectName("emptyCard")
        box = QVBoxLayout(self)
        box.setContentsMargins(20, 18, 20, 18)
        box.setSpacing(7)
        h = QLabel(title)
        h.setObjectName("h2")
        p = QLabel(body)
        p.setObjectName("muted")
        p.setWordWrap(True)
        box.addWidget(h)
        box.addWidget(p)


class FeatureGrid(QWidget):
    """Small wrapper around QGridLayout with dashboard spacing defaults."""

    def __init__(self, columns: int = 2):
        super().__init__()
        self.setObjectName("featureGrid")
        self.columns = max(1, columns)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        for column in range(self.columns):
            self.grid.setColumnStretch(column, 1)

    def add_items(self, widgets: Iterable[QWidget]) -> None:
        for index, widget in enumerate(widgets):
            self.grid.addWidget(widget, index // self.columns, index % self.columns)


class ActionCard(QPushButton):
    """Clickable command card for primary workflows."""

    def __init__(self, title: str, helper: str, icon_name: str, handler, *, tone: str = "default"):
        super().__init__(f"{title}\n{helper}")
        self.setObjectName("ztActionCard")
        self.setProperty("tone", tone)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(104)
        self.setIcon(icon(icon_name, ACCENT_2 if tone != "primary" else ACCENT, 28))
        self.setIconSize(QSize(28, 28))
        self.clicked.connect(handler)
