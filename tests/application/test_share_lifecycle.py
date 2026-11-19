"""Sharing with expiry and logins, imports, access decisions and the recovery policy.

These run the real adapters (AES-GCM, scrypt, X25519 sealed boxes) on a
temporary file, because what matters here is what ends up sealed and chained.
"""
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("cryptography")

from ferrovault.adapters.outbound.clock.system_clock import SystemClock                 # noqa: E402
from ferrovault.adapters.outbound.crypto.aesgcm_cipher import AesGcmCipher              # noqa: E402
from ferrovault.adapters.outbound.crypto.scrypt_kdf import ScryptKeyDerivation           # noqa: E402
from ferrovault.adapters.outbound.sharing.sealed_box import (                           # noqa: E402
    generate_keypair, open_sealed, public_key_of,
)
from ferrovault.adapters.outbound.storage.file_repository import FileVaultRepository     # noqa: E402
from ferrovault.application.services.directory import DirectoryPrincipal, IdentityDirectory  # noqa: E402
from ferrovault.application.services.sharing import (                                   # noqa: E402
    ShareGrant, parse_share_payload, share_payload,
)
from ferrovault.application.services.sync_gateway import ZeroTrustSyncGateway           # noqa: E402
from ferrovault.application.services.vault_service import VaultService                   # noqa: E402

PW = "tinta marfil cobre lince 1984"
SECRET = "vX9#qL2m!Tz7@wR4kP8e"


def _service(path):
    return VaultService(FileVaultRepository(str(path)), ScryptKeyDerivation(), AesGcmCipher(), SystemClock())


@pytest.fixture
def vault(tmp_path):
    service = _service(tmp_path / "personal.avault")
    service.init_vault(PW)
    session = service.unlock(PW)
    session.add("GitHub", "ana", SECRET, url="https://github.com")
    yield service, session
    session.lock()


def _actions(session):
    return [block.action for block in session.audit_log()]


# ---- payload and expiry ------------------------------------------------------------------
def test_share_payload_round_trips_and_plain_text_is_a_bare_secret():
    text = share_payload(SECRET, username="ana", url="https://github.com", name="GitHub")
    assert parse_share_payload(text) == {"secret": SECRET, "username": "ana", "url": "https://github.com",
                                         "name": "GitHub"}
    # envelopes made before logins could be included hold only the secret
    assert parse_share_payload(SECRET) == {"secret": SECRET, "username": "", "url": "", "name": ""}
    # JSON that is not ours is still just a secret
    assert parse_share_payload('{"secret": "x"}')["secret"] == '{"secret": "x"}'


def test_grant_expiry_compares_moments_and_fails_closed():
    now = "2026-11-18T12:00:00+00:00"
    assert not ShareGrant.from_dict({}).expired(now)                       # no expiry
    assert not ShareGrant.from_dict({"expires_at": "2026-11-18T13:00:00+00:00"}).expired(now)
    assert ShareGrant.from_dict({"expires_at": "2026-11-18T12:00:00+00:00"}).expired(now)
    # another zone, same instant ordering
    assert ShareGrant.from_dict({"expires_at": "2026-11-18T12:30:00+01:00"}).expired(now)
    # a time without zone is read as UTC instead of crashing the comparison
    assert not ShareGrant.from_dict({"expires_at": "2026-11-18T12:30:00"}).expired(now)
    # a damaged date must not keep the grant alive
    assert ShareGrant.from_dict({"expires_at": "pronto"}).expired(now)


# ---- sharing through the session ------------------------------------------------------------
def test_share_with_login_seals_user_and_url_for_the_recipient_only(vault):
    _service_, session = vault
    private, public = generate_keypair()
    assert public_key_of(private) == public
    grant = session.share_public_key("GitHub", "Luis Gómez", public, actor="Ana", expires_in=timedelta(days=7),
                                     include_login=True)
    assert grant["includes"] == "login"
    assert datetime.fromisoformat(grant["expires_at"]) > datetime.now(timezone.utc) + timedelta(days=6)
    assert SECRET not in grant["sealed_blob"]
    opened = parse_share_payload(open_sealed(grant["sealed_blob"], private))
    assert opened == {"secret": SECRET, "username": "ana", "url": "https://github.com", "name": "GitHub"}
    other_private, _other_public = generate_keypair()
    with pytest.raises(Exception):
        open_sealed(grant["sealed_blob"], other_private)
    assert "share" in _actions(session)


def test_share_without_login_seals_only_the_secret(vault):
    _service_, session = vault
    private, public = generate_keypair()
    grant = session.share_public_key("GitHub", "Luis Gómez", public)
    assert grant["includes"] == "secret" and grant["expires_at"] == ""
    assert open_sealed(grant["sealed_blob"], private) == SECRET


def test_an_expired_grant_is_no_longer_delivered(vault):
    _service_, session = vault
    _private, public = generate_keypair()
    session.share_public_key("GitHub", "Luis Gómez", public, expires_in=timedelta(hours=1))
    directory = IdentityDirectory(()).upsert(DirectoryPrincipal(label="Luis Gómez", public_key=public))
    gateway = ZeroTrustSyncGateway(directory, require_trusted_device=False)
    entries = [v for v in session.entries() if v.name == "GitHub"]
    now = datetime.now(timezone.utc)
    first = gateway.evaluate(entries, now=now.isoformat())
    assert first[0].allowed and first[0].sealed_blob
    later = gateway.evaluate(entries, now=(now + timedelta(hours=2)).isoformat())
    assert not later[0].allowed
    assert later[0].reason == "grant expired"
    assert later[0].sealed_blob == ""


# ---- import, access decisions, recovery policy ------------------------------------------------
def test_import_adds_new_records_and_skips_the_rest(vault):
    _service_, session = vault
    before = len(session.audit_log())
    added, skipped = session.import_entries([
        {"name": "Jira", "username": "ana", "secret": "x1", "category": "Trabajo"},
        {"name": "GitHub", "secret": "would overwrite"},   # name taken
        {"name": "", "secret": "no name"},
        {"name": "Sin secreto", "secret": ""},
    ])
    assert (added, skipped) == (1, 3)
    names = {v.name for v in session.entries()}
    assert "Jira" in names and "Sin secreto" not in names
    assert session.reveal("GitHub") == SECRET                 # the existing entry is untouched
    assert _actions(session)[-1] == "import"
    assert len(session.audit_log()) == before + 1
    assert session.verify_integrity()[0].ok


def test_an_import_that_adds_nothing_leaves_no_trace(vault):
    _service_, session = vault
    before = len(session.audit_log())
    assert session.import_entries([{"name": "GitHub", "secret": "x"}]) == (0, 1)
    assert len(session.audit_log()) == before


def test_access_decisions_are_chained_in_the_audit(vault):
    _service_, session = vault
    session.log_access_decision("GitHub", "Luis Gómez", "reveal_secret", True)
    session.log_access_decision("GitHub", "Marta Ruiz", "copy_secret", False)
    blocks = session.audit_log()[-2:]
    assert [b.action for b in blocks] == ["access-approve", "access-deny"]
    assert "Luis Gómez" in blocks[0].detail and "reveal_secret" in blocks[0].detail
    assert all(SECRET not in b.detail for b in session.audit_log())
    assert session.verify_integrity()[0].ok


def test_recovery_policy_is_readable_before_unlocking(vault, tmp_path):
    service, session = vault
    assert service.recovery_policy() is None
    shares = session.enroll_recovery(5, 3)
    assert len(shares) == 5
    fresh = _service(tmp_path / "personal.avault")          # no password involved
    assert fresh.recovery_policy() == (3, 5)
    assert _service(tmp_path / "missing.avault").recovery_policy() is None
