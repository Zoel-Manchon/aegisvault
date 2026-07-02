"""Reusable dialog primitives for AegisVault QtWidgets surfaces."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


class DialogHero(QFrame):
    """Consistent title block for large workflow dialogs."""

    def __init__(self, title: str, subtitle: str = ""):
        super().__init__()
        self.setObjectName("dialogHero")
        box = QVBoxLayout(self)
        box.setContentsMargins(18, 16, 18, 16)
        box.setSpacing(6)
        h = QLabel(title)
        h.setObjectName("h1")
        box.addWidget(h)
        if subtitle:
            p = QLabel(subtitle)
            p.setObjectName("muted")
            p.setWordWrap(True)
            box.addWidget(p)


class DialogPage(QScrollArea):
    """Scroll-safe page used inside tabbed dialogs."""

    def __init__(self, *, margin: int = 12, spacing: int = 12):
        super().__init__()
        self.setObjectName("settingsScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("settingsPage")
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(margin, margin, margin, margin)
        self.layout.setSpacing(spacing)
        self.setWidget(self.content)

    def add(self, widget: QWidget) -> QWidget:
        self.layout.addWidget(widget)
        return widget

    def add_stretch(self) -> None:
        self.layout.addStretch()


class FormCard(QFrame):
    """Card container for a related set of dialog fields."""

    def __init__(self, title: str = "", helper: str = ""):
        super().__init__()
        self.setObjectName("formCard")
        self.box = QVBoxLayout(self)
        self.box.setContentsMargins(18, 16, 18, 18)
        self.box.setSpacing(12)
        if title:
            h = QLabel(title)
            h.setObjectName("h2")
            self.box.addWidget(h)
        if helper:
            p = QLabel(helper)
            p.setObjectName("muted")
            p.setWordWrap(True)
            self.box.addWidget(p)

    def add(self, widget: QWidget) -> QWidget:
        self.box.addWidget(widget)
        return widget


class FieldBlock(QFrame):
    """Stacked label + editor block for dense workflow forms."""

    def __init__(self, label: str, editor: QWidget, helper: str = ""):
        super().__init__()
        self.setObjectName("settingsRow")
        box = QVBoxLayout(self)
        box.setContentsMargins(14, 12, 14, 12)
        box.setSpacing(7)
        cap = QLabel(label)
        cap.setObjectName("h2")
        box.addWidget(cap)
        if helper:
            note = QLabel(helper)
            note.setObjectName("smallMuted")
            note.setWordWrap(True)
            box.addWidget(note)
        box.addWidget(editor)


class PolicyCallout(QFrame):
    """Reusable explanatory callout for policy/security notes."""

    def __init__(self, title: str, body: str):
        super().__init__()
        self.setObjectName("policyCallout")
        box = QVBoxLayout(self)
        box.setContentsMargins(16, 14, 16, 14)
        box.setSpacing(5)
        h = QLabel(title)
        h.setObjectName("h2")
        p = QLabel(body)
        p.setObjectName("muted")
        p.setWordWrap(True)
        box.addWidget(h)
        box.addWidget(p)


class DialogFooter(QWidget):
    """Common footer with optional status, secondary action, and close button."""

    def __init__(self, *, status: QLabel | None = None, close_text: str = "Close", on_close=None):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        if status is not None:
            layout.addWidget(status, 1)
        else:
            layout.addStretch()
        self.close_button = QPushButton(close_text)
        if on_close is not None:
            self.close_button.clicked.connect(on_close)
        layout.addWidget(self.close_button)
