"""Desktop passkey / biometric unlock setup dialog."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QTextEdit, QVBoxLayout

from ....application.services.passkey_unlock import DesktopPasskeyUnlockService
from .components.dialogs import DialogFooter, DialogHero, FormCard


class PasskeyUnlockDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Passkey unlock")
        self.setMinimumSize(700, 520)
        service = DesktopPasskeyUnlockService()
        cap = service.capability()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(DialogHero("Passkey / biometric unlock", "Foundation for desktop WebAuthn unlock with user verification and trusted-device policy."))

        status = FormCard("Current capability")
        status.layout().addWidget(QLabel(f"Platform: {cap.platform}"))
        status.layout().addWidget(QLabel(f"Authenticator target: {cap.biometric_hint}"))
        status.layout().addWidget(QLabel("Status: foundation wired, production ceremony not enabled yet"))
        layout.addWidget(status)

        steps = QTextEdit()
        steps.setReadOnly(True)
        steps.setPlainText(cap.message + "\n\nImplementation checklist:\n" + "\n".join(f"• {s}" for s in service.enrollment_steps()))
        layout.addWidget(steps, 1)

        footer = DialogFooter()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        footer.layout().addStretch()
        footer.layout().addWidget(close)
        layout.addWidget(footer)
