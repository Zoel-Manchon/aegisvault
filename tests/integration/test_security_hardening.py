"""Security regressions: each test pins one protection added in the audit.

Real crypto on disk (AES-256-GCM + scrypt/Argon2id) with cheap KDF costs so
the suite stays fast; the production costs are covered by test_kdf_defaults.
"""
import json
import os
import secrets
import tempfile
import time

import pytest

pytest.importorskip("cryptography")

from ferrovault.adapters.outbound.clock.system_clock import SystemClock  # noqa: E402
from ferrovault.adapters.outbound.crypto import argon2_kdf  # noqa: E402
from ferrovault.adapters.outbound.crypto.aesgcm_cipher import AesGcmCipher  # noqa: E402
from ferrovault.adapters.outbound.crypto.kdf_router import KeyDerivationRouter  # noqa: E402
from ferrovault.adapters.outbound.crypto.scrypt_kdf import ScryptKeyDerivation  # noqa: E402
from ferrovault.adapters.outbound.storage.file_repository import FileVaultRepository  # noqa: E402
from ferrovault.application.errors import (AuthenticationError, UnsupportedVaultFormat,  # noqa: E402
                                           VaultConflictError, WeakMasterPassword)
from ferrovault.application.services.master_password import (  # noqa: E402
    master_password_problems, require_strong_master_password)
from ferrovault.application.services.settings import VaultSettings  # noqa: E402
from ferrovault.application.services.vault_service import VaultService  # noqa: E402
from ferrovault.domain.services.shamir import validate_split  # noqa: E402
from ferrovault.domain.value_objects.kdf_params import (ARGON2ID_DEFAULT, KdfParams,  # noqa: E402
                                                        SCRYPT_STRONG)

PW = "correcto-caballo-bateria-grapa"
NEW_PW = "nueva-frase-larga-de-ejemplo-42"

needs_argon2 = pytest.mark.skipif(not argon2_kdf.AVAILABLE, reason="cryptography without Argon2id")


def _fast_argon2() -> KdfParams:
    return KdfParams("argon2id", secrets.token_bytes(16), {"t": 1, "m": 8 * 1024, "p": 1})


def _svc(path, factory=KdfParams.scrypt):
    adapters = [ScryptKeyDerivation()]
    if argon2_kdf.AVAILABLE:
        adapters.insert(0, argon2_kdf.Argon2idKeyDerivation())
    return VaultService(FileVaultRepository(str(path)), KeyDerivationRouter(*adapters),
                        AesGcmCipher(), SystemClock(), kdf_factory=factory)


@pytest.fixture()
def vault_path():
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "vault.fv")
        svc = _svc(path)
        svc.init_vault(PW)
        svc.add_entry(PW, "aws", "root", "AKIA-SECRET")
        yield path


def _header(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)["header"]


def _rewrite_header(path, mutate):
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    mutate(doc["header"])
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh)


# ---- persistence --------------------------------------------------------
def test_trashed_entries_survive_save_and_reload(vault_path):
    """Regression: the serializer used to drop trashed entries on every save."""
    session = _svc(vault_path).unlock(PW)
    session.add("github", "octocat", "gh-token")
    session.remove("aws")
    session.lock()

    reopened = _svc(vault_path).unlock(PW)
    state = {e.name: e.deleted for e in reopened.entries(include_deleted=True)}
    assert state == {"aws": True, "github": False}
    reopened.restore("aws")
    assert reopened.reveal("aws") == "AKIA-SECRET"


def test_snapshots_keep_only_the_newest(vault_path):
    repo = FileVaultRepository(vault_path, keep=3)
    made = []
    for i in range(5):
        made.append(repo.snapshot(f"n{i}"))
        time.sleep(0.01)
    kept = repo.snapshots()
    assert len(kept) == 3
    assert {str(p) for p in kept} == set(made[-3:])
    # A snapshot is a sealed vault: it opens with the same password.
    assert _svc(made[-1]).get_secret(PW, "aws") == "AKIA-SECRET"


# ---- header is untrusted input ------------------------------------------
def test_header_is_authenticated(vault_path):
    _rewrite_header(vault_path, lambda h: h.__setitem__("extra", "attacker"))
    with pytest.raises(AuthenticationError):
        _svc(vault_path).get_secret(PW, "aws")


def test_absurd_kdf_cost_is_refused_before_deriving(vault_path):
    """A crafted header must not make the KDF allocate gigabytes."""
    _rewrite_header(vault_path, lambda h: h["kdf"]["params"].__setitem__("n", 1 << 30))
    started = time.perf_counter()
    with pytest.raises((ValueError, UnsupportedVaultFormat)):
        _svc(vault_path).get_secret(PW, "aws")
    assert time.perf_counter() - started < 2


@pytest.mark.parametrize("mutate", [
    lambda h: h["kdf"].__setitem__("algorithm", "md5"),
    lambda h: h["kdf"].__setitem__("salt", "c2hvcnQ="),          # 5-byte salt
    lambda h: h.__setitem__("cipher", "ROT13"),
])
def test_unknown_or_weak_header_values_are_rejected(vault_path, mutate):
    _rewrite_header(vault_path, mutate)
    with pytest.raises((ValueError, UnsupportedVaultFormat, AuthenticationError)):
        _svc(vault_path).get_secret(PW, "aws")


def test_header_records_cipher_and_format(vault_path):
    header = _header(vault_path)
    assert header["cipher"] == "AES-256-GCM"
    assert int(header["version"]) >= 4


# ---- KDF -----------------------------------------------------------------
def test_production_kdf_defaults_meet_current_guidance():
    assert ARGON2ID_DEFAULT["m"] >= 64 * 1024 and ARGON2ID_DEFAULT["t"] >= 3   # RFC 9106
    assert SCRYPT_STRONG["n"] >= 1 << 17                                     # OWASP
    assert KdfParams.scrypt().weaker_than(KdfParams.argon2id())


@needs_argon2
def test_legacy_scrypt_vault_is_upgraded_on_unlock(vault_path):
    session = _svc(vault_path, _fast_argon2).unlock(PW)
    assert session.upgraded_from and session.upgraded_from.startswith("scrypt")
    assert session.audit_log()[-1].action == "kdf-upgrade"
    session.lock()

    assert _header(vault_path)["kdf"]["algorithm"] == "argon2id"
    assert _svc(vault_path, _fast_argon2).get_secret(PW, "aws") == "AKIA-SECRET"
    with pytest.raises(AuthenticationError):
        _svc(vault_path, _fast_argon2).get_secret("wrong-password", "aws")


@needs_argon2
def test_argon2_adapter_is_deterministic_and_salted():
    kdf = argon2_kdf.Argon2idKeyDerivation()
    params = KdfParams("argon2id", b"\x01" * 16, {"t": 1, "m": 8 * 1024, "p": 1})
    other = KdfParams("argon2id", b"\x02" * 16, {"t": 1, "m": 8 * 1024, "p": 1})
    assert kdf.derive("pw", params).bytes == kdf.derive("pw", params).bytes
    assert kdf.derive("pw", params).bytes != kdf.derive("pw", other).bytes
    assert len(kdf.derive("pw", params)) == 32


# ---- session -------------------------------------------------------------
def test_session_keeps_keys_not_the_password_and_lock_wipes_them(vault_path):
    session = _svc(vault_path).unlock(PW)
    assert PW not in repr(vars(session))
    kek = session._kek
    session.lock()
    assert session.is_locked
    assert kek.bytes == bytes(len(kek))
    assert len(session._dek) == 0
    with pytest.raises(AuthenticationError):
        session.add("x", "u", "p")


def test_concurrent_edit_is_refused_instead_of_lost(vault_path):
    first = _svc(vault_path).unlock(PW)
    second = _svc(vault_path).unlock(PW)
    first.add("one", "u", "1")
    with pytest.raises(VaultConflictError):
        second.add("two", "u", "2")
    assert _svc(vault_path).get_secret(PW, "one") == "1"


def test_password_history_is_bounded_and_keeps_secrets_sealed(vault_path):
    session = _svc(vault_path).unlock(PW)
    for i in range(12):
        session.update("aws", secret=f"rotated-{i}")
    history = session.password_history("aws")
    assert len(history) == 10
    assert not any("rotated" in h or "AKIA" in h for h in history)
    assert session.reveal("aws") == "rotated-11"


def test_rotate_needs_the_current_password_and_snapshots_first(vault_path):
    session = _svc(vault_path).unlock(PW)
    with pytest.raises(AuthenticationError):
        session.rotate(NEW_PW, current_password="not-the-password")
    session.rotate(NEW_PW, current_password=PW)
    session.lock()

    with pytest.raises(AuthenticationError):
        _svc(vault_path).get_secret(PW, "aws")
    assert _svc(vault_path).get_secret(NEW_PW, "aws") == "AKIA-SECRET"
    snaps = FileVaultRepository(vault_path).snapshots()
    assert any("pre-rotate" in p.name for p in snaps)
    # The pre-rotation copy still opens with the old password.
    pre = next(p for p in snaps if "pre-rotate" in p.name)
    assert _svc(pre).get_secret(PW, "aws") == "AKIA-SECRET"


# ---- sync ----------------------------------------------------------------
def test_sync_import_rejects_a_bundle_from_another_vault(vault_path):
    other_path = os.path.join(os.path.dirname(vault_path), "other.fv")
    other = _svc(other_path)
    other.init_vault(PW)
    other.add_entry(PW, "evil", "x", "y")
    foreign = other.export_sync_bundle(PW)

    svc = _svc(vault_path)
    with pytest.raises(ValueError):
        svc.import_sync_bundle(foreign, password=PW)
    session = svc.unlock(PW)
    with pytest.raises(ValueError):
        session.import_sync_bundle(foreign)
    session.lock()
    assert _svc(vault_path).get_secret(PW, "aws") == "AKIA-SECRET"

    own = svc.export_sync_bundle(PW)
    svc.import_sync_bundle(own, password=PW)
    assert any("pre-sync-import" in p.name for p in FileVaultRepository(vault_path).snapshots())


def test_sync_bundle_never_contains_plaintext(vault_path):
    payload = _svc(vault_path).export_sync_bundle(PW)
    assert "AKIA-SECRET" not in payload and "root" not in payload


# ---- policies -------------------------------------------------------------
@pytest.mark.parametrize("weak", ["corta", "password1234", "Barcelona2024", "aaaaaaaaaaaaaaaa",
                                  "123456789012", "qwertyuiopasdf"])
def test_weak_master_passwords_are_refused(weak):
    assert master_password_problems(weak)
    with pytest.raises(WeakMasterPassword):
        require_strong_master_password(weak)


@pytest.mark.parametrize("strong", [PW, NEW_PW, "Tq9#vR2!mZ7&kL4@"])
def test_strong_master_passwords_are_accepted(strong):
    assert master_password_problems(strong) == []


@pytest.mark.parametrize("n,k", [(1, 1), (3, 1), (2, 3), (256, 2), (0, 0)])
def test_shamir_rejects_unsafe_splits(n, k):
    with pytest.raises(ValueError):
        validate_split(n, k)


def test_settings_are_clamped_and_hardening_is_on_by_default():
    defaults = VaultSettings()
    assert defaults.exclude_clipboard_history and defaults.lock_on_screen_lock
    assert defaults.backup_before_risky and not defaults.breach_check_online
    s = VaultSettings.from_dict({"clipboard_clear_seconds": 0, "auto_lock_seconds": -5,
                                 "reveal_hide_seconds": 10 ** 6, "keep_backups": "many",
                                 "theme": "neon", "unknown_key": 1})
    assert s.clipboard_clear_seconds == 1 and s.auto_lock_seconds == 0
    assert s.reveal_hide_seconds == 600 and s.keep_backups == 10 and s.theme == "dark"
