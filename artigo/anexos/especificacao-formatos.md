# Anexo — Especificação dos formatos (para reprodução independente)

Fonte: `src/urna3g/ballot.py`, `ledger.py`, `boletim.py`, `manifest.py` e `docs/03-criptografia.md` do repositório.

## Cédula v1

| Campo | Tamanho | Conteúdo |
|---|---|---|
| versão | 1 B | 0x01 |
| id_curto | 8 B | primeiros 8 bytes do SHA-256 do manifesto canônico |
| len_secao | 1 B | 1–16 |
| secao | len_secao | UTF-8 |
| n_votos | 1 B | ≤ 40 |
| votos | 4 B × n | int32 big-endian: >0 nº do candidato, 0 branco, −1 nulo (ordem dos slots do manifesto) |
| nonce | 16 B | `secrets.token_bytes(16)` |
| assinatura | 64 B | Ed25519(chave da seção, `b"urna3g/cedula/v1"` ‖ todos os campos acima) |

Texto do QR: `"U3G1:" + base64url(campos ‖ assinatura)` sem `=` de preenchimento.

Trecho do código (emissão e verificação):

```python
def mensagem(self) -> bytes:
    return CONTEXTO + self.cabecalho()          # CONTEXTO = b"urna3g/cedula/v1"

def verificar(cedula, eleicao, publica, secao_esperada=None):
    if cedula.eleicao_id_curto != eleicao.id_curto: raise ErroCedula("cédula pertence a outra eleição")
    if secao_esperada is not None and cedula.secao != secao_esperada: raise ErroCedula("seção diferente")
    if not crypto.verificar(publica, cedula.mensagem(), cedula.assinatura): raise ErroCedula("assinatura inválida")
    if len(cedula.votos) != len(eleicao.slots()): raise ErroCedula("número de votos incompatível")
```

## Ledger

```
genesis = SHA-256(b"urna3g/ledger/v1" ‖ eleicao_id ‖ "/" ‖ secao)
hash[s] = SHA-256(hash[s-1] ‖ uint64_be(s) ‖ tipo ‖ 0x00 ‖ dados)
tipos   = abertura | cedula (dados = texto do QR) | encerramento
```

## Boletim

JSON; assinatura = base64(Ed25519(chave de apuração, `b"urna3g/boletim/v1"` ‖ JSON canônico sem o campo
`assinatura`)); canônico = `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)`;
`hash_boletim = SHA-256(canônico)`; QR do boletim impresso: `BU1:<seção>:<hash_boletim>`.

## Manifesto

`id = SHA-256(json.dumps(manifesto, sort_keys=True, separators=(",", ":"), ensure_ascii=False))`;
assinatura = Ed25519(autoridade, `b"urna3g/eleicao/v1"` ‖ canônico), gravada em base64 em `eleicao.sig`.

## Mural

```
genesis       = SHA-256(b"urna3g/mural/v1" ‖ eleicao_id)
hash_cadeia_s = SHA-256(f"{hash_cadeia_(s-1)}|{s}|{secao}|{hash_boletim}")
```

## Código do protótipo de 2016 (para contraste)

```python
# Votar/main.py (2016) — o voto é CIFRADO com a chave pública
def encrypt(message, f):
    rsakey = RSA.importKey(f.read())            # publickey.pem
    rsakey = PKCS1_OAEP.new(rsakey)
    return rsakey.encrypt(message).encode('base64')

id_voto = random.SystemRandom().randint(0, 1000000000)   # ~30 bits
subprocess.Popen("lp '{0}'".format(VOTO_PDF), shell=True)
```
