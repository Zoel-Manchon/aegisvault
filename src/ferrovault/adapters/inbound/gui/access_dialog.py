"""GUI for local Zero Trust access requests and approvals."""
from __future__ import annotations

from datetime import datetime, timezone

from PySide6.QtWidgets import QDialog, QMessageBox, QVBoxLayout

from ....application.services.access_requests import AccessRequestQueue
from ....application.services.settings import VaultSettings
from .access_sections import AccessRequestFooter, AccessRequestForm, AccessRequestTable
from .components.dialogs import DialogHero


class AccessRequestsDialog(QDialog):
    def __init__(self, settings_store, settings: VaultSettings, session, parent=None):
        super().__init__(parent)
        self._settings_store = settings_store
        self._settings = settings.normalized()
        self._session = session
        self._queue = AccessRequestQueue(self._settings.access_requests)
        self.setWindowTitle("Zero Trust access requests")
        self.setMinimumSize(920, 620)
        self.resize(1040, 700)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        outer.addWidget(DialogHero(
            "Access requests & approvals",
            "Create, approve, or deny governed access requests. This is the local workflow foundation for future just-in-time Zero Trust access.",
        ))

        self.table = AccessRequestTable()
        outer.addWidget(self.table, 1)

        self.form = AccessRequestForm(
            [v.name for v in session.entries(include_deleted=False)],
            self._settings.enterprise_user_id,
        )
        outer.addWidget(self.form)

        self.footer = AccessRequestFooter()
        self.footer.create_button.clicked.connect(self.create_request)
        self.footer.approve_button.clicked.connect(lambda: self.decide_selected(True))
        self.footer.deny_button.clicked.connect(lambda: self.decide_selected(False))
        self.footer.save_button.clicked.connect(self.save)
        self.footer.close_button.clicked.connect(self.accept)
        outer.addWidget(self.footer)
        self.refresh()

    @property
    def settings(self) -> VaultSettings:
        return self._settings

    def refresh(self):
        self.table.set_requests(self._queue.list(include_closed=True))

    def create_request(self):
        entry, action, requester, reason = self.form.values()
        if not entry:
            QMessageBox.warning(self, "Missing entry", "Choose or type the entry that needs access.")
            return
        self._queue = self._queue.create(
            entry_name=entry,
            requester=requester or self._settings.enterprise_user_id,
            action=action,
            reason=reason,
            created_at=_now(),
        )
        self.form.clear_reason()
        self.refresh()

    def decide_selected(self, approved: bool):
        row = self.table.currentRow()
        requests = self._queue.list(include_closed=True)
        if row < 0 or row >= len(requests):
            QMessageBox.warning(self, "No request selected", "Select a pending request first.")
            return
        req = requests[row]
        try:
            self._queue = self._queue.decide(
                req.request_id,
                approved=approved,
                decided_by=self._settings.enterprise_user_id,
                decided_at=_now(),
                reason="approved for governed access" if approved else "denied by Zero Trust approver",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Could not update request", str(exc))
            return
        self.refresh()

    def save(self):
        self._settings = VaultSettings(**{**self._settings.to_dict(), "access_requests": tuple(self._queue.to_list())}).normalized()
        self._settings_store.save(self._settings)
        QMessageBox.information(self, "Access workflow saved", "Access requests and approval decisions were saved locally.")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
