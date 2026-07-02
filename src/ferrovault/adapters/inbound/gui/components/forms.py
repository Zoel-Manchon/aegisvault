"""Reusable form rows and scroll pages for settings/dialog surfaces."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget


class ScrollFormPage(QScrollArea):
    """Scroll-safe form page used by large tabbed dialogs."""

    def __init__(self):
        super().__init__()
        self.setObjectName("settingsScroll")
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.content = QWidget()
        self.content.setObjectName("settingsPage")
        self.layout = QVBoxLayout(self.content)
        self.layout.setContentsMargins(12, 12, 12, 12)
        self.layout.setSpacing(10)
        self.setWidget(self.content)

    def addStretch(self) -> None:  # match QVBoxLayout naming used by dialogs
        self.layout.addStretch()


class FormRow(QFrame):
    """Label/helper + editor row for settings dialogs."""

    def __init__(self, title: str, editor: QWidget, helper: str):
        super().__init__()
        self.setObjectName("settingsRow")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(16)
        texts = QVBoxLayout()
        texts.setSpacing(4)
        name = QLabel(title)
        name.setObjectName("h2")
        note = QLabel(helper)
        note.setObjectName("smallMuted")
        note.setWordWrap(True)
        texts.addWidget(name)
        texts.addWidget(note)
        layout.addLayout(texts, 1)
        editor.setMinimumWidth(230)
        layout.addWidget(editor, 0, Qt.AlignVCenter)


class ToggleRow(FormRow):
    """Reusable checkbox row that exposes the checkbox via `.checkbox`."""

    def __init__(self, title: str, checked: bool, helper: str):
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(checked)
        super().__init__(title, self.checkbox, helper)

    def isChecked(self) -> bool:
        return self.checkbox.isChecked()
