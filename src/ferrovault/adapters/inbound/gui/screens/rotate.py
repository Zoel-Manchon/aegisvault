"""Rotate the master password (board 16): form, typed confirmation, progress.

Only the data key is re-sealed (entries are not re-encrypted), the current
password is checked again first, a copy of the file is kept, and the key
derivation runs on a worker thread so the window never freezes.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout, QWidget

from .....application.errors import AuthenticationError, VaultConflictError
from ..background import run_task
from ..components.kit import (
    AvDialog, Banner, Button, Card, PasswordField, StepList, busy_bar, clear_layout, confirm, icon_label, label,
    vbox,
)
from ..theme import PALETTE as P
from .master import NewPasswordFields

STEPS = ("Copia previa guardada", "Derivando la nueva clave", "Re-sellando y escribiendo el archivo",
         "Registrando «rotate» en la auditoría")


def _check_line(icon_name: str, color: str, text: str) -> QWidget:
    w = QWidget()
    w.setObjectName("transparent")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(10)
    row.addWidget(icon_label(icon_name, color, 15), 0, Qt.AlignTop)
    row.addWidget(label(text, "body", wrap=True), 1)
    return w


class RotateMasterDialog(AvDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent, "Rotar la contraseña maestra",
                         "Tus entradas no se vuelven a cifrar: la clave de la bóveda se vuelve a sellar con la nueva "
                         "contraseña.", icon_name="key", width=600)
        self._session = session
        self.rotated = False
        self._running = False
        self._task = None
        self._build_form()

    # ---- stage 1: form -------------------------------------------------------------
    def _build_form(self) -> None:
        clear_layout(self.body)
        self._current = PasswordField()
        self._current.setAccessibleName("Contraseña actual")
        self._current_error = label("", "toneText", tone="danger")
        self._current_error.hide()
        self.add(vbox(label("Contraseña actual", "label"), self._current, self._current_error, spacing=6))
        self._new = NewPasswordFields()
        self.add(self._new)
        card = Card(name="cardSunken", margins=(16, 14, 16, 14), spacing=10)
        card.add(label("Qué cambia y qué no", "bodyStrong"))
        if self._session.has_recovery:
            card.add(_check_line("check", P.SUCCESS,
                                 "Los fragmentos Shamir siguen valiendo: protegen la misma clave de datos."))
        else:
            card.add(_check_line("info", P.INFO, "No tienes fragmentos Shamir: si olvidas la nueva, no hay "
                                                 "recuperación. Puedes crearlos después en Ajustes."))
        card.add(_check_line("check", P.SUCCESS, "Antes de rotar se guarda una copia del archivo actual."))
        card.add(_check_line("info", P.INFO, "Los equipos sincronizados te pedirán la contraseña nueva."))
        card.add(Banner("warning", "Las copias antiguas del archivo se siguen abriendo con la contraseña anterior.",
                        "Si crees que alguien la conoce, sustituye también esas copias.", compact=True))
        self.add(card)
        self._clear_buttons()
        self.add_button(Button("Cancelar", "secondary", on_click=self.reject))
        self._continue = self.add_button(Button("Continuar", "primary", on_click=self._confirm))
        self._continue.setDefault(True)
        self._current.textChanged.connect(self._validate)
        self._new.changed.connect(self._validate)
        self._validate()
        self._current.setFocus()

    def _clear_buttons(self) -> None:
        while self.footer_buttons.count():
            item = self.footer_buttons.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _validate(self, *_):
        current = self._current.text()
        if current != getattr(self, "_avoid_cache", None):
            self._avoid_cache = current
            self._new.set_avoid(current)  # emits changed, which runs this again
            return
        self._current_error.hide()
        self._continue.setEnabled(bool(current) and self._new.is_valid())

    # ---- stage 2: typed confirmation ------------------------------------------------
    def _confirm(self) -> None:
        if not self._continue.isEnabled():
            return
        if not confirm(self, "¿Rotar ahora?",
                       "A partir de ahora, solo la nueva contraseña desbloquea este archivo. La anterior deja de "
                       "funcionar aquí y no hay forma de deshacerlo.", "Rotar contraseña maestra",
                       checkbox="He guardado la nueva contraseña en un lugar seguro", type_word="ROTAR",
                       icon_name="sync", tone="danger"):
            return
        self._run(self._current.text(), self._new.value())

    # ---- stage 3: progress ------------------------------------------------------------
    def _run(self, current: str, new: str) -> None:
        self._running = True
        self._new.wipe()
        self._current.wipe()
        clear_layout(self.body)
        self.title_label.setText("Rotando…")
        self.subtitle_label.setText("No cierres la aplicación.")
        self._steps = StepList(STEPS)
        self._steps.set_state(1)
        self.add(self._steps)
        self.add(busy_bar())
        self._clear_buttons()
        self.set_note("")

        def work(session=self._session, current=current, new=new):
            session.rotate(new, current_password=current)

        self._task = run_task(work, self._finished, parent=self)
        del current, new

    def _finished(self, result) -> None:
        self._running = False
        self._task = None
        clear_layout(self.body)
        if result.ok:
            self.rotated = True
            self.title_label.setText("Contraseña maestra cambiada")
            self.subtitle_label.setText("Desde ahora solo la nueva abre este archivo.")
            steps = StepList(STEPS)
            steps.set_state(len(STEPS))
            self.add(steps)
            done = self.add_button(Button("Listo", "primary", on_click=self.accept))
            done.setDefault(True)
            done.setFocus()
            return
        error = result.payload
        if isinstance(error, AuthenticationError):
            text = "La contraseña actual no es correcta. No se ha cambiado nada."
        elif isinstance(error, VaultConflictError):
            text = str(error)
        else:
            text = f"No se pudo rotar: {result.error}. La contraseña anterior sigue valiendo."
        self.title_label.setText("Rotar la contraseña maestra")
        self.subtitle_label.setText("")
        self.add(Banner("danger", "No se ha rotado.", text))
        self.add_button(Button("Cerrar", "secondary", on_click=self.reject))
        self.add_button(Button("Volver a intentarlo", "primary", on_click=self._build_form)).setDefault(True)

    def reject(self) -> None:
        if self._running:
            return  # the file is being re-sealed; closing now helps nobody
        super().reject()

    def done(self, result):  # noqa: D401 - Qt API
        if self._running:
            return
        for field in (getattr(self, "_current", None),):
            try:
                field.wipe()
            except (AttributeError, RuntimeError):
                pass
        try:
            self._new.wipe()
        except (AttributeError, RuntimeError):
            pass
        super().done(result)
