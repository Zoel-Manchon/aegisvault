"""Modern AegisVault window with a modular enterprise dashboard shell."""
from __future__ import annotations

import time

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QMenu, QWidget

from ....application.services.policy import PolicyEngine
from ....application.services.settings import MemorySettingsStore
from .branding import PRODUCT_NAME
from .components.dashboard import DashboardRenderer
from .components.main_shell import MainShellView
from .controllers import VaultActionsController
from .view_models.navigation import ALL_CATEGORY_LABEL, AppNavigationRouter
from .view_models.vault_list import VaultListViewModel
from .view_models.zero_trust import build_zero_trust_dashboard_model
from .view_models.command_palette import DEFAULT_ACTIONS, build_command_index, PaletteCommand

CLIPBOARD_CLEAR_MS = 15_000


class MainWindow(QWidget):
    def __init__(self, session, clipboard, settings_store=None):
        super().__init__()
        self._session = session
        self._clipboard = clipboard
        self._settings_store = settings_store or MemorySettingsStore()
        self._settings = self._settings_store.load()
        self._policy = PolicyEngine(self._settings)
        self._actions = VaultActionsController(self)
        self._last_activity = time.monotonic()
        self._locked = False
        self._current = None
        self._revealed = False
        self._all_views = []
        self._list_vm = VaultListViewModel()
        self._router = AppNavigationRouter()
        self._sidebar_buttons = []
        self._favicon_worker_owner = None
        self._health_worker_owner = None
        self._health_report_cache = None

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

        self.setObjectName("appShell")
        self.setWindowTitle(f"{PRODUCT_NAME} · Zero Trust Secrets")
        self.resize(1240, 780)
        self.setMinimumSize(1040, 660)

        self._shell = MainShellView(
            primary_actions=(
                ("Command", "search", "accent", self._show_command_palette),
                ("Sharing", "users", "signal", self._open_sharing_center),
                ("SIEM", "shield", "signal", self._show_siem_console),
                ("Sync", "rotate", "muted", self._show_sync_bundle),
                ("Verify", "shield", "accent", self._verify),
            ),
            more_actions=(
                ("History", self._show_history),
                ("Recovery shares", self._enroll_recovery),
                ("Rotate master password", self._rotate_password),
                ("Health report", self._show_health),
                ("Browser autofill agent", self._show_autofill_agent),
                ("Passkey unlock", self._show_passkey_unlock),
                ("Quick start guide", self._show_quick_guide),
            ),
            sections=(
                ("Vault", "vault"),
                ("Categories", "grid"),
                ("Favorites", "star"),
                ("Zero Trust", "shield"),
                ("Shared", "users"),
                ("Trash", "trash"),
            ),
            current_section="Vault",
            show_health=self._settings.show_health_sidebar,
            on_section_select=self._set_section,
            on_settings=self._show_settings,
            list_callbacks={
                "on_add": self._add_entry,
                "on_category_menu": self._open_category_menu,
                "on_toggle_sort": self._toggle_sort,
                "on_clear_filters": self._clear_filters,
                "on_filter_changed": self._schedule_filter,
                "on_select": self._on_select,
            },
            detail_callbacks={
                "on_reveal": self._toggle_reveal,
                "on_copy": self._copy_secret,
                "on_favorite": self._toggle_favorite,
                "on_share": self._share_entry,
                "on_restore": self._restore_entry,
                "on_delete": self._delete_entry,
            },
        )
        from PySide6.QtWidgets import QVBoxLayout  # local import keeps module imports slim for headless tests
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._shell)
        self._bind_shell_aliases()

        self._dashboard = DashboardRenderer(
            self.features_layout,
            on_category_selected=self._filter_category,
            zero_trust_actions=(
                ("Sharing Center", "Create, list, revoke grants", "users", self._open_sharing_center),
                ("Policy Pack", "Edit deny rules", "shield", self._show_policy_pack),
                ("Access Requests", "Approve JIT access", "key", self._show_access_requests),
                ("Directory", "Users, keys, devices", "vault", self._show_directory),
                ("Live SIEM", "Audit stream and export", "history", self._show_siem_console),
                ("Sync Gateway", "Encrypted bundle + delivery", "rotate", self._show_sync_bundle),
            ),
            on_audit_export=lambda fmt: self._export_audit(self, fmt),
        )

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)

        self._filter_timer = QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(90)
        self._filter_timer.timeout.connect(self._apply_filter)

        self._install_shortcuts()
        self._reload()
        self._show_detail(None)
        QTimer.singleShot(350, self._start_background_warmups)
        QTimer.singleShot(900, self._start_background_health_warmup)


    def _install_shortcuts(self) -> None:
        for sequence in ("Ctrl+K", "Meta+K"):
            shortcut = QShortcut(QKeySequence(sequence), self)
            shortcut.activated.connect(self._show_command_palette)

    def _show_command_palette(self) -> None:
        from .command_palette import CommandPaletteDialog

        commands = build_command_index(self._all_views, DEFAULT_ACTIONS)
        CommandPaletteDialog(commands, self._execute_command, self).exec()

    def _execute_command(self, command: PaletteCommand) -> None:
        command_id = command.id
        if command.kind == "entry" and command.payload:
            self._jump_to_entry(str(command.payload))
            return
        actions = {
            "action:add": self._add_entry,
            "action:sharing": self._open_sharing_center,
            "action:zero-trust": lambda: self._set_section("Zero Trust"),
            "action:siem": self._show_siem_console,
            "action:policy": self._show_policy_pack,
            "action:directory": self._show_directory,
            "action:sync": self._show_sync_bundle,
            "action:access": self._show_access_requests,
            "action:agent": self._show_autofill_agent,
            "action:passkey": self._show_passkey_unlock,
            "action:health": self._show_health,
            "action:settings": self._show_settings,
            "action:guide": self._show_quick_guide,
        }
        handler = actions.get(command_id)
        if handler is not None:
            handler()

    def _jump_to_entry(self, entry_name: str) -> None:
        self._list_vm.set_section("Vault")
        self._list_vm.reset_filters()
        self.search.setText(entry_name)
        self._list_vm.set_query(entry_name)
        self.cat_btn.setText(f"{ALL_CATEGORY_LABEL}  ˅")
        self._list_vm.set_selection(entry_name)
        self._sync_sidebar("Vault")
        self._apply_filter()
        for i in range(self.list.count()):
            item = self.list.item(i)
            view = item.data(Qt.UserRole)
            if view and view.name == entry_name:
                self.list.setCurrentItem(item)
                self._show_detail(view)
                break

    def _bind_shell_aliases(self) -> None:
        """Expose stable widget aliases used by controllers and smoke tests."""

        self._sidebar = self._shell.sidebar
        self._sidebar_buttons = self._sidebar.nav_buttons
        self._health_card = self._sidebar.health_card

        self._list_panel = self._shell.list_panel
        self.search = self._list_panel.search
        self.cat_btn = self._list_panel.cat_btn
        self.sort_btn = self._list_panel.sort_btn
        self.list = self._list_panel.list
        self.count_lbl = self._list_panel.count_lbl
        self.page_row = self._list_panel.page_row

        self._detail_panel = self._shell.detail_panel
        for name in (
            "empty_art", "empty_card", "name_lbl", "user_lbl", "url_lbl",
            "features", "features_layout", "content", "secret_lbl",
            "reveal_btn", "copy_btn", "totp_title", "code_lbl", "code_bar",
            "favorite_btn", "share_btn", "restore_btn", "del_btn",
        ):
            setattr(self, name, getattr(self._detail_panel, name))

    def _refresh_categories(self):
        """Rebuild the right-side dashboard for the active route."""

        if self._list_vm.state.section == "Zero Trust":
            model = build_zero_trust_dashboard_model(self._session, self._settings, self._all_views)
            self._dashboard.render_zero_trust(model)
            return
        self._dashboard.render_vault_overview(self._list_vm.overview(self._all_views))

    def _filter_category(self, name: str):
        route = self._router.open_category(name)
        self._list_vm.filter_category_from_dashboard(route.category)
        self._sync_sidebar(route.section)
        self.cat_btn.setText(f"{route.category}  ˅")
        if route.clear_selection:
            self.list.clearSelection()
        self._show_detail(None)
        self._apply_filter()

    def _open_category_menu(self):
        menu = QMenu(self)
        for cat in self._categories():
            act = menu.addAction(cat)
            act.triggered.connect(lambda _=False, c=cat: self._pick_category(c))
        menu.exec(self.cat_btn.mapToGlobal(self.cat_btn.rect().bottomLeft()))

    def _pick_category(self, cat: str):
        self._list_vm.set_category(cat)
        self.cat_btn.setText(f"{cat}  ˅")
        self._apply_filter()

    def _set_section(self, section: str):
        route = self._router.navigate(section)
        self._list_vm.set_section(route.section)
        self._sync_sidebar(route.section)

        if route.reset_category_filter:
            self.cat_btn.setText(f"{ALL_CATEGORY_LABEL}  ˅")
        if route.clear_selection:
            self.list.clearSelection()
        if route.refresh_overview:
            self._refresh_categories()
            self._show_detail(None)
        self._apply_filter()

    def _sync_sidebar(self, section: str):
        if hasattr(self, "_sidebar"):
            self._sidebar.set_active(section)
        else:
            for name, btn in self._sidebar_buttons:
                btn.setObjectName("sideActive" if name == section else "sideNav")
                btn.style().unpolish(btn)
                btn.style().polish(btn)

    def _categories(self):
        return list(self._list_vm.categories(self._all_views))

    def _cycle_category(self):
        cats = self._categories()
        current = self._list_vm.state.category
        idx = cats.index(current) if current in cats else 0
        self._list_vm.set_category(cats[(idx + 1) % len(cats)])
        self.cat_btn.setText(f"{self._list_vm.state.category}  ˅")
        self._apply_filter()

    def _toggle_sort(self):
        self._list_vm.toggle_sort()
        self._list_panel.set_filter_labels(self._list_vm.state.category, self._list_vm.state.sort)
        self._apply_filter()

    def _clear_filters(self):
        self._list_vm.reset_filters()
        self._list_panel.reset_filters()
        self._apply_filter()

    # ---- list / filter -------------------------------------------------
    def _reload(self):
        self._all_views = self._session.entries()
        self._refresh_categories()
        self._apply_filter()

    def _start_background_warmups(self):
        # Optional and strictly post-render: keep first paint responsive.
        try:
            from .background import start_favicon_prefetch

            urls = [getattr(view, "url", "") for view in self._all_views if getattr(view, "url", "")]
            self._favicon_worker_owner = start_favicon_prefetch(
                urls,
                on_finished=lambda _result: setattr(self, "_favicon_worker_owner", None),
                parent=self,
            )
        except Exception:
            self._favicon_worker_owner = None


    def _start_background_health_warmup(self):
        """Warm the expensive health report after first paint.

        This method is intentionally optional and defensive: launch should never
        fail because a non-critical background health scan could not start. The
        result is cached so opening the Health dialog can render instantly.
        """
        if self._health_worker_owner is not None:
            return
        try:
            from .background import start_health_scan
            from .performance import background_health_warmup_enabled

            if not background_health_warmup_enabled():
                return

            def _cache_health_report(result):
                self._health_worker_owner = None
                if getattr(result, "ok", False):
                    self._health_report_cache = result.payload

            self._health_worker_owner = start_health_scan(
                self._session,
                _cache_health_report,
                parent=self,
            )
        except Exception:
            self._health_worker_owner = None

    def _schedule_filter(self):
        self._filter_timer.start()

    def _apply_filter(self):
        query = self.search.text()
        if query != self._list_vm.state.query:
            self._list_vm.set_query(query)
        self.list.clear()
        result = self._list_vm.page(self._all_views)
        for view in result.entries:
            self._list_panel.add_entry(view, selected=(view.name == result.selected_name))
        self.count_lbl.setText(result.count_label)
        self._render_pagination(result.total_pages)

    def _render_pagination(self, pages: int):
        self._list_panel.render_pagination(current_page=self._list_vm.state.page, pages=pages, on_go_page=self._go_page)

    def _go_page(self, page: int):
        self._list_vm.set_page(page)
        self._apply_filter()

    def _on_select(self, item, _prev=None):
        self._revealed = False
        self.reveal_btn.setText("  Reveal")
        view = item.data(Qt.UserRole) if item else None
        self._list_vm.set_selection(view.name if view else None)
        self._refresh_card_selection()
        self._show_detail(view)

    def _refresh_card_selection(self):
        self._list_panel.refresh_selection(self._list_vm.state.selected_name)

    def _show_detail(self, view):
        self._current = view
        has = view is not None
        if not has:
            section = self._list_vm.state.section
            empty = self._router.empty_state_for(section)
            self._detail_panel.set_empty(section=section, title=empty.title, subtitle=empty.subtitle)
            return

        self._detail_panel.set_entry(view)
        shared = getattr(view, "shared_with", ())
        active_count = getattr(view, "active_share_count", 0)
        revoked_count = getattr(view, "revoked_share_count", 0)
        if active_count or revoked_count:
            extra = f"Crypto grants: {active_count} active · {revoked_count} revoked"
        else:
            extra = f"Shared with: {', '.join(shared)}" if shared else ""
        self.url_lbl.setText("\n".join([x for x in (view.url or "", extra) if x]))
        self.secret_lbl.setText("•" * 14)
        self.favorite_btn.setText("  Unfavorite" if getattr(view, "favorite", False) else "  Favorite")
        is_deleted = bool(getattr(view, "deleted", False))
        self.restore_btn.setVisible(is_deleted)
        self.reveal_btn.setEnabled(not is_deleted)
        self.copy_btn.setEnabled(not is_deleted)
        self.share_btn.setEnabled(not is_deleted)
        self.favorite_btn.setEnabled(not is_deleted)
        self.del_btn.setText("  Delete forever" if is_deleted else "  Move to trash")
        self._set_totp_visible(view.has_totp)
        self._tick()

    # ---- secret --------------------------------------------------------
    def _identity(self):
        return self._actions.identity()

    def _policy_context(self, view=None, **extra):
        return self._actions.policy_context(view, **extra)

    def _toggle_reveal(self):
        self._actions.toggle_reveal()

    def _copy_secret(self):
        self._actions.copy_secret()

    # ---- totp ----------------------------------------------------------
    def _set_totp_visible(self, visible: bool):
        self._detail_panel.set_totp_visible(visible)

    def _tick(self):
        self._check_auto_lock()
        if not self._current or not self._current.has_totp:
            return
        code, remaining = self._session.current_code(self._current.name)
        self.code_lbl.setText(code)
        self.code_bar.setValue(remaining)

    # ---- actions -------------------------------------------------------
    def _add_entry(self):
        self._actions.add_entry()

    def _delete_entry(self):
        self._actions.delete_entry()

    def _restore_entry(self):
        self._actions.restore_entry()

    def _toggle_favorite(self):
        self._actions.toggle_favorite()

    def _share_entry(self):
        self._actions.share_entry()

    def _authorize_share_by_name(self, entry_name: str):
        return self._actions.authorize_share_by_name(entry_name)

    def _open_sharing_center(self, entry_view=None):
        self._actions.open_sharing_center(entry_view)

    def _show_history(self):
        self._actions.show_history()

    def _show_siem_console(self):
        self._actions.show_siem_console()

    def _show_sync_bundle(self):
        self._actions.show_sync_bundle()

    def _show_directory(self):
        self._actions.show_directory()

    def _show_access_requests(self):
        self._actions.show_access_requests()

    def _show_policy_pack(self):
        self._actions.show_policy_pack()

    def _enroll_recovery(self):
        self._actions.enroll_recovery()

    def _rotate_password(self):
        self._actions.rotate_password()

    def _verify(self):
        self._actions.verify()

    def _show_settings(self):
        self._actions.show_settings()

    def _show_health(self):
        self._actions.show_health()

    def _show_autofill_agent(self):
        self._actions.show_autofill_agent()

    def _show_passkey_unlock(self):
        self._actions.show_passkey_unlock()

    def _show_quick_guide(self):
        self._actions.show_quick_guide()

    def _export_audit(self, parent, fmt: str):
        self._actions.export_audit(parent, fmt)

    def _export_audit_json(self, parent):
        self._export_audit(parent, "json")

    # ---- session safety --------------------------------------------------
    def eventFilter(self, obj, event):
        if event.type() in {
            QEvent.MouseButtonPress,
            QEvent.MouseButtonDblClick,
            QEvent.KeyPress,
            QEvent.Wheel,
            QEvent.TouchBegin,
        }:
            self._last_activity = time.monotonic()
        return super().eventFilter(obj, event)

    def _check_auto_lock(self):
        self._actions.check_auto_lock()

    def closeEvent(self, event):
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        super().closeEvent(event)
