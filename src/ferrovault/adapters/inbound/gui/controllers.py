"""GUI orchestration controllers for AegisVault.

The widgets stay focused on presentation while this module owns desktop
workflows that combine Qt prompts, policy evaluation, and vault session calls.
"""
from __future__ import annotations

import time
from typing import Any

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import QFileDialog, QMessageBox

from ....application.services.enterprise import EnterpriseIdentity
from ....application.services.policy import PolicyEngine


class VaultActionsController:
    """Coordinates vault actions, policy checks, and Qt user prompts.

    The controller intentionally receives the MainWindow instance. That keeps
    this pass low-risk: UI state still lives on the window, but the action logic
    is no longer mixed into layout construction and rendering code.
    """

    def __init__(self, window: Any):
        self.window = window

    # ---- identity / policy -------------------------------------------
    def identity(self) -> EnterpriseIdentity:
        w = self.window
        trusted = w._settings.local_device_id in w._settings.trusted_device_ids
        return EnterpriseIdentity(
            user_id=w._settings.enterprise_user_id,
            display_name=w._settings.enterprise_display_name,
            role=w._settings.enterprise_role,
            device_id=w._settings.local_device_id,
            device_trusted=trusted,
            mfa_verified=True,
        ).normalized()

    def policy_context(self, view=None, **extra) -> dict[str, Any]:
        w = self.window
        view = view or w._current
        ctx: dict[str, Any] = {
            "identity": self.identity(),
            "role": w._settings.enterprise_role,
            "device_id": w._settings.local_device_id,
            "device_trusted": w._settings.local_device_id in w._settings.trusted_device_ids,
            "mfa_verified": True,
        }
        if view is not None:
            ctx.update({
                "sensitivity": getattr(view, "sensitivity", "standard"),
                "allowed_groups": getattr(view, "allowed_groups", ()),
                "has_totp": getattr(view, "has_totp", False),
                "team_vault": getattr(view, "team_vault", "Personal"),
                "category": getattr(view, "category", ""),
            })
        ctx.update(extra)
        return ctx

    def _refresh_policy(self) -> None:
        w = self.window
        w._settings = w._settings.normalized()
        w._policy = PolicyEngine(w._settings)

    # ---- secret operations -------------------------------------------
    def toggle_reveal(self) -> None:
        w = self.window
        if not w._current:
            return
        w._revealed = not w._revealed
        if w._revealed:
            decision = w._policy.evaluate("reveal_secret", self.policy_context(w._current))
            if not decision.allowed:
                w._revealed = False
                QMessageBox.warning(w, "Policy blocked", decision.reason)
                return
            w.secret_lbl.setText(w._session.reveal(w._current.name))
            w.reveal_btn.setText("  Hide")
        else:
            w.secret_lbl.setText("•" * 14)
            w.reveal_btn.setText("  Reveal")

    def copy_secret(self) -> None:
        w = self.window
        if not w._current:
            return
        decision = w._policy.evaluate("copy_secret", self.policy_context(w._current, revealed=w._revealed))
        if not decision.allowed:
            QMessageBox.warning(w, "Policy blocked", decision.reason)
            return
        w._clipboard.setText(w._session.reveal(w._current.name))
        QTimer.singleShot(w._settings.clipboard_clear_seconds * 1000, w._clipboard.clear)

    # ---- entry lifecycle ---------------------------------------------
    def add_entry(self) -> None:
        from .add_dialog import AddEntryDialog

        w = self.window
        dlg = AddEntryDialog(w._session, w, w._settings)
        if not dlg.exec():
            return
        values = dlg.values()
        if not values["name"] or not values["secret"]:
            QMessageBox.warning(w, "Missing data", "Name and secret/password are required.")
            return
        try:
            w._session.add(**values)
        except Exception as exc:
            QMessageBox.critical(w, "Could not save entry", str(exc))
            return
        self._select_entry_after_reload(values["name"])

    def delete_entry(self) -> None:
        w = self.window
        if not w._current:
            return
        is_deleted = bool(getattr(w._current, "deleted", False))
        title = "Delete forever" if is_deleted else "Move to trash"
        msg = f"Permanently delete {w._current.name}?" if is_deleted else f"Move {w._current.name} to Trash?"
        if QMessageBox.question(w, title, msg) != QMessageBox.Yes:
            return
        if is_deleted:
            decision = w._policy.evaluate("purge_secret", self.policy_context(w._current))
            if not decision.allowed:
                QMessageBox.warning(w, "Policy blocked", decision.reason)
                return
            w._session.purge(w._current.name)
        else:
            w._session.remove(w._current.name)
        w._selected_name = None
        w._reload()
        w._show_detail(None)

    def restore_entry(self) -> None:
        w = self.window
        if not w._current:
            return
        w._session.restore(w._current.name)
        w._selected_name = w._current.name
        w._section = "Vault"
        if hasattr(w, "_sidebar"):
            w._sidebar.set_active("Vault")
        else:
            for name, btn in w._sidebar_buttons:
                btn.setObjectName("sideActive" if name == "Vault" else "sideNav")
                btn.style().unpolish(btn)
                btn.style().polish(btn)
        w._reload()

    def toggle_favorite(self) -> None:
        w = self.window
        if not w._current:
            return
        w._session.toggle_favorite(w._current.name)
        self._select_entry_after_reload(w._current.name)

    def share_entry(self) -> None:
        w = self.window
        if w._current:
            self.open_sharing_center(w._current)

    def _select_entry_after_reload(self, entry_name: str) -> None:
        w = self.window
        w._selected_name = entry_name
        w._reload()
        for i in range(w.list.count()):
            item = w.list.item(i)
            view = item.data(Qt.UserRole)
            if view and view.name == w._selected_name:
                w.list.setCurrentItem(item)
                w._show_detail(view)
                break

    # ---- sharing ------------------------------------------------------
    def authorize_share_by_name(self, entry_name: str):
        w = self.window
        view = next((v for v in w._all_views if v.name == entry_name), None)
        if view is None:
            return False, f"entry '{entry_name}' was not found"
        decision = w._policy.evaluate("share_secret", self.policy_context(view))
        return decision.allowed, decision.reason

    def open_sharing_center(self, entry_view=None) -> None:
        w = self.window
        if isinstance(entry_view, bool):
            entry_view = w._current
        from .share_dialog import SharingCenterDialog

        before = w._current.name if w._current else w._selected_name
        dlg = SharingCenterDialog(
            w._session,
            w,
            actor=w._settings.enterprise_user_id,
            initial_entry=entry_view,
            authorize_share=self.authorize_share_by_name,
        )
        dlg.exec()
        w._selected_name = entry_view.name if entry_view is not None else before
        w._reload()
        if w._selected_name:
            for i in range(w.list.count()):
                item = w.list.item(i)
                view = item.data(Qt.UserRole)
                if view and view.name == w._selected_name:
                    w.list.setCurrentItem(item)
                    w._show_detail(view)
                    break

    # ---- dialogs ------------------------------------------------------
    def show_history(self) -> None:
        from .history_dialog import HistoryDialog

        HistoryDialog(self.window._session, self.window).exec()

    def show_siem_console(self) -> None:
        from .siem_dialog import SiemConsoleDialog

        SiemConsoleDialog(self.window._session, self.window).exec()

    def show_sync_bundle(self) -> None:
        from .sync_dialog import SyncBundleDialog

        w = self.window
        SyncBundleDialog(w._session, w._settings, w).exec()

    def show_directory(self) -> None:
        from .directory_dialog import DirectoryDialog

        w = self.window
        dlg = DirectoryDialog(w._settings_store, w._settings, w)
        dlg.exec()
        w._settings = dlg.settings.normalized()
        self._refresh_policy()
        if hasattr(w, "_health_card"):
            w._health_card.setVisible(w._settings.show_health_sidebar)
        w._refresh_categories()

    def show_access_requests(self) -> None:
        from .access_dialog import AccessRequestsDialog

        w = self.window
        dlg = AccessRequestsDialog(w._settings_store, w._settings, w._session, w)
        dlg.exec()
        w._settings = dlg.settings.normalized()
        self._refresh_policy()
        w._refresh_categories()

    def show_policy_pack(self) -> None:
        from .policy_dialog import PolicyPackDialog

        w = self.window
        dlg = PolicyPackDialog(w._settings_store, w._settings, w)
        dlg.exec()
        w._settings = dlg.settings.normalized()
        self._refresh_policy()
        w._refresh_categories()

    def enroll_recovery(self) -> None:
        from .recovery_dialog import EnrollDialog

        EnrollDialog(self.window._session, self.window).exec()

    def rotate_password(self) -> None:
        from .recovery_dialog import RotateDialog

        if RotateDialog(self.window._session, self.window).exec():
            QMessageBox.information(self.window, "Password rotated", "Your master password was rotated successfully.")

    def verify(self) -> None:
        w = self.window
        verdict, fingerprint, head = w._session.verify_integrity()
        QMessageBox.information(
            w,
            "Audit chain",
            ("Ledger verified.\n\nVault fingerprint: " + fingerprint[:18] + "…\nHead hash: " + head[:18] + "…")
            if verdict.ok else f"Ledger verification failed: {verdict.reason}",
        )

    def show_settings(self) -> None:
        from .settings_dialog import SettingsCenterDialog

        w = self.window
        dlg = SettingsCenterDialog(
            w._settings,
            w,
            open_policy_pack=self.show_policy_pack,
            open_access_requests=self.show_access_requests,
            open_directory=self.show_directory,
            open_sync_bundle=self.show_sync_bundle,
        )
        if not dlg.exec() or dlg.result_settings is None:
            return
        w._settings = dlg.result_settings.normalized()
        w._settings_store.save(w._settings)
        self._refresh_policy()
        w._last_activity = time.monotonic()
        if hasattr(w, "_health_card"):
            w._health_card.setVisible(w._settings.show_health_sidebar)
        w._refresh_categories()
        QMessageBox.information(w, "Settings saved", "Zero Trust settings were saved locally.")

    def show_health(self) -> None:
        from .health_dialog import HealthDialog

        HealthDialog(self.window._session, self.window, initial_report=getattr(self.window, "_health_report_cache", None)).exec()

    def show_autofill_agent(self) -> None:
        from .agent_dialog import AutofillAgentDialog

        AutofillAgentDialog(self.window).exec()

    def show_passkey_unlock(self) -> None:
        from .passkey_dialog import PasskeyUnlockDialog

        PasskeyUnlockDialog(self.window).exec()

    def show_quick_guide(self) -> None:
        from .guide_dialog import QuickStartDialog

        QuickStartDialog(self.window).exec()

    # ---- audit export -------------------------------------------------
    def export_audit(self, parent, fmt: str) -> None:
        w = self.window
        try:
            verdict, _fingerprint, _head = w._session.verify_integrity()
            decision = w._policy.evaluate("export_audit", self.policy_context(audit_ok=verdict.ok))
            if not decision.allowed:
                QMessageBox.warning(parent, "Policy blocked", decision.reason)
                return
        except Exception as exc:
            QMessageBox.critical(parent, "Policy check failed", str(exc))
            return
        extension = "log" if fmt in {"cef", "syslog"} else "json"
        path, _ = QFileDialog.getSaveFileName(parent, f"Export audit {fmt.upper()}", f"aegisvault-audit.{extension}", f"*.{extension}")
        if not path:
            return
        try:
            from ...outbound.audit_export.exporters import build_exporter
            payload = w._session.export_audit(build_exporter(fmt))
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(payload)
            QMessageBox.information(parent, "Audit exported", f"Audit log exported to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(parent, "Export failed", str(exc))

    # ---- session safety ----------------------------------------------
    def check_auto_lock(self) -> None:
        w = self.window
        timeout = w._settings.auto_lock_seconds
        if w._locked or timeout <= 0:
            return
        if time.monotonic() - w._last_activity < timeout:
            return
        w._locked = True
        try:
            w._clipboard.clear()
            w._session.lock()
        finally:
            QMessageBox.information(w, "Vault locked", "AegisVault auto-locked after inactivity. Reopen the vault to continue.")
            w.close()
