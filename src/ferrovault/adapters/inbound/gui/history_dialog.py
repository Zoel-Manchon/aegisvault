"""History dialog: the audit chain drawn as linked blocks."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QFileDialog, QHBoxLayout, QLabel,
                               QPushButton, QScrollArea, QVBoxLayout, QWidget)

from .svg import chain_flow_widget
from .theme import ACCENT, DANGER, MUTED


class HistoryDialog(QDialog):
    def __init__(self, session, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Audit chain")
        self.setMinimumSize(560, 520)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        verdict, root, head = session.verify_integrity()

        head_row = QHBoxLayout()
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {ACCENT if verdict.ok else DANGER};")
        status = QLabel("chain intact" if verdict.ok else "CHAIN TAMPERED")
        status.setObjectName("h1")
        head_row.addWidget(dot)
        head_row.addWidget(status)
        head_row.addStretch()
        layout.addLayout(head_row)

        fp = QLabel(f"Merkle fingerprint   {root[:40]}…")
        fp.setObjectName("mono")
        layout.addWidget(fp)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        hl = QVBoxLayout(holder)
        hl.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        hl.addWidget(chain_flow_widget(session.audit_log()))
        scroll.setWidget(holder)
        layout.addWidget(scroll, 1)

        hint = QLabel("each block hash-links the previous one — a blockchain")
        hint.setObjectName("muted")
        hint.setAlignment(Qt.AlignCenter)
        layout.addWidget(hint)

        export_row = QHBoxLayout()
        export_row.addStretch()
        for fmt in ("json", "cef", "syslog"):
            btn = QPushButton(f"Export {fmt.upper()}")
            btn.setObjectName("ghost")
            btn.clicked.connect(lambda _=False, f=fmt: self._export(f))
            export_row.addWidget(btn)
        layout.addLayout(export_row)
        self._session = session

    def _export(self, fmt):
        from ....adapters.outbound.audit_export.exporters import build_exporter
        ext = {"json": "json", "cef": "cef", "syslog": "log"}[fmt]
        path, _ = QFileDialog.getSaveFileName(
            self, "Export audit ledger", f"audit.{ext}")
        if not path:
            return
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(self._session.export_audit(build_exporter(fmt)))
