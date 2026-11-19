"""Settings (board 19). Every change is saved at once to settings.json, outside
the vault and without secrets; the main window applies it immediately.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import fields, replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from .....application.services.settings import VaultSettings
from ..branding import PRODUCT_NAME
from ..components.kit import (
    Badge, Button, Card, Field, Kbd, LockPill, Segmented, Toggle, clear_layout, confirm, elide, icon_label, label,
    mono_font, set_prop,
)
from ..design.tokens import SIDEBAR_W, TOPBAR_H
from ..fmt import fmt_date, fmt_datetime, plural
from ..icons import pixmap
from ..theme import PALETTE as P

SECTIONS = (("general", "General"), ("master", "Contraseña maestra"), ("shamir", "Recuperación Shamir"),
            ("keys", "Claves para compartir"), ("policies", "Zero Trust y políticas"),
            ("identity", "Identidad y directorio"), ("appearance", "Apariencia"),
            ("shortcuts", "Atajos de teclado"), ("about", "Acerca de"))

AUTO_LOCK = ((60, "1 min"), (300, "5 min"), (900, "15 min"), (1800, "30 min"), (0, "Nunca"))
REVEAL = ((5, "5 s"), (10, "10 s"), (15, "15 s"), (30, "30 s"), (60, "60 s"), (0, "Nunca"))
CLIPBOARD = ((10, "10 s"), (15, "15 s"), (20, "20 s"), (30, "30 s"), (45, "45 s"), (60, "60 s"), (90, "90 s"))
KEEP = ((5, "Las 5 últimas"), (10, "Las 10 últimas"), (20, "Las 20 últimas"), (50, "Las 50 últimas"))
TRASH = ((7, "Tras 7 días"), (30, "Tras 30 días"), (90, "Tras 90 días"), (0, "Nunca"))
OLD = ((180, "6 meses"), (365, "12 meses"), (540, "18 meses"), (730, "24 meses"))
ROLES = {"owner": "Propietario", "admin": "Admin", "auditor": "Auditor", "member": "Miembro",
         "readonly": "Solo lectura"}
SHORTCUTS = (("Ctrl K", "Paleta de comandos y búsqueda"), ("Ctrl F", "Buscar en la lista"),
             ("Ctrl N", "Nueva entrada"), ("Ctrl E", "Editar la entrada"), ("Ctrl C", "Copiar la contraseña (en la lista)"),
             ("Ctrl B", "Copiar el usuario"), ("Ctrl T", "Copiar el código 2FA"), ("Ctrl G", "Generar y copiar una contraseña"),
             ("Ctrl L", "Bloquear ahora"), ("Ctrl ,", "Ajustes"), ("Supr", "Mover a la papelera"),
             ("Ctrl S", "Guardar en el editor"), ("Esc", "Cerrar el diálogo o volver"))

# what "Restablecer" keeps: identity, directory and rules are data, not preferences
_KEEP_ON_RESET = {"enterprise_role", "enterprise_user_id", "enterprise_display_name", "local_device_id",
                  "trusted_device_ids", "policy_rules", "recipient_directory", "access_requests", "last_vault_path",
                  "backup_dir"}


def _select(options, current, on_change: Callable, width: int = 130) -> QComboBox:
    box = QComboBox()
    values = [v for v, _t in options]
    for value, text in options:
        box.addItem(text, value)
    if current not in values:
        box.addItem(f"{current}", current)
    box.setCurrentIndex(box.findData(current))
    box.setFixedWidth(width)
    box.currentIndexChanged.connect(lambda _i: on_change(box.currentData()))
    return box


def _row(title: str, subtitle: str = "", control: QWidget | None = None) -> QWidget:
    w = QWidget()
    w.setObjectName("transparent")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 10, 0, 10)
    row.setSpacing(16)
    text = QVBoxLayout()
    text.setSpacing(2)
    text.addWidget(label(title, "body", wrap=True))
    if subtitle:
        text.addWidget(label(subtitle, "secondary", wrap=True))
    row.addLayout(text, 1)
    if control is not None:
        row.addWidget(control, 0, Qt.AlignVCenter)
    return w


def _hair() -> QFrame:
    line = QFrame()
    line.setObjectName("hairline")
    line.setFixedHeight(1)
    return line


def _card(title: str, icon_name: str, right: QWidget | None = None) -> Card:
    return Card(title, icon_name, right=right, name="cardSunken", margins=(20, 16, 20, 14), spacing=4,
                divider=True)


class SettingsPage(QWidget):
    def __init__(self, session, settings: VaultSettings, store, callbacks: dict, *, actions: dict,
                 on_saved: Callable, section: str = "general"):
        super().__init__()
        self.setObjectName("page")
        self._session = session
        self._settings = settings
        self._store = store
        self._actions = actions
        self._on_saved = on_saved
        self._section = section
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("pageHeader")
        header.setFixedHeight(TOPBAR_H)
        hr = QHBoxLayout(header)
        hr.setContentsMargins(18, 0, 12, 0)
        hr.setSpacing(10)
        brand = QHBoxLayout()
        brand.setSpacing(8)
        logo = label("")
        logo.setPixmap(pixmap("logo", P.TEXT_PRIMARY, 20))
        brand.addWidget(logo)
        brand.addWidget(label(PRODUCT_NAME, "bodyStrong"))
        brand.addStretch(1)
        brand.setContentsMargins(0, 0, 0, 0)
        brand_w = QWidget()
        brand_w.setObjectName("transparent")
        brand_w.setLayout(brand)
        brand_w.setFixedWidth(SIDEBAR_W - 18)
        hr.addWidget(brand_w)
        hr.addWidget(Button("Volver a la bóveda", "nav", "chevron-left", on_click=callbacks["back"],
                            tooltip="Volver a la bóveda (Esc)"))
        hr.addStretch(1)
        self.lock_pill = LockPill()
        hr.addWidget(self.lock_pill)
        hr.addWidget(Button("Bloquear ahora", "secondary", "lock", on_click=callbacks["lock"]))
        root.addWidget(header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        nav = QFrame()
        nav.setObjectName("brandPanel")
        nav.setFixedWidth(SIDEBAR_W)
        nl = QVBoxLayout(nav)
        nl.setContentsMargins(8, 18, 8, 12)
        nl.setSpacing(2)
        over = label("AJUSTES", "overline")
        over.setContentsMargins(10, 0, 0, 8)
        nl.addWidget(over)
        self._nav: dict[str, QPushButton] = {}
        for key, text in SECTIONS:
            btn = QPushButton(text)
            btn.setObjectName("settingsNavItem")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self.show_section(k))
            self._nav[key] = btn
            nl.addWidget(btn)
        nl.addStretch(1)
        nl.addWidget(self._vault_card())
        body.addWidget(nav)

        area = QScrollArea()
        area.setObjectName("plain")
        area.setWidgetResizable(True)
        area.setFrameShape(QFrame.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner.setObjectName("page")
        self._col = QVBoxLayout(inner)
        self._col.setContentsMargins(32, 26, 32, 32)
        self._col.setSpacing(18)
        head = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        self._title = label("", "titleLg")
        titles.addWidget(self._title)
        saved = QHBoxLayout()
        saved.setSpacing(6)
        self._saved_icon = icon_label("check", P.SUCCESS, 14)
        saved.addWidget(self._saved_icon)
        self._saved = label("Cada cambio se guarda al momento en settings.json, fuera de la bóveda y sin secretos.",
                            "secondary")
        saved.addWidget(self._saved)
        saved.addStretch(1)
        titles.addLayout(saved)
        head.addLayout(titles, 1)
        self._reset_btn = Button("Restablecer valores predeterminados", "ghost", on_click=self._reset)
        head.addWidget(self._reset_btn, 0, Qt.AlignTop)
        self._col.addLayout(head)
        self._body = QVBoxLayout()
        self._body.setSpacing(16)
        self._col.addLayout(self._body)
        self._col.addStretch(1)
        area.setWidget(inner)
        body.addWidget(area, 1)
        root.addLayout(body, 1)
        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=callbacks["back"])
        self._flash = QTimer(self)
        self._flash.setSingleShot(True)
        self._flash.timeout.connect(lambda: self._saved.setText(
            "Cada cambio se guarda al momento en settings.json, fuera de la bóveda y sin secretos."))
        self.show_section(section)

    # ---- plumbing ---------------------------------------------------------------
    def _vault_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("cardSunken")
        col = QVBoxLayout(card)
        col.setContentsMargins(12, 10, 12, 12)
        col.setSpacing(4)
        col.addWidget(label("Archivo de la bóveda", "tertiary"))
        location = self._session.location or ""
        path = label("", "monoSm")
        path.setText(elide(_home_relative(location), mono_font(11), SIDEBAR_W - 60) if location else "—")
        path.setToolTip(location)
        col.addWidget(path)
        col.addSpacing(6)
        col.addWidget(label("Huella", "tertiary"))
        try:
            _verdict, fingerprint, _head = self._session.verify_integrity()
        except Exception:
            fingerprint = ""
        fp = fingerprint.upper()
        col.addWidget(label(f"{fp[0:4]} {fp[4:8]} · {fp[8:12]} {fp[12:16]}" if fp else "—", "monoSm"))
        return card

    def _set(self, **changes) -> None:
        self._settings = replace(self._settings, **changes).normalized()
        self._store.save(self._settings)
        self._on_saved(self._settings)
        self._saved.setText("Guardado en settings.json.")
        self._flash.start(2200)

    def show_section(self, key: str) -> None:
        self._section = key
        for k, btn in self._nav.items():
            set_prop(btn, "active", k == key)
        self._title.setText(dict(SECTIONS)[key])
        self._reset_btn.setVisible(key == "general")
        clear_layout(self._body)
        getattr(self, f"_section_{key}")()

    def _reset(self) -> None:
        if not confirm(self, "¿Restablecer los ajustes?", "Vuelven los valores predeterminados de bloqueo, "
                       "portapapeles, privacidad y copias. Tu identidad, el directorio y las reglas no cambian.",
                       "Restablecer", icon_name="sync", tone="warning"):
            return
        defaults = VaultSettings()
        keep = {f.name: getattr(self._settings, f.name) for f in fields(VaultSettings) if f.name in _KEEP_ON_RESET}
        self._settings = replace(defaults, **keep).normalized()
        self._store.save(self._settings)
        self._on_saved(self._settings)
        self.show_section("general")

    def _two_columns(self):
        row = QHBoxLayout()
        row.setSpacing(20)
        left, right = QVBoxLayout(), QVBoxLayout()
        left.setSpacing(16)
        right.setSpacing(16)
        row.addLayout(left, 1)
        row.addLayout(right, 1)
        self._body.addLayout(row)
        return left, right

    # ---- General ------------------------------------------------------------------
    def _section_general(self) -> None:
        s = self._settings
        left, right = self._two_columns()

        lock = _card("Bloqueo automático", "lock")
        lock.add(_row("Bloquear tras un tiempo sin actividad",
                      "Al bloquear, la clave sale de la memoria y hay que volver a escribir la contraseña."))
        options = list(AUTO_LOCK)
        if s.auto_lock_seconds not in dict(options):
            options.insert(-1, (s.auto_lock_seconds, f"{max(1, s.auto_lock_seconds // 60)} min"))
        seg = Segmented([(str(v), t) for v, t in options], str(s.auto_lock_seconds), accent=True, expand=False,
                        check_mark=True)
        seg.changed.connect(lambda k: self._set(auto_lock_seconds=int(k)))
        seg_row = QHBoxLayout()
        seg_row.addWidget(seg)
        seg_row.addStretch(1)
        lock.add(seg_row)
        lock.add(label("«Nunca» deja un aviso permanente en la barra superior.", "tertiary", wrap=True))
        lock.add(_hair())
        lock.add(_row("Bloquear también al suspender el equipo o bloquear Windows", "",
                      self._toggle(s.lock_on_screen_lock, "lock_on_screen_lock")))
        lock.add(_hair())
        lock.add(_row("Bloquear al minimizar la ventana", "",
                      self._toggle(s.lock_on_minimize, "lock_on_minimize")))
        lock.add(_hair())
        lock.add(_row("Volver a ocultar un secreto revelado", "La cuenta atrás se ve junto al secreto.",
                      _select(REVEAL, s.reveal_hide_seconds, lambda v: self._set(reveal_hide_seconds=v), 112)))
        left.addWidget(lock)

        clip = _card("Portapapeles", "clipboard")
        clip.add(_row("Borrar el portapapeles tras copiar",
                      "Predeterminado: 15 s. Si copias otra cosa antes, no se toca.",
                      _select(CLIPBOARD, s.clipboard_clear_seconds, lambda v: self._set(clipboard_clear_seconds=v), 112)))
        clip.add(_hair())
        clip.add(_row("Pedir revelar antes de copiar", "Evita pegar en otro sitio un secreto que no has mirado.",
                      self._toggle(s.require_reveal_before_copy, "require_reveal_before_copy")))
        clip.add(_hair())
        clip.add(_row("Excluir del historial de Windows (Win + V)",
                      "Tampoco se sincroniza con el portapapeles en la nube.",
                      self._toggle(s.exclude_clipboard_history, "exclude_clipboard_history")))
        left.addWidget(clip)

        privacy = _card("Privacidad y red", "eye")
        privacy.add(_row("Comprobar filtraciones con Have I Been Pwned",
                         "Solo salen los 5 primeros caracteres del hash SHA-1, nunca la contraseña.",
                         self._toggle(s.breach_check_online, "breach_check_online")))
        privacy.add(_hair())
        privacy.add(_row("Iconos de los sitios",
                         "No se descargan: pedirlos diría a un tercero qué sitios guardas. Se ve la inicial.",
                         Badge("Sin red", "neutral", "wifi-off")))
        privacy.add(_hair())
        privacy.add(_row("Registrar copias y revelados en la auditoría",
                         "Solo el nombre de la entrada y la acción, nunca el secreto.",
                         self._toggle(s.log_secret_access, "log_secret_access")))
        privacy.add(_hair())
        privacy.add(_row("Vaciar la papelera automáticamente", "",
                         _select(TRASH, s.trash_retention_days, lambda v: self._set(trash_retention_days=v), 140)))
        left.addWidget(privacy)
        left.addStretch(1)

        right.addWidget(self._crypto_card())
        right.addWidget(self._backup_card())
        right.addStretch(1)

    def _toggle(self, value: bool, field: str) -> Toggle:
        toggle = Toggle(value)
        toggle.toggled.connect(lambda on: self._set(**{field: on}))
        return toggle

    def _crypto_card(self) -> Card:
        summary = self._session.crypto_summary()
        card = _card("Backend criptográfico", "chip", label("Se detecta al arrancar", "tertiary"))
        try:
            from .....container import crypto_profile
            profile = crypto_profile()
        except Exception:
            profile = {"backend": "Python", "kdf": "Argon2id", "params": "", "cipher": "AES-256-GCM"}
        argon = summary.get("algorithm") == "argon2id"
        options = (
            (f"{profile['backend']} · Argon2id", f"{summary['kdf'] if argon else profile['params']} · "
             f"{summary.get('cipher') or profile['cipher']}", argon, "Activo" if argon else "Disponible"),
            ("Python · scrypt", f"{_scrypt_params()} · AES-256-GCM" if argon else summary["kdf"],
             not argon, "Activo" if not argon else "Respaldo"),
        )
        for title, detail, active, badge in options:
            box = QFrame()
            box.setObjectName("cardSelected" if active else "card")
            bl = QHBoxLayout(box)
            bl.setContentsMargins(14, 12, 14, 12)
            bl.setSpacing(12)
            dot = label("")
            dot.setPixmap(pixmap("check-circle" if active else "circle",
                                 P.ACCENT if active else P.TEXT_TERTIARY, 18))
            bl.addWidget(dot)
            text = QVBoxLayout()
            text.setSpacing(2)
            text.addWidget(label(title, "bodyStrong"))
            text.addWidget(label(detail, "monoSm", wrap=True))
            bl.addLayout(text, 1)
            bl.addWidget(Badge(badge, "success" if active else "neutral", "check" if active else None))
            card.add(box)
        upgraded = summary.get("upgraded_from")
        note = ("No se elige a mano: la cabecera del archivo guarda algoritmo, sal y coste. Una bóveda con una "
                "derivación más débil se refuerza sola al desbloquearla.")
        if upgraded:
            note = f"Al abrirla se reforzó la derivación (antes: {upgraded}). " + note
        line = QHBoxLayout()
        line.setSpacing(8)
        line.addWidget(icon_label("info", P.INFO, 14), 0, Qt.AlignTop)
        line.addWidget(label(note, "secondary", wrap=True), 1)
        card.add(line)
        return card

    def _backup_dir(self) -> str:
        if self._settings.backup_dir:
            return self._settings.backup_dir
        loc = Path(self._session.location or "boveda.avault")
        return str(loc.parent / f"{loc.stem}-copias")

    def _backup_card(self) -> Card:
        s = self._settings
        card = _card("Copias de seguridad y sincronización", "sync")
        card.add(label("COPIAS LOCALES", "overline"))
        path_row = QHBoxLayout()
        path_row.setSpacing(8)
        self._backup_field = Field(self._backup_dir(), mono=True)
        self._backup_field.setReadOnly(True)
        path_row.addWidget(self._backup_field, 1)
        path_row.addWidget(Button("Cambiar…", "secondary", on_click=self._choose_backup_dir))
        card.add(path_row)
        card.add(_row("Conservar", "", _select(KEEP, s.keep_backups, lambda v: self._set(keep_backups=v), 150)))
        card.add(info_row("Siempre se hace una copia antes de rotar la contraseña maestra, restaurar o importar.",
                          "shield-check", P.SUCCESS))
        last = QHBoxLayout()
        last.setSpacing(8)
        try:
            backups = self._session.backups()
        except Exception:
            backups = []
        if backups:
            b = backups[0]
            size = _size_of(b["path"])
            state = "se abre bien" if b.get("readable") else "no se pudo leer"
            last.addWidget(icon_label("check" if b.get("readable") else "alert",
                                      P.SUCCESS if b.get("readable") else P.DANGER, 14))
            last.addWidget(label(f"Última copia: {fmt_datetime(b['modified'], seconds=False)} · {size} · {state} · "
                                 f"{plural(len(backups), 'copia', 'copias')}", "secondary", wrap=True), 1)
        else:
            last.addWidget(icon_label("info", P.TEXT_TERTIARY, 14))
            last.addWidget(label("Todavía no hay copias.", "secondary"), 1)
        last.addWidget(Button("Copiar ahora", "secondary", on_click=self._snapshot_now))
        card.add(last)
        card.add(_hair())
        card.add(label("SINCRONIZAR", "overline"))
        card.add(label("Exporta un paquete cifrado (sin secretos en claro) y cárgalo en otro equipo. Solo viaja el "
                       "archivo cifrado y un manifiesto con huella, cabeza de la auditoría y número de entradas.",
                       "secondary", wrap=True))
        sync_row = QHBoxLayout()
        sync_row.addStretch(1)
        sync_row.addWidget(Button("Sincronizar y copias…", "secondary", "sync", on_click=self._actions["sync"]))
        card.add(sync_row)
        return card

    def _choose_backup_dir(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Carpeta para las copias", self._backup_dir())
        if folder:
            self._set(backup_dir=folder)
            self._backup_field.setText(folder)

    def _snapshot_now(self) -> None:
        self._actions["snapshot"]()
        self.show_section("general")

    # ---- Contraseña maestra -------------------------------------------------------
    def _section_master(self) -> None:
        summary = self._session.crypto_summary()
        blocks = self._session.audit_log()
        last_rotate = next((b for b in reversed(blocks) if b.action in ("rotate", "recover")), None)
        created = blocks[0].timestamp if blocks else ""
        card = _card("Contraseña maestra", "key")
        card.add(_row("Derivación de la clave", "", label(summary["kdf"], "monoSm")))
        card.add(_hair())
        card.add(_row("Cifrado", "", label(summary.get("cipher") or "AES-256-GCM", "monoSm")))
        card.add(_hair())
        when = (f"Cambiada el {fmt_date(last_rotate.timestamp)}" if last_rotate
                else f"Sin cambios desde que se creó la bóveda ({fmt_date(created)})" if created else "—")
        card.add(_row("Última rotación", when))
        card.add(_hair())
        rot = QHBoxLayout()
        rot.addWidget(label("Rotar cambia cómo se abre el archivo, no las contraseñas guardadas. Antes se hace "
                            "una copia y se pide la contraseña actual.", "secondary", wrap=True), 1)
        rot.addWidget(Button("Cambiar la contraseña maestra…", "primary", on_click=self._actions["rotate"]))
        card.add(rot)
        self._body.addWidget(card)

        passkey = _card("Desbloquear con passkey", "fingerprint", Badge("Próximamente", "dashed"))
        passkey.add(label("Windows Hello en lugar de escribir la contraseña. La contraseña maestra seguirá haciendo "
                          "falta para rotar y recuperar.", "secondary", wrap=True))
        more = QHBoxLayout()
        more.addStretch(1)
        more.addWidget(Button("Más información", "ghost", on_click=self._actions["passkey"]))
        passkey.add(more)
        self._body.addWidget(passkey)

    # ---- Shamir ---------------------------------------------------------------------
    def _section_shamir(self) -> None:
        policy = self._session.recovery_policy
        right = Badge(f"Activa · {policy[0]} de {policy[1]}", "success", "check") if policy else \
            Badge("Sin fragmentos", "warning", "warning")
        card = _card("Recuperación con fragmentos", "shamir", right)
        if policy:
            k, n = policy
            text = (f"Si olvidas la contraseña maestra, {k} de los {n} fragmentos bastan para abrir la bóveda y "
                    "poner una nueva. Volver a repartir anula los fragmentos anteriores.")
            action = "Volver a repartir…"
        else:
            text = ("Reparte una clave de recuperación en fragmentos (por ejemplo, 3 de 5) y guárdalos por "
                    "separado. Ninguno sirve solo; juntos abren la bóveda si olvidas la contraseña.")
            action = "Crear fragmentos…"
        card.add(label(text, "secondary", wrap=True))
        row = QHBoxLayout()
        row.addWidget(label("Para recuperar, usa «Recuperar con fragmentos» en la pantalla de desbloqueo.",
                            "tertiary", wrap=True), 1)
        row.addWidget(Button(action, "primary", on_click=self._actions["shamir"]))
        card.add(row)
        self._body.addWidget(card)

    # ---- Claves para compartir -----------------------------------------------------
    def _section_keys(self) -> None:
        from .....application.services.directory import IdentityDirectory
        card = _card("Compartir con clave pública", "user-share")
        card.add(label("Compartir cifra el secreto con la clave pública X25519 de la otra persona: solo su clave "
                       "privada abre el sobre. Tú guardas el registro y puedes revocarlo.", "secondary", wrap=True))
        people = [p for p in IdentityDirectory(self._settings.recipient_directory).list() if p.public_key]
        card.add(_hair())
        if people:
            for p in people[:8]:
                fp = p.fingerprint
                card.add(_row(p.label + (f" · {p.email}" if p.email else ""), "",
                              label(fp[:19] if fp else "—", "monoSm")))
        else:
            card.add(label("Aún no hay destinatarios con clave en el directorio.", "tertiary"))
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(Button("Mis claves…", "secondary", "key", on_click=self._actions["share_keys"]))
        buttons.addWidget(Button("Directorio…", "secondary", "users", on_click=self._actions["directory"]))
        card.add(buttons)
        self._body.addWidget(card)

    # ---- Zero Trust ------------------------------------------------------------------
    def _section_policies(self) -> None:
        s = self._settings
        card = _card("Políticas", "shield-lock")
        card.add(_row("Aplicar las políticas", "Si se desactiva, nada se bloquea (sigue quedando en la auditoría).",
                      self._toggle(s.policy_enforcement_enabled, "policy_enforcement_enabled")))
        card.add(_hair())
        card.add(_row("Exigir 2FA en lo compartido", "",
                      self._toggle(s.require_totp_for_shared, "require_totp_for_shared")))
        card.add(_hair())
        card.add(_row("Bloquear exportar si la auditoría está rota", "",
                      self._toggle(s.block_export_when_audit_broken, "block_export_when_audit_broken")))
        card.add(_hair())
        card.add(_row("Exigir un dispositivo de confianza", "",
                      self._toggle(s.require_trusted_device, "require_trusted_device")))
        card.add(_hair())
        card.add(_row("Exigir MFA para lo crítico", "Secretos de sensibilidad alta o crítica.",
                      self._toggle(s.require_mfa_for_high_sensitivity, "require_mfa_for_high_sensitivity")))
        card.add(_hair())
        card.add(_row("Avisar de contraseñas antiguas", "Se marcan en Salud y en la lista.",
                      _select(OLD, s.old_password_days, lambda v: self._set(old_password_days=v), 130)))
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(Button("Reglas…", "secondary", on_click=self._actions["policies"]))
        buttons.addWidget(Button("Acceso temporal y roles…", "secondary", on_click=self._actions["access"]))
        buttons.addWidget(Button("Agente en segundo plano…", "secondary", "terminal", on_click=self._actions["agent"]))
        card.add(buttons)
        self._body.addWidget(card)

    # ---- Identidad -------------------------------------------------------------------
    def _section_identity(self) -> None:
        s = self._settings
        card = _card("Identidad en esta bóveda", "user")
        name = Field(s.enterprise_display_name)
        name.setFixedWidth(260)
        name.editingFinished.connect(lambda: self._set(enterprise_display_name=name.text().strip() or "Local Admin"))
        card.add(_row("Nombre visible", "Aparece en los registros de compartir y de acceso.", name))
        card.add(_hair())
        card.add(_row("Rol", "Lo fija quien administra la bóveda.", Badge(ROLES.get(s.enterprise_role,
                                                                                   s.enterprise_role), "neutral")))
        card.add(_hair())
        trusted = s.local_device_id in s.trusted_device_ids
        card.add(_row("Este equipo", s.local_device_id,
                      Badge("De confianza" if trusted else "Sin confianza", "success" if trusted else "warning",
                            "check" if trusted else "warning")))
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(Button("Directorio…", "secondary", "users", on_click=self._actions["directory"]))
        card.add(buttons)
        self._body.addWidget(card)

    # ---- Apariencia --------------------------------------------------------------------
    def _section_appearance(self) -> None:
        s = self._settings
        card = _card("Tema", "theme")
        seg = Segmented((("dark", "Oscuro"), ("light", "Claro"), ("system", "Sistema")), s.theme, accent=True,
                        expand=False, check_mark=True)
        seg.changed.connect(lambda k: self._set(theme=k))
        row = QHBoxLayout()
        row.addWidget(seg)
        row.addStretch(1)
        card.add(row)
        card.add(label("Se aplica la próxima vez que abras AegisVault.", "tertiary"))
        card.add(_hair())
        card.add(_row("Tarjeta de salud en la barra lateral", "",
                      self._toggle(s.show_health_sidebar, "show_health_sidebar")))
        self._body.addWidget(card)

    # ---- Atajos -------------------------------------------------------------------------
    def _section_shortcuts(self) -> None:
        card = _card("Atajos de teclado", "keyboard")
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(10)
        for i, (keys, text) in enumerate(SHORTCUTS):
            kb = QHBoxLayout()
            kb.setSpacing(4)
            for part in keys.split(" "):
                kb.addWidget(Kbd(part))
            kb.addStretch(1)
            holder = QWidget()
            holder.setObjectName("transparent")
            holder.setLayout(kb)
            holder.setFixedWidth(120)
            grid.addWidget(holder, i, 0)
            grid.addWidget(label(text, "body"), i, 1)
        grid.setColumnStretch(1, 1)
        card.add(grid)
        self._body.addWidget(card)

    # ---- Acerca de ------------------------------------------------------------------------
    def _section_about(self) -> None:
        from ..... import __version__
        summary = self._session.crypto_summary()
        card = _card(PRODUCT_NAME, "logo")
        card.add(_row("Versión", "", label(__version__, "monoSm")))
        card.add(_hair())
        card.add(_row("Cifrado", "", label(f"{summary['kdf']} · {summary.get('cipher') or 'AES-256-GCM'}",
                                             "monoSm")))
        card.add(_hair())
        card.add(_row("Red", "Sin telemetría. Solo se conecta a Have I Been Pwned si lo activas.",
                      Badge("Local", "success", "wifi-off")))
        card.add(_hair())
        card.add(_row("Licencia", "", label("MIT", "monoSm")))
        card.add(_hair())
        card.add(_row("Código fuente", "", label("github.com/Zoel-Manchon/aegisvault", "monoSm", selectable=True)))
        self._body.addWidget(card)


def info_row(text: str, icon_name: str, color: str) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addWidget(icon_label(icon_name, color, 14), 0, Qt.AlignTop)
    row.addWidget(label(text, "secondary", wrap=True), 1)
    return row


def _size_of(path: str) -> str:
    try:
        size = Path(path).stat().st_size
    except OSError:
        return "?"
    if size >= 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB".replace(".", ",")
    return f"{max(1, size // 1024)} KB"


def _scrypt_params() -> str:
    from .....domain.value_objects.kdf_params import KdfParams
    return KdfParams.scrypt_strong().describe().replace("scrypt · ", "")


def _home_relative(path: str) -> str:
    """Show the user's home folder as ``~`` so the vault path fits the card."""
    home = str(Path.home())
    if path.lower().startswith(home.lower()):
        return "~" + path[len(home):]
    return path
