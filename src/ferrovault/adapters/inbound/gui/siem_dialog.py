"""Live audit/SIEM console for the GUI."""
from __future__ import annotations

import json
from dataclasses import asdict

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox, QVBoxLayout

from ....application.services.siem import normalize_blocks
from .view_models.audit_stream import IncrementalAuditStream
from .components.dialogs import DialogHero
from .siem_sections import SiemConsoleFooter, SiemEventsTable


class SiemConsoleDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self._session = session
        self.setWindowTitle("Live SIEM / audit console")
        self.setMinimumSize(900, 560)
        self.resize(1040, 640)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(22, 20, 22, 18)
        outer.setSpacing(14)
        outer.addWidget(DialogHero(
            "Live SIEM console",
            "Normalized Zero Trust audit events, ready for Wazuh, Elastic, Splunk, Sentinel, JSONL, or syslog pipelines.",
        ))

        self._stream = IncrementalAuditStream()
        self.table = SiemEventsTable()
        outer.addWidget(self.table, 1)

        self.footer = SiemConsoleFooter()
        self.footer.refresh_button.clicked.connect(self.refresh)
        self.footer.export_jsonl_button.clicked.connect(self.export_jsonl)
        self.footer.export_json_button.clicked.connect(self.export_json)
        self.footer.close_button.clicked.connect(self.accept)
        outer.addWidget(self.footer)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(1500)
        self.refresh()

    def _events(self):
        return normalize_blocks(self._session.audit_log())

    def refresh(self):
        snapshot = self._stream.update(self._session.audit_log())
        self.table.set_events(snapshot.events)

    def export_jsonl(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export SIEM JSONL", "aegisvault-siem.jsonl", "*.jsonl")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                for event in self._events():
                    fh.write(json.dumps(asdict(event), sort_keys=True) + "\n")
            QMessageBox.information(self, "SIEM export complete", f"Wrote normalized SIEM events to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    def export_json(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export SIEM JSON", "aegisvault-siem.json", "*.json")
        if not path:
            return
        try:
            payload = [asdict(e) for e in self._events()]
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
            QMessageBox.information(self, "SIEM export complete", f"Wrote normalized SIEM events to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
