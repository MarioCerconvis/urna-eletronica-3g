# 3. Criptografia e formatos

## 3.1 Chaves e papéis

Três pares Ed25519 (RFC 8032), todos gerados por `urna3g chaves gerar` ou pelo Setup de Urna:

| Chave | Onde fica a **privada** | Onde vai a **pública** | Assina |
|---|---|---|---|
| `autoridade` | offline, com a comissão eleitoral (idealmente em mídia removível guardada) | servidor, todas as máquinas (`autoridade.pub`) | o manifesto (`eleicao.sig`) |
| `secao-ID` | **somente** nas urnas de votação da seção | verificação, apuração, servidor, fiscais | cada cédula |
| `apuracao-ID` | **somente** na máquina de apuração da seção | servidor, fiscais | o boletim de urna |

*Impressão digital* = SHA-256 dos 32 bytes da chave pública, exibida em 8 grupos de 8 hex. Fiscais comparam a impressão exibida na tela de verificação/apuração com a publicada no mural (`/api/chaves`) e na ata.

Arquivos PEM: privada em PKCS#8 (opcionalmente cifrada — `BestAvailableEncryption`, derivação PBKDF2 do OpenSSL) com permissão `0600`; pública em SubjectPublicKeyInfo.

## 3.2 Manifesto da eleição

`eleicao.json` → forma canônica `json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)` em UTF-8 → `id = SHA-256(canônico)` (64 hex). Os 8 primeiros bytes (`id_curto`) entram em cada cédula. `urna3g eleicao assinar` preenche `foto_sha256` de cada foto antes de assinar, de modo que a assinatura cobre também as imagens.

Assinatura: `Ed25519(autoridade, b"urna3g/eleicao/v1" || canônico)`, gravada em base64 em `eleicao.sig`.

## 3.3 Cédula (conteúdo do QR)

```
texto = "U3G1:" + base64url_sem_padding( cabecalho || assinatura )

cabecalho = 0x01                        versão
          || id_curto (8 B)             SHA-256 do manifesto, 8 primeiros bytes
          || len(secao) (1 B) || secao  UTF-8, 1–16 bytes
          || n_slots (1 B)
          || int32_be × n_slots         >0 nº do candidato · 0 BRANCO · −1 NULO  (ordem dos slots do manifesto)
          || nonce (16 B)               secrets.token_bytes — identificador único da cédula
assinatura = Ed25519(secao-ID, b"urna3g/cedula/v1" || cabecalho)     (64 B)
```

Tamanho com 3 cargos: 1+8+4+1+12+16+64 = 106 B → 142 caracteres → QR versão 7 (correção M). Capacidade: até 40 slots e seções de 16 bytes.

**Verificação** (`ballot.verificar`): (1) `id_curto` igual ao da eleição carregada; (2) seção igual à esperada (se informada); (3) assinatura válida; (4) nº de slots igual ao do manifesto. Só então o conteúdo é interpretado. Números de candidato inexistentes são contados como **nulo** e listados em "observações" do boletim.

**Colisão de nonces**: a análise da seção 4 do artigo de 2017 (paradoxo do aniversário) com n = 2¹²⁸ dá, para k = 400 eleitores, P(colisão) ≈ k²/(2·2¹²⁸) ≈ 2,3 × 10⁻³⁴ — contra ≈ 7,5 × 10⁻⁵ do `randint(0, 10⁹)` original. Em eleições nacionais (10⁸ cédulas) continuaria em ~10⁻²³.

## 3.4 Ledger da apuração

SQLite com `journal_mode=WAL` e `synchronous=FULL` (durável a quedas de energia). Tabela `registros(seq, tipo, dados, hash_anterior, hash)`:

```
genesis  = SHA-256(b"urna3g/ledger/v1" || eleicao_id || "/" || secao)
hash[s]  = SHA-256(hash[s-1] || uint64_be(s) || tipo || 0x00 || dados)
```

Tipos: `abertura` (metadados, impressão digital da chave da seção, versão do software), `cedula` (o texto exato do QR aceito), `encerramento`. A tabela `cedulas(nonce UNIQUE → seq)` impede dupla contagem na mesma transação do registro. Leituras repetidas/inválidas vão para `ocorrencias` (fora da cadeia, mas contadas no boletim). **Nenhum timestamp por cédula.**

`Ledger.verificar()` recalcula tudo; qualquer alteração, remoção, inserção ou reordenação é detectada. A totalização é sempre **derivada** dos registros (não há contador separado que possa divergir).

## 3.5 Boletim de urna

JSON com `formato, software, eleicao_id, eleicao_nome, secao, emitido_em, total_cedulas, ocorrencias, observacoes, ledger{registros, hash_final}, chave_publica_secao, chave_publica_apuracao, resultados{cargo: {nome, votos{numero|branco|nulo: n}, legenda}}` e `assinatura = base64(Ed25519(apuracao-ID, b"urna3g/boletim/v1" || canônico_sem_assinatura))`. `hash_boletim = SHA-256(canônico)`; o QR impresso contém `BU1:<secao>:<hash>`.

Gerar o boletim **encerra** a apuração (registro `encerramento` + flag) — nenhuma cédula entra depois, como no botão "GERAR BOLETIM" de 2016.

## 3.6 Mural (servidor)

Para cada boletim aceito: `hash_cadeia[s] = SHA-256(hash_cadeia[s-1] || "|" || s || "|" || secao || "|" || hash_boletim)`, com `genesis = SHA-256(b"urna3g/mural/v1" || eleicao_id)`. O hash de cadeia final é o valor a ancorar em blockchain (`04-blockchain.md`). Um segundo boletim diferente para a mesma seção é recusado (HTTP 409): retificações passam pela comissão, não pelo servidor.

## 3.7 Antes × depois

| | Protótipo 2016/2017 | Esta versão |
|---|---|---|
| Primitiva | RSA-1024 + PKCS#1 OAEP (**cifra**) | Ed25519 (**assinatura**) |
| Quem tem a privada | verificação e apuração | só a urna (cédula) / só o apurador (boletim) |
| Autenticidade da cédula | nenhuma (qualquer um com a pública forja) | sim |
| Id anti-duplicata | `randint(0, 10⁹)` (~30 bits) | 128 bits aleatórios |
| Integridade do cadastro | nenhuma | manifesto assinado + hashes de fotos + id em cada cédula |
| Registro da apuração | dicionário em memória + CSV | ledger encadeado durável + boletim assinado |
| Biblioteca | PyCrypto (abandonada em 2013) | `cryptography` (mantida; OpenSSL) |
