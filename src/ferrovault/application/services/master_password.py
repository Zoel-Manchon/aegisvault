"""Minimum policy for a master password (create, rotate, recover).

The master password is the only thing standing between a stolen vault file and
an offline guessing attack, so it gets a floor that ordinary entries do not:
at least 12 characters, not a well-known password, and at least 60 bits by the
pattern-aware estimate. Messages are user-facing (Spanish, like the GUI).
"""
from __future__ import annotations

from ...domain.services.password_strength import PasswordStrength
from ..errors import WeakMasterPassword

MIN_LENGTH = 12
MIN_BITS = 60


def master_password_problems(password: str, strength: PasswordStrength | None = None) -> list[str]:
    strength = strength or PasswordStrength()
    problems: list[str] = []
    if len(password) < MIN_LENGTH:
        problems.append(f"Mínimo {MIN_LENGTH} caracteres")
    assessment = strength.assess(password)
    if assessment.common:
        problems.append("Es una contraseña muy conocida: los atacantes la prueban primero")
    elif len(password) >= MIN_LENGTH and assessment.bits < MIN_BITS:
        problems.append("Demasiado predecible: añade más palabras o caracteres variados")
    return problems


def require_strong_master_password(password: str, strength: PasswordStrength | None = None) -> None:
    problems = master_password_problems(password, strength)
    if problems:
        raise WeakMasterPassword(problems[0])
