from aegnix_abi.keyring import ABIKeyring
import logging
log = logging.getLogger("Demo.Keyring")

def test_add_and_revoke_key(tmp_path):
    log.info("Regisration Key Creation and Trust Enrollment (add key, list keys, revoke key)")
    db_path = tmp_path / "abi_state.db"
    ring = ABIKeyring(db_path=str(db_path))
    rec = ring.add_key("ae_test", "YWJjZA==")
    log.info(f"Added key: {rec}")
    listed = ring.list_keys()
    log.info(f"Keys after add: {listed}")
    ring.revoke_key("ae_test")
    listed = ring.list_keys()
    log.info(f"Keys after revoke: {listed}")
    assert listed[0]["status"] == "revoked"
