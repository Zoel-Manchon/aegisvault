"""Add-entry dialog with modular Zero Trust form sections."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTabWidget, QVBoxLayout

from .add_sections import CredentialSection, ZeroTrustMetadataSection
from .components.dialogs import DialogHero, DialogPage, PolicyCallout


class AddEntryDialog(QDialog):
    def __init__(self, session, parent=None, settings=None):
        super().__init__(parent)
        self._session = session
        self._settings = settings
        self.setWindowTitle("Add secret")
        self.setMinimumSize(720, 520)
        self.resize(760, 560)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        outer.addWidget(DialogHero(
            "Add Zero Trust secret",
            "Store the credential and attach policy metadata: URL favicon, team vault, sensitivity, groups, rotation, and 2FA.",
        ))

        self.credential_section = CredentialSection(session)
        self.trust_section = ZeroTrustMetadataSection(session, settings)
        self._bind_legacy_field_aliases()

        tabs = QTabWidget()
        tabs.setObjectName("settingsTabs")
        tabs.addTab(self._basic_page(), "Secret")
        tabs.addTab(self._trust_page(), "Zero Trust")
        outer.addWidget(tabs, 1)
        outer.addLayout(self._footer())

    def _bind_legacy_field_aliases(self) -> None:
        """Keep older controller/tests compatible while the dialog is componentized."""
        for name in ("name", "username", "secret", "url", "category", "tags"):
            setattr(self, name, getattr(self.credential_section, name))
        for name in ("team_vault", "sensitivity", "allowed_groups", "rotation_days", "totp"):
            setattr(self, name, getattr(self.trust_section, name))

    def _basic_page(self) -> DialogPage:
        page = DialogPage()
        page.add(self.credential_section)
        page.add(PolicyCallout(
            "Favicons are automatic",
            "Use a website URL like binance.com, github.com, aws.amazon.com, or cloudflare.com. The desktop app caches the favicon and falls back to a local brand icon offline.",
        ))
        page.add_stretch()
        return page

    def _trust_page(self) -> DialogPage:
        page = DialogPage()
        page.add(self.trust_section)
        page.add(PolicyCallout(
            "Zero Trust context",
            "These fields let the policy engine decide whether reveal, copy, share, export, and rotation actions should be allowed for the current identity and device.",
        ))
        page.add_stretch()
        return page

    def _footer(self) -> QHBoxLayout:
        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save secret")
        save.setObjectName("primary")
        save.clicked.connect(self.accept)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        return buttons

    def _generate(self):
        self.credential_section.generate_secret()

    def _generate_totp(self):
        self.trust_section.generate_totp()

    def values(self) -> dict:
        return {**self.credential_section.values(), **self.trust_section.values()}
