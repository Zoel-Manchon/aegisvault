"""Command palette (board 18): jump to an entry or run an action from one field.

Ctrl+K opens it. Typing filters entries and actions without caring about case
or accents; a leading ``>`` keeps only actions. Up/Down move, Enter runs, Esc
closes. Entries are listed by name and user, exactly like the list: the
palette never touches a secret.
"""
from __future__ import annotations

import unicodedata
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QLineEdit, QScrollArea, QSizePolicy,
    QVBoxLayout, QWidget,
)

from ..components.kit import IconTile, Kbd, Scrim, clear_layout, icon_label, label, letter_of, overline, set_prop
from ..design.tokens import ELEVATION_3
from ..theme import PALETTE as P

RECENT = 3          # entries shown before typing
FIRST_ACTIONS = 5   # actions shown before typing
MAX_ENTRIES = 8     # entries shown for a query
LIST_MAX_H = 440


@dataclass(frozen=True)
class Command:
    group: str            # "Recientes" | "Entradas" | "Acciones" | "Ir a"
    command_id: str
    label: str
    hint: str = ""
    icon: str = ""        # empty: a letter tile, as for entries
    key: str = ""
    danger: bool = False  # the action asks for confirmation itself
    payload: object = None
    haystack: str = ""


def norm(text: str) -> str:
    """Lower-case and strip accents: «auditoría» matches «auditoria»."""
    decomposed = unicodedata.normalize("NFD", str(text).lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _cmd(group: str, command_id: str, text: str, hint: str = "", icon_name: str = "", key: str = "",
         danger: bool = False, payload=None, extra: str = "") -> Command:
    return Command(group, command_id, text, hint, icon_name, key, danger, payload,
                   norm(" ".join(part for part in (text, hint, extra) if part)))


def actions(theme_mode: str = "dark") -> list[Command]:
    other = "claro" if theme_mode == "dark" else "oscuro"
    return [
        _cmd("Acciones", "new", "Nueva entrada", "", "plus", "Ctrl N"),
        _cmd("Acciones", "generate", "Generar contraseña", "y copiarla", "key", "Ctrl G"),
        _cmd("Acciones", "lock", "Bloquear ahora", "borra la clave de memoria", "lock", "Ctrl L"),
        _cmd("Acciones", "sync", "Sincronizar ahora", "carpeta de copia", "sync"),
        _cmd("Acciones", "verify", "Verificar la cadena de auditoría", "", "shield-check"),
        _cmd("Acciones", "siem", "Exportar a SIEM…", "JSON, CEF o syslog", "activity"),
        _cmd("Acciones", "share_entry", "Compartir entrada…", "clave X25519", "share"),
        _cmd("Acciones", "rotate", "Rotar contraseña maestra…", "", "key", danger=True),
        _cmd("Acciones", "shamir", "Crear fragmentos Shamir…", "K de N", "shamir"),
        _cmd("Acciones", "import", "Importar entradas…", "CSV de otro gestor", "download"),
        _cmd("Acciones", "policies", "Políticas Zero Trust…", "", "shield", extra="reglas"),
        _cmd("Acciones", "access", "Solicitudes de acceso…", "", "users", extra="aprobar"),
        _cmd("Acciones", "agent", "Agente local…", "uso desde la CLI", "terminal"),
        _cmd("Acciones", "passkey", "Desbloqueo con passkey…", "próximamente", "fingerprint"),
        _cmd("Acciones", "theme", f"Cambiar a modo {other}", "", "theme", extra="tema apariencia"),
        _cmd("Acciones", "settings", "Ajustes", "", "settings", "Ctrl ,", extra="preferencias"),
    ]


GO_TO = (
    _cmd("Ir a", "health", "Salud de la bóveda", "", "gauge"),
    _cmd("Ir a", "audit", "Auditoría", "", "shield"),
    _cmd("Ir a", "share", "Compartidos", "", "users"),
    _cmd("Ir a", "favorites", "Favoritos", "", "star"),
    _cmd("Ir a", "trash", "Papelera", "", "trash"),
)


def entry_commands(views: Iterable) -> list[Command]:
    """Live entries, most recently changed first."""
    live = [v for v in views if not getattr(v, "deleted", False)]
    live.sort(key=lambda v: (getattr(v, "updated_at", "") or getattr(v, "created_at", "") or ""), reverse=True)
    out = []
    for v in live:
        hint = v.username or v.category or ""
        extra = " ".join((v.url or "", v.category or "", " ".join(v.tags or ())))
        out.append(_cmd("Entradas", "entry", v.name, hint, "", payload=v.name, extra=extra))
    return out


def search(entries: list[Command], acts: list[Command], query: str) -> list[Command]:
    """What the palette lists for ``query`` (the logic of the board's prototype)."""
    q = query.strip()
    only_actions = q.startswith(">")
    if only_actions:
        q = q[1:].strip()
    if not q and not only_actions:
        recent = [replace(c, group="Recientes") for c in entries[:RECENT]]
        return recent + acts[:FIRST_ACTIONS]
    nq = norm(q)
    if only_actions:
        return [c for c in acts if nq in c.haystack]
    # Names that start with the query first, then the rest in recency order.
    found = [c for c in entries if nq in c.haystack]
    found.sort(key=lambda c: 0 if norm(c.label).startswith(nq) else 1)
    picked = found[:MAX_ENTRIES]
    picked += [c for c in acts if nq in c.haystack]
    picked += [c for c in GO_TO if nq in c.haystack]
    return picked


class _Row(QFrame):
    def __init__(self, command: Command, on_hover: Callable[[], None], on_click: Callable[[], None]):
        super().__init__()
        self.setObjectName("paletteRow")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(44)
        self.setMouseTracking(True)
        self._hover = on_hover
        self._click = on_click
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 0, 10, 0)
        row.setSpacing(12)
        if command.icon:
            tile = IconTile(command.icon, size=28, icon_size=15)
        else:
            tile = QLabel(letter_of(command.label))
            tile.setObjectName("avatar")
            tile.setProperty("size", "sm")
            tile.setFixedSize(28, 28)
            tile.setAlignment(Qt.AlignCenter)
        row.addWidget(tile)
        title = label(command.label, "bodyStrong")
        row.addWidget(title)
        if command.hint:
            hint = label(command.hint, "secondary")
            hint.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
            hint.setMinimumWidth(0)
            row.addWidget(hint, 1)
        else:
            row.addStretch(1)
        if command.danger:
            row.addWidget(label("pide confirmación", "dangerNote"))
        if command.key:
            row.addWidget(Kbd(command.key))
        self.setAccessibleName(f"{command.label} {command.hint}".strip())

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt API
        # Hover follows real mouse movement only, so scrolling with the keyboard
        # under a resting pointer does not steal the selection.
        self._hover()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt API
        if event.button() == Qt.LeftButton and self.rect().contains(event.position().toPoint()):
            self._click()
            return
        super().mouseReleaseEvent(event)


class CommandPalette(QDialog):
    """Modal palette; ``execute(command_id, payload)`` runs after it closes."""

    WIDTH = 640
    TOP = 112

    def __init__(self, parent: QWidget, views: Iterable, execute: Callable[[str, object], None]):
        super().__init__(parent)
        self.setObjectName("avDialog")
        self.setWindowTitle("Paleta de comandos")
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setModal(True)
        self._execute = execute
        self._entries = entry_commands(views)
        self._actions = actions(P.MODE)
        self._results: list[Command] = []
        self._rows: list[_Row] = []
        self._active = 0
        self._chosen: Command | None = None
        self._scrim: Scrim | None = None

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 28)
        frame = QFrame()
        frame.setObjectName("paletteFrame")
        self._frame = frame
        frame.setFixedWidth(self.WIDTH)
        shadow = QGraphicsDropShadowEffect(frame)
        shadow.setBlurRadius(ELEVATION_3.blur * 2)
        shadow.setOffset(0, ELEVATION_3.y)
        shadow.setColor(QColor(ELEVATION_3.color(P)))
        frame.setGraphicsEffect(shadow)
        outer.addWidget(frame)
        col = QVBoxLayout(frame)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)

        head = QFrame()
        head.setObjectName("paletteHead")
        hr = QHBoxLayout(head)
        hr.setContentsMargins(18, 12, 14, 12)
        hr.setSpacing(12)
        hr.addWidget(icon_label("search", P.TEXT_SECONDARY, 18))
        self.search = QLineEdit()
        self.search.setObjectName("paletteSearch")
        self.search.setPlaceholderText("Busca una entrada o escribe una acción…")
        self.search.setAccessibleName("Buscar entradas o acciones")
        hr.addWidget(self.search, 1)
        hr.addWidget(Kbd("Esc"))
        col.addWidget(head)

        self._area = QScrollArea()
        self._area.setObjectName("plain")
        self._area.setWidgetResizable(True)
        self._area.setFrameShape(QFrame.NoFrame)
        self._area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._list = QWidget()
        self._list.setObjectName("transparent")
        self._list.setAccessibleName("Resultados")
        self._box = QVBoxLayout(self._list)
        self._box.setContentsMargins(8, 6, 8, 8)
        self._box.setSpacing(2)
        self._area.setWidget(self._list)
        col.addWidget(self._area)

        foot = QFrame()
        foot.setObjectName("paletteFoot")
        fr = QHBoxLayout(foot)
        fr.setContentsMargins(16, 10, 16, 10)
        fr.setSpacing(6)
        for keys, text in (("↑ ↓", "moverse"), ("Enter", "ejecutar"), (">", "solo acciones")):
            fr.addWidget(Kbd(keys))
            fr.addWidget(label(text, "tertiary"))
            fr.addSpacing(10)
        fr.addStretch(1)
        self._count = label("", "tertiary")
        fr.addWidget(self._count)
        col.addWidget(foot)

        self.search.textChanged.connect(self._refresh)
        self.search.installEventFilter(self)
        self._refresh()
        QTimer.singleShot(0, self.search.setFocus)

    # ---- results ------------------------------------------------------------------
    def results(self) -> list[Command]:
        return list(self._results)

    def _refresh(self, *_):
        self._results = search(self._entries, self._actions, self.search.text())
        self._active = 0
        clear_layout(self._box)
        self._rows = []
        if not self._results:
            empty = QVBoxLayout()
            empty.setContentsMargins(12, 22, 12, 22)
            empty.setSpacing(6)
            query = self.search.text().strip().lstrip(">").strip()
            empty.addWidget(label(f"Nada coincide con «{query}»", "bodyStrong", align=Qt.AlignHCenter, wrap=True))
            empty.addWidget(label("Prueba con el nombre del sitio o con una acción como «bloquear».", "secondary",
                                  align=Qt.AlignHCenter, wrap=True))
            self._box.addLayout(empty)
        group = None
        for index, command in enumerate(self._results):
            if command.group != group:
                group = command.group
                head = overline(group)
                head.setContentsMargins(10, 10 if index else 4, 10, 4)
                self._box.addWidget(head)
            row = _Row(command, lambda i=index: self._set_active(i), lambda i=index: self._run(i))
            self._rows.append(row)
            self._box.addWidget(row)
        self._box.addStretch(1)
        n = len(self._results)
        self._count.setText("1 resultado" if n == 1 else f"{n} resultados")
        self._set_active(0)
        self._fit_height()

    def _fit_height(self) -> None:
        # Widgets added to a visible layout are shown on the next event-loop turn;
        # until then the layout skips them, so show them now to measure them.
        for child in self._list.findChildren(QWidget):
            if child.parentWidget() is self._list and not child.testAttribute(Qt.WA_WState_ExplicitShowHide):
                child.show()
        self._box.invalidate()
        wanted = self._box.sizeHint().height()
        self._area.setFixedHeight(max(96, min(wanted, LIST_MAX_H)))
        # The outer layout caches the frame's size until the frame says it changed.
        self._frame.updateGeometry()
        self.layout().invalidate()
        self.adjustSize()
        self._place()

    def _set_active(self, index: int) -> None:
        if not self._rows:
            return
        index = max(0, min(index, len(self._rows) - 1))
        for i, row in enumerate(self._rows):
            set_prop(row, "active", i == index)
        self._active = index
        self._area.ensureWidgetVisible(self._rows[index], 0, 8)

    def _run(self, index: int) -> None:
        if 0 <= index < len(self._results):
            self._chosen = self._results[index]
            self.accept()

    # ---- keyboard ------------------------------------------------------------------
    def eventFilter(self, obj, event):  # noqa: N802 - Qt API
        if obj is self.search and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Down, Qt.Key_Tab):
                self._set_active(self._active + 1)
                return True
            if key in (Qt.Key_Up, Qt.Key_Backtab):
                self._set_active(self._active - 1)
                return True
            if key == Qt.Key_PageDown:
                self._set_active(self._active + 5)
                return True
            if key == Qt.Key_PageUp:
                self._set_active(self._active - 5)
                return True
            if key in (Qt.Key_Return, Qt.Key_Enter):
                self._run(self._active)
                return True
            if key == Qt.Key_Escape:
                self.reject()
                return True
        return super().eventFilter(obj, event)

    # ---- placement, scrim and execution ------------------------------------------------
    def _place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        top = parent.window()
        geo = top.frameGeometry() if top.isVisible() else top.geometry()
        x = geo.center().x() - self.width() // 2
        y = geo.top() + self.TOP - 28
        self.move(QPoint(x, y))

    def showEvent(self, event):  # noqa: N802 - Qt API
        parent = self.parentWidget()
        if parent is not None and self._scrim is None and parent.window().isVisible():
            self._scrim = Scrim(parent.window())
            self._scrim.show()
            self._scrim.raise_()
        self._place()
        super().showEvent(event)

    def done(self, result):  # noqa: D401 - Qt API
        if self._scrim is not None:
            self._scrim.hide()
            self._scrim.deleteLater()
            self._scrim = None
        super().done(result)

    def exec(self) -> int:  # noqa: A003 - Qt API
        result = super().exec()
        chosen, self._chosen = self._chosen, None
        if result == QDialog.Accepted and chosen is not None:
            # Run after the palette is gone so the next dialog gets its own scrim.
            self._execute(chosen.command_id, chosen.payload)
        return result
