"""Shamir recovery (board 15): create K-of-N shares, and restore with them.

Creating: choose the split, then each share is shown on its own (and can be
printed alone), then one share is typed back to prove it was copied right.
Every share carries its number and a checksum, so a copying mistake is
caught when typing it, not after a failed reconstruction.

Restoring (from the unlock screen, before any password): shares go in one at
a time and in any order; with K valid ones the key is rebuilt and a new
master password is chosen. The reconstruction runs on a worker thread.
"""
from __future__ import annotations

import secrets
from datetime import datetime
from html import escape

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit, QSpinBox, QVBoxLayout, QWidget

from .....application.errors import AuthenticationError
from .....domain.services.shamir import parse_share, share_groups
from ..background import run_task
from ..components.kit import (
    AvDialog, Banner, Button, Card, StepList, busy_bar, clear_layout, confirm, icon_label, info_line, label,
    mono_font, set_prop,
)
from ..fmt import fmt_date
from ..theme import PALETTE as P
from .master import NewPasswordFields

WORDS = {2: "dos", 3: "tres", 4: "cuatro", 5: "cinco", 6: "seis", 7: "siete", 8: "ocho", 9: "nueve", 10: "diez"}
ORDINALS = ("Primer", "Segundo", "Tercer", "Cuarto", "Quinto", "Sexto", "Séptimo", "Octavo", "Noveno", "Décimo")
MAX_SHARES = 10


def split_text(k: int, n: int) -> str:
    words = WORDS.get(k, str(k))
    less = WORDS.get(k - 1, str(k - 1))
    return (f"{words.capitalize()} fragmentos cualesquiera abren la bóveda. Con {less} o menos no se obtiene nada."
            if k > 1 else "")


def share_problem(text: str, expected_index: int | None = None, taken: set[int] | None = None,
                  total: int | None = None) -> tuple[int | None, str]:
    """(index, problem) for a typed share; problem is "" when it is usable."""
    clean = "".join(text.split())
    if not clean:
        return None, ""
    try:
        index, _data = parse_share(clean)
    except ValueError as exc:
        msg = str(exc)
        if "typo" in msg:
            return None, "Hay un error de copia: la suma de control no cuadra. Revisa los grupos."
        if "short" in msg:
            return None, "Falta algún grupo: el fragmento está incompleto."
        if "hexadecimal" in msg or "hex" in msg:
            return None, "Solo lleva números del 0 al 9 y letras de la A a la F."
        return None, "No parece un fragmento de AegisVault."
    if total and index > total:
        return index, f"Este es el fragmento {index}, pero esta bóveda se repartió en {total}."
    if expected_index is not None and index != expected_index:
        return index, f"Ese es el fragmento {index}; aquí va el {expected_index}."
    if taken and index in taken:
        missing = [str(i) for i in range(1, (total or max(taken) + 1) + 1) if i not in taken]
        options = ", ".join(missing[:-1]) + (f" o {missing[-1]}" if len(missing) > 1 else (missing[0] if missing
                                                                                             else ""))
        return index, f"Este es otra vez el fragmento {index}. Necesitas uno distinto: {options}."
    return index, ""


def _split_card(k: int, n: int) -> Card:
    card = Card(name="cardSunken", margins=(18, 14, 18, 14), spacing=6)
    row = QHBoxLayout()
    row.setSpacing(18)
    big = QLabel(f"{k} de {n}")
    big.setFont(mono_font(26, 600))
    big.setStyleSheet(f"color: {P.TEXT_PRIMARY}; background: transparent;")
    row.addWidget(big)
    row.addWidget(label(split_text(k, n), "secondary", wrap=True), 1)
    card.add(row)
    return card


class _Stepper(QWidget):
    def __init__(self, steps):
        super().__init__()
        self.setObjectName("transparent")
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 4)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)
        self._bars, self._labels = [], []
        for i, text in enumerate(steps):
            bar = QFrame()
            bar.setFixedHeight(3)
            lbl = label(f"{i + 1} · {text}", "tertiary")
            grid.addWidget(bar, 0, i)
            grid.addWidget(lbl, 1, i)
            self._bars.append(bar)
            self._labels.append(lbl)

    def set_step(self, index: int) -> None:
        for i, (bar, lbl) in enumerate(zip(self._bars, self._labels)):
            bar.setStyleSheet(f"background: {P.ACCENT if i <= index else P.SURFACE_3}; border-radius: 1px;")
            lbl.setObjectName("bodyStrong" if i == index else ("secondary" if i < index else "tertiary"))
            lbl.style().unpolish(lbl)
            lbl.style().polish(lbl)


def _share_grid(share: str) -> QWidget:
    w = QWidget()
    w.setObjectName("transparent")
    grid = QGridLayout(w)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(18)
    grid.setVerticalSpacing(8)
    for i, group in enumerate(share_groups(share)):
        cell = QHBoxLayout()
        cell.setSpacing(8)
        num = QLabel(f"{i + 1:02d}")
        num.setFont(mono_font(11))
        num.setStyleSheet(f"color: {P.TEXT_TERTIARY}; background: transparent;")
        text = QLabel(group)
        text.setFont(mono_font(16, 500))
        text.setStyleSheet(f"color: {P.TEXT_PRIMARY}; background: transparent;")
        text.setTextInteractionFlags(Qt.TextSelectableByMouse)
        cell.addWidget(num)
        cell.addWidget(text)
        cell.addStretch(1)
        grid.addLayout(cell, i // 4, i % 4)
    return w


# ---- create shares --------------------------------------------------------------------
class EnrollShamirDialog(AvDialog):
    def __init__(self, session, vault_label: str = "", parent=None):
        super().__init__(parent, "Crear fragmentos de recuperación", "", icon_name="shamir", width=640)
        self._session = session
        self._vault_label = vault_label or "bóveda"
        self._shares: list[str] = []
        self._current = 0
        self._saved: set[int] = set()
        self._check_index = 0
        self.enrolled = False
        self._stepper = _Stepper(("Reparto", "Guardar fragmentos", "Comprobar"))
        self.add_status(self._stepper)
        self._left_action = None
        self._left = Button("", "secondary", on_click=lambda: self._left_action and self._left_action())
        self.footer.layout().insertWidget(0, self._left)
        self._left.hide()
        self._step_split()

    def _reset_footer(self) -> None:
        while self.footer_buttons.count():
            item = self.footer_buttons.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._left_action = None
        self._left.hide()
        self.set_note("")

    # step 1
    def _step_split(self) -> None:
        self._stepper.set_step(0)
        clear_layout(self.body)
        self._reset_footer()
        policy = self._session.recovery_policy
        if policy:
            k, n = policy
            self.add(Banner("warning", f"Ya tienes un juego de {k} de {n}.",
                            "Crear uno nuevo invalida el anterior: los fragmentos repartidos dejarán de valer.",
                            compact=True))
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.addWidget(label("Fragmentos en total", "label"), 0, 0)
        grid.addWidget(label("Necesarios para abrir", "label"), 0, 1)
        self._n = QSpinBox()
        self._n.setRange(2, MAX_SHARES)
        self._n.setValue(5)
        self._n.setAccessibleName("Fragmentos en total")
        self._k = QSpinBox()
        self._k.setRange(2, 5)
        self._k.setValue(3)
        self._k.setAccessibleName("Necesarios para abrir")
        grid.addWidget(self._n, 1, 0)
        grid.addWidget(self._k, 1, 1)
        self.add(grid)
        self._summary = QVBoxLayout()
        self.add(self._summary)
        self.add(info_line("Reparte de forma que ninguna persona ni ningún sitio guarde por sí solo los "
                           "necesarios para abrir.", "info", "info"))
        self._n.valueChanged.connect(self._split_changed)
        self._k.valueChanged.connect(self._split_changed)
        self._split_changed()
        self.add_button(Button("Cancelar", "secondary", on_click=self.reject))
        go = self.add_button(Button("Crear fragmentos", "primary", on_click=self._create))
        go.setDefault(True)

    def _split_changed(self, *_):
        self._k.setMaximum(self._n.value())
        clear_layout(self._summary)
        self._summary.addWidget(_split_card(self._k.value(), self._n.value()))

    def _create(self) -> None:
        n, k = self._n.value(), self._k.value()
        if self._session.recovery_policy and not confirm(
                self, "¿Sustituir el juego actual?", "Los fragmentos repartidos hasta hoy dejarán de abrir la bóveda.",
                "Crear juego nuevo", icon_name="shamir", tone="warning"):
            return
        try:
            self._shares = list(self._session.enroll_recovery(n, k))
        except Exception as exc:  # noqa: BLE001 - disk errors: nothing changed
            self.set_note(f"No se pudieron crear: {exc}")
            return
        self.enrolled = True
        self._k_n = (k, n)
        self._current = 0
        self._saved = set()
        self._step_show()

    # step 2
    def _step_show(self) -> None:
        self._stepper.set_step(1)
        clear_layout(self.body)
        self._reset_footer()
        k, n = self._k_n
        self.add(_split_card(k, n))
        tiles = QHBoxLayout()
        tiles.setSpacing(8)
        for i in range(n):
            tile = QFrame()
            tile.setObjectName("shareTile")
            state = "saved" if i in self._saved else ("active" if i == self._current else "")
            if state:
                tile.setProperty("state", state)
            tl = QVBoxLayout(tile)
            tl.setContentsMargins(10, 8, 10, 8)
            tl.setSpacing(2)
            num = QLabel(f"{i + 1} / {n}")
            num.setFont(mono_font(12, 600))
            num.setStyleSheet(f"color: {P.TEXT_PRIMARY}; background: transparent;")
            tl.addWidget(num)
            word = {"saved": "✓ Guardado", "active": "En pantalla"}.get(state, "Pendiente")
            tone = {"saved": P.SUCCESS, "active": P.TEXT_PRIMARY}.get(state, P.TEXT_TERTIARY)
            st = label(word, "tertiary")
            st.setStyleSheet(f"color: {tone}; background: transparent;")
            tl.addWidget(st)
            tiles.addWidget(tile)
        self.add(tiles)
        share = self._shares[self._current]
        card = Card(name="cardSunken", margins=(18, 14, 18, 14), spacing=10)
        head = QHBoxLayout()
        head.addWidget(label(f"Fragmento {self._current + 1} de {n}", "bodyStrong"))
        head.addStretch(1)
        head.addWidget(label(f"{self._vault_label} · {fmt_date(datetime.now().isoformat())}", "tertiary"))
        card.add(head)
        card.add(_share_grid(share))
        card.add(info_line("Incluye número de fragmento y suma de control: un error de copia se detecta al "
                           "restaurar.", "success", "check"))
        self.add(card)
        warn = Banner("warning", "", "", compact=True)
        warn.set_message("", "• Guarda cada fragmento en un sitio distinto, o dáselo a personas distintas.\n"
                             "• No hagas fotos ni los subas a la nube: un fragmento es parte de la llave.\n"
                             "• Se muestran solo ahora. Si pierdes demasiados, crea un juego nuevo y el anterior "
                             "deja de valer.")
        self.add(warn)
        self._left.setText("Imprimir este fragmento")
        self._left.set_icon_name("printer")
        self._left_action = self._print
        self._left.show()
        self._left.setToolTip("Imprime solo este fragmento, en una hoja aparte.")
        last = self._current == n - 1
        nxt = self.add_button(Button("Guardado · comprobar" if last else "Guardado · siguiente", "primary",
                                     on_click=self._saved_next))
        nxt.setDefault(True)

    def _saved_next(self) -> None:
        self._saved.add(self._current)
        if self._current < len(self._shares) - 1:
            self._current += 1
            self._step_show()
        else:
            self._step_check()

    def _print(self) -> None:
        from PySide6.QtGui import QTextDocument
        from PySide6.QtPrintSupport import QPrintDialog, QPrinter
        k, n = self._k_n
        index = self._current
        groups = share_groups(self._shares[index])
        rows = "".join("<tr>" + "".join(f"<td style='padding:6px 14px'><small>{i + j + 1:02d}</small> "
                                        f"<b>{escape(g)}</b></td>" for j, g in enumerate(groups[i:i + 4])) + "</tr>"
                       for i in range(0, len(groups), 4))
        html = (f"<h2>AegisVault · fragmento {index + 1} de {n}</h2>"
                f"<p>{escape(self._vault_label)} · {fmt_date(datetime.now().isoformat())} · hacen falta {k}</p>"
                f"<table style='font-family:monospace;font-size:14pt'>{rows}</table>"
                "<p>Guárdalo en un sitio distinto de los demás fragmentos. Quien reúna "
                f"{k} puede cambiar la contraseña maestra de esta bóveda.</p>")
        printer = QPrinter(QPrinter.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec():
            doc = QTextDocument()
            doc.setHtml(html)
            doc.print_(printer)

    # step 3
    def _step_check(self) -> None:
        self._stepper.set_step(2)
        clear_layout(self.body)
        self._reset_footer()
        self._check_index = secrets.randbelow(len(self._shares))
        number = self._check_index + 1
        self.add(label(f"Escribe el fragmento {number} tal como lo guardaste. Los espacios no importan.", "body",
                       wrap=True))
        self._typed = QPlainTextEdit()
        self._typed.setObjectName("mono")
        self._typed.setFixedHeight(96)
        self._typed.setAccessibleName(f"Fragmento {number}")
        self.add(self._typed)
        self._check_msg = label("", "toneText", wrap=True, tone="danger")
        self._check_msg.hide()
        self.add(self._check_msg)
        self._left.setText("Volver a los fragmentos")
        self._left.set_icon_name("chevron-left")
        self._left_action = self._back_to_shares
        self._left.show()
        self._finish = self.add_button(Button("Terminar", "primary", on_click=self._done_ok))
        self._finish.setDefault(True)
        self._finish.setEnabled(False)
        self._typed.textChanged.connect(self._check_typed)
        self._typed.setFocus()

    def _back_to_shares(self) -> None:
        self._current = 0
        self._step_show()

    def _check_typed(self) -> None:
        text = self._typed.toPlainText()
        index, problem = share_problem(text, expected_index=self._check_index + 1, total=len(self._shares))
        ok = (not problem and index is not None
              and "".join(text.split()).lower() == self._shares[self._check_index].lower())
        if not problem and index is not None and not ok:
            problem = "Es un fragmento válido, pero no coincide con el que se acaba de crear."
        self._check_msg.setText(problem)
        self._check_msg.setVisible(bool(problem))
        if ok:
            self._check_msg.setText("Coincide. Ya puedes terminar.")
            set_prop(self._check_msg, "tone", "success")
            self._check_msg.show()
        else:
            set_prop(self._check_msg, "tone", "danger")
        self._finish.setEnabled(ok)

    def _done_ok(self) -> None:
        self._shares = []
        self.accept()

    def reject(self) -> None:
        if self._shares and not confirm(
                self, "¿Cerrar sin terminar?", "Los fragmentos que no hayas guardado se pierden y tendrías que crear "
                "un juego nuevo.", "Cerrar", icon_name="warning", tone="warning"):
            return
        super().reject()

    def done(self, result):  # noqa: D401 - Qt API
        self._shares = []
        super().done(result)


# ---- restore with shares -----------------------------------------------------------------
class RestoreShamirDialog(AvDialog):
    """Pre-unlock recovery; on success ``new_password`` holds the new master password."""

    def __init__(self, service, parent=None):
        super().__init__(parent, "Restaurar con fragmentos", "", icon_name="shamir", width=600)
        self._service = service
        policy = service.recovery_policy()
        self._k, self._n = policy if policy else (0, 0)
        self._accepted: dict[int, str] = {}
        self.new_password: str | None = None
        self._running = False
        self._stage_shares()

    def _clear_footer(self) -> None:
        while self.footer_buttons.count():
            item = self.footer_buttons.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    # stage 1: collect shares
    def _stage_shares(self) -> None:
        clear_layout(self.body)
        self._clear_footer()
        if not self._k:
            self.add(Banner("info", "Esta bóveda no tiene fragmentos de recuperación.",
                            "Se crean desde Ajustes › Recuperación Shamir, con la bóveda abierta."))
            self.add_button(Button("Cerrar", "primary", on_click=self.reject))
            return
        self.add(label(f"Introdúcelos de uno en uno y en cualquier orden. Esta bóveda pide {self._k}. Nada se envía "
                       "fuera del equipo.", "secondary", wrap=True))
        have = len(self._accepted)
        head = QHBoxLayout()
        head.addWidget(label(f"{have} de {self._k} fragmentos", "bodyStrong"))
        head.addStretch(1)
        left = self._k - have
        head.addWidget(label("listos" if left <= 0 else f"falta{'n' if left > 1 else ''} {left}", "tertiary"))
        self.add(head)
        bars = QHBoxLayout()
        bars.setSpacing(6)
        for i in range(self._k):
            bar = QFrame()
            bar.setFixedHeight(4)
            bar.setStyleSheet(f"background: {P.ACCENT if i < have else P.SURFACE_3}; border-radius: 2px;")
            bars.addWidget(bar)
        self.add(bars)
        for index in sorted(self._accepted):
            share = self._accepted[index]
            row = QFrame()
            row.setObjectName("card")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(14, 10, 10, 10)
            rl.setSpacing(10)
            rl.addWidget(icon_label("check", P.SUCCESS, 15))
            rl.addWidget(label(f"Fragmento {index} / {self._n}", "body"))
            rl.addStretch(1)
            groups = share_groups(share)
            rl.addWidget(label(f"{groups[0]} … {groups[-1]}", "monoSm"))
            rl.addWidget(Button("", "icon", "close", tooltip=f"Quitar fragmento {index}",
                                on_click=lambda i=index: self._remove(i)))
            self.add(row)
        self._input = None
        if have < self._k:
            self.add(label(f"{ORDINALS[have] if have < len(ORDINALS) else 'Siguiente'} fragmento", "label"))
            self._input = QPlainTextEdit()
            self._input.setObjectName("mono")
            self._input.setFixedHeight(92)
            self._input.setPlaceholderText("3A9F C2E0 5B71 …")
            self._input.setAccessibleName("Fragmento")
            self.add(self._input)
            self._problem = label("", "toneText", wrap=True, tone="danger")
            self._problem.hide()
            self.add(self._problem)
        self.add(Banner("info", "", f"Al completar {self._k} se reconstruye la clave y eliges una contraseña maestra "
                                    "nueva. Los fragmentos actuales siguen valiendo hasta que crees otros.",
                        compact=True))
        self.set_note(f"Con el {self._k}.º válido, el botón pasa a «Reconstruir la clave»" if have < self._k else "")
        self.add_button(Button("Cancelar", "secondary", on_click=self.reject))
        if have >= self._k:
            go = self.add_button(Button("Reconstruir la clave", "primary", "key", on_click=self._stage_password))
        else:
            go = self.add_button(Button("Añadir fragmento", "primary", "plus", on_click=self._add_share))
            go.setEnabled(False)
            self._input.textChanged.connect(self._validate_input)
            self._input.setFocus()
        go.setDefault(True)
        self._go = go

    def _validate_input(self) -> None:
        index, problem = share_problem(self._input.toPlainText(), taken=set(self._accepted), total=self._n)
        self._problem.setText(problem)
        self._problem.setVisible(bool(problem))
        set_prop(self._input, "error", bool(problem))
        self._go.setEnabled(index is not None and not problem)

    def _add_share(self) -> None:
        if self._input is None or not self._go.isEnabled():
            return
        text = "".join(self._input.toPlainText().split())
        index, problem = share_problem(text, taken=set(self._accepted), total=self._n)
        if problem or index is None:
            return
        self._accepted[index] = text
        self._stage_shares()

    def _remove(self, index: int) -> None:
        self._accepted.pop(index, None)
        self._stage_shares()

    # stage 2: new password
    def _stage_password(self) -> None:
        clear_layout(self.body)
        self._clear_footer()
        self.title_label.setText("Elige una contraseña maestra nueva")
        self.add(info_line(f"{len(self._accepted)} fragmentos listos. La clave se reconstruye al confirmar.",
                           "success", "check"))
        self._new = NewPasswordFields()
        self.add(self._new)
        self.set_note("")
        self.add_button(Button("Volver", "secondary", on_click=self._back))
        self._go = self.add_button(Button("Reconstruir y abrir", "primary", "key", on_click=self._recover))
        self._go.setDefault(True)
        self._go.setEnabled(False)
        self._new.changed.connect(lambda: self._go.setEnabled(self._new.is_valid()))
        self._new.password.setFocus()

    def _back(self) -> None:
        self.title_label.setText("Restaurar con fragmentos")
        self._stage_shares()

    def _recover(self) -> None:
        if not self._new.is_valid():
            return
        password = self._new.value()
        shares = list(self._accepted.values())
        self._new.wipe()
        clear_layout(self.body)
        self._clear_footer()
        self.title_label.setText("Reconstruyendo…")
        steps = StepList(("Combinando los fragmentos", "Comprobando la clave de la bóveda",
                          "Sellando con la contraseña nueva"))
        steps.set_state(1)
        self.add(steps)
        self.add(busy_bar())
        self._running = True

        def work(service=self._service, shares=shares, password=password):
            service.recover(shares, password)
            return password

        run_task(work, self._finished, parent=self)

    def _finished(self, result) -> None:
        self._running = False
        if result.ok:
            self.new_password = result.payload
            self._accepted = {}
            self.accept()
            return
        self.title_label.setText("Restaurar con fragmentos")
        clear_layout(self.body)
        self._clear_footer()
        if isinstance(result.payload, AuthenticationError):
            text = ("Los fragmentos no reconstruyen la clave de esta bóveda. ¿Son de un juego anterior o de otra "
                    "bóveda? No se ha cambiado nada.")
        else:
            text = f"No se pudo restaurar: {result.error}. No se ha cambiado nada."
        self._accepted = {}
        self.add(Banner("danger", "No se ha restaurado.", text))
        self.add_button(Button("Cerrar", "secondary", on_click=self.reject))
        self.add_button(Button("Empezar de nuevo", "primary", on_click=self._stage_shares)).setDefault(True)

    def reject(self) -> None:
        if self._running:
            return
        super().reject()

    def done(self, result):  # noqa: D401 - Qt API
        if self._running:
            return
        self._accepted = {}
        super().done(result)
