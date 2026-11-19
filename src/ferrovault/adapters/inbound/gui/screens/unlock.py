"""Start-up splash (board 06) and the unlock / create window (boards 07-08).

The splash runs the cheap checks that tell the user where they stand
(crypto backend, vault file, readable header) before the password is asked.
The unlock window derives the key on a worker thread, slows repeated wrong
passwords (30 s between attempts from the 5th), and creates new vaults only
with a master password that passes the shared policy.
"""
from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox, QFileDialog, QFrame, QHBoxLayout, QMenu, QVBoxLayout, QWidget,
)

from .....application.errors import (
    AuthenticationError, UnsupportedVaultFormat, VaultAlreadyExists, VaultDoesNotExist, WeakMasterPassword,
)
from .....application.services.master_password import require_strong_master_password
from ..background import run_task
from ..branding import PRODUCT_NAME
from ..components.kit import (
    Badge, Banner, Button, Field, IconTile, PasswordField, Segmented, StepList, busy_bar, caps_lock_on,
    clear_layout, elide, icon_label, info_line, label, mono_font, set_prop, ui_font,
)
from ..icons import pixmap
from ..theme import PALETTE as P
from .master import NewPasswordFields

FAILS_BEFORE_WAIT = 5
WAIT_SECONDS = 30
DEFAULT_NAME = "personal.avault"


def default_vault_path() -> Path:
    docs = Path.home() / "Documents"
    return (docs if docs.is_dir() else Path.home()) / "AegisVault" / DEFAULT_NAME


def _profile() -> dict:
    try:
        from .....container import crypto_profile
        return crypto_profile()
    except Exception:  # noqa: BLE001 - the screen must open even if detection fails
        return {"backend": "Python", "kdf": "scrypt", "params": "", "cipher": "AES-256-GCM"}


def _params_text(profile: dict) -> str:
    """``"Argon2id · m=256 MiB · t=3 · p=4"`` → ``"m = 256 MiB · t = 3 · p = 4"``."""
    params = str(profile.get("params", "") or "")
    kdf = str(profile.get("kdf", "") or "")
    if kdf and params.lower().startswith(kdf.lower()):
        params = params[len(kdf):].lstrip(" ·")
    return params.replace("=", " = ")


def _folder_text(path: Path) -> str:
    folder = str(path.parent)
    sep = "\\" if "\\" in folder else "/"
    return folder if folder.endswith(sep) else folder + sep


def lock_message(reason: str, clipboard_cleared: bool = False) -> str:
    text = {
        "idle": "Se bloqueó por inactividad.",
        "manual": "Bóveda bloqueada. La clave ya no está en memoria.",
        "screen-lock": "Se bloqueó al bloquear Windows.",
        "suspend": "Se bloqueó al suspender el equipo.",
        "minimize": "Se bloqueó al minimizar la ventana.",
        "expired": "La sesión ya no era válida: vuelve a desbloquear.",
        "switch": "Elige otra bóveda o crea una nueva.",
        "sync-import": "Se cargó el paquete sincronizado: ábrela con su contraseña.",
        "restore": "Se restauró la copia: ábrela con la contraseña de esa copia.",
        "conflict": "El archivo cambió en disco: vuelve a abrirlo para ver la versión actual.",
    }.get(reason, "Bóveda bloqueada.")
    return f"{text} Portapapeles vaciado." if clipboard_cleared else text


# ---- splash ----------------------------------------------------------------------------
class Splash(QWidget):
    """Brand tile, product name, an indeterminate bar and three real checks."""

    def __init__(self, version: str, offline: bool = True):
        super().__init__()
        self.setObjectName("unlockRoot")
        self.setWindowTitle(PRODUCT_NAME)
        col = QVBoxLayout(self)
        col.setContentsMargins(24, 24, 24, 24)
        col.addStretch(3)
        tile = IconTile("logo", size=88, icon_size=40, color=P.ACCENT)
        set_prop(tile, "hero", True)
        col.addWidget(tile, 0, Qt.AlignHCenter)
        col.addSpacing(26)
        col.addWidget(label(PRODUCT_NAME, "splashTitle", align=Qt.AlignHCenter))
        col.addWidget(label("Tus secretos, en un único archivo cifrado en este equipo.", "secondary",
                            align=Qt.AlignHCenter))
        col.addSpacing(22)
        box = QWidget()
        box.setObjectName("transparent")
        box.setFixedWidth(420)
        bl = QVBoxLayout(box)
        bl.setContentsMargins(0, 0, 0, 0)
        bl.setSpacing(12)
        bar = busy_bar()
        bar.setFixedHeight(3)
        bl.addWidget(bar)
        card = QFrame()
        card.setObjectName("splashCard")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        self.steps = StepList(("Backend criptográfico", "Archivo de bóveda", "Cabecera del archivo"))
        cl.addWidget(self.steps)
        bl.addWidget(card)
        col.addWidget(box, 0, Qt.AlignHCenter)
        col.addStretch(4)
        foot = QHBoxLayout()
        foot.addStretch(1)
        foot.addWidget(label(f"Versión {version}", "tertiary"))
        foot.addSpacing(18)
        foot.addWidget(icon_label("wifi-off", P.TEXT_TERTIARY, 14))
        foot.addWidget(label("Sin conexión de red: nada sale de este equipo" if offline else
                             "Red solo para Have I Been Pwned (k-anonimato)", "tertiary"))
        foot.addStretch(1)
        col.addLayout(foot)


def run_startup_checks(splash: Splash, vault_path: Path, pump) -> dict:
    """Fill the splash with real facts; returns what the unlock screen needs."""
    facts = {"exists": False, "header_ok": False, "problem": ""}
    splash.steps.set_state(0)
    pump()
    profile = _profile()
    facts["profile"] = profile
    splash.steps.set_detail(0, f"{profile['backend']} · {profile['kdf']}")
    splash.steps.set_state(1)
    pump()
    facts["exists"] = vault_path.is_file()
    splash.steps.set_detail(1, vault_path.name if facts["exists"] else "se creará")
    splash.steps.set_state(2)
    pump()
    if facts["exists"]:
        try:
            from .....container import build_vault_service
            facts["recovery"] = build_vault_service(str(vault_path)).recovery_policy()
            facts["header_ok"] = True
            splash.steps.set_detail(2, "correcta")
        except UnsupportedVaultFormat:
            facts["problem"] = "Es de una versión más nueva de AegisVault o no es una bóveda."
            splash.steps.set_detail(2, "no reconocida")
        except Exception as exc:  # noqa: BLE001 - reported on the unlock screen
            facts["problem"] = f"No se pudo leer: {exc}"
            splash.steps.set_detail(2, "ilegible")
    else:
        splash.steps.set_detail(2, "—")
    splash.steps.set_state(3)
    pump()
    return facts


# ---- unlock / create ------------------------------------------------------------------------
class UnlockWindow(QWidget):
    """Emits ``unlocked(session, path, created)`` once a vault is open."""

    unlocked = Signal(object, str, bool)

    def __init__(self, settings, vault_path: str | Path | None = None, *, message: str = "",
                 service_factory=None):
        super().__init__()
        self.setObjectName("unlockRoot")
        self.setWindowTitle(PRODUCT_NAME)
        self._settings = settings
        self._path = Path(vault_path) if vault_path else default_vault_path()
        self._service_factory = service_factory
        self._profile = _profile()
        self._fails = 0
        self._wait_until = 0.0
        self._task = None
        self._busy = False
        self._cancelled = False
        self._message = message
        self.chain_ok = True

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._brand_panel())
        right = QWidget()
        right.setObjectName("transparent")
        rl = QVBoxLayout(right)
        rl.setContentsMargins(32, 32, 32, 32)
        rl.addStretch(1)
        self._form_holder = QWidget()
        self._form_holder.setObjectName("transparent")
        self._form_holder.setFixedWidth(400)
        self._form = QVBoxLayout(self._form_holder)
        self._form.setContentsMargins(0, 0, 0, 0)
        self._form.setSpacing(0)
        # Stretches, not an alignment flag: an aligned widget is laid out at its
        # plain size hint, which ignores word wrap and squeezes the form.
        centre = QHBoxLayout()
        centre.addStretch(1)
        centre.addWidget(self._form_holder)
        centre.addStretch(1)
        rl.addLayout(centre)
        rl.addStretch(1)
        root.addWidget(right, 1)
        self._tick = QTimer(self)
        self._tick.setInterval(500)
        self._tick.timeout.connect(self._update_wait)
        QShortcut(QKeySequence("Ctrl+O"), self, activated=self.choose_file)
        self._mode = "open" if self._path.is_file() else "create"
        self._render()

    # ---- left panel -----------------------------------------------------------------
    def _brand_panel(self) -> QFrame:
        panel = QFrame()
        panel.setObjectName("brandPanel")
        panel.setFixedWidth(520)
        col = QVBoxLayout(panel)
        col.setContentsMargins(56, 44, 56, 44)
        col.setSpacing(0)
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = label("")
        logo.setPixmap(pixmap("logo", P.TEXT_PRIMARY, 28))
        brand.addWidget(logo)
        brand.addWidget(label(PRODUCT_NAME, "brand"))
        brand.addStretch(1)
        col.addLayout(brand)
        col.addStretch(2)
        col.addWidget(label("Un solo archivo.\nCifrado.\nEn tu disco.", "display"))
        col.addSpacing(26)
        for icon_name, lead, text in (
                ("doc", "Sin servidor ni nube.", "La bóveda es un archivo que tú copias, mueves y respaldas."),
                ("key", "La clave nunca se guarda.", "Se deriva de tu contraseña maestra cada vez que desbloqueas."),
                ("link", "Cada cambio queda encadenado.", "El historial de auditoría detecta cualquier "
                                                          "manipulación.")):
            row = QHBoxLayout()
            row.setSpacing(14)
            row.addWidget(IconTile(icon_name, size=32, icon_size=16), 0, Qt.AlignTop)
            row.addWidget(label(f"<b>{lead}</b> {text}", "secondary", wrap=True), 1)
            col.addLayout(row)
            col.addSpacing(16)
        col.addStretch(3)
        foot = QHBoxLayout()
        foot.setSpacing(8)
        p = self._profile
        foot.addWidget(Badge(f"{p['backend']} · {p['kdf']}", "success", "check"))
        foot.addWidget(label(_params_text(p), "tertiary"))
        foot.addStretch(1)
        col.addLayout(foot)
        return panel

    # ---- right panel ------------------------------------------------------------------
    def _render(self) -> None:
        clear_layout(self._form)
        self._mode_switch = Segmented((("open", "Abrir bóveda"), ("create", "Crear nueva")), self._mode)
        self._mode_switch.changed.connect(self._set_mode)
        self._form.addWidget(self._mode_switch)
        self._form.addSpacing(26)
        if self._mode == "open":
            self._render_open()
        else:
            self._render_create()

    def _set_mode(self, mode: str) -> None:
        if self._busy:
            self._mode_switch.set_value(self._mode, emit=False)
            return
        self._mode = mode
        self._render()

    def _file_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("cardSunken")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 10, 10, 10)
        row.setSpacing(12)
        row.addWidget(icon_label("vault-file", P.TEXT_SECONDARY, 18))
        text = QVBoxLayout()
        text.setSpacing(1)
        name = label(elide(self._path.name, ui_font(14, 500), 250), "bodyStrong")
        text.addWidget(name)
        folder = label(elide(_folder_text(self._path), mono_font(11), 250, Qt.ElideMiddle), "monoSm")
        folder.setToolTip(str(self._path))
        name.setToolTip(str(self._path))
        text.addWidget(folder)
        row.addLayout(text, 1)
        change = Button("Cambiar", "ghost", trailing_icon="chevron-down")
        menu = QMenu(change)
        menu.addAction("Abrir otro archivo…", self.choose_file)
        menu.addAction("Crear una bóveda nueva…", lambda: self._set_mode("create"))
        change.setMenu(menu)
        row.addWidget(change)
        return card

    def _render_open(self) -> None:
        f = self._form
        f.addWidget(label("Desbloquea tu bóveda", "display"))
        f.addSpacing(6)
        f.addWidget(label("Escribe tu contraseña maestra para descifrar el archivo.", "secondary", wrap=True))
        f.addSpacing(28)
        if self._message:
            f.addWidget(info_line(self._message, "info", "lock"))
            f.addSpacing(14)
        f.addWidget(label("Archivo", "label"))
        f.addSpacing(6)
        f.addWidget(self._file_card())
        f.addSpacing(18)
        f.addWidget(label("Contraseña maestra", "label"))
        f.addSpacing(6)
        self._password = PasswordField()
        self._password.setAccessibleName("Contraseña maestra")
        self._password.setMinimumHeight(44)
        self._password.returnPressed.connect(self._unlock)
        self._password.installEventFilter(self)
        f.addWidget(self._password)
        f.addSpacing(6)
        self._caps = info_line("Bloq Mayús está activado", "info", "info")
        self._caps.setVisible(caps_lock_on())
        f.addWidget(self._caps)
        f.addWidget(self._error_holder())
        self._attempts = Banner("info", "", "", compact=True)
        self._attempts.hide()
        f.addSpacing(8)
        f.addWidget(self._attempts)
        f.addSpacing(14)
        self._go = Button("Desbloquear", "primary", "lock", shortcut="Enter", size="lg", on_click=self._unlock)
        self._go.setMinimumHeight(44)
        f.addWidget(self._go)
        f.addSpacing(14)
        links = QHBoxLayout()
        self._recover_link = Button("¿La has olvidado? Recuperar con fragmentos Shamir" if self._fails else
                                    "Recuperar con fragmentos Shamir", "link", on_click=self._recover)
        links.addWidget(self._recover_link)
        links.addStretch(1)
        if not self._fails:
            links.addWidget(Button("Abrir otro archivo…", "link", on_click=self.choose_file))
        f.addLayout(links)
        self._refresh_recovery_link()
        f.addSpacing(22)
        line = QFrame()
        line.setObjectName("hairline")
        line.setFixedHeight(1)
        f.addWidget(line)
        f.addSpacing(16)
        seconds = int(self._settings.auto_lock_seconds or 0)
        when = (f"tras {seconds // 60} min sin actividad" if seconds >= 60 else
                f"tras {seconds} s sin actividad" if seconds else "solo cuando tú lo pidas")
        f.addWidget(label(f"Se bloquea sola {when} y al suspender el equipo. Puedes cambiarlo en Ajustes.",
                          "tertiary", wrap=True))
        self._update_wait()
        QTimer.singleShot(0, self._password.setFocus)

    def _refresh_recovery_link(self) -> None:
        policy = None
        try:
            policy = self._service().recovery_policy() if self._path.is_file() else None
        except Exception:  # noqa: BLE001
            policy = None
        self._recover_link.setVisible(bool(policy))

    def _error_holder(self) -> QWidget:
        holder = QWidget()
        holder.setObjectName("transparent")
        self._error_box = QVBoxLayout(holder)
        self._error_box.setContentsMargins(0, 2, 0, 0)
        self._error_box.setSpacing(0)
        holder.hide()
        self._error = holder
        return holder

    def _render_create(self) -> None:
        f = self._form
        f.addWidget(label("Crea tu bóveda", "display"))
        f.addSpacing(20)
        f.addWidget(label("Nombre del archivo", "label"))
        f.addSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(8)
        target = self._path if not self._path.is_file() else default_vault_path()
        if target.is_file():
            target = target.with_name(f"{target.stem}-2{target.suffix}")
        self._new_folder = target.parent
        self._new_name = Field(target.name)
        self._new_name.setAccessibleName("Nombre del archivo")
        row.addWidget(self._new_name, 1)
        row.addWidget(Button("Ubicación…", "secondary", on_click=self._choose_folder))
        f.addLayout(row)
        self._folder_label = label(str(self._new_folder), "monoSm", wrap=True)
        f.addSpacing(4)
        f.addWidget(self._folder_label)
        f.addSpacing(14)
        self._new = NewPasswordFields("Contraseña maestra", "Repite la contraseña",
                                      hint="Una frase de 5+ palabras es ideal")
        f.addWidget(self._new)
        f.addSpacing(14)
        f.addWidget(Banner("warning", "", "Nadie puede recuperarla por ti. Si la olvidas, solo los fragmentos Shamir "
                                          "abren la bóveda: te propondremos crearlos al terminar.", compact=True))
        f.addSpacing(14)
        self._understood = QCheckBox()
        self._understood.setFixedSize(20, 20)
        self._understood.setAccessibleName("Lo entiendo: guardaré la contraseña en un lugar seguro")
        agree = QHBoxLayout()
        agree.setSpacing(10)
        agree.addWidget(self._understood, 0, Qt.AlignTop)
        text = label("Lo entiendo: guardaré la contraseña en un lugar seguro", "body", wrap=True)
        text.mousePressEvent = lambda _e: self._understood.toggle()
        agree.addWidget(text, 1)
        f.addLayout(agree)
        f.addWidget(self._error_holder())
        f.addSpacing(20)
        self._go = Button("Crear bóveda", "primary", size="lg", on_click=self._create)
        self._go.setMinimumHeight(44)
        f.addWidget(self._go)
        self._new.changed.connect(self._validate_create)
        self._understood.toggled.connect(self._validate_create)
        self._new_name.textChanged.connect(self._validate_create)
        self._validate_create()
        QTimer.singleShot(0, self._new.password.setFocus)

    def _validate_create(self, *_):
        name = self._new_name.text().strip()
        ok_name = bool(name) and not any(ch in name for ch in '\\/:*?"<>|')
        self._go.setEnabled(ok_name and self._new.is_valid() and self._understood.isChecked())

    # ---- file choice --------------------------------------------------------------------
    def choose_file(self) -> None:
        if self._busy:
            return
        path, _f = QFileDialog.getOpenFileName(self, "Abrir bóveda", str(self._path.parent),
                                               "Bóvedas de AegisVault (*.avault *.fv *.db);;Todos los archivos (*)")
        if path:
            self._path = Path(path)
            self._fails = 0
            self._message = ""
            self._mode = "open"
            self._render()

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Dónde guardar la bóveda", str(self._new_folder))
        if folder:
            self._new_folder = Path(folder)
            self._folder_label.setText(folder)

    def _service(self, path: Path | None = None):
        path = path or self._path
        if self._service_factory is not None:
            return self._service_factory(str(path))
        from .....container import build_vault_service
        return build_vault_service(str(path), backup_dir=self._settings.backup_dir or None,
                                   keep_backups=self._settings.keep_backups)

    # ---- throttling ------------------------------------------------------------------------
    def _update_wait(self) -> None:
        if self._mode != "open" or self._busy:
            return
        left = int(round(self._wait_until - time.monotonic()))
        try:
            if left > 0:
                self._go.setEnabled(False)
                self._go.set_label(f"Espera {left} s")
                if not self._tick.isActive():
                    self._tick.start()
            else:
                self._tick.stop()
                self._go.setEnabled(True)
                self._go.set_label("Desbloquear")
            if self._go._kbd is not None:
                self._go._kbd.setVisible(left <= 0)
        except RuntimeError:
            self._tick.stop()

    def eventFilter(self, obj, event):  # noqa: N802 - Qt API
        if event.type() in (QEvent.KeyPress, QEvent.KeyRelease, QEvent.FocusIn) and hasattr(self, "_caps"):
            try:
                self._caps.setVisible(caps_lock_on())
            except RuntimeError:
                pass
        return super().eventFilter(obj, event)

    # ---- unlock ------------------------------------------------------------------------------
    def _unlock(self) -> None:
        if self._busy or self._mode != "open" or time.monotonic() < self._wait_until:
            return
        password = self._password.text()
        if not password:
            self._password.setFocus()
            return
        if not self._path.is_file():
            self._show_error("No encuentro el archivo. Elige otro o crea una bóveda nueva.")
            return
        self._password.wipe()
        self._start("open", password)

    def _create(self) -> None:
        if self._busy or not self._go.isEnabled():
            return
        name = self._new_name.text().strip()
        if not name.lower().endswith((".avault", ".fv", ".db")):
            name += ".avault"
        path = self._new_folder / name
        if path.exists():
            self._show_error("Ya existe un archivo con ese nombre ahí. Elige otro nombre.")
            return
        password = self._new.value()
        try:
            require_strong_master_password(password)
        except WeakMasterPassword as exc:
            self._show_error(str(exc))
            return
        self._new.wipe()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            self._show_error(f"No se puede crear la carpeta: {exc}")
            return
        self._path = path
        self._start("create", password)

    def _start(self, mode: str, password: str) -> None:
        self._busy = True
        self._cancelled = False
        service = self._service()
        clear_layout(self._form)
        f = self._form
        f.addWidget(label("Creando tu bóveda…" if mode == "create" else "Desbloqueando…", "display"))
        f.addSpacing(22)
        f.addWidget(label("Contraseña maestra", "tertiary"))
        f.addSpacing(6)
        dots = Field("•" * 18)
        dots.setEnabled(False)
        dots.setMinimumHeight(44)
        f.addWidget(dots)
        f.addSpacing(16)
        kdf = self._profile.get("kdf", "Argon2id")
        head = QHBoxLayout()
        head.addWidget(label(f"Derivando la clave con {kdf}", "bodyStrong"))
        head.addStretch(1)
        head.addWidget(label("≈ 1–2 s", "tertiary"))
        f.addLayout(head)
        f.addSpacing(8)
        bar = busy_bar()
        bar.setFixedHeight(3)
        f.addWidget(bar)
        f.addSpacing(8)
        cost = ("256 MiB de memoria y 3 pasadas: lo que hace caro adivinarla." if kdf.lower() == "argon2id" else
                "Un coste de memoria alto: lo que hace caro adivinarla.")
        f.addWidget(label(cost, "tertiary", wrap=True))
        f.addSpacing(14)
        card = QFrame()
        card.setObjectName("cardSunken")
        cl = QVBoxLayout(card)
        cl.setContentsMargins(16, 12, 16, 12)
        steps = (("Creando el archivo cifrado", "Derivando la clave", "Sellando la bóveda", "Registrando el inicio")
                 if mode == "create" else
                 ("Cabecera del archivo leída", "Derivando la clave", "Descifrar el contenido",
                  "Verificar la cadena de auditoría"))
        self._steps = StepList(steps)
        self._steps.set_state(1)
        cl.addWidget(self._steps)
        f.addWidget(card)
        f.addSpacing(22)
        row = QHBoxLayout()
        working = Button("Derivando…", "primary", size="lg")
        working.setEnabled(False)
        working.setMinimumHeight(44)
        row.addWidget(working, 1)
        cancel = Button("Cancelar", "secondary", size="lg", on_click=self._cancel)
        cancel.setMinimumHeight(44)
        row.addWidget(cancel)
        f.addLayout(row)
        f.addSpacing(10)
        f.addWidget(label("El trabajo corre en segundo plano: la ventana sigue respondiendo.", "tertiary", wrap=True))

        def work(service=service, password=password, create=(mode == "create")):
            if create:
                service.init_vault(password)
            session = service.unlock(password)
            if session.verify_integrity()[0].ok is False:
                return session, False
            return session, True

        self._task = run_task(work, lambda result, m=mode: self._finished(result, m), parent=self)
        del password

    def _cancel(self) -> None:
        # The derivation cannot be interrupted; its result is discarded on arrival.
        self._cancelled = True
        self._busy = False
        self._render()

    def _finished(self, result, mode: str) -> None:
        if self._cancelled:
            self._cancelled = False
            if result.ok:
                try:
                    result.payload[0].lock()
                except Exception:  # noqa: BLE001
                    pass
            return
        self._busy = False
        if result.ok:
            session, self.chain_ok = result.payload
            self._fails = 0
            self.unlocked.emit(session, str(self._path), mode == "create")
            return
        error = result.payload
        self._mode = "open" if mode == "open" else "create"
        self._render()
        if isinstance(error, AuthenticationError) and mode == "open":
            self._fails += 1
            if self._fails >= FAILS_BEFORE_WAIT:
                self._wait_until = time.monotonic() + WAIT_SECONDS
            self._show_error("La contraseña no abre esta bóveda. Revisa Bloq Mayús y la distribución del teclado.")
            set_prop(self._password, "error", True)
            if self._fails >= FAILS_BEFORE_WAIT:
                text = (f"Intento {self._fails} de esta sesión. Espera {WAIT_SECONDS} s entre intentos: así se "
                        "frenan los ataques de fuerza bruta.")
            else:
                text = (f"Intento {self._fails} de esta sesión. A partir del {FAILS_BEFORE_WAIT}.º habrá "
                        f"{WAIT_SECONDS} s de espera entre intentos, para frenar ataques de fuerza bruta.")
            self._attempts.set_message("", text)
            self._attempts.show()
            self._update_wait()
        elif isinstance(error, VaultDoesNotExist):
            self._show_error("No encuentro el archivo. Elige otro o crea una bóveda nueva.")
        elif isinstance(error, VaultAlreadyExists):
            self._show_error("Ya existe una bóveda en esa ruta.")
        elif isinstance(error, UnsupportedVaultFormat):
            # The service says why (another cipher, a damaged header...); keep its words.
            self._show_error(str(error) or "Este archivo es de una versión más nueva de AegisVault o no es una bóveda.")
        else:
            self._show_error(f"No se pudo abrir: {result.error}")

    def _show_error(self, text: str) -> None:
        try:
            clear_layout(self._error_box)
            self._error_box.addWidget(info_line(text, "danger", "alert"))
            self._error.show()
        except (AttributeError, RuntimeError):
            pass

    # ---- recovery ---------------------------------------------------------------------------
    def _recover(self) -> None:
        if self._busy:
            return
        from .shamir import RestoreShamirDialog
        dlg = RestoreShamirDialog(self._service(), self)
        if dlg.exec() and dlg.new_password:
            password, dlg.new_password = dlg.new_password, None
            self._message = "Contraseña cambiada con los fragmentos. Abriendo…"
            self._start("open", password)

    def closeEvent(self, event):  # noqa: N802 - Qt API
        if self._busy:
            self._cancelled = True
        super().closeEvent(event)
