"""Reusable sections for the live SIEM/audit console."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)


class SiemEventsTable(QTableWidget):
    HEADERS = ("#", "Time", "Action", "Severity", "Message", "Hash")

    def __init__(self):
        super().__init__(0, len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)

    def set_events(self, events) -> None:
        self.setRowCount(len(events))
        for row, event in enumerate(events):
            values = (
                str(event.index),
                event.timestamp,
                event.event_type,
                str(event.severity),
                event.message,
                event.hash[:18] + "…",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.setItem(row, col, item)
        self.resizeColumnsToContents()


class SiemConsoleFooter(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.refresh_button = QPushButton("Refresh")
        self.export_jsonl_button = QPushButton("Export JSONL")
        self.export_jsonl_button.setObjectName("primary")
        self.export_json_button = QPushButton("Export JSON")
        self.close_button = QPushButton("Close")
        layout.addWidget(self.refresh_button)
        layout.addStretch()
        layout.addWidget(self.export_json_button)
        layout.addWidget(self.export_jsonl_button)
        layout.addWidget(self.close_button)
