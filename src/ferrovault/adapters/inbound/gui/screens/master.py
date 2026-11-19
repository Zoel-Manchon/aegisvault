"""Choosing a master password: shared by create (unlock), rotate and recover.

The floor comes from ``application.services.master_password`` (12+
characters, not a known password, 60+ bits by the pattern-aware estimate),
so the GUI and the CLI refuse exactly the same passwords.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from .....application.services.master_password import master_password_problems
from .....domain.services.password_strength import PasswordStrength
from ..components.kit import PasswordField, StrengthMeter, caps_lock_on, label

_STRENGTH = PasswordStrength()


class NewPasswordFields(QWidget):
    """New password + meter + policy problem + repeat (with «Coinciden»)."""

    changed = Signal()

    def __init__(self, title: str = "Nueva contraseña maestra", confirm_title: str = "Repite la nueva",
                 avoid: str | None = None, hint: str = ""):
        super().__init__()
        self.setObjectName("transparent")
        self._avoid = avoid
        self._hint = hint
        col = QVBoxLayout(self)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(6)
        col.addWidget(label(title, "label"))
        self.password = PasswordField()
        self.password.setAccessibleName(title)
        col.addWidget(self.password)
        self.meter = StrengthMeter(show_hint=bool(hint))
        self.meter.set_assessment(None, hint)
        col.addWidget(self.meter)
        self.problem = label("", "toneText", wrap=True, tone="danger")
        self.problem.hide()
        col.addWidget(self.problem)
        col.addSpacing(8)
        col.addWidget(label(confirm_title, "label"))
        self.confirm = PasswordField()
        self.confirm.setAccessibleName(confirm_title)
        col.addWidget(self.confirm)
        self.caps = label("Bloq Mayús está activado", "toneText", tone="warning")
        self.caps.hide()
        col.addWidget(self.caps)
        self.password.textChanged.connect(self._update)
        self.confirm.textChanged.connect(self._update)

    def set_avoid(self, previous: str | None) -> None:
        """A password the new one must differ from (the current one, on rotate)."""
        self._avoid = previous
        self._update()

    def value(self) -> str:
        return self.password.text()

    def problems(self) -> list[str]:
        pw = self.password.text()
        problems = master_password_problems(pw, _STRENGTH) if pw else ["Escribe una contraseña"]
        if pw and self._avoid and pw == self._avoid:
            problems.append("Es la misma que la actual")
        return problems

    def is_valid(self) -> bool:
        return not self.problems() and self.password.text() == self.confirm.text()

    def _update(self, *_):
        pw = self.password.text()
        self.meter.set_assessment(_STRENGTH.assess(pw) if pw else None, self._hint)
        problems = self.problems() if pw else []
        self.problem.setText(problems[0] if problems else "")
        self.problem.setVisible(bool(problems))
        repeat = self.confirm.text()
        if repeat and repeat == pw:
            self.confirm.set_trailing("Coinciden", "success", "check")
        elif repeat and not pw.startswith(repeat):
            self.confirm.set_trailing("No coinciden", "danger", "warning")
        else:
            self.confirm.set_trailing("")
        self.caps.setVisible(caps_lock_on())
        self.changed.emit()

    def wipe(self) -> None:
        self.password.wipe()
        self.confirm.wipe()
