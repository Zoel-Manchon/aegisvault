"""Raycast-style command palette for the Qt Widgets GUI."""
from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from .components.dialogs import DialogHero
from .view_models.command_palette import PaletteCommand, search_commands


class CommandPaletteDialog(QDialog):
    def __init__(self, commands: tuple[PaletteCommand, ...], on_execute: Callable[[PaletteCommand], None], parent=None):
        super().__init__(parent)
        self._commands = commands
        self._on_execute = on_execute
        self._visible: tuple[PaletteCommand, ...] = ()
        self.setWindowTitle("Command palette")
        self.setObjectName("commandPalette")
        self.setModal(True)
        self.setMinimumSize(680, 540)
        self.resize(760, 600)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        layout.addWidget(DialogHero("Command palette", "Jump to any secret or Zero Trust action. Press Enter to run, Esc to close."))

        self.search = QLineEdit()
        self.search.setObjectName("commandSearch")
        self.search.setPlaceholderText("Search entries, actions, policy, audit, sharing…")
        self.search.textChanged.connect(self._refresh)
        layout.addWidget(self.search)

        self.results = QListWidget()
        self.results.setObjectName("commandResults")
        self.results.itemDoubleClicked.connect(lambda _item: self._activate())
        layout.addWidget(self.results, 1)
        self._refresh("")

    def showEvent(self, event):  # noqa: N802 - Qt override
        super().showEvent(event)
        self.search.setFocus(Qt.PopupFocusReason)
        self.search.selectAll()

    def keyPressEvent(self, event):  # noqa: N802 - Qt override
        if event.key() in {Qt.Key_Return, Qt.Key_Enter}:
            self._activate()
            return
        if event.key() == Qt.Key_Escape:
            self.reject()
            return
        super().keyPressEvent(event)

    def _refresh(self, query: str) -> None:
        self._visible = search_commands(self._commands, query, limit=16)
        self.results.clear()
        for command in self._visible:
            prefix = "↳" if command.kind == "entry" else "⌘"
            item = QListWidgetItem(f"{prefix}  {command.title}\n{command.subtitle}")
            item.setData(Qt.UserRole, command)
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)

    def _activate(self) -> None:
        item = self.results.currentItem()
        if not item:
            return
        command = item.data(Qt.UserRole)
        self.accept()
        self._on_execute(command)
