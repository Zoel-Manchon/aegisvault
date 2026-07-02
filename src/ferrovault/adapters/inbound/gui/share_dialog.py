"""Zero Trust sharing dialogs for public-key grants and revocation."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTabWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from ...outbound.sharing.sealed_box import generate_keypair
from .components.dialogs import DialogHero, DialogPage, PolicyCallout
from .share_sections import (
    AccessRegistrySection,
    CreateGrantSection,
    ReceiveSecretSection,
    RecipientKeySection,
    SingleEntryAccessSection,
    SingleEntryGrantSection,
)
from .sharing_controller import SharingWorkflowController


class ShareSecretDialog(QDialog):
    """Create and revoke structured public-key grants for one selected entry."""

    def __init__(self, session, entry_view, parent=None, actor="local-admin"):
        super().__init__(parent)
        self._session = session
        self._entry = entry_view
        self._actor = actor or "local-admin"
        self.setWindowTitle(f"Share · {entry_view.name}")
        self.setMinimumSize(820, 620)
        self.resize(900, 680)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        outer.addWidget(DialogHero(
            "Zero Trust sharing",
            "Share this secret with a recipient public key. AegisVault stores a structured encrypted grant, records the audit event, and lets you revoke future access from the same GUI.",
        ))

        tabs = QTabWidget()
        tabs.setObjectName("settingsTabs")
        tabs.addTab(self._share_page(), "Create grant")
        tabs.addTab(self._access_page(), "Existing access")
        outer.addWidget(tabs, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        outer.addLayout(buttons)

    def _share_page(self) -> DialogPage:
        page = DialogPage()
        self.share_section = SingleEntryGrantSection(self._entry.name)
        self.recipient = self.share_section.recipient
        self.public_key = self.share_section.public_key
        self.result = self.share_section.result
        self.share_section.generate_button.clicked.connect(self._generate_demo_keys)
        self.share_section.create_button.clicked.connect(self._create_share)
        page.add(self.share_section)
        page.add(PolicyCallout(
            "Revocation boundary",
            "Revoking a grant blocks future app/sync access and writes an audit event. It cannot erase a sealed blob that was already copied outside the vault.",
        ))
        page.add_stretch()
        return page

    def _access_page(self) -> DialogPage:
        page = DialogPage()
        self.access_section = SingleEntryAccessSection()
        self.grants = self.access_section.grants
        self.revoke_match = self.access_section.revoke_match
        self.revoke_reason = self.access_section.revoke_reason
        self.grants.setPlainText(self._grant_text())
        self.access_section.revoke_button.clicked.connect(self._revoke)
        page.add(self.access_section)
        page.add_stretch()
        return page

    def _grant_text(self) -> str:
        grants = tuple(getattr(self._entry, "sharing_grants", ()) or ())
        if not grants:
            legacy = tuple(getattr(self._entry, "shared_with", ()) or ())
            if legacy:
                return "Legacy labels only, no cryptographic grants yet:\n" + "\n".join(f"- {x}" for x in legacy)
            return "No structured share grants yet."
        lines = []
        for grant in grants:
            state = "REVOKED" if grant.get("revoked_at") else "ACTIVE"
            lines.append(
                f"{state}  {grant.get('recipient', 'recipient')}\n"
                f"  grant: {grant.get('grant_id', '')}\n"
                f"  fingerprint: {grant.get('public_key_fingerprint', '')}\n"
                f"  created: {grant.get('created_at', '')} by {grant.get('created_by', '')}\n"
                f"  revoked: {grant.get('revoked_at', '') or '—'} {(('· ' + grant.get('revoke_reason', '')) if grant.get('revoked_at') else '')}\n"
            )
        return "\n".join(lines)

    def _generate_demo_keys(self):
        priv, pub = generate_keypair()
        self.public_key.setPlainText(pub)
        self.result.setPlainText(
            "Demo recipient keypair generated. Use the public key above to create a grant.\n\n"
            "PRIVATE KEY — keep secret, recipient side only:\n"
            f"{priv}\n\nPUBLIC KEY:\n{pub}"
        )

    def _create_share(self):
        recipient = self.recipient.text().strip() or "recipient"
        pub = self.public_key.toPlainText().strip()
        if not pub:
            QMessageBox.warning(self, "Missing public key", "Paste the recipient public key first.")
            return
        try:
            grant = self._session.share_public_key(self._entry.name, recipient, pub, actor=self._actor)
        except Exception as exc:
            QMessageBox.warning(self, "Share failed", str(exc))
            return
        self.result.setPlainText(
            "Encrypted share grant created. Send this sealed blob to the recipient over an approved channel.\n\n"
            f"grant id: {grant.get('grant_id')}\n"
            f"recipient: {grant.get('recipient')}\n"
            f"fingerprint: {grant.get('public_key_fingerprint')}\n\n"
            f"{grant.get('sealed_blob')}"
        )
        self.grants.setPlainText(self._grant_text())
        QMessageBox.information(self, "Share created", "Encrypted access grant created and audited.")

    def _revoke(self):
        match = self.revoke_match.text().strip()
        if not match:
            QMessageBox.warning(self, "Missing match", "Enter a recipient label, fingerprint, or grant id.")
            return
        try:
            revoked = self._session.revoke_share(
                self._entry.name,
                match,
                reason=self.revoke_reason.text().strip() or "manual revocation",
                actor=self._actor,
            )
        except Exception as exc:
            QMessageBox.warning(self, "Revoke failed", str(exc))
            return
        self.grants.setPlainText(self._grant_text())
        QMessageBox.information(self, "Access revoked", f"Revoked {revoked} active grant(s).")


class SharingCenterDialog(QDialog):
    """Full GUI parity for Zero Trust sharing commands."""

    def __init__(self, session, parent=None, actor="local-admin", initial_entry=None, authorize_share=None):
        super().__init__(parent)
        self._initial_entry_name = getattr(initial_entry, "name", "") if initial_entry is not None else ""
        self._workflow = SharingWorkflowController(
            session,
            actor=actor or "local-admin",
            authorize_share=authorize_share,
        )

        self.setWindowTitle("Zero Trust sharing center")
        self.setMinimumSize(980, 700)
        self.resize(1060, 760)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        outer.addWidget(DialogHero(
            "Zero Trust sharing center",
            "Generate recipient keys, create encrypted grants, inspect active/revoked access, revoke grants, and open received sealed blobs without using a terminal.",
        ))

        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        self.tabs.addTab(self._keys_page(), "Recipient keys")
        self.tabs.addTab(self._create_page(), "Create grant")
        self.tabs.addTab(self._registry_page(), "Access registry")
        self.tabs.addTab(self._receive_page(), "Receive")
        outer.addWidget(self.tabs, 1)

        buttons = QHBoxLayout()
        self.status = QLabel("GUI parity: share-keygen · share · share-list · share-revoke · receive")
        self.status.setObjectName("smallMuted")
        buttons.addWidget(self.status, 1)
        refresh = QPushButton("Refresh")
        refresh.clicked.connect(self._refresh_all)
        buttons.addWidget(refresh)
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        outer.addLayout(buttons)

        self._refresh_all()
        if self._initial_entry_name:
            self._select_combo_text(self.entry_combo, self._initial_entry_name)
            self._select_combo_text(self.revoke_entry, self._initial_entry_name)
            self.tabs.setCurrentIndex(1)

    # ---- page builders -------------------------------------------------
    def _keys_page(self) -> DialogPage:
        page = DialogPage()
        self.key_section = RecipientKeySection()
        self.private_key = self.key_section.private_key
        self.public_key = self.key_section.public_key
        self.key_section.generate_button.clicked.connect(self._generate_keys)
        self.key_section.copy_public_button.clicked.connect(lambda: self._copy_text(self.public_key.toPlainText(), "Public key copied."))
        self.key_section.copy_private_button.clicked.connect(lambda: self._copy_text(self.private_key.toPlainText(), "Private key copied."))
        self.key_section.save_private_button.clicked.connect(self._save_private_key)
        self.key_section.save_public_button.clicked.connect(self._save_public_key)
        page.add(self.key_section)
        page.add(PolicyCallout(
            "Desktop workflow",
            "This replaces `aegisvault share-keygen`. A future team-sync layer can register public keys per user/device instead of pasting them manually.",
        ))
        page.add_stretch()
        return page

    def _create_page(self) -> DialogPage:
        page = DialogPage()
        self.create_section = CreateGrantSection()
        self.entry_combo = self.create_section.entry_combo
        self.recipient = self.create_section.recipient
        self.grant_public_key = self.create_section.public_key
        self.grant_result = self.create_section.result
        self.create_section.use_generated_button.clicked.connect(self._use_generated_public_key)
        self.create_section.create_button.clicked.connect(self._create_grant)
        self.create_section.copy_blob_button.clicked.connect(lambda: self._copy_text(self._sealed_blob_only(), "Sealed blob copied."))
        page.add(self.create_section)
        page.add(PolicyCallout(
            "Zero Trust check",
            "Before creating the grant, the GUI asks the same policy engine used by reveal/copy/export actions. RBAC, MFA, 2FA, and device-trust rules can block sharing.",
        ))
        page.add_stretch()
        return page

    def _registry_page(self) -> DialogPage:
        page = DialogPage()
        self.registry_section = AccessRegistrySection()
        self.registry = self.registry_section.registry
        self.revoke_entry = self.registry_section.revoke_entry
        self.revoke_match = self.registry_section.revoke_match
        self.revoke_reason = self.registry_section.revoke_reason
        self.registry.currentCellChanged.connect(self._registry_selected)
        self.registry_section.revoke_button.clicked.connect(self._revoke_grant)
        page.add(self.registry_section)
        page.add(PolicyCallout(
            "Revocation boundary",
            "Revocation blocks future app/sync access and is audited. It cannot erase a sealed blob that was already copied outside the vault.",
        ))
        page.add_stretch()
        return page

    def _receive_page(self) -> DialogPage:
        page = DialogPage()
        self.receive_section = ReceiveSecretSection()
        self.receive_private_key = self.receive_section.private_key
        self.receive_blob = self.receive_section.sealed_blob
        self.opened_secret = self.receive_section.opened_secret
        self.save_name = self.receive_section.save_name
        self.save_username = self.receive_section.save_username
        self.save_url = self.receive_section.save_url
        self.receive_section.load_private_button.clicked.connect(self._load_private_key)
        self.receive_section.use_generated_button.clicked.connect(self._use_generated_private_key)
        self.receive_section.open_button.clicked.connect(self._open_blob)
        self.receive_section.save_button.clicked.connect(self._save_received_secret)
        page.add(self.receive_section)
        page.add_stretch()
        return page

    # ---- shared UI helpers --------------------------------------------
    def _copy_text(self, text: str, message: str):
        text = (text or "").strip()
        if not text:
            QMessageBox.warning(self, "Nothing to copy", "There is no value to copy yet.")
            return
        cb = QApplication.clipboard()
        if cb is not None:
            cb.setText(text)
        self.status.setText(message)

    def _write_file(self, title: str, default_name: str, payload: str, private: bool = False):
        payload = (payload or "").strip()
        if not payload:
            QMessageBox.warning(self, "Nothing to save", "There is no value to save yet.")
            return
        path, _ = QFileDialog.getSaveFileName(self, title, default_name, "Key files (*.key *.pub);;Text files (*.txt);;All files (*)")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(payload + "\n")
        if private:
            try:
                import os
                os.chmod(path, 0o600)
            except OSError:
                pass
        QMessageBox.information(self, "Saved", f"Saved to:\n{path}")

    @staticmethod
    def _select_combo_text(combo: QComboBox, text: str):
        SharingWorkflowController.select_combo_text(combo, text)

    # ---- data refresh --------------------------------------------------
    def _refresh_all(self):
        current_create = self.entry_combo.currentText() if hasattr(self, "entry_combo") else self._initial_entry_name
        current_revoke = self.revoke_entry.currentText() if hasattr(self, "revoke_entry") else self._initial_entry_name
        names = self._workflow.entry_names()
        for combo, selected in ((self.entry_combo, current_create), (self.revoke_entry, current_revoke)):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            self._select_combo_text(combo, selected or self._initial_entry_name)
            combo.blockSignals(False)
        self._refresh_registry()

    def _refresh_registry(self):
        rows = self._workflow.grant_rows()
        self.registry.setRowCount(len(rows))
        for row, registry_row in enumerate(rows):
            for col, value in enumerate(registry_row.table_values):
                item = QTableWidgetItem(str(value))
                item.setData(Qt.UserRole, {"entry": registry_row.entry_name, "grant": registry_row.grant})
                self.registry.setItem(row, col, item)
        self.registry.resizeColumnsToContents()
        active, revoked = self._workflow.grant_counts()
        self.status.setText(f"Access registry: {active} active · {revoked} revoked grant(s)")

    # ---- actions -------------------------------------------------------
    def _generate_keys(self):
        pair = self._workflow.generate_keys()
        self.private_key.setPlainText(pair.private_key)
        self.public_key.setPlainText(pair.public_key)
        self.status.setText("Recipient keypair generated.")

    def _save_private_key(self):
        self._write_file("Save private key", "aegisvault_recipient.key", self.private_key.toPlainText(), private=True)

    def _save_public_key(self):
        self._write_file("Save public key", "aegisvault_recipient.pub", self.public_key.toPlainText())

    def _use_generated_public_key(self):
        pub = self.public_key.toPlainText().strip() or self._workflow.last_public_key
        if not pub:
            QMessageBox.warning(self, "No generated key", "Generate a keypair first or paste a recipient public key.")
            return
        self.grant_public_key.setPlainText(pub)
        self.tabs.setCurrentIndex(1)

    def _use_generated_private_key(self):
        priv = self.private_key.toPlainText().strip() or self._workflow.last_private_key
        if not priv:
            QMessageBox.warning(self, "No generated key", "Generate a keypair first or paste/load a private key.")
            return
        self.receive_private_key.setPlainText(priv)
        self.tabs.setCurrentIndex(3)

    def _sealed_blob_only(self) -> str:
        return self._workflow.sealed_blob_only(self.grant_result.toPlainText())

    def _create_grant(self):
        try:
            result = self._workflow.create_grant(
                self.entry_combo.currentText(),
                self.recipient.text(),
                self.grant_public_key.toPlainText(),
            )
        except PermissionError as exc:
            QMessageBox.warning(self, "Policy blocked", str(exc))
            return
        except Exception as exc:
            QMessageBox.warning(self, "Share failed", str(exc))
            return
        self.grant_result.setPlainText(result.display_text)
        self._refresh_all()
        self._select_combo_text(self.revoke_entry, result.entry_name)
        self.tabs.setCurrentIndex(2)
        QMessageBox.information(self, "Share created", "Encrypted access grant created and audited.")

    def _registry_selected(self, row: int, _col: int, _prev_row: int, _prev_col: int):
        if row < 0:
            return
        item = self.registry.item(row, 0)
        if item is None:
            return
        data = item.data(Qt.UserRole) or {}
        grant = data.get("grant", {})
        entry_name = data.get("entry", "")
        self._select_combo_text(self.revoke_entry, entry_name)
        self.revoke_match.setText(grant.get("grant_id") or grant.get("recipient") or grant.get("public_key_fingerprint") or "")
        if not self.revoke_reason.text().strip():
            self.revoke_reason.setText("manual revocation")

    def _revoke_grant(self):
        try:
            revoked = self._workflow.revoke_grant(
                self.revoke_entry.currentText(),
                self.revoke_match.text(),
                self.revoke_reason.text(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Revoke failed", str(exc))
            return
        self._refresh_all()
        QMessageBox.information(self, "Access revoked", f"Revoked {revoked} active grant(s).")

    def _load_private_key(self):
        path, _ = QFileDialog.getOpenFileName(self, "Load private key", "", "Key files (*.key *.txt);;All files (*)")
        if not path:
            return
        try:
            with open(path, encoding="utf-8") as fh:
                self.receive_private_key.setPlainText(fh.read().strip())
        except OSError as exc:
            QMessageBox.warning(self, "Could not read key", str(exc))

    def _open_blob(self):
        try:
            secret = self._workflow.open_blob(
                self.receive_private_key.toPlainText(),
                self.receive_blob.toPlainText(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Could not open blob", str(exc))
            return
        self.opened_secret.setPlainText(secret)
        self.status.setText("Sealed blob opened successfully.")

    def _save_received_secret(self):
        try:
            self._workflow.save_received_secret(
                name=self.save_name.text(),
                username=self.save_username.text(),
                secret=self.opened_secret.toPlainText(),
                url=self.save_url.text(),
            )
        except Exception as exc:
            QMessageBox.warning(self, "Could not save secret", str(exc))
            return
        self._refresh_all()
        QMessageBox.information(self, "Saved", f"Received secret saved as '{self.save_name.text().strip()}'.")
