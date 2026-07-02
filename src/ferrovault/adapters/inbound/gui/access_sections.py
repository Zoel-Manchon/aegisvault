"""Reusable sections for the Zero Trust access-request dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ....application.services.access_requests import VALID_ACTIONS
from .components.dialogs import FormCard


class AccessRequestTable(QTableWidget):
    """Read-only table used to inspect local access requests."""

    HEADERS = ("ID", "Entry", "Action", "Requester", "State", "Created", "Decider", "Decision")

    def __init__(self):
        super().__init__(0, len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)

    def set_requests(self, requests) -> None:
        self.setRowCount(len(requests))
        for row, req in enumerate(requests):
            values = (
                req.request_id,
                req.entry_name,
                req.action.replace("_secret", ""),
                req.requester,
                req.status,
                req.created_at,
                req.decided_by,
                req.decision_reason,
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.setItem(row, col, item)
        self.resizeColumnsToContents()


class AccessRequestForm(FormCard):
    """Form for creating a governed local access request."""

    def __init__(self, entries: list[str], requester: str):
        super().__init__("Create governed request")
        self.entry = QComboBox()
        self.entry.setEditable(True)
        self.entry.addItems(entries)
        self.action = QComboBox()
        self.action.addItems(list(VALID_ACTIONS))
        self.requester = QLineEdit(requester)
        self.requester.setPlaceholderText("user@example.com")
        self.reason = QLineEdit()
        self.reason.setPlaceholderText("Why is access needed?")

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        rows = (
            ("Entry", self.entry),
            ("Action", self.action),
            ("Requester", self.requester),
            ("Reason", self.reason),
        )
        for i, (name, widget) in enumerate(rows):
            cap = QLabel(name)
            cap.setObjectName("mono")
            grid.addWidget(cap, i // 2 * 2, i % 2)
            grid.addWidget(widget, i // 2 * 2 + 1, i % 2)
        self.box.addLayout(grid)

    def values(self) -> tuple[str, str, str, str]:
        return (
            self.entry.currentText().strip(),
            self.action.currentText(),
            self.requester.text().strip(),
            self.reason.text().strip(),
        )

    def clear_reason(self) -> None:
        self.reason.clear()


class AccessRequestFooter(QWidget):
    """Action footer for access request workflows."""

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.create_button = QPushButton("Create request")
        self.create_button.setObjectName("primary")
        self.approve_button = QPushButton("Approve selected")
        self.deny_button = QPushButton("Deny selected")
        self.save_button = QPushButton("Save workflow")
        self.close_button = QPushButton("Close")
        layout.addWidget(self.create_button)
        layout.addWidget(self.approve_button)
        layout.addWidget(self.deny_button)
        layout.addStretch()
        layout.addWidget(self.save_button)
        layout.addWidget(self.close_button)
