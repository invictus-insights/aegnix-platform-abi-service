from aegnix_abi.keyring import ABIKeyring

kr = ABIKeyring("db/abi_state.db")
rows = kr.list_keys()

print("=== KEYRING CONTENTS ===")
for r in rows:
    print(r)
