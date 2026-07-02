"""Use-case tests with in-memory fakes - no files, no real crypto, no network."""
from ferrovault.application.errors import AuthenticationError
from ferrovault.application.services.vault_service import VaultService
from ferrovault.domain.value_objects.kdf_params import KdfParams
from ferrovault.domain.value_objects.master_key import MasterKey


class FakeRepo:
    def __init__(self):
        self.artifact = None
    def exists(self):
        return self.artifact is not None
    def load(self):
        return self.artifact
    def save(self, artifact):
        self.artifact = artifact


class FakeKdf:
    def derive(self, password, params):
        return MasterKey(password.encode().ljust(32, b"0")[:32])


class XorCipher:
    """Toy authenticated cipher for tests: XOR + a tag tied to key+aad."""
    def encrypt(self, key, plaintext, aad):
        nonce = b"\x01" * 12
        ct = bytes(b ^ key[i % len(key)] for i, b in enumerate(plaintext))
        return nonce, ct + b"|" + key[:4] + aad[:4]
    def decrypt(self, key, nonce, ciphertext, aad):
        body, _, tag = ciphertext.rpartition(b"|")
        if tag != key[:4] + aad[:4]:
            raise ValueError("bad tag")
        return bytes(b ^ key[i % len(key)] for i, b in enumerate(body))


class FakeClock:
    def now_iso(self):
        return "2026-01-01T00:00:00+00:00"
    def now_unix(self):
        return 1767225600


def _service(repo):
    return VaultService(repo, FakeKdf(), XorCipher(), FakeClock(),
                        kdf_factory=KdfParams.scrypt)


def test_full_roundtrip_add_then_get():
    repo = FakeRepo()
    svc = _service(repo)
    svc.init_vault("correct horse")
    svc.add_entry("correct horse", "github", "octocat", "s3cr3t", tags=("dev",))
    assert svc.get_secret("correct horse", "github") == "s3cr3t"
    assert svc.list_entries("correct horse")[0].name == "github"


def test_wrong_password_fails_authentication():
    repo = FakeRepo()
    _service(repo).init_vault("right")
    try:
        _service(repo).get_secret("wrong", "anything")
        assert False, "should have raised"
    except AuthenticationError:
        pass
