"""Reusable Add Secret dialog sections."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QFormLayout, QHBoxLayout, QLineEdit, QPushButton, QSpinBox, QWidget

from .components.dialogs import FormCard


class CredentialSection(FormCard):
    """Credential fields used by the Add Secret workflow."""

    def __init__(self, session):
        super().__init__("Credential")
        self._session = session
        self.name = QLineEdit()
        self.name.setPlaceholderText("Binance production API key")
        self.username = QLineEdit()
        self.username.setPlaceholderText("email, username, service account, or client id")
        self.secret = QLineEdit()
        self.secret.setEchoMode(QLineEdit.Password)
        self.secret.setPlaceholderText("password, token, API key, recovery code…")
        self.url = QLineEdit()
        self.url.setPlaceholderText("https://binance.com")
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItem("")
        existing = sorted({getattr(v, "category", "") for v in session.entries() if getattr(v, "category", "")})
        self.category.addItems(existing)
        self.category.setCurrentText("")
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("production,crypto,api")

        form = self._form()
        form.addRow("Name", self.name)
        form.addRow("Username", self.username)
        form.addRow("Secret", self._secret_row())
        form.addRow("URL", self.url)
        form.addRow("Category", self.category)
        form.addRow("Tags", self.tags)
        self.box.addLayout(form)

    def _form(self) -> QFormLayout:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        return form

    def _secret_row(self) -> QWidget:
        secret_row = QWidget()
        row = QHBoxLayout(secret_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(self.secret, 1)
        gen = QPushButton("Generate")
        gen.clicked.connect(self.generate_secret)
        row.addWidget(gen)
        return secret_row

    def generate_secret(self) -> None:
        password, _label = self._session.generate()
        self.secret.setEchoMode(QLineEdit.Normal)
        self.secret.setText(password)

    def values(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "username": self.username.text().strip(),
            "secret": self.secret.text(),
            "url": self.url.text().strip(),
            "category": self.category.currentText().strip(),
            "tags": [t.strip() for t in self.tags.text().split(",") if t.strip()],
        }


class ZeroTrustMetadataSection(FormCard):
    """Policy metadata fields used by the Add Secret workflow."""

    def __init__(self, session, settings=None):
        super().__init__("Policy metadata")
        self._session = session
        self.team_vault = QComboBox()
        self.team_vault.setEditable(True)
        default_team = getattr(settings, "default_team_vault", "Personal") if settings else "Personal"
        self.team_vault.addItem(default_team or "Personal")
        existing_teams = sorted({getattr(v, "team_vault", "") for v in session.entries() if getattr(v, "team_vault", "")})
        self.team_vault.addItems([t for t in existing_teams if t != (default_team or "Personal")])
        self.sensitivity = QComboBox()
        self.sensitivity.addItems(["standard", "high", "critical"])
        self.allowed_groups = QLineEdit()
        self.allowed_groups.setPlaceholderText("ops,security,platform")
        self.rotation_days = QSpinBox()
        self.rotation_days.setRange(1, 3650)
        self.rotation_days.setSuffix(" days")
        self.rotation_days.setValue(getattr(settings, "default_rotation_interval_days", 90) if settings else 90)
        self.totp = QLineEdit()
        self.totp.setPlaceholderText("optional base32 TOTP seed")

        form = self._form()
        form.addRow("Team vault", self.team_vault)
        form.addRow("Sensitivity", self.sensitivity)
        form.addRow("Allowed groups", self.allowed_groups)
        form.addRow("Rotation interval", self.rotation_days)
        form.addRow("2FA seed", self._totp_row())
        self.box.addLayout(form)

    def _form(self) -> QFormLayout:
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(12)
        return form

    def _totp_row(self) -> QWidget:
        totp_row = QWidget()
        row = QHBoxLayout(totp_row)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        row.addWidget(self.totp, 1)
        gen_totp = QPushButton("Generate")
        gen_totp.setToolTip("Create a random base32 2FA seed")
        gen_totp.clicked.connect(self.generate_totp)
        row.addWidget(gen_totp)
        return totp_row

    def generate_totp(self) -> None:
        self.totp.setText(self._session.generate_totp_seed())

    def values(self) -> dict:
        return {
            "team_vault": self.team_vault.currentText().strip() or "Personal",
            "sensitivity": self.sensitivity.currentText().strip() or "standard",
            "allowed_groups": [g.strip() for g in self.allowed_groups.text().split(",") if g.strip()],
            "rotation_interval_days": self.rotation_days.value(),
            "totp": self.totp.text().strip() or None,
        }
