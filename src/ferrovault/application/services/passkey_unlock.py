"""Desktop passkey/biometric unlock capability seam.

This module deliberately does not fake WebAuthn.  It provides a product-facing
contract and platform capability report so the GUI can expose the feature while
keeping the actual passkey ceremony behind a proper future adapter.
"""
from __future__ import annotations

import platform
from dataclasses import dataclass


@dataclass(frozen=True)
class PasskeyCapability:
    platform: str
    biometric_hint: str
    webauthn_ready: bool
    message: str


class DesktopPasskeyUnlockService:
    """Report capability and define the passkey unlock lifecycle seam."""

    def capability(self) -> PasskeyCapability:
        system = platform.system() or "Unknown"
        hints = {
            "Windows": "Windows Hello / security key",
            "Darwin": "Touch ID / security key",
            "Linux": "FIDO2 security key / system biometric stack",
        }
        return PasskeyCapability(
            platform=system,
            biometric_hint=hints.get(system, "platform authenticator / security key"),
            webauthn_ready=False,
            message=(
                "Foundation is wired. A production unlock flow still needs a local "
                "credential store, challenge signing, account binding, and recovery path."
            ),
        )

    def enrollment_steps(self) -> tuple[str, ...]:
        return (
            "Unlock with the master password once.",
            "Create a device-bound passkey credential.",
            "Encrypt/wrap a vault unlock secret with hardware-backed proof.",
            "Require policy checks: user present, user verified, trusted device.",
            "Keep recovery shares enabled before passkey-only unlock is allowed.",
        )
