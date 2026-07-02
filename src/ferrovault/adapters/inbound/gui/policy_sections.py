"""Reusable sections for the Zero Trust policy-pack dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QWidget,
)

from ....application.services.policy_pack import PolicyRule
from .components.dialogs import FormCard


class PolicyRuleTable(QTableWidget):
    HEADERS = ("Enabled", "Rule", "Actions", "Sensitivity", "Team vaults", "Categories", "Reason")

    def __init__(self):
        super().__init__(0, len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setAlternatingRowColors(True)
        self.verticalHeader().setVisible(False)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.horizontalHeader().setStretchLastSection(True)

    def set_rules(self, rules: list[PolicyRule]) -> None:
        self.setRowCount(len(rules))
        for row, rule in enumerate(rules):
            rule = rule.normalized()
            values = (
                "yes" if rule.enabled else "no",
                rule.name,
                ",".join(rule.actions),
                ",".join(rule.sensitivities),
                ",".join(rule.team_vaults),
                ",".join(rule.categories),
                rule.reason,
            )
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemIsEditable)
                self.setItem(row, col, item)
        self.resizeColumnsToContents()


class PolicyRuleForm(FormCard):
    """Editor for one deterministic deny rule."""

    def __init__(self):
        super().__init__("Rule editor")
        self.name = QLineEdit(); self.name.setPlaceholderText("Critical secrets need MFA + trusted device")
        self.actions = QLineEdit(); self.actions.setPlaceholderText("reveal_secret,copy_secret,share_secret or *")
        self.sens = QLineEdit(); self.sens.setPlaceholderText("high,critical")
        self.teams = QLineEdit(); self.teams.setPlaceholderText("Production,Cloud")
        self.categories = QLineEdit(); self.categories.setPlaceholderText("AWS,Database")
        self.reason = QLineEdit(); self.reason.setPlaceholderText("Blocked by local Zero Trust policy.")
        self.require_mfa = QCheckBox("Deny when MFA is not verified")
        self.require_device = QCheckBox("Deny when device is not trusted")
        self.enabled = QCheckBox("Enabled"); self.enabled.setChecked(True)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        widgets = (
            ("Name", self.name), ("Actions", self.actions), ("Sensitivity", self.sens),
            ("Team vaults", self.teams), ("Categories", self.categories), ("Reason", self.reason),
            ("MFA", self.require_mfa), ("Device", self.require_device), ("State", self.enabled),
        )
        for i, (label, widget) in enumerate(widgets):
            cap = QLabel(label); cap.setObjectName("mono")
            row = (i // 3) * 2
            col = i % 3
            grid.addWidget(cap, row, col)
            grid.addWidget(widget, row + 1, col)
        self.box.addLayout(grid)

    def rule(self) -> PolicyRule:
        name = self.name.text().strip() or "Policy rule"
        return PolicyRule(
            rule_id=name,
            name=name,
            actions=tuple(x.strip() for x in (self.actions.text() or "*").split(",") if x.strip()),
            sensitivities=tuple(x.strip() for x in self.sens.text().split(",") if x.strip()),
            team_vaults=tuple(x.strip() for x in self.teams.text().split(",") if x.strip()),
            categories=tuple(x.strip() for x in self.categories.text().split(",") if x.strip()),
            require_mfa=self.require_mfa.isChecked(),
            require_trusted_device=self.require_device.isChecked(),
            enabled=self.enabled.isChecked(),
            reason=self.reason.text().strip() or "Blocked by local Zero Trust policy.",
        ).normalized()

    def load(self, rule: PolicyRule) -> None:
        rule = rule.normalized()
        self.name.setText(rule.name)
        self.actions.setText(",".join(rule.actions))
        self.sens.setText(",".join(rule.sensitivities))
        self.teams.setText(",".join(rule.team_vaults))
        self.categories.setText(",".join(rule.categories))
        self.reason.setText(rule.reason)
        self.require_mfa.setChecked(rule.require_mfa)
        self.require_device.setChecked(rule.require_trusted_device)
        self.enabled.setChecked(rule.enabled)


class PolicyRuleFooter(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.add_button = QPushButton("Add / update rule")
        self.add_button.setObjectName("primary")
        self.load_button = QPushButton("Load selected")
        self.remove_button = QPushButton("Remove selected")
        self.reset_button = QPushButton("Restore starter pack")
        self.save_button = QPushButton("Save policy pack")
        self.close_button = QPushButton("Close")
        for button in (self.add_button, self.load_button, self.remove_button, self.reset_button):
            layout.addWidget(button)
        layout.addStretch()
        layout.addWidget(self.save_button)
        layout.addWidget(self.close_button)
