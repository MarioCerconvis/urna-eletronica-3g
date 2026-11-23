# Document S2 — Specification of the Urna3G data formats (for independent verifiers)

Source: `src/urna3g/ballot.py`, `ledger.py`, `boletim.py`, `manifest.py` and `docs/03-criptografia.md` of the
repository https://github.com/MarioCerconvis/urna-eletronica-3g. Identifiers and context strings are kept
exactly as in the code (Portuguese words: *cédula* = ballot, *boletim* = tally report, *eleição* = election,
*mural* = bulletin board, *seção* = polling station).

## 1. Ballot (version 1)

| Field | Size | Content |
|---|---|---|
| version | 1 B | `0x01` |
| short election id | 8 B | first 8 bytes of the SHA-256 digest of the canonical manifest |
| station length | 1 B | 1–16 |
| station | station length | polling-station identifier, UTF-8 |
| number of votes | 1 B | ≤ 40 |
| votes | 4 B × n | big-endian int32 each: > 0 candidate number, 0 blank, −1 null (in the order of the manifest slots) |
| nonce | 16 B | `secrets.token_bytes(16)` |
| signature | 64 B | Ed25519(polling-station key, `b"urna3g/cedula/v1"` ‖ all fields above) |

QR text: `"U3G1:" + base64url(fields ‖ signature)`, without `=` padding.
Example: 3 contests and station `"001"` → 106 bytes → 142 base64url characters + 5-character prefix = 147 characters (QR version 8, level M).

Verification, in this order (a ballot is rejected at the first failing check):
1. short election id equals the first 8 bytes of the manifest id;
2. station equals the expected station (when given);
3. Ed25519 signature is valid under the station public key for `b"urna3g/cedula/v1"` ‖ header;
4. number of votes equals the number of slots in the manifest.
A candidate number absent from the manifest is counted as null and listed in the report observations.

## 2. Election manifest

Canonical form: `json.dumps(manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=False)` encoded in UTF-8.
`election_id = SHA-256(canonical)`; signature = Ed25519(authority key, `b"urna3g/eleicao/v1"` ‖ canonical), stored in base64 in `eleicao.sig`.

## 3. Tally ledger (one per polling station)

```
genesis = SHA-256(b"urna3g/ledger/v1" ‖ election_id ‖ "/" ‖ station)
hash[s] = SHA-256(hash[s-1] ‖ uint64_be(s) ‖ type ‖ 0x00 ‖ data)
types   = abertura (opening) | cedula (ballot; data = exact QR text) | encerramento (closing)
```
SQLite in WAL mode with `synchronous=FULL`; the nonce of each accepted ballot is inserted in a unique index in the
same transaction as the record; repeated and invalid reads are stored as occurrences outside the chain; no record
has a timestamp; totals are derived from the records.

## 4. Tally report (*boletim*)

JSON object; signature = base64(Ed25519(tally key, `b"urna3g/boletim/v1"` ‖ canonical JSON without the field
`assinatura`)), with the canonical form defined as in Section 2; `report_hash = SHA-256(canonical)`; the printed PDF
carries a QR code `BU1:<station>:<report_hash>`. Generating the report appends the closing record to the ledger.

## 5. Public bulletin board (*mural*)

```
genesis       = SHA-256(b"urna3g/mural/v1" ‖ election_id)
chain_hash_s  = SHA-256(f"{chain_hash_(s-1)}|{s}|{station}|{report_hash}")
```
A second, different report for the same station is refused (HTTP 409); resubmitting the same report is idempotent.

## 6. Anchoring contract (`RegistroEleitoral`, Code S3)

* `criarEleicao(eleicaoId, apuradores[])` — registers an election (id = SHA-256 of the manifest) and the authorized tally accounts; the caller becomes the authority of that election.
* `registrarBoletim(eleicaoId, secao, hashBoletim, hashLedger, totalCedulas)` — authorized accounts only; once per station; refused after closing.
* `encerrar(eleicaoId, hashMural)` — authority only.
* Read-only: `boletim()`, `secoes()`, `eleicao()`; events `EleicaoCriada`, `BoletimRegistrado`, `EleicaoEncerrada`.
* Compiled with solc 0.8.26 for the London EVM.

## 7. 2016 prototype (for contrast)

```python
# Votar/main.py (2016) — the vote is ENCRYPTED with the public key
def encrypt(message, f):
    rsakey = RSA.importKey(f.read())            # publickey.pem
    rsakey = PKCS1_OAEP.new(rsakey)
    return rsakey.encrypt(message).encode('base64')

id_voto = random.SystemRandom().randint(0, 1000000000)   # ~30 bits
subprocess.Popen("lp '{0}'".format(VOTO_PDF), shell=True)
```
