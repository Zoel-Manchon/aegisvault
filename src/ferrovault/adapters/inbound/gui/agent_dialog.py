"""Browser extension / autofill agent information dialog."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel, QPushButton, QTextEdit, QVBoxLayout

from ..agent import DEFAULT_SOCKET
from .components.dialogs import DialogFooter, DialogHero, FormCard


class AutofillAgentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Browser autofill agent")
        self.setMinimumSize(720, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)
        layout.addWidget(DialogHero("Browser autofill agent", "Local socket bridge for a future browser extension. The agent never exposes the master key."))

        card = FormCard("Agent contract")
        card.layout().addWidget(QLabel(f"Default socket: {DEFAULT_SOCKET}"))
        card.layout().addWidget(QLabel("Commands: LIST, GET <name>, CODE <name>, LOCK"))
        card.layout().addWidget(QLabel("Security: Unix socket permissions 0600, idle auto-lock, no plaintext vault file."))
        layout.addWidget(card)

        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(
            "Run the current agent manually:\n\n"
            "  aegisvault --vault demo.fv agent --timeout 300\n\n"
            "Browser-extension next step:\n"
            "• Native messaging host manifest\n"
            "• Origin allow-list\n"
            "• Per-site policy check before GET\n"
            "• User-presence prompt for high/critical secrets\n"
            "• Audit event for every autofill request\n"
        )
        layout.addWidget(text, 1)

        footer = DialogFooter()
        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        footer.layout().addStretch()
        footer.layout().addWidget(close)
        layout.addWidget(footer)
