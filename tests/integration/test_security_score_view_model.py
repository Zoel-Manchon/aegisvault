from __future__ import annotations

from dataclasses import dataclass

from ferrovault.adapters.inbound.gui.view_models.security_score import build_security_score


@dataclass(frozen=True)
class Entry:
    name: str
    has_totp: bool = False
    sensitivity: str = "standard"
    deleted: bool = False
    active_share_count: int = 0


@dataclass(frozen=True)
class Finding:
    status: str


def test_security_score_empty_vault_is_not_penalized():
    score = build_security_score([])
    assert score.score == 100
    assert score.grade == "Excellent"


def test_security_score_penalizes_missing_2fa_and_overdue_rotation():
    score = build_security_score(
        [Entry("prod", sensitivity="critical", active_share_count=2), Entry("dev", has_totp=True)],
        [Finding("overdue")],
    )
    assert score.score < 100
    assert score.twofa_percent == 50
    assert score.active_grants == 2
    assert score.overdue_rotations == 1
    assert any("2FA" in warning for warning in score.warnings)
