"""Reusable Settings Center tab components."""
from __future__ import annotations

from PySide6.QtWidgets import QComboBox, QFrame, QLabel, QLineEdit, QPushButton, QSpinBox, QVBoxLayout

from ....application.services.settings import VaultSettings
from .components.forms import FormRow, ScrollFormPage, ToggleRow


class SecuritySettingsPage(ScrollFormPage):
    """Clipboard, auto-lock, and local desktop safety controls."""

    def __init__(self, settings: VaultSettings):
        super().__init__()
        self.clipboard_seconds = QSpinBox()
        self.clipboard_seconds.setRange(1, 3600)
        self.clipboard_seconds.setSuffix(" sec")
        self.clipboard_seconds.setValue(settings.clipboard_clear_seconds)
        self.layout.addWidget(FormRow("Clipboard clear", self.clipboard_seconds, "Clear copied secrets from the OS clipboard after this many seconds."))

        self.auto_lock_seconds = QSpinBox()
        self.auto_lock_seconds.setRange(0, 86400)
        self.auto_lock_seconds.setSuffix(" sec")
        self.auto_lock_seconds.setSpecialValueText("Disabled")
        self.auto_lock_seconds.setValue(settings.auto_lock_seconds)
        self.layout.addWidget(FormRow("Auto-lock", self.auto_lock_seconds, "Wipe the unlocked session and clear the clipboard after inactivity."))

        self.require_reveal = ToggleRow(
            "Require reveal before copy",
            settings.require_reveal_before_copy,
            "Prevents silent copying. A user must intentionally reveal a secret before copy is allowed.",
        )
        self.layout.addWidget(self.require_reveal)

        self.show_health = ToggleRow(
            "Show health status in sidebar",
            settings.show_health_sidebar,
            "Keeps a compact vault-health indicator visible in the left navigation.",
        )
        self.layout.addWidget(self.show_health)
        self.addStretch()


class ZeroTrustSettingsPage(ScrollFormPage):
    """Local policy enforcement and governed access controls."""

    def __init__(self, settings: VaultSettings, *, open_policy_pack=None, open_access_requests=None):
        super().__init__()
        self.policy_enabled = ToggleRow(
            "Enable policy enforcement",
            settings.policy_enforcement_enabled,
            "Turn off only for monitor/demo mode. When enabled, blocked decisions are denied.",
        )
        self.layout.addWidget(self.policy_enabled)

        self.require_trusted = ToggleRow(
            "Require trusted device",
            settings.require_trusted_device,
            "Sensitive actions require the current device ID to appear in the trusted-device list.",
        )
        self.layout.addWidget(self.require_trusted)

        self.require_mfa_high = ToggleRow(
            "Require MFA for high-sensitivity secrets",
            settings.require_mfa_for_high_sensitivity,
            "Critical and high-sensitivity entries require MFA context before reveal/copy/share.",
        )
        self.layout.addWidget(self.require_mfa_high)

        self.require_totp = ToggleRow(
            "Block sharing entries without 2FA",
            settings.require_totp_for_shared,
            "Prevents team sharing of records that have no TOTP seed attached.",
        )
        self.layout.addWidget(self.require_totp)

        self.block_export = ToggleRow(
            "Block SIEM export if audit chain fails",
            settings.block_export_when_audit_broken,
            "Protects exported audit evidence from leaving the app when integrity verification fails.",
        )
        self.layout.addWidget(self.block_export)

        policy_pack_btn = QPushButton("Open policy-pack editor")
        policy_pack_btn.setObjectName("primary")
        if open_policy_pack:
            policy_pack_btn.clicked.connect(open_policy_pack)
        self.layout.addWidget(FormRow("Policy pack", policy_pack_btn, "Create deny rules for action, sensitivity, team vault, category, MFA, and device trust."))

        access_btn = QPushButton("Open access requests")
        access_btn.setObjectName("primary")
        if open_access_requests:
            access_btn.clicked.connect(open_access_requests)
        self.layout.addWidget(FormRow("Access approvals", access_btn, "Create, approve, or deny governed access requests for future just-in-time workflows."))
        self.addStretch()


class IdentitySettingsPage(ScrollFormPage):
    """Local identity, RBAC role, and device-trust defaults."""

    def __init__(self, settings: VaultSettings, *, open_directory=None):
        super().__init__()
        self.role_box = QComboBox()
        self.role_box.addItems(["owner", "admin", "auditor", "member", "readonly"])
        self.role_box.setCurrentText(settings.enterprise_role)
        self.layout.addWidget(FormRow("RBAC role", self.role_box, "Local role used until SSO/OIDC claims provide the real enterprise identity."))

        self.user_id = QLineEdit(settings.enterprise_user_id)
        self.layout.addWidget(FormRow("User ID", self.user_id, "Stable local principal used by audit records and policy context."))

        self.display_name = QLineEdit(settings.enterprise_display_name)
        self.layout.addWidget(FormRow("Display name", self.display_name, "Human-readable identity shown in local enterprise posture."))

        self.device_id = QLineEdit(settings.local_device_id)
        self.layout.addWidget(FormRow("Device ID", self.device_id, "Local device identifier used by device-trust policy."))

        self.trusted_devices = QLineEdit(",".join(settings.trusted_device_ids))
        self.trusted_devices.setPlaceholderText("local-device,laptop-workstation,yubikey-host")
        self.layout.addWidget(FormRow("Trusted devices", self.trusted_devices, "Comma-separated device IDs allowed for sensitive actions."))

        directory_btn = QPushButton("Open user/device directory")
        directory_btn.setObjectName("primary")
        if open_directory:
            directory_btn.clicked.connect(open_directory)
        self.layout.addWidget(FormRow("Directory", directory_btn, "Manage recipient public keys, roles, groups, and trusted device IDs from the GUI."))
        self.addStretch()


class DefaultsSettingsPage(ScrollFormPage):
    """Defaults and local encrypted sync controls."""

    def __init__(self, settings: VaultSettings, *, open_sync_bundle=None):
        super().__init__()
        self.default_team = QLineEdit(settings.default_team_vault)
        self.layout.addWidget(FormRow("Default team vault", self.default_team, "Default collection/team vault for newly-created enterprise secrets."))

        self.default_rotation = QSpinBox()
        self.default_rotation.setRange(1, 3650)
        self.default_rotation.setSuffix(" days")
        self.default_rotation.setValue(settings.default_rotation_interval_days)
        self.layout.addWidget(FormRow("Default rotation", self.default_rotation, "Default secret rotation SLA for new records."))

        self.enterprise_sync = ToggleRow(
            "Enable enterprise sync placeholder",
            settings.enterprise_sync_enabled,
            "Reserved switch for the upcoming encrypted team-vault sync layer.",
        )
        self.layout.addWidget(self.enterprise_sync)

        sync_btn = QPushButton("Open encrypted sync bundles")
        sync_btn.setObjectName("primary")
        if open_sync_bundle:
            sync_btn.clicked.connect(open_sync_bundle)
        self.layout.addWidget(FormRow("Encrypted sync", sync_btn, "Export/import zero-plaintext sync bundles for local multi-device workflows."))
        self.layout.addWidget(self._coverage_callout())
        self.addStretch()

    @staticmethod
    def _coverage_callout() -> QFrame:
        callout = QFrame()
        callout.setObjectName("policyCallout")
        callout_box = QVBoxLayout(callout)
        callout_box.setContentsMargins(16, 14, 16, 14)
        callout_title = QLabel("GUI coverage")
        callout_title.setObjectName("h2")
        callout_body = QLabel(
            "Desktop users can configure the important local controls here. The CLI remains useful for automation, "
            "bulk import/export, CI checks, and future headless agents."
        )
        callout_body.setObjectName("muted")
        callout_body.setWordWrap(True)
        callout_box.addWidget(callout_title)
        callout_box.addWidget(callout_body)
        return callout
