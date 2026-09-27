# Test-only TLS certificates

These files exist only so [`tests/test_tls.py`](../../tests/test_tls.py) can run a real HTTPS server on
`127.0.0.1` (`scripts/fixture_site.py`, `tls=`) and prove that certificate verification is never disabled.

**The private keys here are not secrets.** They are self-signed or signed by a throwaway test CA, trusted by nothing
outside these tests, and bound to `IP:127.0.0.1` and `DNS:localhost` only. Publishing them is harmless. Never use
them for anything else.

| File | What | Subject → issuer | Subject Alt Names |
|---|---|---|---|
| `selfsigned.pem` / `selfsigned.key` | self-signed server certificate | `127.0.0.1 self-signed test` → itself | `IP:127.0.0.1`, `DNS:localhost` |
| `root_ca.pem` | test root CA (its private key was deleted after signing) | `web-monitor Test Root CA` → itself | none |
| `intermediate.pem` | test intermediate CA (private key deleted) | `web-monitor Test Intermediate CA` → test root | none |
| `leaf.pem` / `leaf.key` | server certificate that the test server sends **without** its intermediate, reproducing the HSS server's misconfiguration | `127.0.0.1` → test intermediate | `IP:127.0.0.1`, `DNS:localhost` |

All four certificates expire on 2126-09-02. They were generated with OpenSSL from
[`openssl_test_certs.cnf`](openssl_test_certs.cnf), whose extension sections (`v3_selfsigned`, `v3_root`,
`v3_intermediate`, `v3_leaf`) record exactly how each was made.

What the tests check with them:

* The self-signed server fails by default with `FETCH_ERROR … error_type=SSLError`, and no HTTP request reaches it.
  The fetch succeeds only when `selfsigned.pem` is passed as `ca_bundle`.
* `leaf.pem` fails with only `root_ca.pem` trusted, and succeeds with a bundle of `root_ca.pem` + `intermediate.pem`.
  This is the same fix the live HSS source uses (`certs/`; see the TLS section of the
  [project README](../../README.md#tls-certificates-ca_bundle)).
