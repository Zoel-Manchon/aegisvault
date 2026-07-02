"""Reusable sections for the user/device key directory dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ....application.services.directory import DirectoryPrincipal
from .components.dialogs import FormCard


class DirectoryPrincipalTable(QTableWidget):
    HEADERS = ("Label", "Email", "Role", "Groups", "Devices", "Key fingerprint", "State")

    def __init__(self):
        super().__init__(0, len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)

    def set_principals(self, principals: list[DirectoryPrincipal]) -> None:
        self.setRowCount(len(principals))
        for row, principal in enumerate(principals):
            values = (
                principal.label,
                principal.email,
                principal.role,
                ",".join(principal.groups),
                ",".join(principal.trusted_devices),
                principal.fingerprint,
                "active" if principal.active else "inactive",
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.setItem(row, col, item)
        self.resizeColumnsToContents()


class DirectoryPrincipalForm(FormCard):
    def __init__(self):
        super().__init__("Principal editor")
        self.label = QLineEdit(); self.label.setPlaceholderText("ops@example.com / Zoel")
        self.email = QLineEdit(); self.email.setPlaceholderText("ops@example.com")
        self.public_key = QLineEdit(); self.public_key.setPlaceholderText("base64 X25519 public key")
        self.role = QComboBox(); self.role.addItems(["owner", "admin", "auditor", "member", "readonly"]); self.role.setCurrentText("member")
        self.groups = QLineEdit(); self.groups.setPlaceholderText("ops,security,platform")
        self.devices = QLineEdit(); self.devices.setPlaceholderText("laptop-workstation,yubikey-host")
        self.active = QCheckBox("Active"); self.active.setChecked(True)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        rows = (
            ("Label", self.label), ("Email", self.email), ("Public key", self.public_key),
            ("Role", self.role), ("Groups", self.groups), ("Trusted devices", self.devices),
            ("State", self.active),
        )
        for i, (name, widget) in enumerate(rows):
            cap = QLabel(name); cap.setObjectName("mono")
            grid.addWidget(cap, i // 2 * 2, i % 2)
            grid.addWidget(widget, i // 2 * 2 + 1, i % 2)
        self.box.addLayout(grid)

    def principal(self) -> DirectoryPrincipal:
        return DirectoryPrincipal(
            label=self.label.text().strip() or self.email.text().strip() or "recipient",
            email=self.email.text().strip(),
            public_key=self.public_key.text().strip(),
            role=self.role.currentText(),
            groups=tuple(x.strip() for x in self.groups.text().split(",") if x.strip()),
            trusted_devices=tuple(x.strip() for x in self.devices.text().split(",") if x.strip()),
            active=self.active.isChecked(),
        ).normalized()

    def load(self, principal: DirectoryPrincipal) -> None:
        self.label.setText(principal.label)
        self.email.setText(principal.email)
        self.public_key.setText(principal.public_key)
        self.role.setCurrentText(principal.role)
        self.groups.setText(",".join(principal.groups))
        self.devices.setText(",".join(principal.trusted_devices))
        self.active.setChecked(principal.active)


class DirectoryFooter(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.upsert_button = QPushButton("Add / update principal")
        self.upsert_button.setObjectName("primary")
        self.load_button = QPushButton("Load selected")
        self.deactivate_button = QPushButton("Deactivate selected")
        self.save_button = QPushButton("Save directory")
        self.close_button = QPushButton("Close")
        layout.addWidget(self.upsert_button)
        layout.addWidget(self.load_button)
        layout.addWidget(self.deactivate_button)
        layout.addStretch()
        layout.addWidget(self.save_button)
        layout.addWidget(self.close_button)
