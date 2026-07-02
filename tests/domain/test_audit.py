"""The hash-chained audit ledger - the project's blockchain core."""
from ferrovault.domain.model.audit import AuditLedger, GENESIS_PREV
from ferrovault.domain.services.merkle import merkle_root


def _ledger():
    led = AuditLedger()
    led.append("init", "vault created", "t0")
    led.append("add", "github", "t1")
    led.append("add", "aws", "t2")
    return led


def test_chain_links_each_block_to_the_previous():
    led = _ledger()
    assert led.blocks[0].prev_hash == GENESIS_PREV
    assert led.blocks[1].prev_hash == led.blocks[0].hash
    assert led.blocks[2].prev_hash == led.blocks[1].hash


def test_intact_chain_verifies():
    assert _ledger().verify().ok


def test_tampering_with_a_past_block_breaks_verification():
    led = _ledger()
    # Forge history: rewrite block #1's detail without re-mining the chain.
    b = led.blocks[1]
    led.blocks[1] = type(b)(b.index, b.timestamp, b.action, "attacker",
                            b.prev_hash, b.hash)
    result = led.verify()
    assert not result.ok
    assert result.broken_index == 1


def test_deleting_a_block_breaks_the_chain():
    led = _ledger()
    del led.blocks[1]
    assert not led.verify().ok


def test_merkle_root_changes_with_contents():
    assert merkle_root(["a", "b"]) != merkle_root(["a", "c"])
    assert merkle_root([]) == "0" * 64
    assert len(merkle_root(["only"])) == 64
