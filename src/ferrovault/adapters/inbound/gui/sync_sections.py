"""Reusable sections for encrypted sync workflows."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from .components.dialogs import FormCard


class SyncGatewayPreviewSection(FormCard):
    """Read-only preview of sync-gateway grant-delivery decisions."""

    def __init__(self):
        super().__init__(
            "Zero Trust sync gateway preview",
            "Shows which encrypted share grants would be delivered to the current device. No plaintext secrets are evaluated here.",
        )
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(("Entry", "Recipient", "Fingerprint", "Decision", "Reason"))
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setMaximumHeight(150)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.add(self.table)

    def set_decisions(self, decisions) -> None:
        self.table.setRowCount(len(decisions))
        for row, decision in enumerate(decisions):
            values = (
                decision.entry_name,
                decision.recipient,
                decision.fingerprint[:18] + "…" if decision.fingerprint else "",
                "deliver" if decision.allowed else "blocked",
                decision.reason,
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()


class SyncBundlePreview(QPlainTextEdit):
    """Text preview/import area for encrypted sync bundles."""

    def __init__(self):
        super().__init__()
        self.setPlaceholderText("Exported/imported sync bundle JSON appears here…")


class SyncBundleFooter(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.export_button = QPushButton("Export encrypted bundle")
        self.export_button.setObjectName("primary")
        self.load_button = QPushButton("Load bundle")
        self.refresh_gateway_button = QPushButton("Refresh gateway preview")
        self.import_button = QPushButton("Import / replace local vault")
        self.close_button = QPushButton("Close")
        layout.addWidget(self.export_button)
        layout.addWidget(self.load_button)
        layout.addWidget(self.refresh_gateway_button)
        layout.addStretch()
        layout.addWidget(self.import_button)
        layout.addWidget(self.close_button)
