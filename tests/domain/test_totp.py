"""TOTP validated against the official RFC 6238 test vectors."""
import base64

from ferrovault.domain.value_objects.totp_secret import TotpSecret

# RFC 6238 Appendix B: ASCII seed "12345678901234567890", SHA1, 8 digits.
_SEED = base64.b32encode(b"12345678901234567890").decode()


def _totp():
    return TotpSecret(_SEED, digits=8, period=30, algorithm="SHA1")


def test_rfc6238_vectors():
    assert _totp().code_at(59) == "94287082"
    assert _totp().code_at(1111111109) == "07081804"
    assert _totp().code_at(1234567890) == "89005924"


def test_seconds_remaining():
    assert TotpSecret(_SEED).seconds_remaining(45) == 15      # 30 - (45 % 30)


def test_rejects_invalid_base32():
    import pytest
    with pytest.raises(ValueError):
        TotpSecret("not!base32!")


def test_six_digit_codes_are_padded():
    code = TotpSecret(_SEED).code_at(0)
    assert len(code) == 6 and code.isdigit()


def test_generated_seed_is_valid_and_usable():
    from ferrovault.domain.value_objects.totp_secret import (TotpSecret,
                                                             generate_base32_seed)
    seed = generate_base32_seed()
    assert seed.isalnum() and seed.isupper()      # base32 alphabet (no padding)
    totp = TotpSecret(seed)                        # must construct cleanly
    code = totp.code_at(0)
    assert len(code) == 6 and code.isdigit()

    other = TotpSecret.generate()
    assert other.secret != seed                    # fresh randomness each time
