"""Create or edit an entry (board 12): the form on the left, the generator on the right.

Secrets typed here stay in the widgets only until the dialog closes (the
fields are overwritten then, best effort). Nothing is written to the vault
until "Guardar entrada"; a changed password moves the old one to the entry's
history inside the vault.
"""
from __future__ import annotations

import html
import time
from urllib.parse import parse_qs, urlparse

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit, QScrollArea,
    QSlider, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

from .....application.errors import VaultConflictError
from .....domain.model.vault import EntryNameTaken
from .....domain.services.password_generator import PasswordGenerator
from .....domain.value_objects.password_policy import PassphrasePolicy, PasswordPolicy
from .....domain.value_objects.totp_secret import TotpSecret
from ..components.kit import (
    AvDialog, Button, Chip, Field, FlowLayout, PasswordField, Segmented, StrengthMeter, Toggle, icon_label, label,
    mono_font, set_prop,
)
from ..design.tokens import CONTROL_H_MD
from ..fmt import join_names
from ..theme import PALETTE as P

KINDS = (("login", "Login"), ("api_key", "API key"), ("note", "Nota segura"), ("card", "Tarjeta"))
KIND_ICONS = {"login": "user", "api_key": "code", "note": "note", "card": "card"}


# ---- pure helpers (tested without Qt) -------------------------------------------
def parse_totp(text: str) -> tuple[str | None, str]:
    """``(base32 seed, problem)`` from a bare seed or an ``otpauth://totp/...`` URI."""
    raw = (text or "").strip()
    if not raw:
        return None, "Pega la clave secreta o la URI otpauth:// que da el servicio."
    if raw.lower().startswith("otpauth://"):
        parsed = urlparse(raw)
        if parsed.netloc.lower() != "totp":
            return None, "Solo se admiten códigos por tiempo (TOTP), no HOTP."
        params = {k.lower(): v[0] for k, v in parse_qs(parsed.query).items() if v}
        seed = params.get("secret", "")
        algo = params.get("algorithm", "SHA1").upper().replace("-", "")
        digits = params.get("digits", "6")
        period = params.get("period", "30")
        if (algo, digits, period) != ("SHA1", "6", "30"):
            return None, (f"Esta cuenta usa {algo} · {digits} dígitos · {period} s y AegisVault genera "
                          "SHA-1 · 6 dígitos · 30 s: los códigos no coincidirían.")
        if not seed:
            return None, "La URI no lleva el parámetro «secret»."
    else:
        seed = raw
    seed = "".join(seed.split()).replace("-", "").upper().rstrip("=")
    try:
        TotpSecret(seed)
    except ValueError:
        return None, "No es una clave base32 válida (solo letras A–Z y números 2–7)."
    if len(seed) < 16:
        return None, "La clave es demasiado corta: los servicios dan al menos 16 caracteres."
    return seed, ""


def group4(seed: str) -> str:
    """'JBSWY3DPEHPK3PXP' -> 'JBSW Y3DP EHPK 3PXP' (easier to compare with the service's screen)."""
    seed = "".join(seed.split())
    return " ".join(seed[i:i + 4] for i in range(0, len(seed), 4))


def highlight_digits(text: str) -> str:
    """Rich text with digits tinted, so 0/O and 1/l are not confused when read aloud."""
    out = []
    for ch in text:
        esc = html.escape(ch)
        out.append(f"<span style='color:{P.INFO}'>{esc}</span>" if ch.isdigit() else esc)
        out.append("&#8203;")                  # allow wrapping anywhere
    return "".join(out)


def strength_hint(assessment) -> str:
    if assessment is None or not getattr(assessment, "length", 0):
        return ""
    parts = [f"{assessment.length} caracteres de un alfabeto de {assessment.pool}"]
    if getattr(assessment, "common", False):
        parts.append("es una contraseña conocida")
    elif getattr(assessment, "pattern_penalty", False):
        parts.append("tiene patrones previsibles")
    else:
        parts.append("sin patrones de diccionario")
    return " · ".join(parts)


# ---- generator --------------------------------------------------------------------
class GeneratorPanel(QFrame):
    """Right column of board 12. Uses the system CSPRNG through the vault service."""

    use_password = Signal(str)

    CLASSES = (("upper", "Mayúsculas", "A–Z"), ("lower", "Minúsculas", "a–z"), ("digits", "Números", "0–9"),
               ("symbols", "Símbolos", "!@#$%"), ("ambiguous", "Evitar parecidos", "0 O l 1 I"))

    def __init__(self, session):
        super().__init__()
        self._session = session
        self.current = ""
        self.setObjectName("editorAside")
        self.setFixedWidth(340)
        col = QVBoxLayout(self)
        col.setContentsMargins(22, 20, 22, 20)
        col.setSpacing(14)

        head = QHBoxLayout()
        head.addWidget(label("Generador", "titleSm"))
        head.addStretch(1)
        head.addWidget(label("CSPRNG del sistema", "tertiary"))
        col.addLayout(head)

        self.mode = Segmented((("random", "Aleatoria"), ("phrase", "Frase")), "random")
        self.mode.changed.connect(self._mode_changed)
        col.addWidget(self.mode)

        preview = QFrame()
        preview.setObjectName("cardSunken")
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(14, 12, 14, 12)
        pv.setSpacing(8)
        self.preview = QLabel()
        self.preview.setTextFormat(Qt.RichText)
        self.preview.setWordWrap(True)
        self.preview.setFont(mono_font(17, 500))
        self.preview.setMinimumHeight(28)
        self.preview.setAccessibleName("Contraseña generada")
        pv.addWidget(self.preview)
        self.preview_hint = label("Dígitos resaltados para leerla sin confundir caracteres.", "tertiary", wrap=True)
        pv.addWidget(self.preview_hint)
        col.addWidget(preview)

        self.options = QStackedWidget()
        self.options.setObjectName("transparent")
        self.options.addWidget(self._random_options())
        self.options.addWidget(self._phrase_options())
        col.addWidget(self.options)
        self.bits = label("", "tertiary")
        col.addWidget(self.bits)
        col.addStretch(1)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self.again_btn = Button("Otra", "secondary", "sync", on_click=self.regenerate, tooltip="Generar otra")
        self.use_btn = Button("Usar esta contraseña", "secondary", on_click=lambda: self.use_password.emit(self.current))
        buttons.addWidget(self.again_btn)
        buttons.addWidget(self.use_btn, 1)
        col.addLayout(buttons)
        self.regenerate()

    # options
    def _length_block(self, title: str, low: int, high: int, value: int):
        box = QVBoxLayout()
        box.setSpacing(8)
        row = QHBoxLayout()
        row.addWidget(label(title, "label"))
        row.addStretch(1)
        spin = QSpinBox()
        spin.setRange(low, high)
        spin.setValue(value)
        spin.setFixedSize(64, CONTROL_H_MD)
        spin.setAlignment(Qt.AlignCenter)
        spin.setButtonSymbols(QSpinBox.NoButtons)
        spin.setFont(mono_font(13, 600))
        spin.setAccessibleName(title)
        row.addWidget(spin)
        box.addLayout(row)
        slider = QSlider(Qt.Horizontal)
        slider.setRange(low, high)
        slider.setValue(value)
        slider.setAccessibleName(title)
        box.addWidget(slider)
        ends = QHBoxLayout()
        ends.addWidget(label(str(low), "monoSm"))
        ends.addStretch(1)
        ends.addWidget(label(str(high), "monoSm"))
        box.addLayout(ends)
        spin.valueChanged.connect(slider.setValue)
        slider.valueChanged.connect(spin.setValue)
        slider.valueChanged.connect(lambda _v: self._debounced())
        return box, slider

    def _random_options(self) -> QWidget:
        w = QWidget()
        w.setObjectName("transparent")
        col = QVBoxLayout(w)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(4)
        block, self.length = self._length_block("Longitud", 8, 64, 20)
        col.addLayout(block)
        col.addSpacing(6)
        self.checks: dict[str, QCheckBox] = {}
        for key, text, sample in self.CLASSES:
            row = QHBoxLayout()
            check = QCheckBox(text)
            check.setChecked(key != "ambiguous")
            check.toggled.connect(lambda on, k=key: self._class_toggled(k, on))
            self.checks[key] = check
            row.addWidget(check)
            row.addStretch(1)
            row.addWidget(label(sample, "monoSm"))
            col.addLayout(row)
        return w

    def _phrase_options(self) -> QWidget:
        w = QWidget()
        w.setObjectName("transparent")
        col = QVBoxLayout(w)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)
        block, self.words = self._length_block("Palabras", 4, 12, 6)
        col.addLayout(block)
        sep_row = QHBoxLayout()
        sep_row.addWidget(label("Separador", "label"))
        sep_row.addStretch(1)
        self.separator = Segmented((("-", "-"), (".", "."), ("_", "_"), (" ", "espacio")), "-", expand=False)
        self.separator.changed.connect(lambda _k: self.regenerate())
        sep_row.addWidget(self.separator)
        col.addLayout(sep_row)
        self.capitalize = QCheckBox("Mayúscula inicial")
        self.capitalize.setChecked(True)
        self.add_digit = QCheckBox("Añadir un número")
        self.add_digit.setChecked(True)
        for c in (self.capitalize, self.add_digit):
            c.toggled.connect(lambda _on: self.regenerate())
            col.addWidget(c)
        return w

    def _class_toggled(self, key: str, on: bool) -> None:
        if not on and key != "ambiguous":
            if not any(self.checks[k].isChecked() for k in ("upper", "lower", "digits", "symbols")):
                self.checks[key].blockSignals(True)
                self.checks[key].setChecked(True)
                self.checks[key].blockSignals(False)
                return
        self.regenerate()

    def _mode_changed(self, key: str) -> None:
        self.options.setCurrentIndex(0 if key == "random" else 1)
        self.preview_hint.setText("Dígitos resaltados para leerla sin confundir caracteres." if key == "random"
                                  else "Fácil de teclear y de dictar; la longitud compensa el alfabeto.")
        self.regenerate()

    def _debounced(self) -> None:
        if not hasattr(self, "_debounce"):
            self._debounce = QTimer(self)
            self._debounce.setSingleShot(True)
            self._debounce.setInterval(60)
            self._debounce.timeout.connect(self.regenerate)
        self._debounce.start()

    # generation
    def password_policy(self) -> PasswordPolicy:
        c = self.checks
        return PasswordPolicy(length=self.length.value(), lower=c["lower"].isChecked(), upper=c["upper"].isChecked(),
                              digits=c["digits"].isChecked(), symbols=c["symbols"].isChecked(),
                              avoid_ambiguous=c["ambiguous"].isChecked())

    def phrase_policy(self) -> PassphrasePolicy:
        return PassphrasePolicy(words=self.words.value(), separator=self.separator.value() or "-",
                                capitalize=self.capitalize.isChecked(), add_digit=self.add_digit.isChecked())

    def regenerate(self) -> str:
        if self.mode.value() == "phrase":
            policy = self.phrase_policy()
            self.current = self._session.generate_passphrase(policy)
            bits = PasswordGenerator.passphrase_bits(policy)
        else:
            policy = self.password_policy()
            self.current, _label = self._session.generate(policy)
            bits = PasswordGenerator.entropy_bits(policy)
        self.preview.setText(highlight_digits(self.current))
        self.bits.setText(f"≈ {int(bits)} bits de entropía")
        return self.current

    def set_enabled_for(self, enabled: bool, reason: str = "") -> None:
        for w in (self.mode, self.options, self.again_btn, self.use_btn):
            w.setEnabled(enabled)
        self.preview.setVisible(enabled)
        self.bits.setVisible(enabled)
        self.preview_hint.setText("Dígitos resaltados para leerla sin confundir caracteres." if enabled else reason)


# ---- tags -------------------------------------------------------------------------
class TagInput(QFrame):
    """Chips plus an inline "Añadir…" field. Enter or comma adds; Backspace removes the last."""

    def __init__(self, tags=()):
        super().__init__()
        self.setObjectName("tagInput")
        self._tags: list[str] = []
        self._flow = FlowLayout(self, spacing=6)
        self._flow.setContentsMargins(8, 7, 8, 7)
        self.edit = QLineEdit()
        self.edit.setObjectName("bare")
        self.edit.setPlaceholderText("Añadir…")
        self.edit.setMinimumWidth(80)
        self.edit.setAccessibleName("Añadir etiqueta")
        self.edit.returnPressed.connect(self._commit)
        self.edit.textEdited.connect(self._maybe_split)
        self.edit.installEventFilter(self)
        for t in tags:
            self._add(str(t))
        self._render()

    def tags(self) -> list[str]:
        pending = self.edit.text().strip().strip(",")
        return self._tags + ([pending] if pending and pending not in self._tags else [])

    def _add(self, text: str) -> None:
        text = text.strip().strip(",").strip()
        if text and text not in self._tags and len(self._tags) < 20:
            self._tags.append(text[:40])

    def _commit(self) -> None:
        self._add(self.edit.text())
        self.edit.clear()
        self._render()

    def _maybe_split(self, text: str) -> None:
        if "," in text:
            for part in text.split(",")[:-1]:
                self._add(part)
            self.edit.setText(text.split(",")[-1])
            self._render()

    def _remove(self, tag: str) -> None:
        if tag in self._tags:
            self._tags.remove(tag)
        self._render()

    def _render(self) -> None:
        had_focus = self.edit.hasFocus()
        while self._flow.count():
            item = self._flow.takeAt(0)
            widget = item.widget()
            if widget is not None and widget is not self.edit:
                widget.setParent(None)
                widget.deleteLater()
        for tag in self._tags:
            chip = Chip(tag, removable=True)
            chip.removed.connect(lambda t=tag: self._remove(t))
            self._flow.addWidget(chip)
        self._flow.addWidget(self.edit)
        if had_focus:
            self.edit.setFocus()
        self._flow.invalidate()
        self.updateGeometry()

    def eventFilter(self, obj, event):  # noqa: N802 - Qt API
        from PySide6.QtCore import QEvent
        if obj is self.edit and event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Backspace and not self.edit.text() and self._tags:
                self._tags.pop()
                self._render()
                self.edit.setFocus()
                return True
        return super().eventFilter(obj, event)


# ---- the dialog -------------------------------------------------------------------
def _caption(text: str) -> QLabel:
    return label(text, "label")


class EntryEditor(AvDialog):
    """"Nueva entrada" / "Editar entrada". ``saved_name`` is set after a successful save."""

    def __init__(self, session, parent=None, *, settings=None, view=None, category=None, name=None,
                 focus=None, categories=()):
        editing = view is not None
        super().__init__(parent, "Editar entrada" if editing else "Nueva entrada", width=960, scroll=False)
        self._session = session
        self._settings = settings
        self._view = view
        self.saved_name: str | None = None
        self.conflict = None
        self._original_secret = session.reveal(view.name) if editing else ""
        self._original_seed = session.totp_seed(view.name) if editing and view.has_totp else ""

        hint = label("Esc para cerrar sin guardar", "tertiary")
        self.header_right.addWidget(hint)
        self.body.setContentsMargins(0, 0, 0, 0)
        self.body.setSpacing(0)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        area = QScrollArea()
        area.setObjectName("plain")
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        form = QWidget()
        form.setObjectName("transparent")
        area.setWidget(form)
        screen = QGuiApplication.primaryScreen()
        avail = screen.availableGeometry().height() if screen else 900
        area.setMinimumHeight(max(420, min(660, avail - 220)))
        row.addWidget(area, 1)
        self.generator = GeneratorPanel(session)
        self.generator.use_password.connect(self._use_generated)
        row.addWidget(self.generator)
        self.add(row)

        col = QVBoxLayout(form)
        col.setContentsMargins(24, 20, 24, 24)
        col.setSpacing(16)
        self.kind = Segmented(KINDS, getattr(view, "kind", "login") if editing else "login",
                              icons=KIND_ICONS)
        self.kind.setAccessibleName("Tipo de entrada")
        self.kind.changed.connect(self._kind_changed)
        col.addWidget(self.kind)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        self.name = Field(view.name if editing else (name or ""), "Por ejemplo, GitHub")
        self.name.setAccessibleName("Nombre")
        self.category = QComboBox()
        self.category.setEditable(True)
        self.category.addItems(list(categories))
        self.category.lineEdit().setPlaceholderText("Sin categoría")
        self.category.setCurrentText(view.category if editing else (category or ""))
        self.category.setAccessibleName("Categoría")
        self.name_error = label("", "toneText")
        set_prop(self.name_error, "tone", "danger")
        self.name_error.hide()
        self.name.textEdited.connect(self._clear_name_problem)
        grid.addWidget(_caption("Nombre"), 0, 0)
        grid.addWidget(_caption("Categoría"), 0, 1)
        grid.addWidget(self.name, 1, 0)
        grid.addWidget(self.category, 1, 1)
        grid.addWidget(self.name_error, 2, 0, 1, 2)
        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)
        col.addLayout(grid)

        grid2 = QGridLayout()
        grid2.setHorizontalSpacing(12)
        grid2.setVerticalSpacing(6)
        self.user_caption = _caption("Usuario")
        self.url_caption = _caption("URL")
        self.username = Field(view.username if editing else "", "nombre@dominio.com")
        self.url = Field(view.url if editing else "", "https://")
        grid2.addWidget(self.user_caption, 0, 0)
        grid2.addWidget(self.url_caption, 0, 1)
        grid2.addWidget(self.username, 1, 0)
        grid2.addWidget(self.url, 1, 1)
        self._user_url = grid2
        col.addLayout(grid2)

        # secret
        self.secret_caption = _caption("Contraseña")
        col.addWidget(self.secret_caption)
        self.secret = PasswordField("", on_regenerate=self._regenerate_secret)
        self.secret.setAccessibleName("Contraseña")
        self.secret.setText(self._original_secret if self._view is None or self._view.kind != "note" else "")
        self.secret.textChanged.connect(self._secret_changed)
        col.addWidget(self.secret)
        self.content = QPlainTextEdit()
        self.content.setObjectName("mono")
        self.content.setPlaceholderText("Lo que escribas aquí se cifra igual que una contraseña.")
        self.content.setMinimumHeight(160)
        self.content.setPlainText(self._original_secret if editing and view.kind == "note" else "")
        col.addWidget(self.content)
        self.meter = StrengthMeter()
        col.addWidget(self.meter)
        self.reuse_line = QWidget()
        rl = QHBoxLayout(self.reuse_line)
        rl.setContentsMargins(0, 0, 0, 0)
        rl.setSpacing(6)
        rl.addWidget(icon_label("warning", P.WARNING, 14))
        self.reuse_text = label("", "secondary", wrap=True)
        rl.addWidget(self.reuse_text, 1)
        self.reuse_line.hide()
        col.addWidget(self.reuse_line)
        self.secret_error = label("", "toneText")
        set_prop(self.secret_error, "tone", "danger")
        self.secret_error.hide()
        col.addWidget(self.secret_error)

        # 2FA
        self.totp_card = QFrame()
        self.totp_card.setObjectName("cardSunken")
        tc = QVBoxLayout(self.totp_card)
        tc.setContentsMargins(16, 14, 16, 14)
        tc.setSpacing(10)
        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        titles.addWidget(label("Código 2FA (TOTP)", "bodyStrong"))
        titles.addWidget(label("Opcional. La semilla queda cifrada junto a la contraseña.", "secondary", wrap=True))
        top.addLayout(titles, 1)
        self.totp_toggle = Toggle(bool(self._original_seed))
        self.totp_toggle.switch.setAccessibleName("Añadir código 2FA")
        self.totp_toggle.toggled.connect(self._totp_toggled)
        top.addWidget(self.totp_toggle, 0, Qt.AlignTop)
        tc.addLayout(top)
        self.totp_body = QWidget()
        self.totp_body.setObjectName("transparent")
        tb = QVBoxLayout(self.totp_body)
        tb.setContentsMargins(0, 0, 0, 0)
        tb.setSpacing(8)
        tb.addWidget(_caption("Clave secreta o URI otpauth://"))
        seed_row = QHBoxLayout()
        seed_row.setSpacing(8)
        self.seed = PasswordField("JBSW Y3DP EHPK 3PXP")
        self.seed.setAccessibleName("Clave secreta 2FA")
        self.seed.setText(group4(self._original_seed) if self._original_seed else "")
        self.seed.set_visible_text(not self._original_seed)
        self.seed.textChanged.connect(self._seed_changed)
        seed_row.addWidget(self.seed, 1)
        seed_row.addWidget(Button("Pegar", "secondary", "clipboard", on_click=self._paste_seed,
                                  tooltip="Pegar la clave o la URI otpauth:// del portapapeles"))
        seed_row.addWidget(Button("Generar", "ghost", "key", on_click=self._generate_seed,
                                  tooltip="Crear una semilla nueva (para servicios propios)"))
        tb.addLayout(seed_row)
        status = QHBoxLayout()
        status.setSpacing(6)
        self.seed_icon = QLabel()
        self.seed_icon.setFixedSize(14, 14)
        self.seed_status = label("", "secondary", wrap=True)
        self.seed_code = label("", "monoBody")
        status.addWidget(self.seed_icon, 0, Qt.AlignTop)
        status.addWidget(self.seed_status, 1)
        status.addWidget(self.seed_code)
        tb.addLayout(status)
        tc.addWidget(self.totp_body)
        col.addWidget(self.totp_card)

        # tags + notes
        bottom = QGridLayout()
        bottom.setHorizontalSpacing(12)
        bottom.setVerticalSpacing(6)
        self.tags = TagInput(view.tags if editing else ())
        self.notes = QPlainTextEdit()
        self.notes.setPlaceholderText("Pistas, preguntas de seguridad, contexto…")
        self.notes.setPlainText(session.notes(view.name) if editing else "")
        self.notes.setMinimumHeight(120)
        self.notes_caption = _caption("Notas")
        bottom.addWidget(_caption("Etiquetas"), 0, 0)
        bottom.addWidget(self.notes_caption, 0, 1)
        bottom.addWidget(self.tags, 1, 0, Qt.AlignTop)
        bottom.addWidget(self.notes, 1, 1)
        bottom.setColumnStretch(0, 2)
        bottom.setColumnStretch(1, 3)
        col.addLayout(bottom)
        col.addStretch(1)

        # footer
        self.set_note("Al editar, la contraseña anterior pasa al historial de la entrada." if editing
                      else "Se guarda cifrada en el archivo de la bóveda; nada sale de este equipo.")
        self.add_button(Button("Cancelar", "secondary", on_click=self.reject))
        self.save_btn = self.add_button(Button("Guardar entrada", "primary", shortcut="Ctrl S", on_click=self._save))
        self.save_btn.setDefault(True)
        QShortcut(QKeySequence("Ctrl+S"), self, activated=self._save)

        self._assess_timer = QTimer(self)
        self._assess_timer.setSingleShot(True)
        self._assess_timer.setInterval(180)
        self._assess_timer.timeout.connect(self._assess)
        self._code_timer = QTimer(self)
        self._code_timer.timeout.connect(self._seed_changed)
        self._code_timer.start(1000)

        if not editing:
            self.secret.setText(self.generator.current)
            self.secret.set_visible_text(True)
        self._kind_changed(self.kind.value() or "login")
        self._totp_toggled(self.totp_toggle.isChecked())
        self._assess()
        self._apply_focus(focus)

    # ---- behaviour ------------------------------------------------------------------
    def _apply_focus(self, focus: str | None) -> None:
        if focus == "generate":
            self._regenerate_secret()
            target = self.secret
        elif focus == "totp":
            self.totp_toggle.setChecked(True)
            target = self.seed
        else:
            target = self.name if (not self._view or not self.name.text()) else self.username
        QTimer.singleShot(0, target.setFocus)

    def _kind_changed(self, kind: str) -> None:
        secretish = kind in ("login", "api_key", "card")
        is_note = kind == "note"
        self.user_caption.setText({"login": "Usuario", "api_key": "Cuenta o proyecto", "card": "Titular"}.get(kind, ""))
        self.url_caption.setText("URL o endpoint" if kind == "api_key" else "URL")
        self.secret_caption.setText({"login": "Contraseña", "api_key": "Clave", "card": "Número de tarjeta",
                                     "note": "Contenido"}[kind])
        for w in (self.user_caption, self.username):
            w.setVisible(kind != "note")
        for w in (self.url_caption, self.url):
            w.setVisible(kind in ("login", "api_key"))
        self.secret.setVisible(secretish)
        self.content.setVisible(is_note)
        if is_note and not self.content.toPlainText() and self.secret.text() and self._view is not None:
            self.content.setPlainText(self.secret.text())
        self.meter.setVisible(kind in ("login", "api_key"))
        self.totp_card.setVisible(kind == "login")
        self.notes_caption.setText("Notas" if kind != "card" else "Notas (caducidad, CVV, PIN…)")
        self.notes.setVisible(kind != "note")
        self.notes_caption.setVisible(kind != "note")
        self.secret.setAccessibleName(self.secret_caption.text())
        self.generator.set_enabled_for(kind in ("login", "api_key"),
                                       "Las notas y las tarjetas no usan el generador." if kind in ("note", "card")
                                       else "")
        self.reuse_line.setVisible(False)
        self._assess()

    def _regenerate_secret(self) -> None:
        self.secret.setText(self.generator.regenerate())
        self.secret.set_visible_text(True)

    def _use_generated(self, password: str) -> None:
        if password:
            self.secret.setText(password)
            self.secret.set_visible_text(True)
            self.secret.setFocus()

    def _secret_changed(self, _text: str) -> None:
        self.secret_error.hide()
        set_prop(self.secret, "error", False)
        self._assess_timer.start()

    def _assess(self) -> None:
        kind = self.kind.value()
        text = self.secret.text()
        if kind not in ("login", "api_key") or not text:
            self.meter.set_assessment(None)
            self.reuse_line.hide()
            return
        assessment = self._session.assess(text)
        self.meter.set_assessment(assessment, strength_hint(assessment))
        others = self._session.entries_with_secret(text, exclude=self._view.name if self._view else None)
        if others:
            many = len(others) + 1
            self.reuse_text.setText(f"Ya la usas en {join_names(others)}. Si una se filtra, "
                                    f"caen las {'dos' if many == 2 else many}.")
        self.reuse_line.setVisible(bool(others))

    def _totp_toggled(self, on: bool) -> None:
        self.totp_body.setVisible(on)
        if on:
            self._seed_changed()

    def _paste_seed(self) -> None:
        text = QGuiApplication.clipboard().text().strip()
        if text:
            self.seed.setText(text)
            self.seed.set_visible_text(False)

    def _generate_seed(self) -> None:
        self.seed.setText(group4(self._session.generate_totp_seed()))
        self.seed.set_visible_text(True)

    def _seed_changed(self, *_):
        if not self.totp_toggle.isChecked() or not self.totp_body.isVisible():
            return
        seed, problem = parse_totp(self.seed.text())
        if seed:
            totp = TotpSecret(seed)
            now = int(time.time())
            code = totp.code_at(now)
            self.seed_icon.setPixmap(_pix("check", P.SUCCESS))
            self.seed_status.setText(f"Semilla válida · SHA-1 · 6 dígitos · 30 s · código actual "
                                     f"(quedan {totp.seconds_remaining(now)} s)")
            self.seed_code.setText(f"{code[:3]} {code[3:]}")
            set_prop(self.seed, "error", False)
        else:
            empty = not self.seed.text().strip()
            self.seed_icon.setPixmap(_pix("info" if empty else "alert", P.TEXT_TERTIARY if empty else P.DANGER))
            self.seed_status.setText(problem)
            self.seed_code.setText("")
            set_prop(self.seed, "error", not empty)

    # ---- save -----------------------------------------------------------------------
    def _secret_value(self) -> str:
        return self.content.toPlainText() if self.kind.value() == "note" else self.secret.text()

    def _save(self) -> None:
        kind = self.kind.value() or "login"
        name = self.name.text().strip()
        secret = self._secret_value()
        ok = True
        if not name:
            self._name_problem("Ponle un nombre: es lo que verás en la lista.")
            ok = False
        else:
            taken = {v.name for v in self._session.entries()} - ({self._view.name} if self._view else set())
            if name in taken:
                self._name_problem("Ya hay una entrada con ese nombre (puede estar en la papelera).")
                ok = False
        if not secret.strip():
            what = {"login": "la contraseña", "api_key": "la clave", "card": "el número",
                    "note": "el contenido"}[kind]
            self.secret_error.setText(f"Falta {what}.")
            self.secret_error.show()
            set_prop(self.secret, "error", True)
            ok = False
        seed = None
        if kind == "login" and self.totp_toggle.isChecked():
            seed, problem = parse_totp(self.seed.text())
            if not seed:
                self._seed_changed()
                self.seed.setFocus()
                ok = False
        if not ok:
            return
        username = self.username.text().strip() if kind != "note" else ""
        url = self.url.text().strip() if kind in ("login", "api_key") else ""
        notes = self.notes.toPlainText() if kind != "note" else ""
        category = self.category.currentText().strip()
        tags = self.tags.tags()
        try:
            if self._view is None:
                self._session.add(name, username, secret, url=url, notes=notes, tags=tags, category=category,
                                  totp=seed, kind=kind)
                self.saved_name = name
            else:
                changes = dict(new_name=name, username=username, url=url, notes=notes, tags=tags,
                               category=category, kind=kind)
                if secret != self._original_secret:
                    changes["secret"] = secret
                if (seed or "") != (self._original_seed or ""):
                    changes["totp"] = seed
                self.saved_name = self._session.update(self._view.name, **changes)
        except EntryNameTaken:
            self._name_problem("Ya hay una entrada con ese nombre (puede estar en la papelera).")
            return
        except VaultConflictError as exc:
            self.conflict = exc
            self.reject()
            return
        except ValueError as exc:
            self.secret_error.setText(str(exc))
            self.secret_error.show()
            return
        self.accept()

    def _name_problem(self, text: str) -> None:
        self.name_error.setText(text)
        self.name_error.show()
        set_prop(self.name, "error", True)
        self.name.setFocus()

    def _clear_name_problem(self, *_):
        self.name_error.hide()
        set_prop(self.name, "error", False)

    def done(self, result):  # noqa: D401 - Qt API
        self._code_timer.stop()
        for field in (self.secret, self.seed):
            field.wipe()
        self.content.setPlainText("")
        self._original_secret = ""
        self._original_seed = ""
        super().done(result)


def _pix(name: str, color: str):
    from ..icons import pixmap
    return pixmap(name, color, 14, 2.0)

