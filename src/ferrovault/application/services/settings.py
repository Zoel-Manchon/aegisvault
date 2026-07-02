"""Persistent desktop settings for AegisVault.

These settings are intentionally stored outside the encrypted vault: they are
non-secret UI and policy preferences, not vault data. The store uses atomic JSON
writes so toggles survive restarts without risking a partially written file.
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, fields

from .policy_pack import default_policy_rules
from pathlib import Path


@dataclass(frozen=True)
class VaultSettings:
    """User-facing desktop and local policy settings."""

    clipboard_clear_seconds: int = 15
    auto_lock_seconds: int = 300
    require_reveal_before_copy: bool = True
    show_health_sidebar: bool = True
    enterprise_sync_enabled: bool = False
    policy_enforcement_enabled: bool = True
    require_totp_for_shared: bool = True
    block_export_when_audit_broken: bool = True
    enterprise_role: str = "owner"
    enterprise_user_id: str = "local-admin"
    enterprise_display_name: str = "Local Admin"
    local_device_id: str = "local-device"
    trusted_device_ids: tuple[str, ...] = ("local-device",)
    require_trusted_device: bool = True
    require_mfa_for_high_sensitivity: bool = True
    default_team_vault: str = "Personal"
    default_rotation_interval_days: int = 90
    policy_rules: tuple[dict, ...] = default_policy_rules()
    recipient_directory: tuple[dict, ...] = ()
    access_requests: tuple[dict, ...] = ()

    @classmethod
    def from_dict(cls, data: dict | None) -> "VaultSettings":
        data = data or {}
        allowed = {f.name for f in fields(cls)}
        clean = {k: v for k, v in data.items() if k in allowed}
        settings = cls(**clean)
        return settings.normalized()

    def normalized(self) -> "VaultSettings":
        clear = max(1, min(int(self.clipboard_clear_seconds), 3600))
        lock = max(0, min(int(self.auto_lock_seconds), 24 * 3600))
        valid_roles = {"owner", "admin", "auditor", "member", "readonly"}
        role = self.enterprise_role if self.enterprise_role in valid_roles else "readonly"
        trusted = self.trusted_device_ids
        if isinstance(trusted, str):
            trusted = (trusted,)
        trusted = tuple(dict.fromkeys(str(x).strip() for x in trusted if str(x).strip()))
        device_id = (self.local_device_id or "local-device").strip()
        if self.require_trusted_device and not trusted:
            trusted = (device_id,)
        return VaultSettings(
            clipboard_clear_seconds=clear,
            auto_lock_seconds=lock,
            require_reveal_before_copy=bool(self.require_reveal_before_copy),
            show_health_sidebar=bool(self.show_health_sidebar),
            enterprise_sync_enabled=bool(self.enterprise_sync_enabled),
            policy_enforcement_enabled=bool(self.policy_enforcement_enabled),
            require_totp_for_shared=bool(self.require_totp_for_shared),
            block_export_when_audit_broken=bool(self.block_export_when_audit_broken),
            enterprise_role=role,
            enterprise_user_id=(self.enterprise_user_id or "local-admin").strip(),
            enterprise_display_name=(self.enterprise_display_name or "Local Admin").strip(),
            local_device_id=device_id,
            trusted_device_ids=trusted,
            require_trusted_device=bool(self.require_trusted_device),
            require_mfa_for_high_sensitivity=bool(self.require_mfa_for_high_sensitivity),
            default_team_vault=(self.default_team_vault or "Personal").strip(),
            default_rotation_interval_days=max(1, min(int(self.default_rotation_interval_days), 3650)),
            policy_rules=_normalize_dict_tuple(self.policy_rules),
            recipient_directory=_normalize_dict_tuple(self.recipient_directory),
            access_requests=_normalize_dict_tuple(self.access_requests),
        )

    def to_dict(self) -> dict:
        return asdict(self.normalized())


class JsonSettingsStore:
    """Small JSON-backed settings repository."""

    def __init__(self, path: str | os.PathLike | None = None):
        self.path = Path(path) if path else default_settings_path()

    def load(self) -> VaultSettings:
        if not self.path.exists():
            return VaultSettings()
        try:
            with self.path.open(encoding="utf-8") as fh:
                return VaultSettings.from_dict(json.load(fh))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return VaultSettings()

    def save(self, settings: VaultSettings) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8") as fh:
            json.dump(settings.to_dict(), fh, indent=2, sort_keys=True)
        os.replace(tmp, self.path)


class MemorySettingsStore:
    """In-memory settings store for tests and embedders."""

    def __init__(self, settings: VaultSettings | None = None):
        self._settings = settings or VaultSettings()

    def load(self) -> VaultSettings:
        return self._settings

    def save(self, settings: VaultSettings) -> None:
        self._settings = settings.normalized()



def _normalize_dict_tuple(value) -> tuple[dict, ...]:
    if not value:
        return ()
    if isinstance(value, dict):
        value = (value,)
    out = []
    for item in value:
        if isinstance(item, dict):
            out.append({str(k): _freeze_json_value(v) for k, v in item.items()})
    return tuple(out)


def _freeze_json_value(value):
    if isinstance(value, list):
        return tuple(_freeze_json_value(v) for v in value)
    if isinstance(value, dict):
        return {str(k): _freeze_json_value(v) for k, v in value.items()}
    return value


def default_settings_path() -> Path:
    root = (os.environ.get("AEGISVAULT_CONFIG_DIR") or os.environ.get("SNEKRUST_CONFIG_DIR") or os.environ.get("FERROVAULT_CONFIG_DIR"))
    if root:
        return Path(root) / "settings.json"
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
        return Path(base) / "aegisvault" / "settings.json"
    return Path.home() / ".config" / "aegisvault" / "settings.json"
