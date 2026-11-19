"""Sharing (board 17): share one entry, the shared-items centre and your own keys.

Sharing seals the secret (optionally with the user name and URL) to one
X25519 public key. The sender reads the recipient's fingerprint aloud over a
second channel before sending, and the grant - with its expiry - is recorded
inside the encrypted vault and in the audit chain. Revoking or expiring stops
future delivery; it cannot take back an envelope that was already opened, so
the revoke confirmation offers to rotate the password.
"""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QPlainTextEdit,
    QVBoxLayout, QWidget,
)

from .....application.services.directory import IdentityDirectory
from .....application.services.sharing import ShareGrant, parse_share_payload, public_key_fingerprint
from .....domain.model.vault import EntryNameTaken
from ....outbound.sharing.sealed_box import generate_keypair, open_sealed, public_key_of
from ..components.kit import (
    AvDialog, Badge, Banner, Button, Card, EmptyState, Field, Segmented, clear_layout, icon_label, info_line, label,
    mono_font, vbox,
)
from ..fmt import fmt_date
from ..theme import PALETTE as P

EXPIRY = (
    ("1h", "En 1 hora", timedelta(hours=1)),
    ("24h", "En 24 horas", timedelta(hours=24)),
    ("7d", "En 7 días", timedelta(days=7)),
    ("30d", "En 30 días", timedelta(days=30)),
    ("never", "Sin caducidad", None),
)
KEY_ENTRY = "Mi clave para compartir (X25519)"


# ---- pure helpers -----------------------------------------------------------------
def fp_groups(fingerprint: str) -> list[str]:
    """'7f3a91c20d4eb58a' -> ['7F3A', '91C2', '0D4E', 'B58A']."""
    fp = (fingerprint or "").upper()
    return [fp[i:i + 4] for i in range(0, min(len(fp), 16), 4)]


def short_fp(fingerprint: str) -> str:
    groups = fp_groups(fingerprint)
    return f"{groups[0]} {groups[1]} …" if len(groups) >= 2 else (fingerprint or "—")


def first_name(name: str) -> str:
    parts = (name or "").split()
    return parts[0] if parts else "la otra persona"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def expiry_text(expires_at: str, now: datetime | None = None) -> tuple[str, str | None]:
    """(text, tone) for the «Caduca» column."""
    if not expires_at:
        return "Sin caducidad", None
    try:
        when = datetime.fromisoformat(expires_at)
        left = when - (now or _now())
    except (TypeError, ValueError):
        return "—", None
    seconds = left.total_seconds()
    if seconds <= 0:
        return "Caducada", "warning"
    if seconds < 3600:
        return f"en {max(1, int(seconds // 60))} min", "warning"
    if seconds < 24 * 3600:
        return f"en {int(seconds // 3600)} h", "warning"
    if seconds < 48 * 3600:
        return "mañana", "warning"
    return f"en {int(seconds // 86400)} días", None


def grant_state(grant: ShareGrant, now_iso: str) -> str:
    if not grant.active:
        return "revoked"
    if grant.expired(now_iso):
        return "expired"
    return "active"


def grant_rows(views) -> list[tuple[str, ShareGrant]]:
    """(entry name, grant) for every grant of every live entry, newest first."""
    rows = []
    for view in views:
        if getattr(view, "deleted", False):
            continue
        for raw in getattr(view, "sharing_grants", ()) or ():
            rows.append((view.name, ShareGrant.from_dict(raw)))
    rows.sort(key=lambda r: r[1].created_at or "", reverse=True)
    return rows


def _fp_tiles(fingerprint: str) -> QWidget:
    w = QWidget()
    w.setObjectName("transparent")
    grid = QGridLayout(w)
    grid.setContentsMargins(0, 0, 0, 0)
    grid.setHorizontalSpacing(6)
    for i, group in enumerate(fp_groups(fingerprint) or ["—"]):
        tile = QLabel(group)
        tile.setObjectName("fpTile")
        tile.setAlignment(Qt.AlignCenter)
        tile.setFont(mono_font(16, 500))
        tile.setFixedHeight(34)
        grid.addWidget(tile, 0, i)
    return w


def _copy(text: str) -> None:
    QApplication.clipboard().setText(text)


# ---- share one entry ----------------------------------------------------------------
class ShareDialog(AvDialog):
    """Compartir «entrada»: pick a key, check its fingerprint, seal."""

    def __init__(self, session, view, settings, parent=None):
        super().__init__(parent, f"Compartir «{view.name}»", avatar=view.name, width=540)
        self._session = session
        self._view = view
        self._settings = settings
        self.grant: dict | None = None
        self._people = [p for p in IdentityDirectory(settings.recipient_directory).list(include_inactive=False)
                        if p.public_key and p.fingerprint not in ("", "invalid")]
        self._paste_mode = not self._people
        self._build_form()
        self._cancel = self.add_button(Button("Cancelar", "secondary", on_click=self.reject))
        self._submit = self.add_button(Button("Cifrar y compartir", "primary", "lock", on_click=self._share))
        self._submit.setDefault(True)
        self._sync()

    # form
    def _build_form(self) -> None:
        self._combo = QComboBox()
        self._combo.setAccessibleName("Destinatario")
        for person in self._people:
            self._combo.addItem(person.label + (f"  ·  {person.email}" if person.email else ""), person)
        self._combo.currentIndexChanged.connect(self._sync)
        self._combo_hint = label("Directorio del equipo · clave X25519", "tertiary")
        self._paste = QWidget()
        self._paste.setObjectName("transparent")
        pcol = QVBoxLayout(self._paste)
        pcol.setContentsMargins(0, 0, 0, 0)
        pcol.setSpacing(8)
        self._who = Field(placeholder="Nombre de la persona")
        self._who.setAccessibleName("Nombre de la persona")
        self._key = Field(placeholder="Clave pública X25519 (base64, 44 caracteres)", mono=True)
        self._key.setAccessibleName("Clave pública")
        self._key_error = label("", "toneText", wrap=True, tone="danger")
        pcol.addWidget(self._who)
        pcol.addWidget(self._key)
        pcol.addWidget(self._key_error)
        self._who.textChanged.connect(self._sync)
        self._key.textChanged.connect(self._sync)
        self._mode_link = Button("", "link", on_click=self._toggle_mode)
        self._mode_link.setVisible(bool(self._people))
        row = QHBoxLayout()
        row.addWidget(self._mode_link)
        row.addStretch(1)
        self.add(vbox(label("Destinatario", "label"), self._combo, self._combo_hint, self._paste, row, spacing=6))

        self._fp_card = Card(name="cardSunken", margins=(16, 14, 16, 14), spacing=10)
        self._fp_card.add(label("Comprueba la huella antes de enviar", "bodyStrong"))
        self._fp_holder = QVBoxLayout()
        self._fp_card.add(self._fp_holder)
        self._fp_text = label("", "secondary", wrap=True)
        self._fp_card.add(self._fp_text)
        self._checked = QCheckBox()
        self._checked.toggled.connect(self._sync)
        self._fp_card.add(self._checked)
        self.add(self._fp_card)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(6)
        grid.addWidget(label("Caduca", "label"), 0, 0)
        grid.addWidget(label("Incluye", "label"), 0, 1)
        self._expiry = QComboBox()
        self._expiry.setAccessibleName("Caduca")
        for key, text, _delta in EXPIRY:
            self._expiry.addItem(text, key)
        self._expiry.setCurrentIndex(2)
        self._includes = QComboBox()
        self._includes.setAccessibleName("Incluye")
        if self._view.kind == "login" and self._view.username:
            self._includes.addItem("Usuario y contraseña", "login")
            self._includes.addItem("Solo la contraseña", "secret")
        else:
            self._includes.addItem("Solo el secreto", "secret")
        grid.addWidget(self._expiry, 1, 0)
        grid.addWidget(self._includes, 1, 1)
        self.add(grid)
        self._banner = Banner("info", text="", icon_name="info", compact=True)
        self.add(self._banner)

    def _toggle_mode(self) -> None:
        self._paste_mode = not self._paste_mode
        self._checked.setChecked(False)
        self._sync()
        (self._key if self._paste_mode else self._combo).setFocus()

    def _recipient(self) -> tuple[str, str]:
        """(label, public key) currently chosen; the key may be invalid."""
        if self._paste_mode:
            return self._who.text().strip(), self._key.text().strip()
        person = self._combo.currentData()
        return (person.label, person.public_key) if person else ("", "")

    def _sync(self, *_):
        paste = self._paste_mode
        self._combo.setVisible(not paste)
        self._combo_hint.setVisible(not paste)
        self._paste.setVisible(paste)
        self._mode_link.setText("Elegir del directorio" if paste else "O pega una clave pública")
        who, key = self._recipient()
        fingerprint = ""
        error = ""
        if key:
            try:
                fingerprint = public_key_fingerprint(key)
            except Exception:  # noqa: BLE001 - any decoding problem means "not a key"
                error = "No es una clave pública X25519 válida (44 caracteres en base64)."
        self._key_error.setText(error)
        self._key_error.setVisible(bool(error))
        clear_layout(self._fp_holder)
        if fingerprint:
            self._fp_holder.addWidget(_fp_tiles(fingerprint))
        first = first_name(who)
        self._fp_card.setVisible(bool(fingerprint))
        self._fp_text.setText(f"Pídele a {first} que te lea su huella por otro canal (en persona o por llamada). "
                              "Si no coincide, no envíes nada.")
        self._checked.setText(f"He comprobado la huella con {first}")
        self._banner.set_message("", f"Se genera un sobre cifrado solo para la clave de {first}. Puedes mandarlo por cualquier "
                         "canal: sin su clave privada no se abre.")
        ok = bool(fingerprint) and bool(who) and self._checked.isChecked()
        self._submit.setEnabled(ok)
        if not who and paste and key and fingerprint:
            self._submit.setToolTip("Escribe el nombre de la persona")
        elif fingerprint and not self._checked.isChecked():
            self._submit.setToolTip("Marca que has comprobado la huella")
        else:
            self._submit.setToolTip("")

    # actions
    def _share(self) -> None:
        if not self._submit.isEnabled():
            return
        who, key = self._recipient()
        delta = next(d for k, _t, d in EXPIRY if k == self._expiry.currentData())
        try:
            grant = self._session.share_public_key(
                self._view.name, who, key, actor=self._settings.enterprise_display_name or "local-admin",
                expires_in=delta, include_login=self._includes.currentData() == "login")
        except (ValueError, KeyError) as exc:
            self._key_error.setText(f"No se pudo cifrar el sobre: {exc}")
            self._key_error.setVisible(True)
            return
        self.grant = dict(grant)
        self._show_result(who)

    def _show_result(self, who: str) -> None:
        clear_layout(self.body)
        first = first_name(who)
        self.title_label.setText(f"Sobre listo para {first}")
        self.add(info_line("Cifrado con su clave pública. Solo su clave privada lo abre; la concesión y la huella "
                           "quedan en la auditoría.", "success", "check-circle"))
        blob = QPlainTextEdit(self.grant.get("sealed_blob", ""))
        blob.setObjectName("mono")
        blob.setReadOnly(True)
        blob.setFixedHeight(120)
        blob.setAccessibleName("Sobre cifrado")
        self.add(blob)
        row = QHBoxLayout()
        row.addWidget(Button("Copiar sobre", "secondary", "copy", on_click=lambda: self._copy_blob()))
        row.addWidget(Button("Guardar como…", "secondary", "download", on_click=self._save_blob))
        row.addStretch(1)
        self.add(row)
        self._copied = label("", "tertiary")
        self.add(self._copied)
        self._cancel.hide()
        self._submit.hide()
        done = self.add_button(Button("Listo", "primary", on_click=self.accept))
        done.setDefault(True)
        self.set_note("El sobre no contiene nada legible sin su clave privada.")
        self.adjustSize()

    def _copy_blob(self) -> None:
        _copy(self.grant.get("sealed_blob", ""))
        self._copied.setText("Sobre copiado al portapapeles.")

    def _save_blob(self) -> None:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in self._view.name).strip("-") or "sobre"
        path, _f = QFileDialog.getSaveFileName(self, "Guardar sobre", str(Path.home() / f"{safe}.sobre.txt"),
                                               "Texto (*.txt)")
        if not path:
            return
        try:
            Path(path).write_text(self.grant.get("sealed_blob", "") + "\n", encoding="utf-8")
        except OSError as exc:
            self._copied.setText(f"No se pudo guardar: {exc}")
            return
        self._copied.setText(f"Guardado en {path}")

    def reject(self) -> None:
        # Once the grant exists the share happened: report it as accepted.
        if self.grant is not None:
            self.accept()
            return
        super().reject()


# ---- shared-items centre ----------------------------------------------------------
COLS = (190, 230, 120, 120)


class SharedCenter(AvDialog):
    """Compartidos: every grant, filterable, revocable inline."""

    def __init__(self, session, settings, parent=None, on_share: Callable | None = None,
                 on_rotate: Callable[[str], None] | None = None):
        super().__init__(parent, "Compartidos", "", width="l")
        self._session = session
        self._settings = settings
        self._on_rotate = on_rotate
        self._rotate_after: str | None = None
        self._open_panel: QFrame | None = None
        self._filter = Segmented((("active", "Activos"), ("all", "Todos")), "active", expand=False)
        self._filter.changed.connect(lambda _v: self._render())
        self.header_right.addWidget(self._filter)
        self.body.setContentsMargins(0, 0, 0, 12)
        self.body.setSpacing(0)
        self.set_note("Cada concesión y revocación queda en la cadena de auditoría con la huella del destinatario.")
        self.add_button(Button("Mis claves…", "secondary", "key", on_click=self._keys))
        close = self.add_button(Button("Cerrar", "primary", on_click=self.accept))
        close.setDefault(True)
        self._render()

    def _keys(self) -> None:
        KeysDialog(self._session, self._settings, self).exec()

    def _render(self) -> None:
        clear_layout(self.body)
        self._open_panel = None
        now_iso = _now().isoformat()
        rows = grant_rows(self._session.entries())
        states = [grant_state(g, now_iso) for _n, g in rows]
        active = states.count("active")
        revoked = states.count("revoked")
        expired = states.count("expired")
        parts = [f"{active} activo{'s' if active != 1 else ''}", f"{revoked} revocado{'s' if revoked != 1 else ''}"]
        if expired:
            parts.append(f"{expired} caducado{'s' if expired != 1 else ''}")
        self.subtitle_label.setText(" · ".join(parts))
        self.subtitle_label.setVisible(True)
        show_all = self._filter.value() == "all"
        visible = [(n, g, s) for (n, g), s in zip(rows, states) if show_all or s == "active"]
        if not visible:
            text = ("Abre una entrada y pulsa «Compartir». Cada sobre se cifra para una sola clave pública."
                    if not rows else "No hay concesiones activas. Cambia a «Todos» para ver el historial.")
            self.body.addWidget(EmptyState("share", "Nada compartido" if not rows else "Sin concesiones activas",
                                           text))
            return
        self.body.addWidget(self._head())
        for name, grant, state in visible:
            self.body.addWidget(self._row(name, grant, state))
        self.body.addStretch(1)

    def _head(self) -> QFrame:
        head = QFrame()
        head.setObjectName("tableHead")
        row = QHBoxLayout(head)
        row.setContentsMargins(24, 10, 24, 10)
        row.setSpacing(12)
        for title, width in zip(("Entrada", "Destinatario y huella", "Caduca", "Estado"), COLS):
            lbl = label(title.upper(), "overline")
            lbl.setFixedWidth(width)
            row.addWidget(lbl)
        row.addStretch(1)
        return head

    def _row(self, name: str, grant: ShareGrant, state: str) -> QWidget:
        holder = QWidget()
        holder.setObjectName("transparent")
        col = QVBoxLayout(holder)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        frame = QFrame()
        frame.setObjectName("tableRow")
        row = QHBoxLayout(frame)
        row.setContentsMargins(24, 10, 24, 10)
        row.setSpacing(12)
        muted = state != "active"
        entry = label(name, "tertiary" if muted else "bodyStrong")
        entry.setFixedWidth(COLS[0])
        row.addWidget(entry)
        who = QVBoxLayout()
        who.setSpacing(1)
        who.addWidget(label(grant.recipient, "body"))
        fp = label(short_fp(grant.public_key_fingerprint), "monoSm")
        fp.setToolTip(grant.public_key_fingerprint.upper())
        who.addWidget(fp)
        who_w = QWidget()
        who_w.setObjectName("transparent")
        who_w.setLayout(who)
        who_w.setFixedWidth(COLS[1])
        row.addWidget(who_w)
        if state == "revoked":
            when, tone = "—", None
        else:
            when, tone = expiry_text(grant.expires_at)
        when_w = QWidget()
        when_w.setObjectName("transparent")
        wl = QHBoxLayout(when_w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(5)
        if tone == "warning" and state == "active":
            wl.addWidget(icon_label("clock", P.WARNING, 14))
        wl.addWidget(label(when, "toneText", tone=tone) if tone else label(when, "body"))
        wl.addStretch(1)
        when_w.setFixedWidth(COLS[2])
        row.addWidget(when_w)
        status = {"active": ("Activo", "success", "check"), "revoked": ("Revocado", "neutral", "ban"),
                  "expired": ("Caducado", "warning", "clock")}[state]
        status_w = QWidget()
        status_w.setObjectName("transparent")
        sl = QHBoxLayout(status_w)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(Badge(status[0], status[1], status[2]))
        sl.addStretch(1)
        status_w.setFixedWidth(COLS[3])
        row.addWidget(status_w)
        row.addStretch(1)
        if state == "active":
            revoke = Button("Revocar", "danger", size="sm")
            revoke.clicked.connect(lambda _c=False, h=holder, n=name, g=grant: self._ask_revoke(h, n, g))
            row.addWidget(revoke)
        else:
            stamp = grant.revoked_at or grant.expires_at
            row.addWidget(label(fmt_date(stamp) if stamp else "", "tertiary"))
        col.addWidget(frame)
        return holder

    def _ask_revoke(self, holder: QWidget, name: str, grant: ShareGrant) -> None:
        if self._open_panel is not None:
            self._open_panel.deleteLater()
            self._open_panel = None
        panel = QFrame()
        panel.setObjectName("revokePanel")
        outer = QHBoxLayout(panel)
        outer.setContentsMargins(16, 14, 16, 14)
        outer.setSpacing(12)
        outer.addWidget(icon_label("alert", P.DANGER, 18), 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(8)
        first = first_name(grant.recipient)
        col.addWidget(label(f"¿Revocar el acceso de {first} a «{name}»?", "bodyStrong", wrap=True))
        col.addWidget(label("Su permiso desaparece de la bóveda y queda en la auditoría. Si ya abrió el sobre, pudo "
                            "copiar la contraseña: tras revocar, rótala.", "secondary", wrap=True))
        rotate = QCheckBox(f"Abrir «{name}» para rotarla al terminar")
        rotate.setChecked(self._on_rotate is not None)
        rotate.setVisible(self._on_rotate is not None)
        col.addWidget(rotate)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = Button("Cancelar", "secondary", on_click=lambda: self._close_panel(panel))
        go = Button("Revocar acceso", "dangerSolid",
                    on_click=lambda: self._revoke(name, grant, rotate.isChecked()))
        buttons.addWidget(cancel)
        buttons.addWidget(go)
        col.addLayout(buttons)
        outer.addLayout(col, 1)
        wrap = QWidget()
        wrap.setObjectName("transparent")
        wl = QVBoxLayout(wrap)
        wl.setContentsMargins(24, 2, 24, 10)
        wl.addWidget(panel)
        holder.layout().addWidget(wrap)
        self._open_panel = wrap
        cancel.setFocus()

    def _close_panel(self, _panel) -> None:
        if self._open_panel is not None:
            self._open_panel.deleteLater()
            self._open_panel = None

    def _revoke(self, name: str, grant: ShareGrant, rotate_after: bool) -> None:
        try:
            self._session.revoke_share(name, grant.grant_id or grant.public_key_fingerprint,
                                       reason="revocado desde Compartidos",
                                       actor=self._settings.enterprise_display_name or "local-admin")
        except (ValueError, KeyError) as exc:
            self.set_note(f"No se pudo revocar: {exc}")
            return
        if rotate_after and self._on_rotate is not None:
            self._rotate_after = name
            self.accept()
            return
        self._render()

    def done(self, result):  # noqa: D401 - Qt API
        target, self._rotate_after = self._rotate_after, None
        super().done(result)
        if target and self._on_rotate is not None:
            self._on_rotate(target)


# ---- own keys -------------------------------------------------------------------------
class KeysDialog(AvDialog):
    """Your X25519 key pair (private half kept as an entry) and opening envelopes."""

    def __init__(self, session, settings, parent=None):
        super().__init__(parent, "Mis claves para compartir",
                         "Con tu clave pública te mandan sobres que solo tú puedes abrir.", icon_name="key")
        self._session = session
        self._settings = settings
        self._opened: dict | None = None
        close = self.add_button(Button("Cerrar", "primary", on_click=self.accept))
        close.setDefault(True)
        self._render()

    def _has_key(self) -> bool:
        return any(v.name == KEY_ENTRY and not v.deleted for v in self._session.entries())

    def _render(self) -> None:
        clear_layout(self.body)
        mine = Card("Tu clave pública", "key", name="cardSunken", margins=(16, 14, 16, 16), spacing=10)
        if self._has_key():
            try:
                public = public_key_of(self._session.reveal(KEY_ENTRY))
            except ValueError:
                public = ""
            if public:
                field = Field(public, mono=True)
                field.setReadOnly(True)
                field.setAccessibleName("Tu clave pública")
                mine.add(field)
                mine.add(label("Huella (léela en voz alta a quien te comparta algo):", "secondary"))
                mine.add(_fp_tiles(public_key_fingerprint(public)))
                row = QHBoxLayout()
                row.addWidget(Button("Copiar clave pública", "secondary", "copy",
                                     on_click=lambda: (_copy(public), self.set_note("Clave pública copiada."))))
                row.addStretch(1)
                mine.add(row)
                mine.add(info_line(f"La clave privada vive cifrada en la entrada «{KEY_ENTRY}». No la compartas.",
                                   "info", "info"))
            else:
                mine.add(info_line(f"La entrada «{KEY_ENTRY}» no contiene una clave X25519 válida.", "danger",
                                   "alert"))
        else:
            mine.add(label("Aún no tienes un par de claves. Se genera aquí y la parte privada se guarda cifrada "
                           "como una entrada más de la bóveda.", "secondary", wrap=True))
            row = QHBoxLayout()
            row.addWidget(Button("Generar mi par de claves", "primary", "key", on_click=self._generate))
            row.addStretch(1)
            mine.add(row)
        self.add(mine)

        box = Card("Abrir un sobre recibido", "inbox", name="cardSunken", margins=(16, 14, 16, 16), spacing=10)
        if not self._has_key():
            box.add(label("Primero genera tu par de claves y pásale la pública a quien te vaya a compartir algo.",
                          "tertiary", wrap=True))
            self.add(box)
            return
        self._blob = QPlainTextEdit()
        self._blob.setObjectName("mono")
        self._blob.setPlaceholderText("Pega aquí el sobre (texto en base64)")
        self._blob.setFixedHeight(96)
        self._blob.setAccessibleName("Sobre recibido")
        box.add(self._blob)
        self._open_error = label("", "toneText", wrap=True, tone="danger")
        self._open_error.hide()
        box.add(self._open_error)
        row = QHBoxLayout()
        row.addWidget(Button("Abrir sobre", "secondary", "unlock", on_click=self._open))
        row.addStretch(1)
        box.add(row)
        self._save_box = QWidget()
        self._save_box.setObjectName("transparent")
        self._save_box.hide()
        sc = QVBoxLayout(self._save_box)
        sc.setContentsMargins(0, 6, 0, 0)
        sc.setSpacing(8)
        sc.addWidget(info_line("Sobre abierto. El secreto sigue oculto; se guarda cifrado en esta bóveda.",
                               "success", "check-circle"))
        self._name = Field(placeholder="Nombre de la entrada")
        self._name.setAccessibleName("Nombre de la entrada")
        self._user = Field(placeholder="Usuario (opcional)")
        self._user.setAccessibleName("Usuario")
        sc.addWidget(self._name)
        sc.addWidget(self._user)
        save_row = QHBoxLayout()
        save_row.addWidget(Button("Guardar en la bóveda", "primary", "check", on_click=self._save))
        save_row.addStretch(1)
        sc.addLayout(save_row)
        box.add(self._save_box)
        self.add(box)

    def _generate(self) -> None:
        private, _public = generate_keypair()
        try:
            self._session.add(KEY_ENTRY, "X25519", private, notes="Clave privada para abrir sobres compartidos. "
                              "No la compartas: quien la tenga puede abrir lo que te envíen.",
                              tags=("aegisvault", "compartir"), kind="api_key")
        except EntryNameTaken:
            pass
        del private
        self._render()

    def _open(self) -> None:
        blob = "".join(self._blob.toPlainText().split())
        if not blob:
            return
        try:
            opened = parse_share_payload(open_sealed(blob, self._session.reveal(KEY_ENTRY)))
        except Exception:  # noqa: BLE001 - wrong key, damaged or foreign envelope
            self._open_error.setText("Este sobre no se abre con tu clave: puede ser para otra persona o estar dañado.")
            self._open_error.show()
            self._save_box.hide()
            return
        self._open_error.hide()
        self._opened = opened
        self._name.setText(opened["name"] or "Recibida")
        self._user.setText(opened["username"])
        self._save_box.show()
        self._name.setFocus()
        self._name.selectAll()

    def _save(self) -> None:
        if not self._opened:
            return
        name = self._name.text().strip()
        if not name:
            self._name.setFocus()
            return
        try:
            self._session.add(name, self._user.text().strip(), self._opened["secret"], url=self._opened["url"],
                              category="Recibidas", tags=("recibida",))
        except EntryNameTaken:
            self._open_error.setText(f"Ya hay una entrada «{name}». Elige otro nombre.")
            self._open_error.show()
            return
        self._opened = None
        self._blob.clear()
        self._save_box.hide()
        self.set_note(f"«{name}» guardada en la categoría Recibidas.")

    def done(self, result):  # noqa: D401 - Qt API
        self._opened = None
        super().done(result)
