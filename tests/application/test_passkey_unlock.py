from __future__ import annotations

from ferrovault.application.services.passkey_unlock import DesktopPasskeyUnlockService


def test_passkey_capability_reports_foundation_status():
    service = DesktopPasskeyUnlockService()
    capability = service.capability()
    assert capability.platform
    assert capability.biometric_hint
    assert capability.webauthn_ready is False
    assert service.enrollment_steps()
