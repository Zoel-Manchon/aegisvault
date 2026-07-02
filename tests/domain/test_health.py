"""Vault health analyzer."""
from ferrovault.domain.model.vault import Entry
from ferrovault.domain.services.health import HealthAnalyzer
from ferrovault.domain.value_objects.entry_id import EntryId
from ferrovault.domain.value_objects.secret import Secret
from ferrovault.domain.value_objects.totp_secret import TotpSecret


def _entry(name, secret, totp=None):
    return Entry(EntryId.new(), name, "user", Secret(secret),
                 totp=(TotpSecret(totp) if totp else None))


def test_flags_weak_reused_and_no_totp():
    entries = [
        _entry("a", "123", ),                          # weak
        _entry("b", "Tr0ub4dour&3xtr4-Str0ng-P@ss!!"), # strong
        _entry("c", "shared-pw-value-000"),            # reused w/ d
        _entry("d", "shared-pw-value-000"),            # reused w/ c
    ]
    r = HealthAnalyzer().analyze(entries)
    assert "a" in r.weak
    assert ("c", "d") in r.reused
    assert set(r.no_totp) == {"a", "b", "c", "d"}      # none have 2FA
    assert r.score < 100


def test_breached_passed_in_from_adapter():
    entries = [_entry("x", "Str0ng-Uniqu3-P@ssw0rd-42!", totp="JBSWY3DPEHPK3PXP")]
    r = HealthAnalyzer().analyze(entries, breached={"x": 4210})
    assert r.breached == (("x", 4210),)
    assert not r.no_totp


def test_healthy_vault_scores_100():
    entries = [_entry("only", "A-Very-Str0ng-Uniqu3-P@ss!!", totp="JBSWY3DPEHPK3PXP")]
    r = HealthAnalyzer().analyze(entries)
    assert r.score == 100 and r.is_healthy
