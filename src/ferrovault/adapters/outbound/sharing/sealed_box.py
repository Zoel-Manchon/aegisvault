"""Public-key secret sharing via an X25519 sealed box (ECIES).

Encrypt a secret *to* a colleague's public key so only their private key can
open it — the enterprise "share this credential securely" primitive. Uses an
ephemeral X25519 keypair per message, ECDH, HKDF-SHA256 to derive a key, and
AES-256-GCM for the payload. The shared secret is bound to both public keys via
the HKDF info, so a blob can't be re-pointed at a different recipient.

Wire format (then base64):  0x01 | eph_pub(32) | nonce(12) | ciphertext
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey, X25519PublicKey)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding, PrivateFormat, PublicFormat, NoEncryption)

_VERSION = 1
_INFO = b"ferrovault:share:v1"


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _b64d(s: str) -> bytes:
    return base64.b64decode(s.strip())


def _raw_pub(pub: X25519PublicKey) -> bytes:
    return pub.public_bytes(Encoding.Raw, PublicFormat.Raw)


def generate_keypair() -> tuple:
    """Return (private_key_b64, public_key_b64)."""
    priv = X25519PrivateKey.generate()
    priv_raw = priv.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
    return _b64(priv_raw), _b64(_raw_pub(priv.public_key()))


def _derive(shared: bytes, eph_pub: bytes, recipient_pub: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None,
                info=_INFO + eph_pub + recipient_pub).derive(shared)


def seal(plaintext: str, recipient_pub_b64: str) -> str:
    recipient_pub_raw = _b64d(recipient_pub_b64)
    recipient_pub = X25519PublicKey.from_public_bytes(recipient_pub_raw)
    eph = X25519PrivateKey.generate()
    eph_pub_raw = _raw_pub(eph.public_key())
    shared = eph.exchange(recipient_pub)
    key = _derive(shared, eph_pub_raw, recipient_pub_raw)
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return _b64(bytes([_VERSION]) + eph_pub_raw + nonce + ct)


def open_sealed(blob_b64: str, recipient_priv_b64: str) -> str:
    blob = _b64d(blob_b64)
    if not blob or blob[0] != _VERSION:
        raise ValueError("unrecognised share blob")
    eph_pub_raw, nonce, ct = blob[1:33], blob[33:45], blob[45:]
    priv = X25519PrivateKey.from_private_bytes(_b64d(recipient_priv_b64))
    recipient_pub_raw = _raw_pub(priv.public_key())
    shared = priv.exchange(X25519PublicKey.from_public_bytes(eph_pub_raw))
    key = _derive(shared, eph_pub_raw, recipient_pub_raw)
    return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
