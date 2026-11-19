"""Secondary dialogs (board 20) and the small text prompt.

Every dialog follows the same anatomy (AvDialog): header with icon, title and
a one-line purpose; an optional status strip; a scrolling body; a footer with
a fact or link on the left and the actions on the right. The primary button
names the action, destructive actions are red and confirm separately, and
what does not exist yet is labelled «Próximamente» with disabled controls.
"""
from __future__ import annotations

import json
import socket
from dataclasses import asdict, replace
from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QPlainTextEdit, QPushButton,
    QRadioButton, QSpinBox, QVBoxLayout, QWidget,
)

from .....application.services.access_requests import AccessRequestQueue
from .....application.services.directory import DirectoryPrincipal, IdentityDirectory
from .....application.services.policy_pack import PolicyRule
from .....application.services.sharing import public_key_fingerprint
from .....application.services.siem import SiemStreamer, UdpSyslogSiemSink, normalize_blocks
from .....application.services.sync import SyncBundle
from .....application.services.sync_gateway import ZeroTrustSyncGateway
from ....outbound.audit_export.exporters import build_exporter
from ..components.kit import (
    AvDialog, Avatar, Badge, Banner, Button, Card, EmptyState, Field, Segmented, Toggle, clear_layout, confirm,
    icon_label, info_line, label, mono_font, overline, set_prop,
)
from ..fmt import ago, fmt_date, fmt_datetime, plural, starter_rule_text, thousands
from ..theme import PALETTE as P

ACTION_LABELS = {
    "*": "todo", "reveal_secret": "revelar", "copy_secret": "copiar", "share_secret": "compartir",
    "export_audit": "exportar auditoría", "purge_secret": "borrar", "rotate_secret": "rotar",
    "manage_policy": "cambiar políticas", "manage_members": "gestionar miembros",
}
SENSITIVITY_LABELS = {"standard": "normal", "high": "alta", "critical": "crítica"}
ROLE_LABELS = (("owner", "Propietario"), ("admin", "Admin"), ("auditor", "Auditor"), ("member", "Miembro"),
               ("readonly", "Solo lectura"))


# ---- shared helpers -------------------------------------------------------------------
def _short(value: str, head: int = 4, tail: int = 4) -> str:
    value = (value or "").upper()
    return f"{value[:head]}…{value[-tail:]}" if len(value) > head + tail else (value or "—")


def _row(title: str, subtitle: str = "", control: QWidget | None = None) -> QWidget:
    w = QWidget()
    w.setObjectName("transparent")
    row = QHBoxLayout(w)
    row.setContentsMargins(0, 8, 0, 8)
    row.setSpacing(16)
    text = QVBoxLayout()
    text.setSpacing(2)
    text.addWidget(label(title, "body", wrap=True))
    if subtitle:
        text.addWidget(label(subtitle, "tertiary", wrap=True))
    row.addLayout(text, 1)
    if control is not None:
        row.addWidget(control, 0, Qt.AlignVCenter)
    return w


def _hair() -> QFrame:
    line = QFrame()
    line.setObjectName("hairline")
    line.setFixedHeight(1)
    return line


def _documents() -> Path:
    docs = Path.home() / "Documents"
    return docs if docs.is_dir() else Path.home()


class _Tabs(QFrame):
    """Underlined text tabs (Sync, Access)."""

    def __init__(self, options, on_change):
        super().__init__()
        self.setObjectName("tabBar")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        self._buttons: dict[str, QPushButton] = {}
        self._on_change = on_change
        for key, text in options:
            btn = QPushButton(text)
            btn.setObjectName("tabBtn")
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _c=False, k=key: self.set_value(k))
            row.addWidget(btn)
            self._buttons[key] = btn
        row.addStretch(1)
        self.value = options[0][0]

    def set_text(self, key: str, text: str) -> None:
        self._buttons[key].setText(text)

    def set_value(self, key: str, emit: bool = True) -> None:
        self.value = key
        for k, btn in self._buttons.items():
            set_prop(btn, "active", k == key)
        if emit:
            self._on_change(key)


def ask_text(parent, title: str, text: str = "", placeholder: str = "", button: str = "Aceptar",
             value: str = "") -> str | None:
    """One-field prompt in the kit style; None when cancelled or left empty."""
    dlg = AvDialog(parent, title, text, width="s", scroll=False)
    field = Field(value, placeholder=placeholder)
    field.setAccessibleName(placeholder or title)
    dlg.add(field)
    dlg.add_button(Button("Cancelar", "secondary", on_click=dlg.reject))
    ok = dlg.add_button(Button(button, "primary", on_click=dlg.accept))
    ok.setDefault(True)
    ok.setEnabled(bool(value.strip()))
    field.textChanged.connect(lambda t: ok.setEnabled(bool(t.strip())))
    field.returnPressed.connect(lambda: ok.isEnabled() and dlg.accept())
    field.setFocus()
    if dlg.exec() and field.text().strip():
        return field.text().strip()
    return None


# ---- SIEM ------------------------------------------------------------------------------
class SiemDialog(AvDialog):
    """Exportar a SIEM: JSONL, CEF or syslog to a file, or syslog over UDP."""

    def __init__(self, session, settings, policy_context_fn, policy, parent=None):
        super().__init__(parent, "Exportar a SIEM", "Envía la cadena de auditoría a tu sistema de eventos.",
                         icon_name="activity")
        self._session = session
        self._settings = settings
        self._blocks = list(session.audit_log())
        verification, _fp, head = session.verify_integrity()
        self._chain_ok = bool(verification.ok)
        decision = policy.evaluate("export_audit", policy_context_fn(None, audit_ok=self._chain_ok))
        self._blocked_reason = "" if decision.allowed else starter_rule_text(decision.reason)
        n = len(self._blocks)
        if self._chain_ok:
            self.add_status(Banner("success", "Cadena verificada",
                                   f"· {thousands(n)} bloques · cabeza {_short(head, 4, 2)}", compact=True))
        else:
            broken = (verification.broken_index or 0)
            self.add_status(Banner("danger", f"La cadena se rompe en el bloque #{broken}",
                                   "Lo exportado a partir de ahí no tiene garantía.", compact=True))

        self.add(label("Formato", "label"))
        self._format = Segmented((("json", "JSON"), ("cef", "CEF"), ("syslog", "syslog")), "json", accent=True,
                                 check_mark=True)
        self._format.changed.connect(lambda _v: self._sync())
        self.add(self._format)
        self._format_hint = label("", "tertiary", wrap=True)
        self.add(self._format_hint)

        self.add(label("Destino", "label"))
        self._dest = QButtonGroup(self)
        file_card = QFrame()
        fc = QVBoxLayout(file_card)
        fc.setContentsMargins(14, 12, 14, 14)
        fc.setSpacing(8)
        self._to_file = QRadioButton("Archivo")
        self._dest.addButton(self._to_file)
        fc.addWidget(self._to_file)
        prow = QHBoxLayout()
        prow.setSpacing(8)
        stamp = datetime.now().strftime("%Y-%m-%d")
        self._path = Field(str(_documents() / f"aegisvault-{stamp}.jsonl"), mono=True)
        self._path.setAccessibleName("Archivo de destino")
        prow.addWidget(self._path, 1)
        prow.addWidget(Button("Elegir…", "secondary", on_click=self._choose))
        fc.addLayout(prow)
        self.add(file_card)
        udp_card = QFrame()
        uc = QVBoxLayout(udp_card)
        uc.setContentsMargins(14, 12, 14, 14)
        uc.setSpacing(6)
        self._to_udp = QRadioButton("Syslog por UDP")
        self._dest.addButton(self._to_udp)
        uc.addWidget(self._to_udp)
        urow = QHBoxLayout()
        self._target = Field("127.0.0.1:514", mono=True)
        self._target.setAccessibleName("Servidor syslog")
        self._target.setFixedWidth(220)
        urow.addWidget(self._target)
        urow.addStretch(1)
        uc.addLayout(urow)
        uc.addWidget(label("Sin cifrar ni confirmación de entrega: solo para laboratorio.", "tertiary", wrap=True))
        self.add(udp_card)
        self._cards = {self._to_file: file_card, self._to_udp: udp_card}
        self._to_file.setChecked(True)
        self._dest.buttonToggled.connect(lambda *_: self._sync())

        frow = QHBoxLayout()
        frow.addWidget(label("Desde el bloque", "body"))
        self._from = QSpinBox()
        first = self._blocks[0].index if self._blocks else 0
        self._from.setRange(first, self._blocks[-1].index if self._blocks else 0)
        self._from.setValue(first)
        self._from.setPrefix("#")
        self._from.setFixedWidth(110)
        self._from.setAccessibleName("Desde el bloque")
        self._from.valueChanged.connect(lambda _v: self._sync())
        frow.addWidget(self._from)
        frow.addStretch(1)
        self.add(frow)

        self.add(label("Vista previa · lleva nombres de entradas y acciones, nunca secretos", "tertiary", wrap=True))
        self._preview = QPlainTextEdit()
        self._preview.setObjectName("mono")
        self._preview.setReadOnly(True)
        self._preview.setFixedHeight(110)
        self._preview.setAccessibleName("Vista previa")
        self.add(self._preview)
        self._result = label("", "toneText", wrap=True, tone="success")
        self._result.hide()
        self.add(self._result)

        self._cancel = self.add_button(Button("Cancelar", "secondary", on_click=self.reject))
        self._go = self.add_button(Button("Exportar", "primary", on_click=self._export))
        self._go.setDefault(True)
        self._sync()

    def _selected(self) -> list:
        start = self._from.value()
        return [b for b in self._blocks if b.index >= start]

    def _sync(self) -> None:
        udp = self._to_udp.isChecked()
        for radio, card in self._cards.items():
            card.setObjectName("cardSelected" if radio.isChecked() else "card")
            card.style().unpolish(card)
            card.style().polish(card)
        self._path.setEnabled(not udp)
        self._target.setEnabled(udp)
        if udp and self._format.value() != "syslog":
            self._format.set_value("syslog", emit=False)
        for key in ("json", "cef"):
            self._format.button(key).setEnabled(not udp)
        fmt = self._format.value()
        self._format_hint.setText("Por UDP siempre se envía syslog." if udp else
                                  "Un objeto por línea (.jsonl). CEF y syslog escriben un .log.")
        path = self._path.text().strip()
        if path and not udp:
            suffix = ".jsonl" if fmt == "json" else ".log"
            stem = path.rsplit(".", 1)[0] if path.lower().endswith((".jsonl", ".log", ".json")) else path
            if not path.endswith(suffix):
                self._path.setText(stem + suffix)
        blocks = self._selected()
        self._preview.setPlainText(self._render(blocks[-2:], fmt) if blocks else "(sin eventos)")
        n = len(blocks)
        self._go.setText(f"Exportar {thousands(n)} {'evento' if n == 1 else 'eventos'}")
        self.set_note(f"Desde el bloque #{self._from.value()}")
        allowed = not self._blocked_reason and n > 0
        self._go.setEnabled(allowed)
        self._go.setToolTip(self._blocked_reason)
        if self._blocked_reason:
            self.set_note("Bloqueado por una política: la auditoría no está verificada.")

    @staticmethod
    def _render(blocks, fmt: str) -> str:
        if fmt == "json":
            return "\n".join(json.dumps(asdict(e), sort_keys=True, ensure_ascii=False) for e in normalize_blocks(blocks))
        return build_exporter(fmt).export(blocks)

    def _choose(self) -> None:
        fmt = self._format.value()
        pattern = "JSON Lines (*.jsonl)" if fmt == "json" else "Registro (*.log)"
        path, _f = QFileDialog.getSaveFileName(self, "Exportar auditoría", self._path.text(), pattern)
        if path:
            self._path.setText(path)
            self._sync()

    def _export(self) -> None:
        blocks = self._selected()
        try:
            if self._to_udp.isChecked():
                host, _, port = self._target.text().strip().rpartition(":")
                if not host or not port.isdigit():
                    raise ValueError("escribe el destino como host:puerto, p. ej. 127.0.0.1:514")
                count = SiemStreamer(UdpSyslogSiemSink(host, int(port))).stream(blocks)
                where = f"{host}:{port} (UDP)"
            else:
                path = Path(self._path.text().strip())
                if not str(path):
                    raise ValueError("elige un archivo de destino")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(self._render(blocks, self._format.value()) + "\n", encoding="utf-8")
                count = len(blocks)
                where = str(path)
        except (OSError, ValueError, socket.error) as exc:
            self._result.setProperty("tone", "danger")
            self._result.setText(f"No se pudo exportar: {exc}")
            self._result.style().polish(self._result)
            self._result.show()
            return
        self._result.setProperty("tone", "success")
        self._result.setText(f"Exportados {thousands(count)} eventos a {where}.")
        self._result.style().polish(self._result)
        self._result.show()
        self._cancel.setText("Cerrar")


# ---- sync and backups ---------------------------------------------------------------------
class SyncDialog(AvDialog):
    """Sincronizar y copias: export / load an encrypted bundle, local backups."""

    def __init__(self, session, settings, parent=None, tab: str = "export"):
        super().__init__(parent, "Sincronizar y copias", "Paquete cifrado, sin secretos en claro.", icon_name="sync")
        self._session = session
        self._settings = settings
        self.replaced = False
        self._bundle: SyncBundle | None = None
        self._bundle_text = ""
        self._tabs = _Tabs((("export", "Exportar paquete"), ("load", "Cargar paquete"), ("backups", "Copias")),
                           self._show_tab)
        self.add(self._tabs)
        self._page = QVBoxLayout()
        self._page.setSpacing(12)
        self.add(self._page)
        self._cancel = self.add_button(Button("Cancelar", "secondary", on_click=self.reject))
        self._primary = self.add_button(Button("", "primary", on_click=self._primary_action))
        self._danger = self.add_button(Button("Reemplazar bóveda local…", "dangerSolid", on_click=self._replace))
        self._tabs.set_value(tab)

    # tabs
    def _show_tab(self, key: str) -> None:
        clear_layout(self._page)
        self._danger.hide()
        self._primary.show()
        self._cancel.setText("Cancelar")
        self.set_note("")
        {"export": self._export_tab, "load": self._load_tab, "backups": self._backups_tab}[key]()

    def _backup_dir(self) -> str:
        if self._settings.backup_dir:
            return self._settings.backup_dir
        loc = Path(self._session.location or "boveda.avault")
        return str(loc.parent / f"{loc.stem}-copias")

    def _export_tab(self) -> None:
        self._page.addWidget(label("Exporta un paquete cifrado y cárgalo en otro equipo. Solo viaja el archivo "
                                   "cifrado y un manifiesto con huella, cabeza de la auditoría y número de "
                                   "entradas.", "secondary", wrap=True))
        row = QHBoxLayout()
        stem = Path(self._session.location or "boveda").stem
        self._out = Field(str(_documents() / f"{stem}.bundle.json"), mono=True)
        self._out.setAccessibleName("Archivo del paquete")
        row.addWidget(self._out, 1)
        row.addWidget(Button("Elegir…", "secondary", on_click=self._choose_out))
        self._page.addLayout(row)
        self._page.addWidget(self._gateway_line())
        self._msg = label("", "toneText", wrap=True, tone="success")
        self._msg.hide()
        self._page.addWidget(self._msg)
        self._primary.setText("Exportar paquete")
        self._primary.setEnabled(True)
        self.set_note("No contiene secretos en claro")

    def _gateway_line(self) -> QWidget:
        try:
            directory = IdentityDirectory(self._settings.recipient_directory)
            decisions = ZeroTrustSyncGateway(directory, require_trusted_device=self._settings.require_trusted_device
                                             ).evaluate([v for v in self._session.entries() if not v.deleted],
                                                        device_id=self._settings.local_device_id)
        except Exception:  # noqa: BLE001 - a preview must never block the export
            decisions = ()
        if not decisions:
            return info_line("No hay concesiones compartidas que entregar a otros dispositivos.", "info", "info")
        allowed = sum(1 for d in decisions if d.allowed)
        held = len(decisions) - allowed
        reasons = sorted({d.reason for d in decisions if not d.allowed})
        text = f"Entrega a dispositivos: {allowed} de {len(decisions)} concesiones"
        if held:
            text += f"; {held} retenida{'s' if held != 1 else ''} ({', '.join(_reason_es(r) for r in reasons)})"
        return info_line(text + ".", "info", "info")

    def _choose_out(self) -> None:
        path, _f = QFileDialog.getSaveFileName(self, "Guardar paquete", self._out.text(), "Paquete (*.json)")
        if path:
            self._out.setText(path)

    def _load_tab(self) -> None:
        row = QHBoxLayout()
        self._src = Field("", placeholder="Elige un paquete .bundle.json", mono=True)
        self._src.setReadOnly(True)
        self._src.setAccessibleName("Paquete")
        row.addWidget(self._src, 1)
        row.addWidget(Button("Elegir…", "secondary", on_click=self._choose_src))
        self._page.addLayout(row)
        self._compare = QVBoxLayout()
        self._page.addLayout(self._compare)
        self._primary.hide()
        self._danger.show()
        self._danger.setEnabled(False)
        self.set_note("Pide confirmación")
        if self._bundle is not None:
            self._show_bundle()

    def _choose_src(self) -> None:
        path, _f = QFileDialog.getOpenFileName(self, "Cargar paquete", str(_documents()), "Paquete (*.json)")
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
            bundle = SyncBundle.from_json(text)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._bundle = None
            clear_layout(self._compare)
            self._compare.addWidget(info_line(f"No es un paquete válido: {exc}", "danger", "alert"))
            self._danger.setEnabled(False)
            return
        self._bundle, self._bundle_text = bundle, text
        self._src.setText(path)
        self._show_bundle()

    def _show_bundle(self) -> None:
        clear_layout(self._compare)
        m = self._bundle.manifest
        _verdict, fp, head = self._session.verify_integrity()
        live = sum(1 for v in self._session.entries() if not v.deleted)
        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(8)
        grid.addWidget(label("", "tertiary"), 0, 0)
        grid.addWidget(label("Este equipo", "tertiary"), 0, 1)
        grid.addWidget(label("Paquete", "tertiary"), 0, 2)
        rows = (("Huella", _short(fp), _short(m.vault_fingerprint)),
                ("Auditoría", _short(head), _short(m.audit_head)),
                ("Entradas", str(live), str(m.entry_count)),
                ("Dispositivo", self._settings.local_device_id or "—",
                 f"{m.device_id} · {fmt_datetime(m.created_at, seconds=False)}"))
        for i, (title, here, there) in enumerate(rows, start=1):
            grid.addWidget(label(title, "secondary"), i, 0)
            mine = label(here, "monoSm")
            grid.addWidget(mine, i, 1)
            differs = here != there and title != "Dispositivo"
            theirs = label(("≠ " if differs else "") + there, "monoSm")
            if differs:
                theirs.setStyleSheet(f"color: {P.WARNING}; background: transparent;")
            grid.addWidget(theirs, i, 2)
        grid.setColumnStretch(2, 1)
        self._compare.addLayout(grid)
        self._compare.addWidget(label(f"Creado por {m.created_by}", "tertiary"))
        self._compare.addWidget(Banner("warning", "Importar reemplaza la bóveda de este equipo",
                                       f"por la del paquete. Antes se guarda una copia en {self._backup_dir()}.",
                                       compact=True))
        self._danger.setEnabled(True)

    def _backups_tab(self) -> None:
        self._page.addWidget(label(f"Carpeta: {self._backup_dir()}", "monoSm", wrap=True, selectable=True))
        try:
            backups = self._session.backups()
        except Exception:  # noqa: BLE001 - unreadable folder: show the empty state
            backups = []
        if not backups:
            self._page.addWidget(EmptyState("history", "Todavía no hay copias",
                                            "Se hace una antes de rotar, restaurar o importar, y cuando la pides."))
        for item in backups[:12]:
            row = QFrame()
            row.setObjectName("tableRow")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 10, 4, 10)
            rl.setSpacing(12)
            text = QVBoxLayout()
            text.setSpacing(2)
            when = fmt_datetime(item.get("modified", ""), seconds=False)
            text.addWidget(label(when or item.get("name", ""), "bodyStrong"))
            if item.get("readable"):
                detail = (f"{plural(item.get('entries', 0), 'entrada', 'entradas')} · "
                          f"{'cadena íntegra' if item.get('chain_ok') else 'cadena rota'}")
            else:
                detail = "No se puede abrir con esta bóveda"
            text.addWidget(label(detail, "tertiary"))
            rl.addLayout(text, 1)
            restore = Button("Restaurar…", "secondary", size="sm",
                             on_click=lambda _p=item.get("path"), w=when: self._restore(_p, w))
            restore.setEnabled(bool(item.get("readable")))
            rl.addWidget(restore)
            self._page.addWidget(row)
        self._primary.setText("Copiar ahora")
        self._primary.setEnabled(True)
        self._cancel.setText("Cerrar")
        self.set_note("Se guardan cifradas, igual que la bóveda")

    # actions
    def _primary_action(self) -> None:
        if self._tabs.value == "export":
            self._export()
        elif self._tabs.value == "backups":
            try:
                self._session.snapshot("manual")
            except Exception as exc:  # noqa: BLE001
                self.set_note(f"No se pudo copiar: {exc}")
                return
            self._show_tab("backups")
            self.set_note("Copia guardada")

    def _export(self) -> None:
        path = Path(self._out.text().strip())
        try:
            payload = self._session.export_sync_bundle(created_by=self._settings.enterprise_user_id,
                                                       device_id=self._settings.local_device_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(payload, encoding="utf-8")
        except (OSError, ValueError) as exc:
            self._msg.setProperty("tone", "danger")
            self._msg.setText(f"No se pudo exportar: {exc}")
        else:
            self._msg.setProperty("tone", "success")
            self._msg.setText(f"Paquete guardado en {path}. Cárgalo en el otro equipo con la misma contraseña.")
            self._cancel.setText("Cerrar")
        self._msg.style().polish(self._msg)
        self._msg.show()

    def _replace(self) -> None:
        if self._bundle is None:
            return
        if not confirm(self, "¿Reemplazar la bóveda de este equipo?",
                       "Se sustituye por la del paquete y se bloquea. Antes se guarda una copia de la actual.",
                       "Reemplazar bóveda", type_word="REEMPLAZAR", icon_name="sync"):
            return
        try:
            self._session.import_sync_bundle(self._bundle_text)
        except Exception as exc:  # noqa: BLE001 - other vault, damaged bundle, disk error
            clear_layout(self._compare)
            self._compare.addWidget(info_line(f"No se importó: {exc}. La bóveda local no ha cambiado.",
                                              "danger", "alert"))
            self._danger.setEnabled(False)
            return
        self.replaced = True
        self.accept()

    def _restore(self, path, when: str) -> None:
        if not confirm(self, "¿Restaurar esta copia?",
                       f"La bóveda vuelve al estado del {when}. Lo posterior se pierde, aunque antes se guarda una "
                       "copia de la actual. Se bloquea al terminar.", "Restaurar copia", icon_name="history"):
            return
        try:
            self._session.restore_backup(path)
        except Exception as exc:  # noqa: BLE001
            self.set_note(f"No se pudo restaurar: {exc}")
            return
        self.replaced = True
        self.accept()


def _reason_es(reason: str) -> str:
    return {"grant revoked": "revocada", "grant expired": "caducada",
            "recipient is not in the user/device directory": "fuera del directorio",
            "recipient is inactive": "persona inactiva",
            "recipient device is not trusted for sync delivery": "dispositivo sin confianza"}.get(reason, reason)


class RestoreSnapshotDialog(SyncDialog):
    """The backups tab on its own (audit page: «Restaurar la copia…»)."""

    def __init__(self, session, parent=None):
        from .....application.services.settings import VaultSettings
        settings = getattr(parent, "_settings", None) or VaultSettings()
        super().__init__(session, settings, parent, tab="backups")
        self.setWindowTitle("Restaurar una copia")
        self.title_label.setText("Restaurar una copia")
        self.subtitle_label.setText("Copias cifradas de esta bóveda; se comprueba su cadena de auditoría.")
        self._tabs.hide()

    @property
    def restored(self) -> bool:
        return self.replaced


# ---- Zero Trust policies -------------------------------------------------------------------
class _RuleEditor(AvDialog):
    def __init__(self, parent, rule: PolicyRule | None = None):
        super().__init__(parent, "Nueva regla" if rule is None else "Editar regla",
                         "Si todo lo marcado coincide, la acción se bloquea con tu mensaje.", icon_name="shield",
                         width="s")
        rule = rule or PolicyRule(rule_id="regla", name="")
        self.rule: PolicyRule | None = None
        self._name = Field(starter_rule_text(rule.name), placeholder="Por ejemplo: Compartir en Producción, bloqueado")
        self._name.setAccessibleName("Nombre de la regla")
        self.add(label("Nombre", "label"))
        self.add(self._name)
        self.add(label("Acciones que bloquea", "label"))
        self._actions: dict[str, QCheckBox] = {}
        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        for i, key in enumerate(("reveal_secret", "copy_secret", "share_secret", "export_audit", "purge_secret",
                                 "rotate_secret")):
            box = QCheckBox(ACTION_LABELS[key])
            box.setChecked(key in rule.actions or "*" in rule.actions and rule.name != "")
            self._actions[key] = box
            grid.addWidget(box, i // 2, i % 2)
        self.add(grid)
        self.add(label("Sensibilidad", "label"))
        self._sens = QComboBox()
        for value, text in (("", "Cualquiera"), ("high", "Alta"), ("critical", "Crítica"), ("high,critical",
                                                                                             "Alta o crítica")):
            self._sens.addItem(text, value)
        current = ",".join(rule.sensitivities)
        self._sens.setCurrentIndex(max(0, self._sens.findData(current)))
        self.add(self._sens)
        two = QGridLayout()
        two.setHorizontalSpacing(12)
        two.addWidget(label("Bóveda de equipo", "label"), 0, 0)
        two.addWidget(label("Categoría", "label"), 0, 1)
        self._team = Field(", ".join(rule.team_vaults), placeholder="Cualquiera")
        self._cat = Field(", ".join(rule.categories), placeholder="Cualquiera")
        two.addWidget(self._team, 1, 0)
        two.addWidget(self._cat, 1, 1)
        self.add(two)
        self._mfa = QCheckBox("Permitir solo con MFA verificada")
        self._mfa.setChecked(rule.require_mfa)
        self._device = QCheckBox("Permitir solo desde un dispositivo de confianza")
        self._device.setChecked(rule.require_trusted_device)
        self.add(self._mfa)
        self.add(self._device)
        self.add(label("Mensaje al bloquear", "label"))
        self._reason = Field(starter_rule_text(rule.reason) if rule.name else "",
                             placeholder="Lo que verá quien choque con la regla")
        self.add(self._reason)
        self.add_button(Button("Cancelar", "secondary", on_click=self.reject))
        self._save = self.add_button(Button("Guardar regla", "primary", on_click=self._done))
        self._save.setDefault(True)
        self._name.textChanged.connect(self._validate)
        for box in self._actions.values():
            box.toggled.connect(self._validate)
        self._validate()

    def _validate(self, *_):
        self._save.setEnabled(bool(self._name.text().strip()) and any(b.isChecked() for b in self._actions.values()))

    def _done(self) -> None:
        name = self._name.text().strip()
        split = lambda text: tuple(x.strip() for x in text.split(",") if x.strip())  # noqa: E731
        self.rule = PolicyRule(
            rule_id=name, name=name,
            actions=tuple(k for k, b in self._actions.items() if b.isChecked()),
            sensitivities=split(self._sens.currentData() or ""),
            team_vaults=split(self._team.text()), categories=split(self._cat.text()),
            require_mfa=self._mfa.isChecked(), require_trusted_device=self._device.isChecked(),
            reason=self._reason.text().strip() or f"Bloqueado por la regla «{name}».",
        ).normalized()
        self.accept()


class PoliciesDialog(AvDialog):
    """Políticas Zero Trust: general switches and ordered deny rules."""

    GENERAL = (("policy_enforcement_enabled", "Aplicar las políticas"),
               ("require_totp_for_shared", "Exigir TOTP en lo compartido"),
               ("block_export_when_audit_broken", "Bloquear exportar si la auditoría está rota"),
               ("require_reveal_before_copy", "Pedir revelar antes de copiar"))

    def __init__(self, settings, store, parent=None):
        super().__init__(parent, "Políticas Zero Trust", "La primera regla que coincide bloquea y dice por qué.",
                         icon_name="shield")
        self._original = settings
        self.settings = settings
        self._store = store
        self._content = QVBoxLayout()
        self._content.setSpacing(4)
        self.add(self._content)
        self._discard = self.add_button(Button("Descartar", "secondary", on_click=self._discard_changes))
        self._save = self.add_button(Button("Guardar políticas", "primary", on_click=self._save_all))
        self._save.setDefault(True)
        self._render()

    def _rules(self) -> list[PolicyRule]:
        return [PolicyRule.from_dict(r) for r in self.settings.policy_rules]

    def _changes(self) -> int:
        a, b = self._original, self.settings
        n = sum(1 for key, _t in self.GENERAL if getattr(a, key) != getattr(b, key))
        return n + (0 if tuple(a.policy_rules) == tuple(b.policy_rules) else 1)

    def _render(self) -> None:
        clear_layout(self._content)
        self._content.addWidget(overline("Generales"))
        for i, (key, title) in enumerate(self.GENERAL):
            toggle = Toggle(bool(getattr(self.settings, key)))
            toggle.toggled.connect(lambda on, k=key: self._set(**{k: on}))
            if i:
                self._content.addWidget(_hair())
            self._content.addWidget(_row(title, "", toggle))
        head = QHBoxLayout()
        head.setContentsMargins(0, 14, 0, 4)
        head.addWidget(overline("Reglas · en orden"))
        head.addStretch(1)
        head.addWidget(Button("Nueva regla", "ghost", "plus", on_click=self._new_rule))
        self._content.addLayout(head)
        rules = self._rules()
        if not rules:
            self._content.addWidget(label("Sin reglas propias: solo se aplican los interruptores de arriba.",
                                          "tertiary", wrap=True))
        saved = {json.dumps(r, sort_keys=True) for r in self._original.policy_rules}
        for index, rule in enumerate(rules, start=1):
            self._content.addWidget(self._rule_card(index, rule,
                                                    json.dumps(rule.to_dict(), sort_keys=True) not in saved))
        n = self._changes()
        self.set_note(plural(n, "cambio sin guardar", "cambios sin guardar") if n else "Sin cambios")
        self._save.setEnabled(bool(n))
        self._discard.setEnabled(bool(n))

    def _rule_card(self, index: int, rule: PolicyRule, unsaved: bool) -> QFrame:
        card = QFrame()
        card.setObjectName("cardSelected" if unsaved else "card")
        row = QHBoxLayout(card)
        row.setContentsMargins(14, 12, 14, 12)
        row.setSpacing(12)
        row.addWidget(label(str(index), "tertiary"), 0, Qt.AlignVCenter)
        col = QVBoxLayout()
        col.setSpacing(6)
        col.addWidget(label(starter_rule_text(rule.name), "bodyStrong", wrap=True))
        chips = QHBoxLayout()
        chips.setSpacing(6)
        actions = " · ".join(ACTION_LABELS.get(a, a) for a in rule.actions)
        chips.addWidget(Badge(actions, "neutral"))
        if rule.sensitivities:
            chips.addWidget(Badge("sensibilidad: " + ", ".join(SENSITIVITY_LABELS.get(s, s)
                                                               for s in rule.sensitivities), "neutral"))
        if rule.team_vaults:
            chips.addWidget(Badge("bóveda: " + ", ".join(rule.team_vaults), "neutral"))
        if rule.categories:
            chips.addWidget(Badge("categoría: " + ", ".join(rule.categories), "neutral"))
        if unsaved:
            chips.addWidget(Badge("sin guardar", "info"))
        chips.addStretch(1)
        col.addLayout(chips)
        row.addLayout(col, 1)
        toggle = Toggle(rule.enabled)
        toggle.toggled.connect(lambda on, r=rule: self._replace_rule(r, replace(r, enabled=on)))
        row.addWidget(toggle)
        row.addWidget(Button("", "icon", "edit", tooltip="Editar regla", on_click=lambda r=rule: self._edit_rule(r)))
        row.addWidget(Button("", "icon", "trash", tooltip="Quitar regla", on_click=lambda r=rule: self._drop(r)))
        return card

    def _set(self, **changes) -> None:
        self.settings = replace(self.settings, **changes).normalized()
        self._render()

    def _store_rules(self, rules: list[PolicyRule]) -> None:
        self._set(policy_rules=tuple(r.to_dict() for r in rules))

    def _new_rule(self) -> None:
        dlg = _RuleEditor(self)
        if dlg.exec() and dlg.rule is not None:
            rules = self._rules()
            taken = {r.rule_id for r in rules}
            rule, n = dlg.rule, 2
            while rule.rule_id in taken:
                rule = replace(dlg.rule, rule_id=f"{dlg.rule.rule_id}-{n}")
                n += 1
            self._store_rules(rules + [rule])

    def _edit_rule(self, rule: PolicyRule) -> None:
        dlg = _RuleEditor(self, rule)
        if dlg.exec() and dlg.rule is not None:
            self._replace_rule(rule, replace(dlg.rule, rule_id=rule.rule_id, enabled=rule.enabled))

    def _replace_rule(self, old: PolicyRule, new: PolicyRule) -> None:
        self._store_rules([new if r.rule_id == old.rule_id else r for r in self._rules()])

    def _drop(self, rule: PolicyRule) -> None:
        if confirm(self, f"¿Quitar la regla «{starter_rule_text(rule.name)}»?", "Deja de aplicarse cuando guardes las políticas.",
                   "Quitar regla"):
            self._store_rules([r for r in self._rules() if r.rule_id != rule.rule_id])

    def _discard_changes(self) -> None:
        self.settings = self._original
        self._render()

    def _save_all(self) -> None:
        self._store.save(self.settings)
        self._original = self.settings
        self.accept()

    def reject(self) -> None:
        if self._changes() and not confirm(self, "¿Descartar los cambios?",
                                           "Las políticas siguen como estaban al abrir.", "Descartar",
                                           icon_name="warning", tone="warning"):
            return
        self.settings = self._original
        super().reject()


# ---- Just-in-time access ---------------------------------------------------------------------
class AccessDialog(AvDialog):
    """Acceso temporal y roles: JIT requests, history and the local role."""

    def __init__(self, settings, store, session, parent=None, on_audit=None):
        super().__init__(parent, "Acceso temporal y roles", "Peticiones de acceso justo a tiempo (JIT).",
                         icon_name="timer")
        self.settings = settings
        self._store = store
        self._session = session
        self._on_audit = on_audit
        self._tabs = _Tabs((("pending", "Peticiones"), ("history", "Historial"), ("members", "Miembros y roles")),
                           lambda _k: self._render())
        self.add(self._tabs)
        self._content = QVBoxLayout()
        self._content.setSpacing(10)
        self.add(self._content)
        self.add(info_line("Aprobar no salta las políticas: el acceso sigue pasando por Zero Trust y queda en la "
                           "auditoría.", "info", "info"))
        if on_audit is not None:
            link = Button("Ver decisiones en la auditoría", "link", on_click=self._audit)
            self.footer.layout().insertWidget(0, link)
            self.footer_note.hide()
        close = self.add_button(Button("Cerrar", "secondary", on_click=self.accept))
        close.setDefault(True)
        self._tabs.set_value("pending")

    def _queue(self) -> AccessRequestQueue:
        return AccessRequestQueue(self.settings.access_requests)

    def _save_queue(self, queue: AccessRequestQueue) -> None:
        self.settings = replace(self.settings, access_requests=tuple(queue.to_list())).normalized()
        self._store.save(self.settings)

    def _audit(self) -> None:
        self.accept()
        self._on_audit()

    def _render(self) -> None:
        clear_layout(self._content)
        queue = self._queue()
        pending = queue.pending_count()
        self._tabs.set_text("pending", f"Peticiones {pending}" if pending else "Peticiones")
        {"pending": self._pending, "history": self._history, "members": self._members}[self._tabs.value](queue)

    def _pending(self, queue: AccessRequestQueue) -> None:
        open_requests = [r for r in queue.list(include_closed=False)]
        if not open_requests:
            self._content.addWidget(label("No hay peticiones pendientes.", "tertiary"))
        for req in open_requests:
            card = QFrame()
            card.setObjectName("cardSelected")
            col = QVBoxLayout(card)
            col.setContentsMargins(16, 14, 16, 14)
            col.setSpacing(8)
            head = QHBoxLayout()
            head.setSpacing(10)
            head.addWidget(Avatar(req.requester, "sm"))
            head.addWidget(label(f"<b>{_html(req.requester)}</b> pide {ACTION_LABELS.get(req.action, req.action)} "
                                 f"«{_html(req.entry_name)}»", "body", wrap=True), 1)
            head.addWidget(Badge("Pendiente", "warning", "clock"))
            col.addLayout(head)
            facts = [f"«{req.reason}»" if req.reason else "sin motivo", ago(req.created_at) if req.created_at else ""]
            col.addWidget(label(" · ".join(f for f in facts if f), "secondary", wrap=True))
            buttons = QHBoxLayout()
            buttons.addWidget(Button("Denegar…", "secondary", on_click=lambda r=req: self._decide(r, False)))
            buttons.addWidget(Button("Aprobar", "primary", on_click=lambda r=req: self._decide(r, True)))
            buttons.addStretch(1)
            col.addLayout(buttons)
            self._content.addWidget(card)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(Button("Nueva petición…", "ghost", "plus", on_click=self._new_request))
        self._content.addLayout(row)

    def _history(self, queue: AccessRequestQueue) -> None:
        closed = [r for r in queue.list(include_closed=True) if not r.is_open]
        if not closed:
            self._content.addWidget(label("Aún no se ha decidido ninguna petición.", "tertiary"))
        tones = {"approved": ("Aprobada", "success", "check"), "denied": ("Denegada", "danger", "ban"),
                 "expired": ("Caducada", "neutral", None), "revoked": ("Revocada", "neutral", "ban")}
        for req in sorted(closed, key=lambda r: r.decided_at or r.created_at, reverse=True)[:50]:
            row = QHBoxLayout()
            row.addWidget(label(f"<b>{_html(req.requester)}</b> · {ACTION_LABELS.get(req.action, req.action)} · "
                                f"{_html(req.entry_name)}", "body", wrap=True), 1)
            text, tone, icon_name = tones.get(req.status, (req.status, "neutral", None))
            row.addWidget(Badge(text, tone, icon_name))
            self._content.addLayout(row)
            if req.decision_reason:
                self._content.addWidget(label(f"Motivo: {req.decision_reason}", "tertiary", wrap=True))
            self._content.addWidget(_hair())

    def _members(self, _queue) -> None:
        box = Card(name="cardSunken", margins=(16, 14, 16, 14), spacing=10)
        box.add(label("Tu rol en esta bóveda", "secondary"))
        can_change = self.settings.enterprise_role in ("owner", "admin")
        roles = Segmented(ROLE_LABELS, self.settings.enterprise_role, expand=False, check_mark=True)
        roles.setEnabled(can_change)
        roles.changed.connect(self._set_role)
        box.add(roles)
        if not can_change:
            box.add(label("Solo un propietario o un admin cambia los roles.", "tertiary"))
        self._content.addWidget(box)
        people = IdentityDirectory(self.settings.recipient_directory).list()
        self._content.addWidget(overline("Directorio"))
        if not people:
            self._content.addWidget(label("Nadie en el directorio todavía.", "tertiary"))
        for person in people[:20]:
            row = QHBoxLayout()
            row.addWidget(Avatar(person.label, "sm"))
            row.addWidget(label(person.label + (f" · {person.email}" if person.email else ""), "body"), 1)
            row.addWidget(Badge(dict(ROLE_LABELS).get(person.role, person.role), "neutral"))
            if not person.active:
                row.addWidget(Badge("Inactivo", "neutral"))
            self._content.addLayout(row)

    def _set_role(self, role: str) -> None:
        self.settings = replace(self.settings, enterprise_role=role).normalized()
        self._store.save(self.settings)

    def _decide(self, req, approved: bool) -> None:
        reason = ""
        if not approved:
            reason = ask_text(self, "Denegar la petición", f"{req.requester} verá este motivo.",
                              "Motivo de la denegación", "Denegar")
            if reason is None:
                return
        now = datetime.now(timezone.utc).isoformat()
        queue = self._queue().decide(req.request_id, approved=approved,
                                     decided_by=self.settings.enterprise_display_name or "local-admin",
                                     decided_at=now, reason=reason)
        self._save_queue(queue)
        try:
            self._session.log_access_decision(req.entry_name, req.requester, req.action, approved)
        except Exception:  # noqa: BLE001 - the decision is saved even if the vault is busy
            pass
        self._render()

    def _new_request(self) -> None:
        names = sorted(v.name for v in self._session.entries() if not v.deleted)
        if not names:
            return
        dlg = AvDialog(self, "Nueva petición", "Pide un acceso puntual; otra persona lo aprueba.", width="s",
                       scroll=False)
        entry = QComboBox()
        entry.addItems(names)
        action = QComboBox()
        for key in ("reveal_secret", "copy_secret", "share_secret", "export_audit"):
            action.addItem(ACTION_LABELS[key], key)
        why = Field(placeholder="Motivo, p. ej. «INC-2231: rotar claves filtradas»")
        for title, widget in (("Entrada", entry), ("Acción", action), ("Motivo", why)):
            dlg.add(label(title, "label"))
            dlg.add(widget)
        dlg.add_button(Button("Cancelar", "secondary", on_click=dlg.reject))
        dlg.add_button(Button("Pedir acceso", "primary", on_click=dlg.accept)).setDefault(True)
        if not dlg.exec():
            return
        queue = self._queue().create(entry_name=entry.currentText(),
                                     requester=self.settings.enterprise_display_name or "local-admin",
                                     action=action.currentData(), reason=why.text().strip(),
                                     created_at=datetime.now(timezone.utc).isoformat())
        self._save_queue(queue)
        self._render()


def _html(text: str) -> str:
    from html import escape
    return escape(text or "")


# ---- directory ---------------------------------------------------------------------------------
class _PersonEditor(AvDialog):
    def __init__(self, parent, person: DirectoryPrincipal | None = None):
        super().__init__(parent, "Añadir persona" if person is None else f"Editar «{person.label}»",
                         "Su clave pública permite compartirle entradas cifradas.", icon_name="user", width="s")
        person = person or DirectoryPrincipal(label="")
        self.person: DirectoryPrincipal | None = None
        self._label = Field(person.label, placeholder="Nombre")
        self._email = Field(person.email, placeholder="correo@empresa.com")
        self._key = Field(person.public_key, placeholder="Clave pública X25519 (base64)", mono=True)
        self._role = QComboBox()
        for value, text in ROLE_LABELS:
            self._role.addItem(text, value)
        self._role.setCurrentIndex(max(0, self._role.findData(person.role)))
        self._groups = Field(", ".join(person.groups), placeholder="soporte, finanzas")
        self._devices = Field(", ".join(person.trusted_devices), placeholder="portatil-ana, sobremesa")
        for title, widget in (("Nombre", self._label), ("Correo", self._email), ("Clave pública", self._key),
                              ("Rol", self._role), ("Grupos", self._groups),
                              ("Dispositivos de confianza", self._devices)):
            self.add(label(title, "label"))
            self.add(widget)
        self._fp = label("", "monoSm")
        self.add(self._fp)
        self._active = QCheckBox("Activa")
        self._active.setChecked(person.active)
        self.add(self._active)
        self.add_button(Button("Cancelar", "secondary", on_click=self.reject))
        self._save = self.add_button(Button("Guardar", "primary", on_click=self._done))
        self._save.setDefault(True)
        self._label.textChanged.connect(self._validate)
        self._key.textChanged.connect(self._validate)
        self._validate()

    def _validate(self, *_):
        key = self._key.text().strip()
        ok_key = True
        if key:
            try:
                self._fp.setText("Huella " + " ".join(public_key_fingerprint(key).upper()[i:i + 4]
                                                      for i in range(0, 16, 4)))
            except Exception:  # noqa: BLE001
                ok_key = False
                self._fp.setText("Clave no válida")
        else:
            self._fp.setText("Sin clave: no se le puede compartir nada")
        self._save.setEnabled(bool(self._label.text().strip()) and ok_key)

    def _done(self) -> None:
        split = lambda text: tuple(x.strip() for x in text.split(",") if x.strip())  # noqa: E731
        self.person = DirectoryPrincipal(label=self._label.text().strip(), email=self._email.text().strip(),
                                         public_key=self._key.text().strip(), role=self._role.currentData(),
                                         groups=split(self._groups.text()),
                                         trusted_devices=split(self._devices.text()),
                                         active=self._active.isChecked()).normalized()
        self.accept()


class DirectoryDialog(AvDialog):
    """People and devices you can share with (stored in settings: no secrets)."""

    def __init__(self, settings, store, parent=None):
        super().__init__(parent, "Directorio", "Personas, sus claves públicas y sus dispositivos de confianza.",
                         icon_name="users")
        self.settings = settings
        self._store = store
        self._content = QVBoxLayout()
        self._content.setSpacing(0)
        self.add(self._content)
        self.set_note("Se guarda en settings.json; solo claves públicas")
        self.add_button(Button("Añadir persona", "secondary", "plus", on_click=lambda: self._edit(None)))
        close = self.add_button(Button("Cerrar", "primary", on_click=self.accept))
        close.setDefault(True)
        self._render()

    def _directory(self) -> IdentityDirectory:
        return IdentityDirectory(self.settings.recipient_directory)

    def _render(self) -> None:
        clear_layout(self._content)
        people = self._directory().list()
        if not people:
            self._content.addWidget(EmptyState("users", "Directorio vacío",
                                               "Añade a quien vaya a recibir entradas compartidas, con su clave "
                                               "pública."))
            return
        for person in people:
            row = QFrame()
            row.setObjectName("tableRow")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(4, 10, 4, 10)
            rl.setSpacing(12)
            rl.addWidget(Avatar(person.label, "sm", muted=not person.active))
            text = QVBoxLayout()
            text.setSpacing(2)
            text.addWidget(label(person.label + (f" · {person.email}" if person.email else ""), "bodyStrong"))
            fp = person.fingerprint
            text.addWidget(label(("Huella " + " ".join(fp.upper()[i:i + 4] for i in range(0, 16, 4)))
                                 if fp and fp != "invalid" else "Sin clave pública", "monoSm"))
            rl.addLayout(text, 1)
            rl.addWidget(Badge(dict(ROLE_LABELS).get(person.role, person.role), "neutral"))
            if not person.active:
                rl.addWidget(Badge("Inactiva", "neutral"))
            rl.addWidget(Button("", "icon", "edit", tooltip="Editar", on_click=lambda p=person: self._edit(p)))
            self._content.addWidget(row)

    def _edit(self, person) -> None:
        dlg = _PersonEditor(self, person)
        if not dlg.exec() or dlg.person is None:
            return
        directory = self._directory()
        if person is not None and (person.email or person.label).lower() != (dlg.person.email or
                                                                             dlg.person.label).lower():
            directory = IdentityDirectory([p for p in directory.list() if p != person])
        directory = directory.upsert(dlg.person)
        self.settings = replace(self.settings, recipient_directory=tuple(directory.to_list())).normalized()
        self._store.save(self.settings)
        self._render()


# ---- agent and passkey (information) ----------------------------------------------------------------
class AgentDialog(AvDialog):
    """Agente en segundo plano: the CLI agent, explained honestly."""

    def __init__(self, parent=None, vault_path: str | None = None):
        super().__init__(parent, "Agente en segundo plano", "Sirve secretos a tus scripts, como ssh-agent.",
                         icon_name="terminal")
        from ...agent import DEFAULT_SOCKET
        supported = hasattr(socket, "AF_UNIX")
        state = QHBoxLayout()
        if supported:
            state.addWidget(Badge("Se inicia desde la terminal", "neutral", "terminal"))
            state.addWidget(label("se bloquea tras 5 min sin peticiones", "secondary"))
        else:
            state.addWidget(Badge("Próximamente en Windows", "info"))
            state.addWidget(label("usa sockets Unix, que esta versión no ofrece aquí", "secondary"))
        state.addStretch(1)
        self.add(state)
        sock = Field(DEFAULT_SOCKET, mono=True)
        sock.setReadOnly(True)
        sock.setAccessibleName("Socket del agente")
        self.add(sock)
        self.add(_row("Órdenes", "", label("LIST · GET · CODE · LOCK", "monoSm")))
        self.add(label("Cada cliente recibe solo lo que pide; la clave maestra nunca sale del proceso.", "tertiary",
                       wrap=True))
        vault = vault_path or "personal.avault"
        command = f'aegisvault --vault "{vault}" agent --timeout 300'
        cmd = Field(command, mono=True)
        cmd.setReadOnly(True)
        cmd.setAccessibleName("Orden para iniciarlo")
        self.add(label("Para iniciarlo", "label"))
        self.add(cmd)
        self.set_note("Socket 0600 · solo tu usuario")
        copy_btn = self.add_button(Button("Copiar orden", "secondary", "copy"))
        copy_btn.clicked.connect(lambda: (_clipboard(command), self.set_note("Orden copiada")))
        copy_btn.setEnabled(supported)
        close = self.add_button(Button("Cerrar", "primary", on_click=self.accept))
        close.setDefault(True)


def _clipboard(text: str) -> None:
    from PySide6.QtWidgets import QApplication
    QApplication.clipboard().setText(text)


class PasskeyDialog(AvDialog):
    """Desbloquear con passkey: «Próximamente», controls disabled."""

    def __init__(self, parent=None):
        super().__init__(parent, "Desbloquear con passkey", "Windows Hello en lugar de escribir la contraseña.",
                         icon_name="fingerprint", width="s")
        from .....application.services.passkey_unlock import DesktopPasskeyUnlockService
        cap = DesktopPasskeyUnlockService().capability()
        self.header_right.addWidget(Badge("Próximamente", "info"))
        self.add(label("La base ya está; falta la ceremonia de registro. La contraseña maestra seguirá haciendo falta "
                       "para rotar y recuperar.", "body", wrap=True))
        toggle = Toggle(False, off_text="No disponible")
        toggle.setEnabled(False)
        self.add(_row("Usar passkey en este equipo", "", toggle))
        self.set_note(f"Detectado: {cap.biometric_hint}")
        close = self.add_button(Button("Cerrar", "secondary", on_click=self.accept))
        close.setDefault(True)


# ---- import -----------------------------------------------------------------------------------------
class ImportDialog(AvDialog):
    """Importar entradas desde otro gestor (CSV o Bitwarden JSON)."""

    FORMATS = (("csv", "CSV"), ("bitwarden", "Bitwarden (JSON)"))

    def __init__(self, session, parent=None):
        super().__init__(parent, "Importar entradas", "Desde un CSV (Chrome, Firefox, 1Password, KeePass…) o una "
                         "exportación JSON de Bitwarden.", icon_name="download")
        self._session = session
        self.imported = 0
        self._records: list = []
        self.add(label("Formato", "label"))
        self._format = Segmented(self.FORMATS, "csv", accent=True, check_mark=True)
        self._format.changed.connect(lambda _v: self._load())
        self.add(self._format)
        row = QHBoxLayout()
        self._path = Field("", placeholder="Elige el archivo exportado", mono=True)
        self._path.setReadOnly(True)
        self._path.setAccessibleName("Archivo a importar")
        row.addWidget(self._path, 1)
        row.addWidget(Button("Elegir…", "secondary", on_click=self._choose))
        self.add(row)
        self._summary = QVBoxLayout()
        self.add(self._summary)
        self.add(Banner("warning", "El archivo de origen está en claro.",
                        "Cuando termines, bórralo y vacía la papelera del sistema.", compact=True))
        self.set_note("Antes de importar se guarda una copia")
        self.add_button(Button("Cancelar", "secondary", on_click=self.reject))
        self._go = self.add_button(Button("Importar", "primary", on_click=self._import))
        self._go.setDefault(True)
        self._go.setEnabled(False)

    def _choose(self) -> None:
        pattern = "CSV (*.csv)" if self._format.value() == "csv" else "JSON (*.json)"
        path, _f = QFileDialog.getOpenFileName(self, "Importar", str(_documents()), pattern)
        if path:
            self._path.setText(path)
            self._load()

    def _load(self) -> None:
        from ....outbound.importers.parsers import parse
        clear_layout(self._summary)
        self._records = []
        path = self._path.text().strip()
        if not path:
            self._go.setEnabled(False)
            return
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
            records = parse(self._format.value(), text)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._summary.addWidget(info_line(f"No se pudo leer: {exc}", "danger", "alert"))
            self._go.setEnabled(False)
            return
        existing = {v.name.lower() for v in self._session.entries()}
        usable = [r for r in records if (r.get("name") or "").strip() and r.get("secret")]
        dupes = [r for r in usable if r["name"].strip().lower() in existing]
        self._records = usable
        new = len(usable) - len(dupes)
        self._summary.addWidget(info_line(
            f"{plural(len(records), 'registro', 'registros')} en el archivo · {new} nuevas · "
            f"{len(dupes)} ya existen (se omiten) · {len(records) - len(usable)} sin nombre o contraseña",
            "info", "info"))
        self._go.setText(f"Importar {plural(new, 'entrada', 'entradas')}")
        self._go.setEnabled(new > 0)

    def _import(self) -> None:
        try:
            added, _skipped = self._session.import_entries(self._records)
        except Exception as exc:  # noqa: BLE001 - disk errors: nothing was saved
            clear_layout(self._summary)
            self._summary.addWidget(info_line(f"No se importó: {exc}", "danger", "alert"))
            return
        self.imported = added
        self._records = []
        self.accept()

    def done(self, result):  # noqa: D401 - Qt API
        self._records = []
        super().done(result)
