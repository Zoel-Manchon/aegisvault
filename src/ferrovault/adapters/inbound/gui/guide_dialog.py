"""Short in-app guide for the main AegisVault workflows."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget


class QuickStartDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Quick start · AegisVault")
        self.setMinimumSize(560, 620)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(14)

        title = QLabel("How to use AegisVault")
        title.setObjectName("h1")
        subtitle = QLabel("Finish the product features first, then this guide becomes the user manual. For now it covers the safest daily workflow.")
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        root.addWidget(title)
        root.addWidget(subtitle)

        body = QWidget()
        col = QVBoxLayout(body)
        col.setSpacing(12)
        for heading, text in _STEPS:
            col.addWidget(_step_card(heading, text))
        col.addStretch(1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        root.addWidget(close, alignment=Qt.AlignRight)


def _step_card(heading: str, text: str) -> QFrame:
    card = QFrame()
    card.setObjectName("panel")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(16, 14, 16, 14)
    layout.setSpacing(6)
    h = QLabel(heading)
    h.setObjectName("h2")
    body = QLabel(text)
    body.setObjectName("muted")
    body.setWordWrap(True)
    layout.addWidget(h)
    layout.addWidget(body)
    return card


_STEPS = (
    ("1. Add a secret", "Use New to save a credential. Add a URL so the vault can show a site icon and later support browser autofill."),
    ("2. Use Ctrl+K", "The command palette jumps to entries and opens Zero Trust tools without hunting through menus."),
    ("3. Reveal only when needed", "AegisVault keeps secrets hidden by default. Copy/reveal actions are checked by the policy engine."),
    ("4. Add 2FA when possible", "TOTP makes each entry stronger and unlocks stricter Zero Trust sharing policies."),
    ("5. Share with grants", "Use Sharing Center to create recipient-key grants, list active access, and revoke users/devices."),
    ("6. Watch Zero Trust", "The Zero Trust command center shows identity, device trust, audit integrity, sharing, sync, and policy posture."),
    ("7. Check health in the background", "Health scanning now runs asynchronously, so large vaults should not freeze the interface."),
)
