from aegnix_abi.keyring import ABIKeyring

def test_add_and_revoke_key(tmp_path):
    db_path = tmp_path / "abi_state.db"
    ring = ABIKeyring(db_path=str(db_path))
    rec = ring.add_key("ae_test", "YWJjZA==")
    assert rec.ae_id == "ae_test"
    listed = ring.list_keys()
    assert listed[0]["status"] == "trusted"
    ring.revoke_key("ae_test")
    listed = ring.list_keys()
    assert listed[0]["status"] == "revoked"
