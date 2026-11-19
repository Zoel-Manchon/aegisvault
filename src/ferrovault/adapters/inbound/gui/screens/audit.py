"""Audit chain (board 14): the hash-chained history, where it breaks and what to do.

Blocks are verified in order: everything before the first failure is
"Verificado", the failing block is "Alterado" and everything after it is
"Sin garantía" (it may be fine, but the chain can no longer prove it).
"""
from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPen
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from ..components.kit import (
    Badge, Banner, Button, SearchField, clear_layout, icon_label, label, mono_font, set_prop, tone_color,
)
from ..fmt import fmt_date, fmt_datetime, parse_iso, plural, thousands
from ..icons import pixmap
from ..theme import PALETTE as P
from .common import Page

PAGE = 200

ACTIONS = {
    "init": "Bóveda creada", "add": "Entrada creada", "edit": "Entrada editada", "trash": "Movida a la papelera",
    "remove": "Entrada borrada", "restore": "Restaurada de la papelera", "purge": "Borrada para siempre",
    "favorite": "Marcada como favorita", "unfavorite": "Quitada de favoritos", "share": "Compartida",
    "unshare": "Dejó de compartirse", "revoke-share": "Acceso revocado", "rotate-secret": "Marcada como rotada",
    "enterprise-meta": "Política de la entrada cambiada", "recovery-enroll": "Fragmentos de recuperación creados",
    "recover": "Recuperada con fragmentos Shamir", "rotate": "Contraseña maestra cambiada",
    "kdf-upgrade": "Derivación de clave reforzada", "import": "Importación", "copy": "Contraseña copiada",
    "copy-user": "Usuario copiado", "copy-totp": "Código 2FA copiado", "reveal": "Contraseña revelada",
    "unlock": "Bóveda desbloqueada", "access-approve": "Acceso aprobado", "access-deny": "Acceso denegado",
    "pre-import": "Copia previa a importar",
}
FIELDS = {"nombre": "nombre", "secreto": "contraseña", "username": "usuario", "url": "URL", "notes": "notas",
          "category": "categoría", "team_vault": "equipo", "sensitivity": "sensibilidad", "2FA": "2FA"}
STATUS = {"ok": ("Verificado", "success", "check"), "unverified": ("Sin garantía", "warning", "warning"),
          "broken": ("Alterado", "danger", "alert")}


def describe(block) -> tuple[str, str]:
    """(title, extra) in Spanish for a ledger block. Details hold names only, never secrets."""
    action, detail = block.action, block.detail or ""
    title = ACTIONS.get(action, action)
    extra = ""
    if action == "edit" and detail.endswith(")") and " (" in detail:
        name, changes = detail[:-1].split(" (", 1)
        fields = [FIELDS.get(c.strip(), c.strip()) for c in changes.split(",")]
        return f"{title} · {name}", "cambió: " + ", ".join(fields)
    if action in ("share", "revoke-share") and " -> " in detail:
        name, rest = detail.split(" -> ", 1)
        who = rest.split(" (", 1)[0]
        return f"{title} · {name} → {who}", ""
    if action == "recovery-enroll" and "-of-" in detail:
        k, n = detail.split("-of-", 1)
        return f"{title} · {k} de {n}", ""
    if action == "import":
        return f"{title} · {detail.replace('entries', 'entradas')}", ""
    if action == "kdf-upgrade":
        return title, detail
    if action in ("init", "rotate", "recover", "unlock"):
        return title, ""
    if action == "purge" and " (papelera" in detail:
        name = detail.split(" (papelera", 1)[0]
        return f"{title} · {name}", "plazo de la papelera cumplido"
    return (f"{title} · {detail}" if detail else title), extra


def statuses(blocks, verification) -> list[str]:
    if verification.ok:
        return ["ok"] * len(blocks)
    b = verification.broken_index if verification.broken_index is not None else 0
    return ["ok" if i < b else "broken" if i == b else "unverified" for i in range(len(blocks))]


def short(h: str) -> str:
    return f"{h[:4]}…{h[-4:]}" if len(h) > 10 else h


def grouped(h: str, size: int = 8) -> list[str]:
    return [h[i:i + size] for i in range(0, len(h), size)]


class _Gutter(QWidget):
    """Timeline dot and line on the left of each block."""

    def __init__(self, state: str, first: bool, last: bool):
        super().__init__()
        self.setFixedWidth(28)
        self._state, self._first, self._last = state, first, last

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        cx, cy = self.width() / 2, self.height() / 2
        line = QColor(tone_color(STATUS[self._state][1]))
        line.setAlphaF(0.55)
        pen = QPen(line, 1.5)
        if self._state == "unverified":
            pen.setStyle(Qt.DashLine)
        p.setPen(pen)
        p.drawLine(int(cx), 0 if not self._first else int(cy), int(cx), self.height() if not self._last else int(cy))
        r = 10
        color = QColor(tone_color(STATUS[self._state][1]))
        bg = QColor(P.BG_BASE)
        p.setBrush(bg)
        p.setPen(QPen(color, 1.5))
        p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
        name = {"ok": "check", "unverified": "info", "broken": "close"}[self._state]
        p.drawPixmap(int(cx - 6), int(cy - 6), pixmap(name, color.name(), 12, 2.2))
        p.end()


class _BlockRow(QFrame):
    clicked = Signal(int)

    def __init__(self, block, state: str, first: bool, last: bool):
        super().__init__()
        self._index = block.index
        outer = QHBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)
        outer.addWidget(_Gutter(state, first, last))
        self.card = QFrame()
        self.card.setObjectName("blockRow")
        if state == "broken":
            self.card.setProperty("state", "broken")
        self.card.setCursor(Qt.PointingHandCursor)
        row = QHBoxLayout(self.card)
        row.setContentsMargins(16, 10, 16, 10)
        row.setSpacing(16)
        num = label(f"#{thousands(block.index + 1)}", "monoBody")
        num.setFixedWidth(72)
        row.addWidget(num)
        title, extra = describe(block)
        text = QVBoxLayout()
        text.setSpacing(1)
        text.addWidget(label(title, "body"))
        sub = fmt_datetime(block.timestamp) + (f" · {extra}" if extra else "")
        text.addWidget(label(sub, "secondary"))
        row.addLayout(text, 1)
        row.addWidget(label(short(block.hash), "monoSm"))
        st_text, tone, icon_name = STATUS[state]
        st = QHBoxLayout()
        st.setSpacing(4)
        st.addWidget(icon_label(icon_name, tone_color(tone), 13))
        st_lbl = label(st_text, "toneText")
        st_lbl.setProperty("tone", tone)
        st.addWidget(st_lbl)
        st_box = QWidget()
        st_box.setObjectName("transparent")
        st_box.setLayout(st)
        st_box.setFixedWidth(116)
        row.addWidget(st_box)
        outer.addWidget(self.card, 1)

    def set_selected(self, on: bool) -> None:
        set_prop(self.card, "selected", on)

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self._index)
        super().mouseReleaseEvent(event)


class AuditPage(Page):
    def __init__(self, session, callbacks: dict, *, filter_text: str = "", on_export: Callable,
                 on_rotate: Callable, on_restore: Callable):
        super().__init__("Auditoría", callbacks, scroll=False, margins=(40, 24, 40, 24), spacing=18)
        self._session = session
        self._on_export, self._on_rotate, self._on_restore = on_export, on_rotate, on_restore
        self._limit = PAGE
        self._selected: int | None = None
        self._rows: dict[int, _BlockRow] = {}
        self._verified_at = time.time()

        self._banner_box = QVBoxLayout()
        self._banner_box.setSpacing(0)
        self.content.addLayout(self._banner_box)

        head = QHBoxLayout()
        head.setSpacing(12)
        head.addWidget(label("Historial encadenado", "titleLg"))
        self.meta = label("", "secondary")
        head.addWidget(self.meta, 0, Qt.AlignVCenter)
        head.addStretch(1)
        self.filter = SearchField("Filtrar eventos")
        self.filter.setFixedWidth(260)
        self.filter.setText(filter_text)
        self.filter.textChanged.connect(lambda _t: self._render_list())
        head.addWidget(self.filter)
        head.addWidget(Button("Verificar de nuevo", "secondary", "shield-check",
                              on_click=lambda: self.verify(announce=True)))
        self.content.addLayout(head)

        body = QHBoxLayout()
        body.setSpacing(24)
        area = QScrollArea()
        area.setObjectName("plain")
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        holder.setObjectName("page")
        self._list = QVBoxLayout(holder)
        self._list.setContentsMargins(0, 0, 8, 0)
        self._list.setSpacing(8)
        area.setWidget(holder)
        body.addWidget(area, 1)
        self.detail = QFrame()
        self.detail.setObjectName("cardSunken")
        self.detail.setFixedWidth(460)
        self._detail = QVBoxLayout(self.detail)
        self._detail.setContentsMargins(20, 18, 20, 18)
        self._detail.setSpacing(12)
        body.addWidget(self.detail, 0, Qt.AlignTop)
        self.content.addLayout(body, 1)
        self.verify(announce=False)

    # ---- data ---------------------------------------------------------------------
    def verify(self, announce: bool = False) -> None:
        self._blocks = self._session.audit_log()
        self._verification, self._fingerprint, self._head = self._session.verify_integrity()
        self._states = statuses(self._blocks, self._verification)
        self._verified_at = time.time()
        if not self._verification.ok and self._selected is None:
            self._selected = self._verification.broken_index
        elif self._selected is None and self._blocks:
            self._selected = self._blocks[-1].index
        self._render_banner(announce)
        self._render_list()
        self._render_detail()

    def _render_banner(self, announce: bool) -> None:
        clear_layout(self._banner_box)
        n = len(self._blocks)
        self.meta.setText(f"{thousands(n)} {'bloque' if n == 1 else 'bloques'} · SHA-256 · verificado "
                          "hace un momento")
        if not self._verification.ok:
            b = self._verification.broken_index or 0
            good = b
            backup = self._best_backup()
            actions = [Button("Exportar informe", "banner", on_click=self._on_export)]
            if backup is not None:
                actions.append(Button(f"Restaurar la copia del {fmt_date(backup['modified'])}", "primary",
                                      on_click=self._on_restore))
            else:
                actions.append(Button("Ver copias de seguridad", "primary", on_click=self._on_restore))
            text = (f"{'El bloque anterior está íntegro' if good == 1 else f'Los {thousands(good)} bloques anteriores están íntegros'}. "
                    "Los registros a partir de ahí no se pueden garantizar. Tus contraseñas no se han tocado: "
                    "esto afecta solo al historial.") if good else (
                    "Ni el primer bloque coincide con su hash. Tus contraseñas no se han tocado: esto afecta solo "
                    "al historial.")
            self._banner_box.addWidget(Banner("danger", f"La cadena se rompe en el bloque #{thousands(b + 1)}",
                                              text, actions, icon_name="link-broken"))
            self._banner_box.addSpacing(4)
        elif announce:
            genesis = fmt_date(self._blocks[0].timestamp) if self._blocks else ""
            self._banner_box.addWidget(Banner(
                "success", "Cadena íntegra",
                f"{plural(n, 'bloque verificado', 'bloques verificados')} hasta el génesis del {genesis}. "
                f"Huella de la bóveda: {self._fingerprint[:16]}…", icon_name="shield-check", compact=True))
            self._banner_box.addSpacing(4)

    def _best_backup(self):
        try:
            backups = self._session.backups()
        except Exception:
            return None
        return next((b for b in backups if b.get("chain_ok")), None)

    def _render_list(self) -> None:
        clear_layout(self._list)
        self._rows = {}
        query = self.filter.text().strip().lower()
        blocks = list(reversed(self._blocks))
        if query:
            blocks = [b for b in blocks if query in (" ".join(describe(b)) + " " + b.action + " " + (b.detail or "")).lower()]
        shown = blocks[: self._limit]
        broken = None if self._verification.ok else self._verification.broken_index
        for i, block in enumerate(shown):
            state = self._states[block.index]
            if broken is not None and block.index == broken and not query:
                reason = self._verification.reason or ""
                if "link" in reason and block.index > 0:
                    msg = (f"Enlace roto: el «prev» de #{thousands(block.index + 1)} no coincide con el hash de "
                           f"#{thousands(block.index)}")
                else:
                    msg = f"El contenido de #{thousands(block.index + 1)} no coincide con su hash"
                warn = QHBoxLayout()
                warn.setContentsMargins(0, 0, 0, 0)
                warn.setSpacing(10)
                warn.addWidget(icon_label("close", P.DANGER, 16))
                w = label(msg, "toneText")
                w.setProperty("tone", "danger")
                warn.addWidget(w, 1)
                self._list.addLayout(warn)
            row = _BlockRow(block, state, i == 0, i == len(shown) - 1)
            row.clicked.connect(self._select)
            row.set_selected(block.index == self._selected)
            self._rows[block.index] = row
            self._list.addWidget(row)
        if not shown:
            self._list.addWidget(label("Ningún evento coincide con el filtro.", "secondary"))
        rest = len(blocks) - len(shown)
        foot = QHBoxLayout()
        foot.setSpacing(6)
        if self._blocks:
            older_ok = sum(1 for b in blocks[len(shown):] if self._states[b.index] == "ok")
            if rest and older_ok:
                foot.addWidget(icon_label("check", P.SUCCESS, 13))
                foot.addWidget(label(f"{thousands(older_ok)} bloques anteriores verificados, hasta el bloque génesis "
                                     f"del {fmt_date(self._blocks[0].timestamp)} ·", "secondary"))
            elif not rest:
                foot.addWidget(icon_label("check", P.SUCCESS, 13))
                foot.addWidget(label(f"Bloque génesis del {fmt_date(self._blocks[0].timestamp)}", "secondary"))
        if rest:
            foot.addWidget(Button("Cargar más", "link", on_click=self._more))
        foot.addStretch(1)
        self._list.addLayout(foot)
        self._list.addStretch(1)

    def _more(self) -> None:
        self._limit += PAGE
        self._render_list()

    def _select(self, index: int) -> None:
        self._selected = index
        for i, row in self._rows.items():
            row.set_selected(i == index)
        self._render_detail()

    # ---- detail -------------------------------------------------------------------
    def _render_detail(self) -> None:
        clear_layout(self._detail)
        if self._selected is None or self._selected >= len(self._blocks):
            self._detail.addWidget(label("La bóveda no tiene eventos todavía.", "secondary", wrap=True))
            return
        block = self._blocks[self._selected]
        state = self._states[block.index]
        nxt = self._blocks[block.index + 1] if block.index + 1 < len(self._blocks) else None
        prev = self._blocks[block.index - 1] if block.index > 0 else None

        head = QHBoxLayout()
        head.addWidget(label(f"Bloque #{thousands(block.index + 1)}", "titleSm"))
        head.addStretch(1)
        st_text, tone, icon_name = STATUS[state]
        head.addWidget(Badge(st_text, tone, icon_name))
        self._detail.addLayout(head)

        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        title, extra = describe(block)
        dt = parse_iso(block.timestamp)
        when = dt.astimezone().strftime("%Y-%m-%d %H:%M:%S") if dt else block.timestamp
        prev_ok = (prev.hash if prev else "0" * 64) == block.prev_hash
        rows = [("Evento", label(title + (f" · {extra}" if extra else ""), "body", wrap=True)),
                ("Fecha", label(when, "monoBody"))]
        prev_row = QHBoxLayout()
        prev_row.setSpacing(8)
        prev_row.addWidget(label(short(block.prev_hash), "monoBody"))
        mark = label("✓ coincide" if prev_ok else "✗ no coincide", "monoSm")
        mark.setStyleSheet(f"color: {P.SUCCESS if prev_ok else P.DANGER};")
        prev_row.addWidget(mark)
        prev_row.addStretch(1)
        for r, (k, w) in enumerate(rows):
            grid.addWidget(label(k, "secondary"), r, 0, Qt.AlignTop)
            grid.addWidget(w, r, 1)
        grid.addWidget(label("Prev", "secondary"), len(rows), 0)
        grid.addLayout(prev_row, len(rows), 1)
        grid.setColumnStretch(1, 1)
        self._detail.addLayout(grid)

        expected = nxt.prev_hash if nxt is not None else block.hash
        expected_caption = (f"Hash que #{thousands(block.index + 2)} espera (su «prev»)" if nxt is not None
                            else "Hash guardado en el bloque")
        actual = block.recompute()
        box = QFrame()
        box.setObjectName("cardSunken")
        bx = QVBoxLayout(box)
        bx.setContentsMargins(14, 12, 14, 12)
        bx.setSpacing(8)
        bx.addWidget(label(expected_caption, "secondary"))
        bx.addWidget(self._hash_label(expected, None))
        bx.addWidget(_hairline())
        bx.addWidget(label("Hash recalculado del contenido actual", "secondary"))
        bx.addWidget(self._hash_label(actual, expected))
        match = expected == actual
        verdict = QHBoxLayout()
        verdict.setSpacing(6)
        verdict.addWidget(icon_label("check" if match else "close", P.SUCCESS if match else P.DANGER, 13))
        v = label("Coinciden" if match else "No coinciden (subrayado: lo que difiere)", "toneText")
        v.setProperty("tone", "success" if match else "danger")
        verdict.addWidget(v, 1)
        bx.addLayout(verdict)
        self._detail.addWidget(box)

        if state == "ok":
            self._detail.addWidget(label("Qué significa", "bodyStrong"))
            self._detail.addWidget(label("El contenido de este bloque coincide con su hash y enlaza con el anterior: "
                                         "no ha cambiado desde que se escribió.", "secondary", wrap=True))
        else:
            self._detail.addWidget(label("Qué significa", "bodyStrong"))
            meaning = ("El contenido de este bloque cambió después de escribirse. Suele deberse a una edición del "
                       "archivo fuera de AegisVault o a un fallo del disco." if state == "broken" else
                       "Este bloque viene después de la rotura: puede estar bien, pero la cadena ya no lo puede "
                       "demostrar.")
            self._detail.addWidget(label(meaning, "secondary", wrap=True))
            self._detail.addWidget(label("Qué puedes hacer", "bodyStrong"))
            steps = ["Exporta el informe para conservar la evidencia.",
                     "Restaura la última copia con la cadena íntegra.",
                     "Si no reconoces el cambio, rota la contraseña maestra."]
            for i, step in enumerate(steps, 1):
                self._detail.addWidget(label(f"{i}. {step}", "secondary", wrap=True))
        self._detail.addSpacing(6)
        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        if state != "ok":
            buttons.addWidget(Button("Rotar contraseña maestra", "secondary", on_click=self._on_rotate), 1)
        buttons.addWidget(Button("Copiar hashes", "ghost", "copy", on_click=lambda: self._copy_hashes(block, expected, actual)))
        if state == "ok":
            buttons.addStretch(1)
        self._detail.addLayout(buttons)

    def _hash_label(self, value: str, compare: str | None) -> QLabel:
        parts = []
        for i, chunk in enumerate(grouped(value)):
            other = grouped(compare)[i] if compare and i < len(grouped(compare)) else chunk
            if compare is not None and chunk != other:
                parts.append(f"<span style='color:{P.DANGER}; text-decoration: underline'>{chunk}</span>")
            else:
                parts.append(chunk)
        lbl = QLabel(" ".join(parts))
        lbl.setTextFormat(Qt.RichText)
        lbl.setWordWrap(True)
        lbl.setFont(mono_font(13))
        lbl.setTextInteractionFlags(Qt.TextSelectableByMouse)
        return lbl

    def _copy_hashes(self, block, expected: str, actual: str) -> None:
        text = (f"AegisVault · bloque #{block.index + 1} ({block.action}, {block.timestamp})\n"
                f"esperado:    {expected}\nrecalculado: {actual}\nprev:        {block.prev_hash}\n"
                f"huella de la bóveda: {self._fingerprint}\n")
        QGuiApplication.clipboard().setText(text)


def _hairline() -> QFrame:
    line = QFrame()
    line.setObjectName("hairline")
    line.setFixedHeight(1)
    return line
