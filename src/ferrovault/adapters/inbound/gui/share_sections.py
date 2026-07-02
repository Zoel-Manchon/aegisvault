"""Reusable Zero Trust sharing dialog sections."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
)
from PySide6.QtWidgets import QAbstractItemView

from .components.dialogs import FieldBlock, FormCard


class RecipientKeySection(FormCard):
    """Key-generation controls for recipient-side sharing."""

    def __init__(self):
        super().__init__(
            "Recipient keypair",
            "Generate a recipient keypair from the GUI. Share only the public key. Keep the private key offline or save it with strict permissions.",
        )
        self.private_key = QPlainTextEdit()
        self.private_key.setPlaceholderText("private key appears here")
        self.private_key.setMinimumHeight(90)
        self.public_key = QPlainTextEdit()
        self.public_key.setPlaceholderText("public key appears here")
        self.public_key.setMinimumHeight(90)
        self.add(FieldBlock("Private key — keep secret", self.private_key))
        self.add(FieldBlock("Public key — share with sender", self.public_key))

        row = QHBoxLayout()
        self.generate_button = QPushButton("Generate keypair")
        self.generate_button.setObjectName("primary")
        self.copy_public_button = QPushButton("Copy public")
        self.copy_private_button = QPushButton("Copy private")
        self.save_private_button = QPushButton("Save private key")
        self.save_public_button = QPushButton("Save public key")
        for button in (
            self.generate_button,
            self.copy_public_button,
            self.copy_private_button,
            self.save_private_button,
            self.save_public_button,
        ):
            row.addWidget(button)
        row.addStretch()
        self.box.addLayout(row)


class CreateGrantSection(FormCard):
    """Controls for creating one encrypted public-key grant."""

    def __init__(self):
        super().__init__("Create encrypted grant")
        self.entry_combo = QComboBox()
        self.recipient = QLineEdit()
        self.recipient.setPlaceholderText("ops@example.com, platform-team, Zoel…")
        self.public_key = QPlainTextEdit()
        self.public_key.setPlaceholderText("recipient X25519 public key, base64 encoded")
        self.public_key.setMinimumHeight(92)
        self.result = QPlainTextEdit()
        self.result.setPlaceholderText("sealed blob will appear here")
        self.result.setMinimumHeight(130)
        self.result.setReadOnly(True)

        self.add(FieldBlock("Secret", self.entry_combo))
        self.add(FieldBlock("Recipient label", self.recipient))
        self.add(FieldBlock("Recipient public key", self.public_key))

        row = QHBoxLayout()
        self.use_generated_button = QPushButton("Use generated public key")
        self.create_button = QPushButton("Create encrypted grant")
        self.create_button.setObjectName("primary")
        self.copy_blob_button = QPushButton("Copy sealed blob")
        row.addWidget(self.use_generated_button)
        row.addStretch()
        row.addWidget(self.create_button)
        row.addWidget(self.copy_blob_button)
        self.box.addLayout(row)
        self.add(FieldBlock("Result", self.result))


class AccessRegistrySection(FormCard):
    """Grant registry table plus revocation controls."""

    def __init__(self):
        super().__init__("Access registry")
        self.registry = QTableWidget(0, 8)
        self.registry.setHorizontalHeaderLabels(("Entry", "State", "Recipient", "Grant ID", "Fingerprint", "Created", "Revoked", "Reason"))
        self.registry.setMinimumHeight(260)
        self.registry.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.registry.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.add(self.registry)

        self.revoke_entry = QComboBox()
        self.revoke_match = QLineEdit()
        self.revoke_match.setPlaceholderText("recipient label, public-key fingerprint, or grant id")
        self.revoke_reason = QLineEdit()
        self.revoke_reason.setPlaceholderText("reason, e.g. offboarding, incident, key rotation")
        self.add(FieldBlock("Secret", self.revoke_entry))
        self.add(FieldBlock("Revoke match", self.revoke_match))
        self.add(FieldBlock("Reason", self.revoke_reason))

        row = QHBoxLayout()
        row.addStretch()
        self.revoke_button = QPushButton("Revoke matching active grant")
        self.revoke_button.setObjectName("danger")
        row.addWidget(self.revoke_button)
        self.box.addLayout(row)


class ReceiveSecretSection(FormCard):
    """Recipient-side sealed-blob opening and save controls."""

    def __init__(self):
        super().__init__(
            "Receive sealed secret",
            "Open a sealed blob with your private key. You can then save the received secret into this unlocked vault.",
        )
        self.private_key = QPlainTextEdit()
        self.private_key.setPlaceholderText("recipient private key")
        self.private_key.setMinimumHeight(90)
        self.sealed_blob = QPlainTextEdit()
        self.sealed_blob.setPlaceholderText("sealed blob from sender")
        self.sealed_blob.setMinimumHeight(100)
        self.opened_secret = QPlainTextEdit()
        self.opened_secret.setPlaceholderText("decrypted secret appears here")
        self.opened_secret.setMinimumHeight(90)
        self.opened_secret.setReadOnly(True)
        self.save_name = QLineEdit()
        self.save_name.setPlaceholderText("new entry name")
        self.save_username = QLineEdit()
        self.save_username.setPlaceholderText("username / account")
        self.save_url = QLineEdit()
        self.save_url.setPlaceholderText("https://example.com")

        self.add(FieldBlock("Private key", self.private_key))
        self.add(FieldBlock("Sealed blob", self.sealed_blob))
        row = QHBoxLayout()
        self.load_private_button = QPushButton("Load private key file")
        self.use_generated_button = QPushButton("Use generated private key")
        self.open_button = QPushButton("Open sealed blob")
        self.open_button.setObjectName("primary")
        row.addWidget(self.load_private_button)
        row.addWidget(self.use_generated_button)
        row.addStretch()
        row.addWidget(self.open_button)
        self.box.addLayout(row)
        self.add(FieldBlock("Opened secret", self.opened_secret))
        self.add(FieldBlock("Save as", self.save_name))
        self.add(FieldBlock("Username", self.save_username))
        self.add(FieldBlock("URL", self.save_url))
        self.save_button = QPushButton("Save received secret as vault entry")
        self.save_button.setObjectName("primary")
        self.add(self.save_button)


class SingleEntryGrantSection(FormCard):
    """Compact public-key grant creator for one selected secret."""

    def __init__(self, entry_name: str):
        super().__init__(f"Share: {entry_name}")
        self.recipient = QLineEdit()
        self.recipient.setPlaceholderText("ops@example.com, Zoel, platform-team…")
        self.public_key = QPlainTextEdit()
        self.public_key.setPlaceholderText("recipient X25519 public key, base64 encoded")
        self.public_key.setMinimumHeight(92)
        self.result = QPlainTextEdit()
        self.result.setPlaceholderText("sealed share blob will appear here")
        self.result.setMinimumHeight(120)
        self.result.setReadOnly(True)

        self.add(FieldBlock("Recipient label", self.recipient))
        self.add(FieldBlock("Recipient public key", self.public_key))
        row = QHBoxLayout()
        self.generate_button = QPushButton("Generate demo recipient keypair")
        self.create_button = QPushButton("Create encrypted grant")
        self.create_button.setObjectName("primary")
        row.addWidget(self.generate_button)
        row.addStretch()
        row.addWidget(self.create_button)
        self.box.addLayout(row)
        self.add(FieldBlock("Sealed blob / demo keys", self.result))


class SingleEntryAccessSection(FormCard):
    """Compact grant registry and revocation form for one selected secret."""

    def __init__(self):
        super().__init__("Access grants")
        self.grants = QPlainTextEdit()
        self.grants.setReadOnly(True)
        self.grants.setMinimumHeight(220)
        self.add(self.grants)
        self.revoke_match = QLineEdit()
        self.revoke_match.setPlaceholderText("recipient label, public-key fingerprint, or grant id")
        self.revoke_reason = QLineEdit()
        self.revoke_reason.setPlaceholderText("reason, e.g. offboarding, incident, key rotation")
        self.add(FieldBlock("Revoke match", self.revoke_match))
        self.add(FieldBlock("Reason", self.revoke_reason))
        row = QHBoxLayout()
        row.addStretch()
        self.revoke_button = QPushButton("Revoke matching active grant")
        self.revoke_button.setObjectName("danger")
        row.addWidget(self.revoke_button)
        self.box.addLayout(row)
