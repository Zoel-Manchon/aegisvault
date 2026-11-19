"""AegisVault main window (board 09): vault workspace plus the health, audit and
settings pages, with the desktop safety rules:

* the master key never outlives the session: "Bloquear ahora", Ctrl+L, the
  inactivity timer, Windows lock / sleep and (optionally) minimising all lock
  the vault, wipe the keys and return to the unlock screen;
* a revealed secret hides itself again after ``reveal_hide_seconds``;
* copies are kept out of clipboard history and cleared after
  ``clipboard_clear_seconds`` only if the clipboard still holds them;
* copies and reveals are written to the audit chain (names only).
"""
from __future__ import annotations

import sys
import time

from PySide6.QtCore import QEvent, QTimer, QUrl, Qt, Signal
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QHBoxLayout, QMenu, QStackedWidget, QVBoxLayout, QWidget

from ....application.errors import AuthenticationError, VaultConflictError
from ....application.services.enterprise import EnterpriseIdentity
from ....application.services.policy import PolicyEngine
from ....application.services.settings import MemorySettingsStore
from .branding import PRODUCT_NAME
from .clipboard import SecureClipboard
from .components.kit import Button, EmptyState, ToastHost, confirm, notify
from .components.vault_view import DetailModel, DetailPanel, ListPanel, RowAlert, Sidebar, TopBar, compact_for
from .design.tokens import LOCK_WARN_S
from .fmt import (
    ago, count_word, days_since, fmt_date, join_names, plural, safe_web_url, starter_rule_text, thousands,
)
from .view_models.vault_list import ALL_CATEGORIES, VaultListViewModel

PAGE_SIZE = 25

ACTION_TEXT = {
    "add": "Entrada creada", "edit": "Entrada editada", "trash": "Movida a la papelera",
    "restore": "Restaurada de la papelera", "favorite": "Marcada como favorita",
    "unfavorite": "Quitada de favoritos", "share": "Compartida", "unshare": "Dejó de compartirse",
    "revoke-share": "Acceso revocado", "rotate-secret": "Marcada como rotada",
    "enterprise-meta": "Política de la entrada cambiada", "import": "Importada",
}
ACCESS_ACTIONS = {"copy", "copy-user", "copy-totp", "reveal"}

POLICY_TEXT = {
    "reveal_required": "Tu política pide revelar el secreto antes de copiarlo. Pulsa «Revelar» y vuelve a copiar.",
    "totp_required": "Tu política solo deja compartir entradas que tengan código 2FA.",
    "audit_chain_broken": "La cadena de auditoría no se pudo verificar, así que la exportación está bloqueada.",
    "mfa_required": "Los secretos de sensibilidad alta piden MFA verificado.",
    "untrusted_device": "Este equipo no está en la lista de dispositivos de confianza.",
    "role_forbidden": "Tu rol no permite esta acción.",
    "group_forbidden": "Esta entrada está limitada a otro equipo o grupo.",
    "break_glass_mfa_required": "El acceso de emergencia pide MFA verificado.",
}


class MainWindow(QWidget):
    """The unlocked workspace. Emits ``lock_requested(reason)`` after wiping the session."""

    lock_requested = Signal(str)

    def __init__(self, session, clipboard, settings_store=None, vault_path: str | None = None):
        super().__init__()
        self._session = session
        self._settings_store = settings_store or MemorySettingsStore()
        self._settings = self._settings_store.load()
        self._policy = PolicyEngine(self._settings)
        self._clipboard = clipboard
        self._clip = SecureClipboard(clipboard, self)
        self._vault_path = vault_path or getattr(session, "location", "") or ""
        self._list_vm = VaultListViewModel(page_size=PAGE_SIZE)
        self._all_views = []
        self._current = None
        self._revealed = False
        self._reveal_left = 0
        self._health = None
        self._health_report_cache = None
        self._health_worker_owner = None
        self._health_dirty = False
        self._breach_checked_at: float | None = None
        self._locked = False
        self._wts_registered = False
        self._last_activity = time.monotonic()
        self._pills = []
        self.on_locked = None

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self.setObjectName("appShell")
        self.setWindowTitle(f"{PRODUCT_NAME} · {self._vault_label()}")
        self.resize(1440, 900)
        self.setMinimumSize(1080, 680)

        self._build()
        self._install_shortcuts()
        self._toasts = ToastHost(self)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(90)
        self._filter_timer.timeout.connect(self._apply_filter)

        self._reload()
        self._show_detail(None)
        self._tick()
        QTimer.singleShot(350, self._start_background_warmups)
        QTimer.singleShot(900, self._start_background_health_warmup)

    # ================================================================ build
    def _vault_label(self) -> str:
        from pathlib import Path
        return Path(self._vault_path).stem if self._vault_path else "bóveda"

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        self._stack = QStackedWidget()
        root.addWidget(self._stack)

        vault_page = QWidget()
        vault_page.setObjectName("appShell")
        col = QVBoxLayout(vault_page)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(0)
        self._topbar = TopBar(
            self._vault_label(), self._build_vault_menu(), self._show_command_palette,
            (("Compartir", "share", self._open_shared_center),
             ("SIEM", "activity", self._show_siem),
             ("Sincronizar", "sync", self._show_sync),
             ("Verificar", "shield-check", lambda: self._open_audit(verify=True))),
            self._build_more_menu(), lambda: self.lock_now("manual"))
        self._pills.append(self._topbar.lock_pill)
        col.addWidget(self._topbar)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)
        self._sidebar = Sidebar()
        self._sidebar.section_selected.connect(self._set_section)
        self._sidebar.category_selected.connect(self._filter_category)
        self._sidebar.zero_trust.connect(self._show_policies)
        self._sidebar.health.connect(self._open_health)
        self._sidebar.settings.connect(self._open_settings)
        self._sidebar.new_category.connect(self._new_category)
        self._sidebar.health_card.setVisible(self._settings.show_health_sidebar)
        body.addWidget(self._sidebar)

        self._cat_menu = QMenu(self)
        self._cat_menu.aboutToShow.connect(self._fill_category_menu)
        self._sort_menu = QMenu(self)
        for key, text in (("recent", "Recientes"), ("name", "Nombre (A–Z)")):
            act = self._sort_menu.addAction(text)
            act.triggered.connect(lambda _=False, k=key: self._set_sort(k))
        self._list_panel = ListPanel(
            on_new=self._new_entry, on_search=lambda _t: self._schedule_filter(), on_select=self._on_select,
            on_page=self._go_page, category_menu=self._cat_menu, sort_menu=self._sort_menu,
            on_clear_category=lambda: self._filter_category(ALL_CATEGORIES))
        self._list_panel.list.activated_entry.connect(lambda _v: self._edit_entry())
        self._list_panel.list.delete_requested.connect(lambda _v: self._trash_entry())
        self._list_panel.list.menu_requested.connect(self._entry_menu)
        self._empty_trash_btn = Button("Vaciar papelera", "secondary", on_click=self._empty_trash)
        self._empty_trash_btn.hide()
        self._list_panel.add_header_widget(self._empty_trash_btn)
        body.addWidget(self._list_panel, 4)

        self._detail = DetailPanel()
        body.addWidget(self._detail, 9)
        col.addLayout(body, 1)
        self._stack.addWidget(vault_page)

        # aliases kept for controllers and tests
        self.list = self._list_panel.list
        self.search = self._list_panel.search

    def _build_vault_menu(self) -> QMenu:
        menu = QMenu(self)
        where = menu.addAction(self._vault_path or "Bóveda")
        where.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Mostrar en el explorador", self._reveal_vault_file)
        menu.addAction("Hacer una copia ahora", self._snapshot_now)
        menu.addSeparator()
        menu.addAction("Abrir otra bóveda…", lambda: self.lock_now("switch"))
        return menu

    def _build_more_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.addAction("Salud de la bóveda", self._open_health)
        menu.addAction("Auditoría", lambda: self._open_audit())
        menu.addSeparator()
        menu.addAction("Fragmentos de recuperación (Shamir)…", self._enroll_recovery)
        menu.addAction("Rotar contraseña maestra…", self._rotate_password)
        menu.addSeparator()
        menu.addAction("Importar…", self._import_entries)
        menu.addAction("Políticas Zero Trust…", self._show_policies)
        menu.addAction("Acceso temporal y roles…", self._show_access)
        menu.addAction("Agente en segundo plano…", self._show_agent)
        menu.addAction("Desbloquear con passkey…", self._show_passkey)
        menu.addSeparator()
        menu.addAction("Ajustes", self._open_settings)
        return menu

    def _install_shortcuts(self) -> None:
        def sc(seq, handler, widget=None, context=Qt.WindowShortcut):
            shortcut = QShortcut(QKeySequence(seq), widget or self)
            shortcut.setContext(context)
            shortcut.activated.connect(handler)
            return shortcut

        sc("Ctrl+K", self._show_command_palette)
        sc("Ctrl+F", self._focus_search)
        sc("Ctrl+N", self._new_entry)
        sc("Ctrl+E", self._edit_entry)
        sc("Ctrl+L", lambda: self.lock_now("manual"))
        sc("Ctrl+G", self._generate_and_copy)
        sc("Ctrl+B", self._copy_user)
        sc("Ctrl+T", self._copy_code)
        sc("Ctrl+,", self._open_settings)
        # Ctrl+C copies the secret only from the list, so text fields keep normal copy.
        sc("Ctrl+C", self._copy_secret, self.list, Qt.WidgetWithChildrenShortcut)

    # ================================================================ data
    def _reload(self) -> None:
        self._all_views = list(self._session.entries())
        live = [v for v in self._all_views if not v.deleted]
        cats: dict[str, int] = {}
        for v in live:
            if v.category:
                cats[v.category] = cats.get(v.category, 0) + 1
        self._sidebar.set_categories(sorted(cats.items(), key=lambda kv: (-kv[1], kv[0].lower())))
        self._sidebar.set_counts(
            total=len(live),
            favorites=sum(1 for v in live if v.favorite),
            shared=sum(1 for v in live if v.shared_with or v.active_share_count),
            trash=sum(1 for v in self._all_views if v.deleted))
        self._sync_sidebar()
        self._apply_filter()
        self._mark_health_dirty()

    def _sync_sidebar(self) -> None:
        st = self._list_vm.state
        cat = st.category if st.category != ALL_CATEGORIES else None
        self._sidebar.set_active(st.section, cat if st.section == "Vault" else None)

    def _schedule_filter(self) -> None:
        self._filter_timer.start()

    def _category_label(self, category: str) -> str:
        """Filter button text; short in a narrow window so it never overlaps «Recientes»."""
        compact = compact_for(self.width())
        if category == ALL_CATEGORIES:
            return "Todas" if compact else "Todas las categorías"
        limit = 14 if compact else 22
        return category if len(category) <= limit else category[:limit - 1] + "…"

    def _apply_filter(self) -> None:
        query = self.search.text()
        if query != self._list_vm.state.query:
            self._list_vm.set_query(query)
        st = self._list_vm.state
        result = self._list_vm.page(self._all_views)
        alerts = self._alerts()
        trash_left = {v.name: self._trash_days_left(v) for v in result.entries if v.deleted}
        section_titles = {"Vault": "Bóveda", "Favorites": "Favoritos", "Shared": "Compartidos", "Trash": "Papelera"}
        title = st.category if (st.section == "Vault" and st.category != ALL_CATEGORIES) else \
            section_titles.get(st.section, "Bóveda")
        in_scope = self._scope_count()
        if st.query.strip():
            count_text = f"{result.matched_count} de {in_scope}"
        else:
            count_text = plural(result.matched_count, "entrada", "entradas")
        self._list_panel.set_header(title, count_text)
        self._list_panel.cat_btn.set_label(self._category_label(st.category))
        self._list_panel.sort_btn.set_label("Recientes" if st.sort == "recent" else "Nombre (A–Z)")
        self._list_panel.set_category_chip(st.category if (st.category != ALL_CATEGORIES and st.query.strip()) else None)
        is_trash = st.section == "Trash"
        self._list_panel.new_btn.setVisible(not is_trash)
        self._empty_trash_btn.setVisible(is_trash and bool(result.matched_count))
        if result.matched_count:
            self._list_panel.set_rows(result.entries, st.selected_name, alerts, trash_left)
        else:
            self._list_panel.list.clear()
            self._list_panel.show_empty(self._empty_state())
        page, pages = st.page, result.total_pages
        if result.matched_count:
            start = page * PAGE_SIZE + 1
            end = start + len(result.entries) - 1
            footer = f"{start}–{end} de {thousands(result.matched_count)}"
            if pages > 1:
                footer += f" · página {page + 1} de {pages}"
        else:
            footer = ""
        self._list_panel.set_footer(footer, page > 0, page < pages - 1)

    def _scope_count(self) -> int:
        st = self._list_vm.state
        views = [v for v in self._all_views if (v.deleted if st.section == "Trash" else not v.deleted)]
        if st.section == "Favorites":
            views = [v for v in views if v.favorite]
        elif st.section == "Shared":
            views = [v for v in views if v.shared_with or v.active_share_count or v.revoked_share_count]
        if st.category != ALL_CATEGORIES:
            views = [v for v in views if v.category.lower() == st.category.lower()]
        return len(views)

    def _empty_state(self) -> QWidget:
        st = self._list_vm.state
        q = st.query.strip()
        if q:
            elsewhere = sum(1 for v in self._all_views if not v.deleted and q.lower() in _search_text(v))
            in_trash = sum(1 for v in self._all_views if v.deleted and q.lower() in _search_text(v))
            scope = f"Solo se está buscando en {st.category}. " if st.category != ALL_CATEGORIES else ""
            actions = []
            if st.category != ALL_CATEGORIES and elsewhere:
                actions.append(Button(f"Buscar en toda la bóveda ({elsewhere})", "secondary",
                                      on_click=lambda: self._filter_category(ALL_CATEGORIES)))
            if st.section != "Trash":
                actions.append(Button(f"Crear «{q}»", "ghost", "add", on_click=lambda: self._new_entry(name=q)))
            note = f"{plural(in_trash, 'coincidencia', 'coincidencias')} en la papelera" if in_trash and st.section != "Trash" else ""
            return EmptyState("search-minus", f"Nada coincide con «{q}»",
                              scope + "Se busca en nombre, usuario, URL y etiquetas; nunca dentro de contraseñas.",
                              actions, note)
        if st.section == "Trash":
            days = self._settings.trash_retention_days
            text = (f"Lo que borres se queda aquí {days} días, cifrado como el resto. Después sale del archivo "
                    "de forma definitiva." if days else "Lo que borres se queda aquí, cifrado, hasta que lo borres para siempre.")
            return EmptyState("trash", "La papelera está vacía", text,
                              [Button("Cambiar el plazo en Ajustes", "link", on_click=self._open_settings)])
        if st.section == "Favorites":
            return EmptyState("star", "Sin favoritos todavía",
                              "Marca con la estrella las entradas que usas a diario y aparecerán aquí.")
        if st.section == "Shared":
            return EmptyState("users", "No has compartido nada",
                              "Comparte una entrada con la clave pública de otra persona: solo ella podrá abrir "
                              "el sobre cifrado.")
        return EmptyState("vault", "Tu bóveda está vacía",
                          "Añade tu primera contraseña o tráete las que ya tienes. Todo se guarda solo en este archivo.",
                          [Button("Nueva entrada", "primary", "add", on_click=self._new_entry),
                           Button("Importar…", "secondary", "download", on_click=self._import_entries)],
                          "CSV o Bitwarden JSON · Ctrl+N crea una entrada desde cualquier sitio")

    def _trash_days_left(self, view) -> int | None:
        days = self._settings.trash_retention_days
        age = days_since(getattr(view, "deleted_at", "") or getattr(view, "updated_at", ""))
        if not days or age is None:
            return None
        return max(0, days - age)

    # ---- filters ---------------------------------------------------------
    def _set_section(self, section: str) -> None:
        self._show_page(0)
        self._list_vm.set_section(section)
        if section != "Vault":
            self._list_vm.set_category(ALL_CATEGORIES)
        self._list_vm.set_selection(None)
        self._sync_sidebar()
        self._apply_filter()
        self._show_detail(None)

    def _filter_category(self, name: str) -> None:
        self._show_page(0)
        self._list_vm.state = self._list_vm.state.with_section("Vault")
        self._list_vm.set_category(name or ALL_CATEGORIES)
        self._sync_sidebar()
        self._apply_filter()

    def _fill_category_menu(self) -> None:
        self._cat_menu.clear()
        current = self._list_vm.state.category
        cats = [c for c in self._list_vm.categories(v for v in self._all_views if not v.deleted)]
        for cat in cats:
            label = "Todas las categorías" if cat == ALL_CATEGORIES else cat
            act = self._cat_menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(cat == current)
            act.triggered.connect(lambda _=False, c=cat: self._filter_category(c))

    def _set_sort(self, key: str) -> None:
        self._list_vm.state = self._list_vm.state.with_sort(key)
        self._apply_filter()

    def _go_page(self, delta: int) -> None:
        self._list_vm.set_page(self._list_vm.state.page + delta)
        self._apply_filter()

    def _focus_search(self) -> None:
        self._show_page(0)
        self.search.setFocus()
        self.search.selectAll()

    # ================================================================ selection
    def _on_select(self, view) -> None:
        self._hide_secret()
        self._list_vm.set_selection(view.name if view else None)
        self._list_panel.refresh_selection(view.name if view else None)
        self._show_detail(view)

    def _show_detail(self, view) -> None:
        self._current = view
        self._revealed = False
        if view is None:
            self._detail.show_placeholder("Elige una entrada",
                                          "Sus datos aparecen aquí. La contraseña sigue oculta hasta que la reveles.")
            return
        self._detail.show_entry(self._detail_model(view), {
            "favorite": self._toggle_favorite, "edit": self._edit_entry,
            "menu": lambda pos: self._entry_menu(self._current, pos),
            "copy_user": self._copy_user, "reveal": self._toggle_reveal, "copy_secret": self._copy_secret,
            "open_url": self._open_url, "copy_code": self._copy_code,
            "alert": self._alert_action, "add_totp": lambda: self._edit_entry(focus="totp"),
            "audit": lambda: self._open_audit(filter_text=view.name),
            "restore": self._restore_entry, "purge": self._purge_entry,
        })
        self._tick_totp()

    def _detail_model(self, view) -> DetailModel:
        changed = getattr(view, "password_changed_at", "") or getattr(view, "updated_at", "")
        kind = getattr(view, "kind", "login")
        changed_text = ""
        if changed:
            changed_text = ("Cambiada " if kind in ("login", "api_key") else "Editada ") + ago(changed)
        strength = None
        if not view.deleted and kind in ("login", "api_key"):
            try:
                strength = self._session.strength(view.name)
            except Exception:
                strength = None
        return DetailModel(view=view, changed_text=changed_text, alert=self._alerts().get(view.name),
                           strength=strength, history=self._history_for(view.name),
                           trash_days_left=self._trash_days_left(view) if view.deleted else None)

    def _history_for(self, name: str) -> list:
        rows = []
        for block in reversed(self._session.audit_log()):
            detail = block.detail or ""
            if not (detail == name or detail.startswith(name + " (") or detail.startswith(name + " -> ")):
                continue
            if block.action in ACCESS_ACTIONS:
                continue
            text = ACTION_TEXT.get(block.action, block.action)
            if block.action == "edit" and "(" in detail:
                changes = detail[detail.index("(") + 1:].rstrip(")")
                if "secreto" in changes:
                    text = "Contraseña cambiada"
                elif "2FA" in changes:
                    text = "Código 2FA cambiado"
                elif "nombre" in changes:
                    text = "Renombrada"
            rows.append((text, fmt_date(block.timestamp)))
            if len(rows) >= 6:
                break
        return rows

    def _refresh_card_selection(self) -> None:
        self._list_panel.refresh_selection(self._list_vm.state.selected_name)

    def _select_after_reload(self, name: str) -> None:
        self._list_vm.set_selection(name)
        self._reload()
        for i in range(self.list.count()):
            item = self.list.item(i)
            view = item.data(Qt.UserRole)
            if view and view.name == name:
                self.list.setCurrentItem(item)
                self._show_detail(view)
                return
        view = next((v for v in self._all_views if v.name == name), None)
        self._show_detail(view)

    # ================================================================ alerts / health
    def _alerts(self) -> dict:
        report = self._health
        if report is None:
            return {}
        out: dict[str, RowAlert] = {}
        for name, count in getattr(report, "breached", ()):
            out[name] = RowAlert("danger", "Filtrada", "Filtrada",
                                 f"Aparece en {thousands(count)} filtraciones públicas (Have I Been Pwned). "
                                 "Cámbiala en el sitio y aquí.", "Cambiar contraseña", "generate")
        for group in getattr(report, "reused", ()):
            for name in group:
                if name in out:
                    continue
                others = [n for n in group if n != name]
                out[name] = RowAlert("warning", "Reutilizada", "Reutilizada",
                                     f"La misma contraseña está en {join_names(others)}. Si una se filtra, "
                                     f"caen las {count_word(len(group))}.", "Generar una nueva", "generate")
        bits = dict(getattr(report, "weak_bits", ()))
        for name in getattr(report, "weak", ()):
            out.setdefault(name, RowAlert("warning", "Débil", "Débil",
                                          f"{bits.get(name, 0)} bits: se adivina rápido. Una frase de 5 palabras "
                                          "la lleva a más de 60.", "Generar una nueva", "generate"))
        policy_months = max(1, self._settings.old_password_days // 30)
        for name, days in getattr(report, "old", ()):
            out.setdefault(name, RowAlert("warning", "Antigua", "Antigua",
                                          f"{days // 30} meses sin cambios; tu política de rotación es de "
                                          f"{policy_months}.", "Rotar ahora", "generate"))
        return out

    def _alert_action(self, key: str) -> None:
        if key == "generate":
            self._edit_entry(focus="generate")
        else:
            self._edit_entry()

    def _start_background_warmups(self) -> None:
        """Housekeeping after first paint: expire old trash."""
        if self._locked:
            return
        try:
            purged = self._session.purge_expired_trash(self._settings.trash_retention_days)
        except Exception:
            purged = []
        if purged:
            self._reload()
            self._toasts.show(f"{plural(len(purged), 'entrada', 'entradas')} salieron de la papelera",
                              f"Llevaban más de {self._settings.trash_retention_days} días.", icon_name="trash")

    def _start_background_health_warmup(self):
        """Compute the health report off the GUI thread after first paint.

        Optional and defensive: the window must never fail because the scan
        could not start. The result feeds the sidebar card, the list badges
        and the detail banner.
        """
        if self._health_worker_owner is not None or self._locked:
            return
        try:
            from .background import start_health_scan
            from .performance import background_health_warmup_enabled

            if not background_health_warmup_enabled():
                return

            checker = None
            if self._settings.breach_check_online:
                from ....container import build_breach_checker
                checker = build_breach_checker(online=True)

            def _done(result):
                self._health_worker_owner = None
                if self._locked:
                    return
                if getattr(result, "ok", False):
                    if checker is not None:
                        self._breach_checked_at = time.time()
                    self._set_health(result.payload)
                if self._health_dirty:
                    self._health_dirty = False
                    QTimer.singleShot(400, self._start_background_health_warmup)

            self._health_dirty = False
            self._health_worker_owner = start_health_scan(self._session, _done, breach_checker=checker, parent=self,
                                                          old_after_days=self._settings.old_password_days)
        except Exception:
            self._health_worker_owner = None

    def _mark_health_dirty(self) -> None:
        if self._health_worker_owner is not None:
            self._health_dirty = True
        elif self._health is not None:
            QTimer.singleShot(300, self._start_background_health_warmup)

    def _set_health(self, report) -> None:
        self._health = report
        self._health_report_cache = report
        self._sidebar.health_card.set_report(report.score, report.warning_count)
        page = self._stack.currentWidget()
        if hasattr(page, "set_report"):
            page.set_report(report, self._breach_checked_at)
        self._apply_filter()
        if self._current is not None and not self._revealed:
            current = next((v for v in self._all_views if v.name == self._current.name), None)
            if current is not None:
                self._show_detail(current)

    # ================================================================ secrets
    def _identity(self) -> EnterpriseIdentity:
        s = self._settings
        return EnterpriseIdentity(user_id=s.enterprise_user_id, display_name=s.enterprise_display_name,
                                  role=s.enterprise_role, device_id=s.local_device_id,
                                  device_trusted=s.local_device_id in s.trusted_device_ids,
                                  mfa_verified=True).normalized()

    def _policy_context(self, view=None, **extra) -> dict:
        s = self._settings
        view = view or self._current
        ctx = {"identity": self._identity(), "role": s.enterprise_role, "device_id": s.local_device_id,
               "device_trusted": s.local_device_id in s.trusted_device_ids, "mfa_verified": True}
        if view is not None:
            ctx.update({"sensitivity": getattr(view, "sensitivity", "standard"),
                        "allowed_groups": getattr(view, "allowed_groups", ()),
                        "has_totp": getattr(view, "has_totp", False),
                        "team_vault": getattr(view, "team_vault", "Personal"),
                        "category": getattr(view, "category", "")})
        ctx.update(extra)
        return ctx

    def _allowed(self, action: str, view=None, **extra) -> bool:
        decision = self._policy.evaluate(action, self._policy_context(view, **extra))
        if not decision.allowed:
            notify(self, "Bloqueado por una política", POLICY_TEXT.get(decision.code, starter_rule_text(decision.reason)),
                   tone="warning")
        return decision.allowed

    def _toggle_reveal(self) -> None:
        if not self._current or self._current.deleted:
            return
        if self._revealed:
            self._hide_secret()
            return
        if not self._allowed("reveal_secret"):
            return
        self._revealed = True
        self._reveal_left = self._settings.reveal_hide_seconds
        self._detail.set_revealed(self._session.reveal(self._current.name), self._reveal_left or None)
        self._log_access("reveal", self._current.name)

    def _hide_secret(self) -> None:
        if self._revealed:
            self._revealed = False
            self._detail.set_revealed(None)

    def _copy(self, text: str, title: str, action: str, name: str) -> None:
        seconds = self._settings.clipboard_clear_seconds
        self._clip.copy(text, seconds, self._settings.exclude_clipboard_history)
        self._toasts.show(title, "Se borra del portapapeles en {s} s", icon_name="copy", action_text="Borrar ya",
                          on_action=self._clear_clipboard_now, countdown=seconds, key="clipboard")
        self._log_access(action, name)

    def _clear_clipboard_now(self) -> None:
        self._clip.clear_if_ours()

    def _copy_secret(self) -> None:
        view = self._current
        if view is None or view.deleted:
            return
        if not self._allowed("copy_secret", view, revealed=self._revealed):
            return
        what = {"api_key": "Clave", "card": "Número", "note": "Nota"}.get(view.kind, "Contraseña")
        self._copy(self._session.reveal(view.name), f"{what} de {view.name} copiada", "copy", view.name)

    def _copy_user(self) -> None:
        view = self._current
        if view is None or not view.username:
            return
        self._clipboard.setText(view.username)
        self._toasts.show("Usuario copiado", view.username, icon_name="user", key="clipboard-user")

    def _copy_code(self) -> None:
        view = self._current
        if view is None or not view.has_totp or view.deleted:
            return
        code = self._session.current_code(view.name)
        if code:
            self._copy(code[0], f"Código 2FA de {view.name} copiado", "copy-totp", view.name)

    def _log_access(self, action: str, name: str) -> None:
        if not self._settings.log_secret_access:
            return
        try:
            self._session.log_access(action, name)
        except VaultConflictError as exc:
            self._conflict(exc)
        except Exception:
            pass

    def _generate_and_copy(self) -> None:
        password, _label = self._session.generate()
        self._clip.copy(password, self._settings.clipboard_clear_seconds, self._settings.exclude_clipboard_history)
        self._toasts.show("Contraseña nueva copiada", "Se borra del portapapeles en {s} s", icon_name="key",
                          action_text="Borrar ya", on_action=self._clear_clipboard_now,
                          countdown=self._settings.clipboard_clear_seconds, key="clipboard")

    def _open_url(self) -> None:
        if self._current is None:
            return
        url = safe_web_url(self._current.url)
        if url:
            QDesktopServices.openUrl(QUrl(url))
        else:
            self._toasts.show("No se abre esa dirección", "Solo se abren enlaces http y https.", tone="warning",
                              icon_name="warning")

    # ================================================================ tick
    def _tick(self) -> None:
        if self._locked:
            return
        self._check_auto_lock()
        if self._locked:
            return
        if self._revealed and self._reveal_left:
            self._reveal_left -= 1
            if self._reveal_left <= 0:
                self._hide_secret()
            else:
                self._detail.set_revealed(self._detail.secret_lbl.text(), self._reveal_left)
        self._tick_totp()

    def _tick_totp(self) -> None:
        view = self._current
        if view is None or not view.has_totp or view.deleted:
            return
        try:
            code = self._session.current_code(view.name)
        except Exception:
            return
        if code:
            self._detail.set_code(code[0], code[1])

    def _remaining_lock(self) -> int | None:
        timeout = self._settings.auto_lock_seconds
        if timeout <= 0:
            return None
        return max(0, int(timeout - (time.monotonic() - self._last_activity)))

    def _check_auto_lock(self) -> None:
        remaining = self._remaining_lock()
        for pill in self._pills:
            try:
                pill.set_remaining(remaining, LOCK_WARN_S)
            except RuntimeError:
                pass
        if remaining is not None and remaining <= 0:
            self.lock_now("idle")

    # ================================================================ entry actions
    def _new_entry(self, category: str | None = None, name: str | None = None) -> None:
        from .screens.editor import EntryEditor
        dlg = EntryEditor(self._session, self, settings=self._settings, category=category, name=name,
                          categories=self._category_names())
        accepted = dlg.exec()
        if dlg.conflict is not None:
            self._conflict(dlg.conflict)
            return
        if accepted and dlg.saved_name:
            self._show_page(0)
            self._list_vm.set_section("Vault")
            self._list_vm.set_category(ALL_CATEGORIES)
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)
            self._list_vm.set_query("")
            self._select_after_reload(dlg.saved_name)
            self._toasts.show("Entrada guardada", dlg.saved_name, tone="success", icon_name="check")

    def _edit_entry(self, focus: str | None = None) -> None:
        view = self._current
        if view is None or view.deleted:
            return
        from .screens.editor import EntryEditor
        self._hide_secret()
        dlg = EntryEditor(self._session, self, settings=self._settings, view=view, focus=focus,
                          categories=self._category_names())
        accepted = dlg.exec()
        if dlg.conflict is not None:
            self._conflict(dlg.conflict)
            return
        if accepted and dlg.saved_name:
            self._select_after_reload(dlg.saved_name)
            self._toasts.show("Cambios guardados", dlg.saved_name, tone="success", icon_name="check")

    def _category_names(self) -> list:
        return sorted({v.category for v in self._all_views if v.category and not v.deleted}, key=str.lower)

    def _new_category(self) -> None:
        from .screens.secondary import ask_text
        name = ask_text(self, "Nueva categoría", "Una categoría existe mientras tenga entradas: crea la primera.",
                        "Nombre de la categoría", "Crear y añadir entrada")
        if name:
            self._new_entry(category=name)

    def _toggle_favorite(self) -> None:
        view = self._current
        if view is None:
            return
        self._mutate(lambda: self._session.toggle_favorite(view.name))
        self._select_after_reload(view.name)

    def _trash_entry(self) -> None:
        view = self._current
        if view is None:
            return
        if view.deleted:
            self._purge_entry()
            return
        if not self._mutate(lambda: self._session.remove(view.name)):
            return
        self._list_vm.set_selection(None)
        self._reload()
        self._show_detail(None)
        self._toasts.show(f"«{view.name}» está en la papelera", "Puedes restaurarla durante "
                          f"{self._settings.trash_retention_days or 'todos los'} días.", icon_name="trash",
                          action_text="Deshacer", on_action=lambda n=view.name: self._restore_by_name(n))

    def _restore_by_name(self, name: str) -> None:
        if self._mutate(lambda: self._session.restore(name)):
            self._select_after_reload(name)

    def _restore_entry(self) -> None:
        view = self._current
        if view is None:
            return
        if self._mutate(lambda: self._session.restore(view.name)):
            self._list_vm.set_section("Vault")
            self._select_after_reload(view.name)
            self._toasts.show("Entrada restaurada", view.name, tone="success", icon_name="check")

    def _purge_entry(self) -> None:
        view = self._current
        if view is None or not view.deleted:
            return
        if not self._allowed("purge_secret", view):
            return
        if not confirm(self, f"¿Borrar «{view.name}» para siempre?",
                       "Se elimina del archivo de la bóveda. Las copias de seguridad anteriores la conservan hasta "
                       "que se renueven.", "Borrar para siempre", items=[view.name], type_word="BORRAR"):
            return
        if self._mutate(lambda: self._session.purge(view.name)):
            self._list_vm.set_selection(None)
            self._reload()
            self._show_detail(None)

    def _empty_trash(self) -> None:
        trashed = [v for v in self._all_views if v.deleted]
        if not trashed:
            return
        n = len(trashed)
        if not confirm(self, f"¿Borrar {plural(n, 'entrada', 'entradas')} para siempre?",
                       "Se eliminan del archivo de la bóveda. No se pueden recuperar, ni siquiera con los "
                       "fragmentos Shamir.", f"Borrar {plural(n, 'entrada', 'entradas')}",
                       items=[v.name for v in trashed[:8]] + ([f"… y {n - 8} más"] if n > 8 else []),
                       type_word="BORRAR"):
            return
        for v in trashed:
            if not self._mutate(lambda name=v.name: self._session.purge(name), reload=False):
                break
        self._list_vm.set_selection(None)
        self._reload()
        self._show_detail(None)

    def _mutate(self, action, reload: bool = False) -> bool:
        try:
            action()
        except VaultConflictError as exc:
            self._conflict(exc)
            return False
        except AuthenticationError:
            self.lock_now("expired")
            return False
        except Exception as exc:  # noqa: BLE001 - surfaced to the user
            notify(self, "No se pudo guardar", str(exc), tone="danger")
            return False
        if reload:
            self._reload()
        return True

    def _conflict(self, exc) -> None:
        notify(self, "El archivo cambió en disco", str(exc), tone="warning", button="Bloquear y reabrir")
        self.lock_now("conflict")

    def _entry_menu(self, view, pos) -> None:
        if view is None:
            return
        menu = QMenu(self)
        deleted = view.deleted

        def add(text, handler, shortcut=None, enabled=True, danger=False):
            act = QAction(text, menu)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
                act.setShortcutVisibleInContextMenu(True)
            act.setEnabled(enabled)
            act.triggered.connect(lambda _=False: handler())
            menu.addAction(act)
            return act

        if not deleted:
            add("Copiar usuario", self._copy_user, "Ctrl+B", bool(view.username))
            add("Copiar contraseña", self._copy_secret, "Ctrl+C")
            add("Copiar código 2FA", self._copy_code, "Ctrl+T", view.has_totp)
            add("Abrir URL", self._open_url, enabled=bool(safe_web_url(view.url)))
            menu.addSeparator()
            add("Editar", self._edit_entry, "Ctrl+E")
            move = menu.addMenu("Mover a categoría")
            for cat in self._category_names():
                act = move.addAction(cat)
                act.setEnabled(cat != view.category)
                act.triggered.connect(lambda _=False, c=cat: self._move_to_category(view.name, c))
            move.addSeparator()
            move.addAction("Nueva categoría…", lambda: self._move_to_new_category(view.name))
            add("Compartir…", lambda: self._share_entry(view))
            add("Marcar como rotada", lambda: self._mark_rotated(view.name))
            menu.addSeparator()
            add("Mover a la papelera", self._trash_entry, "Del")
        else:
            add("Restaurar", self._restore_entry)
            add("Borrar para siempre…", self._purge_entry)
        menu.exec(pos)

    def _move_to_category(self, name: str, category: str) -> None:
        if self._mutate(lambda: self._session.update(name, category=category)):
            self._select_after_reload(name)

    def _move_to_new_category(self, name: str) -> None:
        from .screens.secondary import ask_text
        category = ask_text(self, "Mover a una categoría nueva", "", "Nombre de la categoría", "Mover")
        if category:
            self._move_to_category(name, category)

    def _mark_rotated(self, name: str) -> None:
        if self._mutate(lambda: self._session.mark_rotated(name)):
            self._select_after_reload(name)

    # ================================================================ pages
    def _show_page(self, index: int) -> None:
        if index == 0 and self._stack.currentIndex() != 0:
            old = self._stack.currentWidget()
            self._stack.setCurrentIndex(0)
            if old is not None and self._stack.indexOf(old) > 0:
                self._stack.removeWidget(old)
                old.deleteLater()
            self._pills = [self._topbar.lock_pill]
            self._reload()

    def _push_page(self, page: QWidget) -> None:
        self._hide_secret()
        while self._stack.count() > 1:
            w = self._stack.widget(1)
            self._stack.removeWidget(w)
            w.deleteLater()
        self._stack.addWidget(page)
        self._stack.setCurrentWidget(page)
        pill = getattr(page, "lock_pill", None)
        self._pills = [self._topbar.lock_pill] + ([pill] if pill is not None else [])
        self._check_auto_lock()

    def _page_callbacks(self) -> dict:
        return {"back": lambda: self._show_page(0), "lock": lambda: self.lock_now("manual")}

    def _open_health(self) -> None:
        from .screens.health import HealthPage
        if self._health is None and self._health_worker_owner is None:
            try:   # offline analysis is fast; the online breach check stays in the background
                self._health = self._session.health_report(old_after_days=self._settings.old_password_days)
                self._sidebar.health_card.set_report(self._health.score, self._health.warning_count)
            except Exception:
                self._health = None
        page = HealthPage(self._session, self._settings, self._health, self._page_callbacks(),
                          on_fix=self._fix_from_health, on_recheck=self._recheck_breaches,
                          on_policies=self._open_settings, checked_at=self._breach_checked_at)
        self._push_page(page)
        if self._health is not None and self._settings.breach_check_online and self._breach_checked_at is None:
            self._start_background_health_warmup()

    def _fix_from_health(self, name: str, key: str) -> None:
        self._show_page(0)
        self._list_vm.set_section("Vault")
        self._list_vm.set_category(ALL_CATEGORIES)
        self._select_after_reload(name)
        if key in ("generate", "edit"):
            self._edit_entry(focus="generate")
        elif key == "totp":
            self._edit_entry(focus="totp")

    def _recheck_breaches(self, page=None) -> None:
        if not self._settings.breach_check_online:
            notify(self, "Comprobación de filtraciones desactivada",
                   "Actívala en Ajustes › Privacidad y red. Solo salen los 5 primeros caracteres del hash SHA-1 "
                   "de cada contraseña, nunca la contraseña.", tone="info")
            return
        self._start_background_health_warmup()
        self._toasts.show("Comprobando filtraciones…", "Se consulta el rango k-anónimo de Have I Been Pwned.",
                          icon_name="sync")

    def _open_audit(self, filter_text: str = "", verify: bool = False) -> None:
        from .screens.audit import AuditPage
        page = AuditPage(self._session, self._page_callbacks(), filter_text=filter_text,
                         on_export=self._show_siem, on_rotate=self._rotate_password,
                         on_restore=self._restore_snapshot)
        self._push_page(page)
        if verify:
            page.verify(announce=True)

    def _open_settings(self) -> None:
        from .screens.settings import SettingsPage
        page = SettingsPage(self._session, self._settings, self._settings_store, self._page_callbacks(),
                            actions={"rotate": self._rotate_password, "shamir": self._enroll_recovery,
                                     "policies": self._show_policies, "access": self._show_access,
                                     "directory": self._show_directory, "sync": self._show_sync,
                                     "snapshot": self._snapshot_now, "agent": self._show_agent,
                                     "passkey": self._show_passkey, "share_keys": self._share_keys},
                            on_saved=self._settings_saved)
        self._push_page(page)

    def _settings_saved(self, settings) -> None:
        self._settings = settings.normalized()
        self._policy = PolicyEngine(self._settings)
        self._sidebar.health_card.setVisible(self._settings.show_health_sidebar)
        repo = getattr(self._session._service, "_repo", None)
        if repo is not None and hasattr(repo, "configure_backups"):
            repo.configure_backups(self._settings.backup_dir or "", self._settings.keep_backups)
        self._last_activity = time.monotonic()

    # ================================================================ dialogs
    def _show_command_palette(self) -> None:
        from .screens.palette import CommandPalette
        CommandPalette(self, self._all_views, self._execute_command).exec()

    def _execute_command(self, command_id: str, payload=None) -> None:
        if command_id == "entry" and payload:
            self._jump_to_entry(str(payload))
            return
        handlers = {
            "new": self._new_entry, "generate": self._generate_and_copy, "lock": lambda: self.lock_now("manual"),
            "sync": self._show_sync, "verify": lambda: self._open_audit(verify=True), "health": self._open_health,
            "audit": lambda: self._open_audit(), "settings": self._open_settings, "share": self._open_shared_center,
            "siem": self._show_siem, "shamir": self._enroll_recovery, "rotate": self._rotate_password,
            "import": self._import_entries, "policies": self._show_policies, "access": self._show_access,
            "agent": self._show_agent, "passkey": self._show_passkey, "trash": lambda: self._set_section("Trash"),
            "favorites": lambda: self._set_section("Favorites"), "share_entry": self._share_current,
            "theme": self._toggle_theme,
        }
        handler = handlers.get(command_id)
        if handler is not None:
            handler()

    def _jump_to_entry(self, name: str) -> None:
        self._show_page(0)
        self._list_vm.set_section("Vault")
        self._list_vm.reset_filters()
        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)
        self._select_after_reload(name)
        self.list.setFocus()

    def _share_entry(self, view=None) -> None:
        view = view or self._current
        if view is None or view.deleted:
            return
        if not self._allowed("share_secret", view):
            return
        from .screens.share import ShareDialog
        if ShareDialog(self._session, view, self._settings, self).exec():
            self._select_after_reload(view.name)
            self._toasts.show("Sobre cifrado creado", f"«{view.name}» compartida. Queda en la auditoría.",
                              tone="success", icon_name="check")

    def _share_current(self) -> None:
        if self._current is None or self._current.deleted:
            self._toasts.show("Elige primero una entrada", "Compartir cifra una entrada concreta para otra persona.",
                              tone="info", icon_name="info")
            return
        self._share_entry(self._current)

    def _toggle_theme(self) -> None:
        from dataclasses import replace

        from .theme import PALETTE
        target = "light" if PALETTE.MODE == "dark" else "dark"
        self._settings = replace(self._settings, theme=target).normalized()
        self._settings_store.save(self._settings)
        word = "claro" if target == "light" else "oscuro"
        self._toasts.show(f"Modo {word} guardado", "Se aplica la próxima vez que abras AegisVault.",
                          tone="info", icon_name="theme")

    def _open_shared_center(self) -> None:
        from .screens.share import SharedCenter
        SharedCenter(self._session, self._settings, self, on_share=self._share_entry,
                     on_rotate=self._rotate_entry_after_revoke).exec()
        self._reload()

    def _rotate_entry_after_revoke(self, name: str) -> None:
        self._jump_to_entry(name)
        if self._current is not None and self._current.name == name:
            self._edit_entry(focus="generate")

    def _share_keys(self) -> None:
        from .screens.share import KeysDialog
        KeysDialog(self._session, self._settings, self).exec()

    def _show_siem(self) -> None:
        from .screens.secondary import SiemDialog
        SiemDialog(self._session, self._settings, self._policy_context, self._policy, self).exec()

    def _show_sync(self) -> None:
        from .screens.secondary import SyncDialog
        dlg = SyncDialog(self._session, self._settings, self)
        dlg.exec()
        if getattr(dlg, "replaced", False):
            self.lock_now("sync-import")

    def _show_policies(self) -> None:
        from .screens.secondary import PoliciesDialog
        dlg = PoliciesDialog(self._settings, self._settings_store, self)
        if dlg.exec():
            self._settings_saved(dlg.settings)

    def _show_access(self) -> None:
        from .screens.secondary import AccessDialog
        dlg = AccessDialog(self._settings, self._settings_store, self._session, self,
                           on_audit=lambda: self._open_audit(filter_text="acceso"))
        dlg.exec()
        self._settings_saved(dlg.settings)

    def _show_directory(self) -> None:
        from .screens.secondary import DirectoryDialog
        dlg = DirectoryDialog(self._settings, self._settings_store, self)
        dlg.exec()
        self._settings_saved(dlg.settings)

    def _show_agent(self) -> None:
        from .screens.secondary import AgentDialog
        AgentDialog(self, vault_path=self._vault_path).exec()

    def _show_passkey(self) -> None:
        from .screens.secondary import PasskeyDialog
        PasskeyDialog(self).exec()

    def _enroll_recovery(self) -> None:
        from .screens.shamir import EnrollShamirDialog
        EnrollShamirDialog(self._session, self._vault_label(), self).exec()
        self._reload()

    def _rotate_password(self) -> None:
        from .screens.rotate import RotateMasterDialog
        dlg = RotateMasterDialog(self._session, self)
        if dlg.exec() and dlg.rotated:
            self._toasts.show("Contraseña maestra cambiada", "Desde ahora solo la nueva abre este archivo.",
                              tone="success", icon_name="check")
            self._reload()

    def _import_entries(self) -> None:
        from .screens.secondary import ImportDialog
        dlg = ImportDialog(self._session, self)
        if dlg.exec() and dlg.imported:
            self._reload()
            self._toasts.show(f"{plural(dlg.imported, 'entrada importada', 'entradas importadas')}",
                              "Ya están cifradas en la bóveda. Borra el archivo de origen.", tone="success",
                              icon_name="check")

    def _restore_snapshot(self) -> None:
        from .screens.secondary import RestoreSnapshotDialog
        dlg = RestoreSnapshotDialog(self._session, self)
        if dlg.exec() and dlg.restored:
            self.lock_now("restore")

    def _snapshot_now(self) -> None:
        try:
            path = self._session.snapshot("manual")
        except Exception as exc:  # noqa: BLE001
            self._toasts.show("No se pudo escribir la copia", str(exc), tone="danger", icon_name="alert",
                              action_text="Reintentar", on_action=self._snapshot_now)
            return
        if path:
            self._toasts.show("Copia guardada", path, tone="success", icon_name="check")

    def _reveal_vault_file(self) -> None:
        from pathlib import Path
        if self._vault_path:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._vault_path).resolve().parent)))

    # ================================================================ locking
    def lock_now(self, reason: str = "manual") -> None:
        """Wipe the session and hand control back to the unlock screen."""
        if self._locked:
            return
        self._locked = True
        self._timer.stop()
        self._filter_timer.stop()
        cleared = self._clip.clear_if_ours()
        try:
            self._detail.set_revealed(None)
        except RuntimeError:
            pass
        try:
            self._toasts.clear()
        except RuntimeError:
            pass
        self._health = None
        self._health_report_cache = None
        self._all_views = []
        self._current = None
        try:
            self._session.lock()
        except Exception:
            pass
        self._last_lock = (reason, cleared)
        if self.on_locked is not None:
            self.on_locked(reason)
        else:
            self.lock_requested.emit(reason)
            self.close()

    @property
    def is_locked(self) -> bool:
        return self._locked

    # ---- Qt plumbing ------------------------------------------------------
    @property
    def secret_lbl(self):
        return self._detail.secret_lbl

    @property
    def code_lbl(self):
        return self._detail.code_lbl

    def eventFilter(self, obj, event):  # noqa: N802 - Qt API
        # Installed on the whole application, so it sees every event. It never
        # filters, and it returns False itself: handing the event to Qt's base
        # implementation (which only returns False) re-entered this override
        # during interpreter shutdown until the stack ran out.
        if event.type() in (QEvent.MouseButtonPress, QEvent.KeyPress, QEvent.Wheel, QEvent.TouchBegin):
            self._last_activity = time.monotonic()
        return False

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        compact = compact_for(self.width())
        self._topbar.set_compact(compact)
        if compact != getattr(self, "_compact", None):
            self._compact = compact
            self._list_panel.cat_btn.set_label(self._category_label(self._list_vm.state.category))

    def changeEvent(self, event):  # noqa: N802 - Qt API
        if (event.type() == QEvent.WindowStateChange and self.isMinimized()
                and self._settings.lock_on_minimize and not self._locked):
            QTimer.singleShot(0, lambda: self.lock_now("minimize"))
        super().changeEvent(event)

    def showEvent(self, event):  # noqa: N802 - Qt API
        super().showEvent(event)
        self._register_session_events()

    def _register_session_events(self) -> None:
        """Ask Windows to tell us when the session locks (Win+L) or the PC sleeps."""
        if sys.platform != "win32" or self._wts_registered:
            return
        try:
            import ctypes
            hwnd = int(self.winId())
            if ctypes.WinDLL("wtsapi32").WTSRegisterSessionNotification(ctypes.c_void_p(hwnd), 0):
                self._wts_registered = True
        except Exception:
            self._wts_registered = False

    def nativeEvent(self, event_type, message):  # noqa: N802 - Qt API
        try:
            if (sys.platform == "win32" and not self._locked and self._settings.lock_on_screen_lock
                    and bytes(event_type) == b"windows_generic_MSG"):
                import ctypes.wintypes
                msg = ctypes.wintypes.MSG.from_address(int(message))
                if msg.message == 0x02B1 and msg.wParam == 0x7:        # WM_WTSSESSION_CHANGE / WTS_SESSION_LOCK
                    QTimer.singleShot(0, lambda: self.lock_now("screen-lock"))
                elif msg.message == 0x0218 and msg.wParam == 0x4:      # WM_POWERBROADCAST / PBT_APMSUSPEND
                    QTimer.singleShot(0, lambda: self.lock_now("suspend"))
        except Exception:
            pass
        return False, 0

    def closeEvent(self, event):  # noqa: N802 - Qt API
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        if self._wts_registered:
            try:
                import ctypes
                ctypes.WinDLL("wtsapi32").WTSUnRegisterSessionNotification(ctypes.c_void_p(int(self.winId())))
            except Exception:
                pass
            self._wts_registered = False
        if not self._locked:
            self._locked = True
            self._timer.stop()
            self._clip.clear_if_ours()
            try:
                self._session.lock()
            except Exception:
                pass
        super().closeEvent(event)


def _search_text(view) -> str:
    tags = getattr(view, "tags", ()) or ()
    return f"{view.name} {view.username} {view.url} {' '.join(map(str, tags))}".lower()

