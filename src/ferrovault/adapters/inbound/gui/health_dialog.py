"""Vault health dialog with background scanning.

Full health analysis reveals secrets in memory to score weak/reused passwords, so
it is intentionally moved off the GUI thread. The dialog opens immediately with
a lightweight metadata summary, then hydrates the detailed report when ready.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (QDialog, QFrame, QHBoxLayout, QLabel,
                               QPushButton, QProgressBar, QScrollArea, QVBoxLayout, QWidget)

from .background import WorkerResult, start_health_scan
from .theme import ACCENT, DANGER, MUTED, TEXT

_AMBER = "#f2c14e"


class HealthDialog(QDialog):
    def __init__(self, session, parent=None, initial_report=None):
        super().__init__(parent)
        self._session = session
        self._initial_report = initial_report
        self._worker_owner = None
        self.setWindowTitle("Vault health")
        self.setMinimumSize(500, 560)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(20, 20, 20, 20)
        self._root.setSpacing(14)

        self._breach_btn = QPushButton("Check breaches online (HaveIBeenPwned)")
        self._breach_btn.clicked.connect(self._check_breaches)

        if initial_report is not None:
            self._render(initial_report)
        else:
            self._render_loading()
            QTimer.singleShot(0, self._start_offline_scan)

    def _score_color(self, score: int) -> str:
        return ACCENT if score >= 80 else _AMBER if score >= 50 else DANGER

    def _clear_root(self) -> None:
        while self._root.count():
            item = self._root.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

    def _render_loading(self, status: str = "Scanning vault health in the background…") -> None:
        self._clear_root()
        entries = self._session.entries()
        total = len([e for e in entries if not getattr(e, "deleted", False)])
        without_2fa = sum(1 for e in entries if not getattr(e, "deleted", False) and not getattr(e, "has_totp", False))
        with_2fa = max(0, total - without_2fa)

        head = QVBoxLayout()
        title = QLabel("Health scan")
        title.setObjectName("h1")
        title.setAlignment(Qt.AlignCenter)
        subtitle = QLabel(f"{total} active entries · {with_2fa} with 2FA · {without_2fa} without 2FA")
        subtitle.setObjectName("muted")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        head.addWidget(title)
        head.addWidget(subtitle)
        holder = QWidget()
        holder.setLayout(head)
        self._root.addWidget(holder)

        card = QFrame()
        card.setObjectName("panel")
        col = QVBoxLayout(card)
        col.setContentsMargins(18, 16, 18, 16)
        label = QLabel(status)
        label.setObjectName("muted")
        label.setAlignment(Qt.AlignCenter)
        label.setWordWrap(True)
        progress = QProgressBar()
        progress.setRange(0, 0)
        progress.setTextVisible(False)
        col.addWidget(label)
        col.addWidget(progress)
        self._root.addWidget(card)
        self._root.addStretch(1)
        self._root.addWidget(self._breach_btn)

    def _start_offline_scan(self) -> None:
        self._breach_btn.setEnabled(False)
        self._worker_owner = start_health_scan(self._session, self._on_health_scan_finished, parent=self)

    def _on_health_scan_finished(self, result: WorkerResult) -> None:
        self._worker_owner = None
        self._breach_btn.setEnabled(True)
        if result.ok:
            self._render(result.payload)
        else:
            self._render_error(f"Health scan failed: {result.error}")

    def _render_error(self, message: str) -> None:
        self._clear_root()
        label = QLabel(message)
        label.setObjectName("muted")
        label.setWordWrap(True)
        self._root.addWidget(label)
        self._root.addStretch(1)
        self._root.addWidget(self._breach_btn)

    def _render(self, report):
        self._clear_root()

        head = QVBoxLayout()
        score = QLabel(f"{report.score}")
        score.setAlignment(Qt.AlignCenter)
        score.setStyleSheet(
            f"font-size: 60px; font-weight: 700; color: {self._score_color(report.score)};")
        cap = QLabel(f"health score · {report.total} entries")
        cap.setObjectName("muted")
        cap.setAlignment(Qt.AlignCenter)
        head.addWidget(score)
        head.addWidget(cap)
        holder = QWidget()
        holder.setLayout(head)
        self._root.addWidget(holder)

        body = QWidget()
        col = QVBoxLayout(body)
        col.setSpacing(8)
        if report.is_healthy and not report.no_totp:
            col.addWidget(self._ok("✓ No weak, reused, or breached passwords"))
        if report.breached:
            col.addWidget(self._section(
                "Breached", DANGER,
                [f"{n} — seen {c:,}× in breaches" for n, c in report.breached]))
        if report.weak:
            col.addWidget(self._section("Weak", _AMBER, list(report.weak)))
        if report.reused:
            col.addWidget(self._section(
                "Reused", _AMBER, [" / ".join(g) for g in report.reused]))
        if report.no_totp:
            col.addWidget(self._section("No 2FA", MUTED, list(report.no_totp)))
        col.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        self._root.addWidget(scroll, 1)
        self._root.addWidget(self._breach_btn)

    def _section(self, title, color, items):
        frame = QFrame()
        frame.setObjectName("panel")
        v = QVBoxLayout(frame)
        head = QLabel(f"{title}  ·  {len(items)}")
        head.setStyleSheet(f"color: {color}; font-weight: 600;")
        v.addWidget(head)
        for it in items:
            lbl = QLabel(it)
            lbl.setStyleSheet(f"color: {TEXT};")
            lbl.setWordWrap(True)
            v.addWidget(lbl)
        return frame

    def _ok(self, text):
        lbl = QLabel(text)
        lbl.setStyleSheet(f"color: {ACCENT}; font-weight: 600;")
        return lbl

    def _check_breaches(self):
        from ....container import build_breach_checker
        self._breach_btn.setText("checking…")
        self._breach_btn.setEnabled(False)
        self._render_loading("Checking breached-password exposure online…")
        self._worker_owner = start_health_scan(
            self._session,
            self._on_breach_scan_finished,
            breach_checker=build_breach_checker(online=True),
            parent=self,
        )

    def _on_breach_scan_finished(self, result: WorkerResult) -> None:
        self._worker_owner = None
        self._breach_btn.setText("Check breaches online (HaveIBeenPwned)")
        self._breach_btn.setEnabled(True)
        if result.ok:
            self._render(result.payload)
        else:
            self._render_error(f"Breach check failed: {result.error}")
