"""User/device key directory editor."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QMessageBox, QVBoxLayout

from ....application.services.directory import IdentityDirectory
from ....application.services.settings import VaultSettings
from .components.dialogs import DialogHero
from .directory_sections import DirectoryFooter, DirectoryPrincipalForm, DirectoryPrincipalTable


class DirectoryDialog(QDialog):
    def __init__(self, settings_store, settings: VaultSettings, parent=None):
        super().__init__(parent)
        self._settings_store = settings_store
        self._settings = settings.normalized()
        self._directory = IdentityDirectory(self._settings.recipient_directory)
        self.setWindowTitle("User / device key directory")
        self.setMinimumSize(920, 620)
        self.resize(1040, 700)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        outer.addWidget(DialogHero(
            "User & device key directory",
            "Store recipient public keys, roles, groups, and trusted devices for Zero Trust sharing and future SCIM/SSO sync.",
        ))

        self.table = DirectoryPrincipalTable()
        outer.addWidget(self.table, 1)

        self.form = DirectoryPrincipalForm()
        outer.addWidget(self.form)

        self.footer = DirectoryFooter()
        self.footer.upsert_button.clicked.connect(self.upsert)
        self.footer.load_button.clicked.connect(self.load_selected)
        self.footer.deactivate_button.clicked.connect(self.deactivate_selected)
        self.footer.save_button.clicked.connect(self.save)
        self.footer.close_button.clicked.connect(self.accept)
        outer.addWidget(self.footer)
        self.refresh()

    @property
    def settings(self) -> VaultSettings:
        return self._settings

    def refresh(self):
        self.table.set_principals(self._directory.list(include_inactive=True))

    def upsert(self):
        principal = self.form.principal()
        if principal.public_key and principal.fingerprint == "invalid":
            QMessageBox.warning(self, "Invalid key", "Recipient public key must be a base64-encoded 32-byte X25519 public key.")
            return
        self._directory = self._directory.upsert(principal)
        self.refresh()

    def load_selected(self):
        row = self.table.currentRow()
        principals = self._directory.list(include_inactive=True)
        if row < 0 or row >= len(principals):
            return
        self.form.load(principals[row])

    def deactivate_selected(self):
        row = self.table.currentRow()
        principals = self._directory.list(include_inactive=True)
        if row < 0 or row >= len(principals):
            return
        self._directory = self._directory.deactivate(principals[row].email or principals[row].label)
        self.refresh()

    def save(self):
        dir_devices = self._directory.trusted_device_ids()
        trusted = tuple(dict.fromkeys(tuple(self._settings.trusted_device_ids) + dir_devices))
        self._settings = VaultSettings(**{**self._settings.to_dict(),
                                          "recipient_directory": tuple(self._directory.to_list()),
                                          "trusted_device_ids": trusted}).normalized()
        self._settings_store.save(self._settings)
        QMessageBox.information(self, "Directory saved", "User/device directory and trusted device list were saved.")
