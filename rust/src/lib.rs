//! ferrovault's crypto core, in Rust.
//!
//! Three primitives, exposed to Python via PyO3:
//!   - `derive_key`  : Argon2id password-based key derivation
//!   - `encrypt`     : XChaCha20-Poly1305 AEAD (random 24-byte nonce)
//!   - `decrypt`     : XChaCha20-Poly1305 AEAD verify + decrypt
//!
//! Derived key material is wiped (`zeroize`) before each function returns, so
//! it does not linger in the Rust heap. These satisfy the same `KeyDerivation`
//! and `Cipher` ports as the pure-Python adapters; the composition root picks
//! this backend when the extension is built.

use chacha20poly1305::aead::{Aead, KeyInit, Payload};
use chacha20poly1305::{XChaCha20Poly1305, XNonce};
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyBytes;
use rand::RngCore;
use zeroize::Zeroize;

/// Argon2id KDF. `m_cost` is in KiB, `t_cost` is iterations, `p_cost` lanes.
#[pyfunction]
fn derive_key<'py>(
    py: Python<'py>,
    password: &[u8],
    salt: &[u8],
    t_cost: u32,
    m_cost: u32,
    p_cost: u32,
    length: usize,
) -> PyResult<Bound<'py, PyBytes>> {
    use argon2::{Algorithm, Argon2, Params, Version};

    let params = Params::new(m_cost, t_cost, p_cost, Some(length))
        .map_err(|e| PyValueError::new_err(format!("bad argon2 params: {e}")))?;
    let argon = Argon2::new(Algorithm::Argon2id, Version::V0x13, params);

    let mut out = vec![0u8; length];
    argon
        .hash_password_into(password, salt, &mut out)
        .map_err(|e| PyValueError::new_err(format!("kdf failed: {e}")))?;

    let result = PyBytes::new(py, &out);
    out.zeroize();
    Ok(result)
}

/// Encrypt with XChaCha20-Poly1305. Returns (nonce, ciphertext-with-tag).
#[pyfunction]
fn encrypt<'py>(
    py: Python<'py>,
    key: &[u8],
    plaintext: &[u8],
    aad: &[u8],
) -> PyResult<(Bound<'py, PyBytes>, Bound<'py, PyBytes>)> {
    let cipher = XChaCha20Poly1305::new_from_slice(key)
        .map_err(|_| PyValueError::new_err("key must be 32 bytes"))?;

    let mut nonce_bytes = [0u8; 24];
    rand::thread_rng().fill_bytes(&mut nonce_bytes);
    let nonce = XNonce::from_slice(&nonce_bytes);

    let ciphertext = cipher
        .encrypt(nonce, Payload { msg: plaintext, aad })
        .map_err(|_| PyValueError::new_err("encryption failed"))?;

    Ok((
        PyBytes::new(py, &nonce_bytes),
        PyBytes::new(py, &ciphertext),
    ))
}

/// Verify + decrypt. Raises ValueError on any authentication failure.
#[pyfunction]
fn decrypt<'py>(
    py: Python<'py>,
    key: &[u8],
    nonce: &[u8],
    ciphertext: &[u8],
    aad: &[u8],
) -> PyResult<Bound<'py, PyBytes>> {
    let cipher = XChaCha20Poly1305::new_from_slice(key)
        .map_err(|_| PyValueError::new_err("key must be 32 bytes"))?;
    if nonce.len() != 24 {
        return Err(PyValueError::new_err("nonce must be 24 bytes"));
    }
    let plaintext = cipher
        .decrypt(XNonce::from_slice(nonce), Payload { msg: ciphertext, aad })
        .map_err(|_| PyValueError::new_err("decryption failed (wrong key or tampered)"))?;

    Ok(PyBytes::new(py, &plaintext))
}

#[pymodule]
fn ferrocrypto(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(derive_key, m)?)?;
    m.add_function(wrap_pyfunction!(encrypt, m)?)?;
    m.add_function(wrap_pyfunction!(decrypt, m)?)?;
    Ok(())
}
