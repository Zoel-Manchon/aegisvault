"""Tabbed settings center for local Zero Trust controls."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QHBoxLayout, QPushButton, QTabWidget, QVBoxLayout

from ....application.services.settings import VaultSettings
from .components.dialogs import DialogHero
from .settings_sections import DefaultsSettingsPage, IdentitySettingsPage, SecuritySettingsPage, ZeroTrustSettingsPage


class SettingsCenterDialog(QDialog):
    """Scroll-safe GUI for all local policy/security settings.

    The dialog now composes reusable tab components. MainWindow remains
    responsible for persisting the returned settings and refreshing live policy.
    """

    def __init__(
        self,
        settings: VaultSettings,
        parent=None,
        *,
        open_policy_pack=None,
        open_access_requests=None,
        open_directory=None,
        open_sync_bundle=None,
    ):
        super().__init__(parent)
        self._settings = settings
        self.result_settings: VaultSettings | None = None

        self.setWindowTitle("Zero Trust settings")
        self.setMinimumSize(760, 560)
        self.resize(840, 660)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        outer.addWidget(DialogHero(
            "Zero Trust policy center",
            "Configure identity, device trust, MFA, clipboard safety, audit export, defaults, and encrypted sync controls from one place.",
        ))

        self.tabs = QTabWidget()
        self.tabs.setObjectName("settingsTabs")
        outer.addWidget(self.tabs, 1)

        self.security_page = SecuritySettingsPage(settings)
        self.zero_trust_page = ZeroTrustSettingsPage(
            settings,
            open_policy_pack=open_policy_pack,
            open_access_requests=open_access_requests,
        )
        self.identity_page = IdentitySettingsPage(settings, open_directory=open_directory)
        self.defaults_page = DefaultsSettingsPage(settings, open_sync_bundle=open_sync_bundle)

        self.tabs.addTab(self.security_page, "Security")
        self.tabs.addTab(self.zero_trust_page, "Zero Trust")
        self.tabs.addTab(self.identity_page, "Identity / RBAC")
        self.tabs.addTab(self.defaults_page, "Defaults")

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save settings")
        save.setObjectName("primary")
        save.clicked.connect(self._accept_settings)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        outer.addLayout(buttons)

    def _accept_settings(self) -> None:
        security = self.security_page
        zero_trust = self.zero_trust_page
        identity = self.identity_page
        defaults = self.defaults_page
        self.result_settings = VaultSettings(
            clipboard_clear_seconds=security.clipboard_seconds.value(),
            auto_lock_seconds=security.auto_lock_seconds.value(),
            require_reveal_before_copy=security.require_reveal.isChecked(),
            show_health_sidebar=security.show_health.isChecked(),
            enterprise_sync_enabled=defaults.enterprise_sync.isChecked(),
            policy_enforcement_enabled=zero_trust.policy_enabled.isChecked(),
            require_totp_for_shared=zero_trust.require_totp.isChecked(),
            block_export_when_audit_broken=zero_trust.block_export.isChecked(),
            enterprise_role=identity.role_box.currentText(),
            enterprise_user_id=identity.user_id.text().strip() or "local-admin",
            enterprise_display_name=identity.display_name.text().strip() or "Local Admin",
            local_device_id=identity.device_id.text().strip() or "local-device",
            trusted_device_ids=tuple(x.strip() for x in identity.trusted_devices.text().split(",") if x.strip()),
            require_trusted_device=zero_trust.require_trusted.isChecked(),
            require_mfa_for_high_sensitivity=zero_trust.require_mfa_high.isChecked(),
            default_team_vault=defaults.default_team.text().strip() or "Personal",
            default_rotation_interval_days=defaults.default_rotation.value(),
            policy_rules=self._settings.policy_rules,
            recipient_directory=self._settings.recipient_directory,
            access_requests=self._settings.access_requests,
        ).normalized()
        self.accept()
