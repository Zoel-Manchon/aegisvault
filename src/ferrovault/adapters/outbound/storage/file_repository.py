"""VaultRepository adapter: store the encrypted artifact as a single JSON file.

Knows nothing about crypto - it persists opaque bytes (base64) plus the
authenticated header.

Durability: the new content goes to a temporary file in the same directory,
is flushed and fsync'ed, and only then atomically replaces the vault, so a
crash or power cut leaves either the old vault or the new one, never a
truncated file. On POSIX the file is created 0600.

``snapshot()`` copies the sealed file into a backup folder (default: a
``<name>-copias`` folder next to the vault) and keeps the newest ``keep``.
Snapshots are as encrypted as the vault itself.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import time
from pathlib import Path

from ....application.services.dto import EncryptedVault

DEFAULT_KEEP = 10


class FileVaultRepository:
    def __init__(self, path: str, backup_dir: str | None = None, keep: int = DEFAULT_KEEP):
        self._path = str(path)
        self._backup_dir = backup_dir
        self._keep = max(1, int(keep))

    @property
    def path(self) -> str:
        return self._path

    @property
    def backup_dir(self) -> Path:
        if self._backup_dir:
            return Path(self._backup_dir)
        p = Path(self._path)
        return p.parent / f"{p.stem}-copias"

    def configure_backups(self, backup_dir: str | None = None, keep: int | None = None) -> None:
        if backup_dir is not None:
            self._backup_dir = backup_dir or None
        if keep is not None:
            self._keep = max(1, int(keep))

    def exists(self) -> bool:
        return os.path.exists(self._path)

    def load(self) -> EncryptedVault:
        with open(self._path, encoding="utf-8") as fh:
            doc = json.load(fh)
        if not isinstance(doc, dict) or not isinstance(doc.get("header"), dict):
            raise ValueError(f"{self._path} is not an AegisVault file")
        return EncryptedVault(
            header=doc["header"],
            nonce=base64.b64decode(doc["nonce"]),
            ciphertext=base64.b64decode(doc["ciphertext"]),
        )

    def save(self, artifact: EncryptedVault) -> None:
        doc = {
            "header": artifact.header,
            "nonce": base64.b64encode(artifact.nonce).decode(),
            "ciphertext": base64.b64encode(artifact.ciphertext).decode(),
        }
        target = Path(self._path)
        directory = target.parent if str(target.parent) else Path(".")
        directory.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=directory)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            if os.name != "nt":
                os.chmod(tmp, 0o600)
            os.replace(tmp, self._path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        _fsync_dir(directory)

    def snapshot(self, label: str = "manual") -> str | None:
        """Copy the current sealed file to the backup folder; returns its path."""
        if not self.exists():
            return None
        folder = self.backup_dir
        folder.mkdir(parents=True, exist_ok=True)
        stem, suffix = Path(self._path).stem, Path(self._path).suffix or ".fv"
        safe_label = "".join(c if c.isalnum() or c in "-_" else "-" for c in label)[:32] or "copia"
        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = folder / f"{stem}-{stamp}-{safe_label}{suffix}"
        n = 1
        while dest.exists():
            dest = folder / f"{stem}-{stamp}-{safe_label}-{n}{suffix}"
            n += 1
        # copyfile, not copy2: the snapshot's mtime must be when it was taken,
        # because pruning keeps the newest ones by mtime.
        shutil.copyfile(self._path, dest)
        if os.name != "nt":
            os.chmod(dest, 0o600)
        self._prune(folder, stem, suffix)
        return str(dest)

    def read(self, path) -> EncryptedVault:
        """Load the artifact of another file (a backup copy) without touching the vault."""
        return FileVaultRepository(str(path)).load()

    def snapshots(self) -> list[Path]:
        folder = self.backup_dir
        if not folder.is_dir():
            return []
        stem, suffix = Path(self._path).stem, Path(self._path).suffix or ".fv"
        found = [p for p in folder.glob(f"{stem}-*{suffix}") if p.is_file()]
        return sorted(found, key=lambda p: (p.stat().st_mtime_ns, p.name), reverse=True)

    def _prune(self, folder: Path, stem: str, suffix: str) -> None:
        for old in self.snapshots()[self._keep:]:
            try:
                old.unlink()
            except OSError:
                pass


def _fsync_dir(directory: Path) -> None:
    """Persist the rename itself (POSIX; Windows has no directory handles for this)."""
    if os.name == "nt":
        return
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)
