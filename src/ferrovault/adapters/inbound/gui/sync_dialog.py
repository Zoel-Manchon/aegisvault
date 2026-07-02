"""Encrypted sync-bundle GUI."""
from __future__ import annotations

import json

from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QVBoxLayout

from ....application.services.directory import IdentityDirectory
from ....application.services.sync import SyncBundle
from ....application.services.sync_gateway import ZeroTrustSyncGateway
from .components.dialogs import DialogHero
from .sync_sections import SyncBundleFooter, SyncBundlePreview, SyncGatewayPreviewSection


class SyncBundleDialog(QDialog):
    def __init__(self, session, settings, parent=None):
        super().__init__(parent)
        self._session = session
        self._settings = settings
        self.setWindowTitle("Encrypted team-vault sync")
        self.setMinimumSize(820, 560)
        self.resize(920, 640)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        outer.addWidget(DialogHero(
            "Encrypted sync foundation",
            "Export or import a zero-plaintext sync bundle. The bundle contains the already-encrypted vault artifact plus a manifest; no server or synced folder sees decrypted secrets.",
        ))

        self.gateway = SyncGatewayPreviewSection()
        self.gateway_table = self.gateway.table
        outer.addWidget(self.gateway)

        self.preview = SyncBundlePreview()
        outer.addWidget(self.preview, 1)

        self.footer = SyncBundleFooter()
        self.footer.export_button.clicked.connect(self.export_bundle)
        self.footer.load_button.clicked.connect(self.load_bundle)
        self.footer.refresh_gateway_button.clicked.connect(self.refresh_gateway)
        self.footer.import_button.clicked.connect(self.import_bundle)
        self.footer.close_button.clicked.connect(self.accept)
        outer.addWidget(self.footer)
        self.refresh_gateway()

    def refresh_gateway(self):
        try:
            directory = IdentityDirectory(self._settings.recipient_directory)
            gateway = ZeroTrustSyncGateway(directory, require_trusted_device=self._settings.require_trusted_device)
            decisions = gateway.evaluate(self._session.entries(include_deleted=False), device_id=self._settings.local_device_id)
        except Exception as exc:
            QMessageBox.warning(self, "Gateway preview failed", str(exc))
            return
        self.gateway.set_decisions(decisions)

    def export_bundle(self):
        try:
            payload = self._session.export_sync_bundle(
                created_by=self._settings.enterprise_user_id,
                device_id=self._settings.local_device_id,
            )
        except Exception as exc:
            QMessageBox.critical(self, "Sync export failed", str(exc))
            return
        self.preview.setPlainText(payload)
        path, _ = QFileDialog.getSaveFileName(self, "Save encrypted sync bundle", "aegisvault-sync-bundle.json", "*.json")
        if path:
            try:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(payload)
                QMessageBox.information(self, "Sync bundle exported", f"Encrypted bundle written to:\n{path}")
            except Exception as exc:
                QMessageBox.critical(self, "Could not write bundle", str(exc))

    def load_bundle(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load encrypted sync bundle", "", "*.json")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                payload = fh.read()
            bundle = SyncBundle.from_json(payload)
            self.preview.setPlainText(json.dumps({"manifest": bundle.manifest.__dict__}, indent=2, sort_keys=True) + "\n\n" + payload)
        except Exception as exc:
            QMessageBox.critical(self, "Invalid bundle", str(exc))

    def import_bundle(self):
        payload = self.preview.toPlainText().strip()
        if "\n\n{" in payload and payload.lstrip().startswith("{"):
            payload = payload[payload.find("\n\n{") + 2:].strip()
        if not payload:
            QMessageBox.warning(self, "Missing bundle", "Load or paste an encrypted sync bundle first.")
            return
        try:
            bundle = SyncBundle.from_json(payload)
        except Exception as exc:
            QMessageBox.critical(self, "Invalid bundle", str(exc))
            return
        msg = (
            "This will replace the local encrypted vault artifact with the selected bundle and lock the current session.\n\n"
            f"Bundle created by: {bundle.manifest.created_by}\n"
            f"Device: {bundle.manifest.device_id}\n"
            f"Entries: {bundle.manifest.entry_count}\n\nContinue?"
        )
        if QMessageBox.question(self, "Replace local vault?", msg) != QMessageBox.Yes:
            return
        try:
            self._session.import_sync_bundle(payload)
            QMessageBox.information(self, "Bundle imported", "Encrypted vault replaced. Reopen the vault to continue.")
            self.accept()
            if self.parent():
                self.parent().close()
        except Exception as exc:
            QMessageBox.critical(self, "Import failed", str(exc))
