import pytest

from ferrovault.domain.model.vault import (Entry, EntryNameTaken,
                                           EntryNotFound, Vault)
from ferrovault.domain.value_objects.entry_id import EntryId
from ferrovault.domain.value_objects.secret import Secret


def _entry(name):
    return Entry(EntryId.new(), name, "user", Secret("pw"))


def test_add_and_get():
    v = Vault()
    v.add(_entry("github"))
    assert v.get("GitHub").name == "github"   # case-insensitive
    assert len(v) == 1


def test_unique_name_invariant():
    v = Vault()
    v.add(_entry("aws"))
    with pytest.raises(EntryNameTaken):
        v.add(_entry("AWS"))


def test_remove_missing_raises():
    with pytest.raises(EntryNotFound):
        Vault().remove("nope")
