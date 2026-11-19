"""KeyDerivation that picks the adapter named by the vault header.

A vault records its KDF algorithm; the router sends each ``derive`` to the
adapter that implements it, so one build can open vaults sealed with scrypt
and with Argon2id. An algorithm with no adapter raises
``UnsupportedVaultFormat`` rather than deriving a wrong key and reporting a
wrong password.
"""
from __future__ import annotations

from ....application.errors import UnsupportedVaultFormat
from ....domain.value_objects.kdf_params import KdfParams
from ....domain.value_objects.master_key import MasterKey


class KeyDerivationRouter:
    def __init__(self, *adapters):
        self._by_algorithm: dict = {}
        for adapter in adapters:
            for algorithm in getattr(adapter, "ALGORITHMS", ()):
                self._by_algorithm.setdefault(algorithm, adapter)

    @property
    def algorithms(self) -> frozenset:
        return frozenset(self._by_algorithm)

    def adapter_for(self, algorithm: str):
        return self._by_algorithm.get(algorithm)

    def derive(self, password: str, params: KdfParams) -> MasterKey:
        adapter = self._by_algorithm.get(params.algorithm)
        if adapter is None:
            raise UnsupportedVaultFormat(
                f"Esta compilación no puede derivar claves con {params.algorithm}."
            )
        return adapter.derive(password, params)
