"""Vault health (board 13): score, the five counters, issues ranked by impact,
the breach check and the rotation policy.

Everything here is computed from the HealthReport (entry names only, never
secrets). "+N pts" is the real score gain of fixing that item with the
analyzer's own weights.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .....domain.services.health import PENALTY, WEAK_BITS
from ..components.kit import Avatar, Badge, Button, Card, Ring, Spinner, clear_layout, icon_label, label, tone_color
from ..fmt import count_word, plural, thousands
from ..theme import PALETTE as P
from .common import Page, kv_row

SEVERITY = {"critical": ("Crítico", "danger", "alert"), "high": ("Alto", "warning", "warning"),
            "medium": ("Medio", "muted", "clock"), "low": ("Bajo", "muted", "circle")}


@dataclass(frozen=True)
class Issue:
    key: str               # breached | reused | weak | old | no_totp
    names: tuple
    title: str
    text: str
    severity: str
    penalty: int           # points this item costs today
    action: str
    fix: str               # generate | totp


def build_issues(report, policy_months: int = 12) -> list[Issue]:
    """Issues ranked by impact (points recovered), most valuable first."""
    issues: list[Issue] = []
    if report is None:
        return issues
    for name, count in report.breached:
        times = "una filtración pública" if count == 1 else f"{thousands(count)} filtraciones públicas"
        issues.append(Issue("breached", (name,), name, f"Aparece en {times}. Cámbiala en el sitio y aquí.",
                            "critical", PENALTY["breached"], "Cambiar contraseña", "generate"))
    for group in report.reused:
        n = len(group)
        title = ", ".join(group[:-1]) + " y " + group[-1] if n <= 3 else f"{group[0]}, {group[1]} y {n - 2} más"
        issues.append(Issue("reused", tuple(group), title,
                            f"Comparten contraseña: si se filtra una, caen las {count_word(n)}.",
                            "high", PENALTY["reused"] * n, "Revisar el grupo", "generate"))
    bits = dict(report.weak_bits)
    for name in report.weak:
        issues.append(Issue("weak", (name,), name,
                            f"Débil: {bits.get(name, 0)} bits. Una frase de 5 palabras la lleva a más de 60.",
                            "high", PENALTY["weak"], "Generar una nueva", "generate"))
    for name, days in report.old:
        months = max(1, days // 30)
        issues.append(Issue("old", (name,), name,
                            f"{months} meses sin cambios; tu política de rotación es de {policy_months}.",
                            "medium", PENALTY["old"], "Rotar ahora", "generate"))
    for name in report.no_totp:
        issues.append(Issue("no_totp", (name,), name,
                            "Sin código 2FA. Si el sitio lo admite, se añade en un minuto.",
                            "low", PENALTY["no_totp"], "Añadir TOTP", "totp"))
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    issues.sort(key=lambda i: (-i.penalty, order[i.severity]))
    return issues


def score_after(report, issues: list[Issue]) -> int:
    """Score once ``issues`` are fixed (the analyzer floors the score at 0)."""
    if report is None:
        return 0
    return max(0, min(100, 100 - (_raw_penalty(report) - sum(i.penalty for i in issues))))


def _raw_penalty(report) -> int:
    return (PENALTY["breached"] * len(report.breached) + PENALTY["weak"] * len(report.weak)
            + PENALTY["reused"] * sum(len(g) for g in report.reused)
            + PENALTY["old"] * len(report.old) + PENALTY["no_totp"] * len(report.no_totp))


def verdict(score: int) -> tuple[str, str]:
    if score >= 80:
        return "Buena", "success"
    if score >= 50:
        return "Mejorable", "warning"
    return "En riesgo", "danger"


class _StatCard(QFrame):
    def __init__(self, title: str, icon_name: str, value: int, caption: str, tone: str | None):
        super().__init__()
        self.setObjectName("statCard")
        if tone and value:
            self.setProperty("tone", tone)
        self.setMinimumHeight(150)
        col = QVBoxLayout(self)
        col.setContentsMargins(16, 16, 16, 16)
        col.setSpacing(6)
        head = QHBoxLayout()
        head.setSpacing(6)
        color = tone_color(tone) if (tone and value) else P.TEXT_SECONDARY
        head.addWidget(icon_label(icon_name, color, 14))
        t = label(title, "statTitle")
        if tone and value:
            t.setProperty("tone", tone)
        head.addWidget(t)
        head.addStretch(1)
        col.addLayout(head)
        col.addStretch(1)
        col.addWidget(label(str(value), "statValue"))
        col.addStretch(1)
        col.addWidget(label(caption, "secondary", wrap=True))


class _IssueRow(QFrame):
    def __init__(self, issue: Issue, gain: int, on_fix: Callable):
        super().__init__()
        self.setObjectName("issueRow")
        row = QHBoxLayout(self)
        row.setContentsMargins(20, 14, 20, 14)
        row.setSpacing(14)
        if issue.key == "reused":
            tile = QLabel(f"×{len(issue.names)}")
            tile.setObjectName("avatar")
            tile.setFixedSize(36, 36)
            tile.setAlignment(Qt.AlignCenter)
            row.addWidget(tile)
        else:
            row.addWidget(Avatar(issue.names[0]))
        text = QVBoxLayout()
        text.setSpacing(2)
        text.addWidget(label(issue.title, "body"))
        text.addWidget(label(issue.text, "secondary", wrap=True))
        row.addLayout(text, 1)
        sev_text, tone, icon_name = SEVERITY[issue.severity]
        sev = QHBoxLayout()
        sev.setSpacing(5)
        color = tone_color(tone)
        sev.addWidget(icon_label(icon_name, color, 13))
        sev_lbl = label(sev_text, "toneText")
        if tone != "muted":
            sev_lbl.setProperty("tone", tone)
        else:
            sev_lbl.setStyleSheet(f"color: {P.TEXT_SECONDARY};")
        sev.addWidget(sev_lbl)
        sev_box = QWidget()
        sev_box.setObjectName("transparent")
        sev_box.setLayout(sev)
        sev_box.setFixedWidth(96)
        row.addWidget(sev_box)
        pts = label(f"+{gain} pt" if gain == 1 else f"+{gain} pts", "monoSm")
        pts.setStyleSheet(f"color: {P.SUCCESS if gain else P.TEXT_TERTIARY};")
        pts.setFixedWidth(64)
        pts.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        row.addWidget(pts)
        btn = Button(issue.action, "secondary", on_click=lambda: on_fix(issue.names[0], issue.fix))
        btn.setFixedWidth(156)
        row.addWidget(btn)


class HealthPage(Page):
    VISIBLE = 5

    def __init__(self, session, settings, report, callbacks: dict, *, on_fix: Callable, on_recheck: Callable,
                 on_policies: Callable, checked_at: float | None = None):
        super().__init__("Salud", callbacks)
        self._session = session
        self._settings = settings
        self._on_fix = on_fix
        self._on_recheck = on_recheck
        self._on_policies = on_policies
        self._checked_at = checked_at
        self._expanded = False
        self._report = None
        self._body = QVBoxLayout()
        self._body.setSpacing(20)
        self.content.addLayout(self._body)
        self.content.addStretch(1)
        self.set_report(report, checked_at)

    def set_report(self, report, checked_at: float | None = None) -> None:
        self._report = report
        if checked_at is not None:
            self._checked_at = checked_at
        clear_layout(self._body)
        if report is None:
            waiting = QHBoxLayout()
            waiting.addStretch(1)
            waiting.addWidget(Spinner(18))
            waiting.addWidget(label("Analizando la bóveda… (solo en este equipo)", "secondary"))
            waiting.addStretch(1)
            self._body.addSpacing(80)
            self._body.addLayout(waiting)
            return
        policy_months = max(1, self._settings.old_password_days // 30)
        issues = build_issues(report, policy_months)
        self._body.addLayout(self._top_row(report, issues))
        columns = QHBoxLayout()
        columns.setSpacing(24)
        columns.addWidget(self._issues_card(report, issues), 1)
        side = QVBoxLayout()
        side.setSpacing(16)
        side.addWidget(self._breach_card(report))
        side.addWidget(self._policy_card())
        note = QFrame()
        note.setObjectName("cardDashed")
        nl = QVBoxLayout(note)
        nl.setContentsMargins(16, 14, 16, 14)
        nl.addWidget(label("Cómo se calcula: parte de 100 y resta por cada asunto según su gravedad y cuántas "
                           "entradas afecta. Nunca baja por tener muchas entradas.", "secondary", wrap=True))
        side.addWidget(note)
        side.addStretch(1)
        side_box = QWidget()
        side_box.setObjectName("transparent")
        side_box.setLayout(side)
        side_box.setFixedWidth(380)
        columns.addWidget(side_box, 0, Qt.AlignTop)
        self._body.addLayout(columns)

    # ---- pieces -------------------------------------------------------------------
    def _top_row(self, report, issues) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        score_card = QFrame()
        score_card.setObjectName("statCard")
        sc = QHBoxLayout(score_card)
        sc.setContentsMargins(28, 22, 28, 22)
        sc.setSpacing(28)
        text, tone = verdict(report.score)
        ring = Ring(130, 9.0, 40, "de 100")
        ring.set_value(report.score / 100, str(report.score), tone_color(tone))
        sc.addWidget(ring)
        col = QVBoxLayout()
        col.setSpacing(8)
        col.addStretch(1)
        col.addWidget(Badge(text, tone, "check" if tone == "success" else "warning"), 0, Qt.AlignLeft)
        col.addWidget(label("Salud de la bóveda", "titleLg"))
        if issues:
            target = score_after(report, issues[:2])
            first = "el primer punto" if len(issues) == 1 else "los dos primeros puntos"
            msg = (f"Arreglando {first} de la lista subes a {target}." if target > report.score
                   else f"{plural(len(issues), 'asunto pendiente', 'asuntos pendientes')}, ordenados por impacto.")
        else:
            msg = "Nada pendiente. Vuelve de vez en cuando: las contraseñas envejecen."
        col.addWidget(label(msg, "secondary", wrap=True))
        col.addStretch(1)
        sc.addLayout(col, 1)
        score_card.setMinimumWidth(420)
        row.addWidget(score_card, 5)
        reused_entries = sum(len(g) for g in report.reused)
        groups = len(report.reused)
        stats = (
            ("Filtradas", "alert", len(report.breached),
             "En Have I Been Pwned" if self._settings.breach_check_online else "Comprobación desactivada", "danger"),
            ("Reutilizadas", "link", reused_entries,
             f"En {plural(groups, 'grupo', 'grupos')}" if groups else "Ninguna repetida", "warning"),
            ("Débiles", "warning", len(report.weak), f"Menos de {WEAK_BITS} bits", "warning"),
            ("Antiguas", "clock", len(report.old),
             f"Más de {max(1, self._settings.old_password_days // 30)} meses", None),
            ("Sin 2FA", "shield", len(report.no_totp), "Logins sin código", None),
        )
        for title, icon_name, value, caption, tone in stats:
            row.addWidget(_StatCard(title, icon_name, value, caption, tone), 2)
        return row

    def _issues_card(self, report, issues) -> QFrame:
        card = QFrame()
        card.setObjectName("cardSunken")
        col = QVBoxLayout(card)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        head = QHBoxLayout()
        head.setContentsMargins(20, 18, 20, 14)
        head.addWidget(label("Por resolver · ordenado por impacto", "titleSm"))
        head.addStretch(1)
        head.addWidget(label(f"{len(issues)} en total", "tertiary"))
        col.addLayout(head)
        if not issues:
            empty = QVBoxLayout()
            empty.setContentsMargins(20, 30, 20, 30)
            empty.addWidget(icon_label("shield-check", P.SUCCESS, 28), 0, Qt.AlignHCenter)
            empty.addWidget(label("Todo en orden", "titleSm", align=Qt.AlignHCenter))
            empty.addWidget(label("Ninguna contraseña filtrada, repetida, débil ni antigua.", "secondary",
                                  align=Qt.AlignHCenter, wrap=True))
            col.addLayout(empty)
            return card
        shown = issues if self._expanded else issues[: self.VISIBLE]
        for issue in shown:
            gain = score_after(report, [issue]) - report.score
            col.addWidget(_IssueRow(issue, max(0, gain), self._on_fix))
        col.addStretch(1)
        rest = len(issues) - len(shown)
        if rest > 0 or self._expanded:
            foot = QFrame()
            foot.setObjectName("dialogFooter")
            fl = QHBoxLayout(foot)
            fl.setContentsMargins(20, 12, 20, 12)
            text = f"Ver {'el restante' if rest == 1 else f'los {rest} restantes'}" if rest else "Ver menos"
            fl.addWidget(Button(text, "link", on_click=self._toggle_expanded))
            fl.addStretch(1)
            col.addWidget(foot)
        return card

    def _toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        self.set_report(self._report)

    def _breach_card(self, report) -> Card:
        card = Card("Comprobación de filtraciones", name="cardSunken", margins=(20, 18, 20, 18), spacing=12)
        online = self._settings.breach_check_online
        line = QHBoxLayout()
        line.setSpacing(8)
        if online and self._checked_at:
            minutes = int((time.time() - self._checked_at) // 60)
            when = "hace un momento" if minutes < 1 else f"hace {minutes} min"
            line.addWidget(icon_label("check", P.SUCCESS, 14))
            line.addWidget(label(f"Última {when} · {plural(report.total, 'entrada', 'entradas')}", "body"))
        elif online:
            line.addWidget(icon_label("clock", P.TEXT_SECONDARY, 14))
            line.addWidget(label("Pendiente de la primera comprobación", "body"))
        else:
            line.addWidget(icon_label("wifi-off", P.TEXT_SECONDARY, 14))
            line.addWidget(label("Desactivada · nada sale de este equipo", "body"))
        line.addStretch(1)
        card.add(line)
        card.add(label("Se usa el rango k-anónimo de Have I Been Pwned: solo salen del equipo los 5 primeros "
                       "caracteres del hash SHA-1, nunca la contraseña.", "secondary", wrap=True))
        if online:
            card.add(_left(Button("Volver a comprobar", "secondary", "sync", on_click=self._on_recheck)))
        else:
            card.add(_left(Button("Activar en Ajustes", "secondary", "settings", on_click=self._on_policies)))
        return card

    def _policy_card(self) -> Card:
        s = self._settings
        card = Card("Política de rotación", name="cardSunken", margins=(20, 18, 20, 18), spacing=10)
        card.add(kv_row("Contraseñas antiguas", f"{max(1, s.old_password_days // 30)} meses"))
        card.add(kv_row("Rotación por defecto", f"{s.default_rotation_interval_days} días"))
        card.add(kv_row("Fuerza mínima", f"{WEAK_BITS} bits"))
        card.add(_left(Button("Editar políticas", "link", on_click=self._on_policies)))
        return card


def _left(widget: QWidget) -> QHBoxLayout:
    row = QHBoxLayout()
    row.addWidget(widget)
    row.addStretch(1)
    return row

