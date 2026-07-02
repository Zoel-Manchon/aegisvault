import string

from ferrovault.domain.services.password_generator import PasswordGenerator
from ferrovault.domain.value_objects.password_policy import PasswordPolicy


def test_respects_length_and_classes():
    pw = PasswordGenerator().generate(PasswordPolicy(length=24))
    assert len(pw) == 24
    assert any(c in string.ascii_lowercase for c in pw)
    assert any(c in string.ascii_uppercase for c in pw)
    assert any(c in string.digits for c in pw)


def test_can_restrict_charset():
    pw = PasswordGenerator().generate(
        PasswordPolicy(length=16, upper=False, symbols=False))
    assert not any(c in string.ascii_uppercase for c in pw)
