"""Zero Trust command-center components."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .primitives import ActionCard, FeatureGrid, Pill, SectionHeader, SummaryCard


class ZeroTrustSignal(QFrame):
    """Compact posture signal for identity/device/policy posture."""

    def __init__(self, label: str, value: str, helper: str, tone: str = "neutral"):
        super().__init__()
        self.setObjectName("ztSignalCard")
        self.setProperty("tone", tone)
        self.setMinimumHeight(86)
        box = QVBoxLayout(self)
        box.setContentsMargins(15, 12, 15, 12)
        box.setSpacing(4)
        cap = QLabel(label.upper())
        cap.setObjectName("mono")
        val = QLabel(value)
        val.setObjectName("metricValue")
        val.setWordWrap(True)
        note = QLabel(helper)
        note.setObjectName("smallMuted")
        note.setWordWrap(True)
        box.addWidget(cap)
        box.addWidget(val)
        box.addWidget(note)


class ZeroTrustTrustStrip(QFrame):
    """Compact chain-of-trust summary strip below the hero copy."""

    def __init__(self, items: tuple[tuple[str, str], ...]):
        super().__init__()
        self.setObjectName("ztTrustStrip")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(8)
        for index, (label, tone) in enumerate(items):
            row.addWidget(Pill(label, tone))
            if index < len(items) - 1:
                arrow = QLabel("→")
                arrow.setObjectName("smallMuted")
                arrow.setAlignment(Qt.AlignCenter)
                row.addWidget(arrow)
        row.addStretch()


class ZeroTrustHero(QFrame):
    """Hero summary for the Zero Trust dashboard."""

    def __init__(
        self,
        *,
        score: str,
        twofa: str,
        overdue: str,
        policy_state: str,
        role: str,
        device: str,
        audit_state: str,
        audit_ok: bool,
        device_ok: bool,
        policy_enforced: bool,
    ):
        super().__init__()
        self.setObjectName("ztHero")
        hero_box = QHBoxLayout(self)
        hero_box.setContentsMargins(24, 22, 24, 22)
        hero_box.setSpacing(22)

        left = QVBoxLayout()
        left.setSpacing(10)
        eyebrow = QLabel("ZERO TRUST CONTROL PLANE")
        eyebrow.setObjectName("mono")
        title = QLabel("Verify every action")
        title.setObjectName("ztTitle")
        body = QLabel(
            "A governed vault workspace for identity-aware access, device trust, encrypted sharing, approvals, audit evidence, and sync delivery."
        )
        body.setObjectName("muted")
        body.setWordWrap(True)
        left.addWidget(eyebrow)
        left.addWidget(title)
        left.addWidget(body)
        left.addWidget(
            ZeroTrustTrustStrip(
                (
                    (f"Policy {policy_state}", "good" if policy_enforced else "warn"),
                    (f"Role {role}", "neutral"),
                    (f"Device {device}", "good" if device_ok else "danger"),
                    (f"Audit {audit_state}", "good" if audit_ok else "danger"),
                )
            )
        )
        hero_box.addLayout(left, 2)

        score_card = QFrame()
        score_card.setObjectName("ztScoreCard")
        score_card.setMinimumWidth(220)
        sc = QVBoxLayout(score_card)
        sc.setContentsMargins(18, 16, 18, 16)
        sc.setSpacing(6)
        cap = QLabel("POSTURE SCORE")
        cap.setObjectName("mono")
        val = QLabel(score)
        val.setObjectName("ztScore")
        sub = QLabel(f"2FA {twofa}\n{overdue} overdue rotations")
        sub.setObjectName("smallMuted")
        sub.setWordWrap(True)
        sc.addWidget(cap)
        sc.addWidget(val)
        sc.addWidget(sub)
        sc.addStretch()
        hero_box.addWidget(score_card, 0, Qt.AlignTop)


class ZeroTrustDashboard(QWidget):
    """Reusable full Zero Trust command-center view."""

    def __init__(
        self,
        *,
        score: str,
        audit_state: str,
        audit_ok: bool,
        role: str,
        device: str,
        device_ok: bool,
        overdue: str,
        twofa: str,
        policy_state: str,
        policy_enforced: bool,
        grants: int,
        pending_requests: int,
        actions: tuple,
        team_lines: tuple[str, ...],
        rotation_lines: tuple[str, ...],
        fingerprint: str,
        head_hash: str,
        on_export,
    ):
        super().__init__()
        self.setObjectName("featureGrid")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(
            ZeroTrustHero(
                score=score,
                twofa=twofa,
                overdue=overdue,
                policy_state=policy_state,
                role=role,
                device=device,
                audit_state=audit_state,
                audit_ok=audit_ok,
                device_ok=device_ok,
                policy_enforced=policy_enforced,
            )
        )

        signals = FeatureGrid(columns=2)
        signals.add_items(
            (
                ZeroTrustSignal("Audit chain", audit_state, "tamper-evident local ledger", "good" if audit_ok else "danger"),
                ZeroTrustSignal("Trusted device", device, "blocks sensitive actions on unknown endpoints", "good" if device_ok else "danger"),
                ZeroTrustSignal("RBAC context", role, "role-gated reveal, copy, share, export, purge", "neutral"),
                ZeroTrustSignal("2FA coverage", twofa, "TOTP coverage for secrets and sharing", "good" if twofa == "100%" else "warn"),
                ZeroTrustSignal("Active grants", str(grants), "recipient-sealed encrypted share grants", "neutral"),
                ZeroTrustSignal("Access requests", str(pending_requests), "pending just-in-time approvals", "warn" if pending_requests else "good"),
            )
        )
        layout.addWidget(signals)

        layout.addWidget(SectionHeader("Control surface", "Core Zero Trust workflows available from the desktop interface."))
        action_grid = FeatureGrid(columns=2)
        action_grid.add_items(ActionCard(title, helper, icon_name, handler) for title, helper, icon_name, handler in actions)
        layout.addWidget(action_grid)

        layout.addWidget(SectionHeader("Operational posture", "Policies, sync delivery, rotation posture, and team-vault evidence."))
        operations = FeatureGrid(columns=2)
        operations.add_items(
            (
                SummaryCard("Team vaults", team_lines),
                SummaryCard(
                    "Policy modules",
                    (
                        "RBAC gates · trusted-device checks",
                        "MFA gates · reveal-before-copy",
                        "Audit-safe export · break-glass seam",
                        "SSO/OIDC + SCIM integration seams",
                    ),
                ),
                SummaryCard(
                    "Sync delivery model",
                    (
                        "No plaintext secrets in bundles",
                        "Only active grants should be delivered",
                        "Directory + device trust drive delivery",
                        "Revoked grants stay blocked",
                    ),
                ),
                SummaryCard("Rotation watchlist", rotation_lines),
            )
        )
        layout.addWidget(operations)

        evidence = QFrame()
        evidence.setObjectName("ztEvidence")
        ev = QHBoxLayout(evidence)
        ev.setContentsMargins(16, 14, 16, 14)
        ev.setSpacing(10)
        fp = fingerprint[:28] + "…" if fingerprint != "unavailable" else "unavailable"
        hh = head_hash[:28] + "…" if head_hash != "unavailable" else "unavailable"
        evidence_text = QLabel(f"Fingerprint {fp}   ·   Head hash {hh}")
        evidence_text.setObjectName("smallMuted")
        evidence_text.setWordWrap(True)
        ev.addWidget(evidence_text, 1)
        for label, fmt in (("JSON", "json"), ("CEF", "cef"), ("syslog", "syslog")):
            button = QPushButton(f"Export {label}")
            button.setObjectName("ghost")
            button.clicked.connect(lambda _=False, f=fmt: on_export(f))
            ev.addWidget(button)
        layout.addWidget(evidence)
