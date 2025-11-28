If need to to help clean out the db 
sqlite3 abi_state.db

.tables;


Delete ONLY pub_ae and sub_ae
DELETE FROM keyring WHERE ae_id = 'pub_ae';
DELETE FROM keyring WHERE ae_id = 'sub_ae';


Then verify:

SELECT * FROM keyring;

........................
(abi_service) PS E:\git\invictus_insights\platform\abi_service\scripts> python .\enroll_ae.py pub_ae

=== Enrolling AE: pub_ae ===
[1] Generated new keypair
    Public Key (b64):  Mxa1MuXQ3Rr3UBic+KHCl+erYUSc1cBaP0SznjfmRPQ=
    Private Key (b64): wgwgU4jYAnRxUnMU5mFywhbY82mmVpwAJ3NEiuuS1J8=
[2] Keyring upsert complete
[3] Keyring read-back:
    ae_id:       pub_ae
    pubkey_b64:  Mxa1MuXQ3Rr3UBic+KHCl+erYUSc1cBaP0SznjfmRPQ=
    roles:
    status:      untrusted
    expires_at:  None

=== SUCCESS ===
Store the PRIVATE key safely — your AE will need it to sign the registration challenge.


.......................................
(abi_service) PS E:\git\invictus_insights\platform\abi_service\scripts> python .\enroll_ae.py sub_ae

=== Enrolling AE: sub_ae ===
[1] Generated new keypair
    Public Key (b64):  GuID6ZdkQIzHNDRTpo7xm1JiTBU4V9S9v+FIBQ8qAWs=
    Private Key (b64): 4TOFlMe3SS+Zqeo81JOVns5Y8QEqmcizSKsmp39VAMI=
[2] Keyring upsert complete
[3] Keyring read-back:
    ae_id:       sub_ae
    pubkey_b64:  GuID6ZdkQIzHNDRTpo7xm1JiTBU4V9S9v+FIBQ8qAWs=
    roles:       
    status:      untrusted
    expires_at:  None

=== SUCCESS ===
Store the PRIVATE key safely — your AE will need it to sign the registration challenge.

