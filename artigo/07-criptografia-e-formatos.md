# 07 — Criptografia e formatos (detalhe técnico)

Especificação completa e código em `anexos/especificacao-formatos.md`. Aqui, o que o artigo precisa.

## 7.1 Cédula (conteúdo do QR) [implementado; tamanhos MEDIDOS]

```
texto     = "U3G1:" + base64url_sem_padding( cabecalho || assinatura )
cabecalho = versão (1 B) || id_curto da eleição (8 B, prefixo do SHA-256 do manifesto)
          || len(seção) (1 B) || seção (1–16 B, UTF-8)
          || nº de votos (1 B) || votos (int32 big-endian cada: >0 candidato, 0 branco, −1 nulo)
          || nonce (16 B, aleatório criptográfico)
assinatura = Ed25519(chave da seção, "urna3g/cedula/v1" || cabecalho)   (64 B)
```

* Com 3 cargos e seção "001": 106 bytes → **147 caracteres**, **QR versão 8**, correção de erro M (≈15%). [MEDIDO, E1]
* Comparação: no protótipo, o QR carregava 128 bytes de RSA-1024 em base64 (175 caracteres) com correção L → também
  versão 8. Mesmo tamanho físico; a nova cédula ganha correção M e autenticidade. Tamanhos para 1–40 votos em `11`.
* Emitir (montar + assinar) uma cédula: **0,117 ± 0,007 ms**; ler (decodificar + verificar): **0,197 ± 0,008 ms**
  (n = 10 000, i7-4770). [MEDIDO, E2]
* Limites: até 40 votos por cédula; seção de até 16 bytes.
* Verificação: (1) id curto igual ao da eleição; (2) seção igual à esperada; (3) assinatura válida; (4) nº de votos
  igual ao do manifesto. Número de candidato inexistente conta como nulo e é listado nas observações do boletim.

## 7.2 Manifesto da eleição

* JSON com formato, nome, data, seções, cargos (id, nome, votos por eleitor, dígitos), partidos e candidatos (com
  caminho e SHA-256 da foto).
* Forma canônica: chaves ordenadas, sem espaços, UTF-8 → `id = SHA-256(canônico)`; os 8 primeiros bytes vão em cada
  cédula. Assinatura: `Ed25519(autoridade, "urna3g/eleicao/v1" || canônico)`.

## 7.3 Ledger da apuração

* SQLite em modo WAL com `synchronous=FULL` (resiste a queda de energia).
* `genesis = SHA-256("urna3g/ledger/v1" || eleicao_id || "/" || seção)`;
  `hash[s] = SHA-256(hash[s−1] || uint64_be(s) || tipo || 0x00 || dados)`.
* Tipos de registro: `abertura` (metadados, impressão digital da chave da seção, versão do software), `cedula` (o
  texto exato do QR aceito), `encerramento`. Índice único de nonces na mesma transação do registro.
* Leituras repetidas e inválidas vão para uma tabela de ocorrências (fora da cadeia, contadas no boletim).
* **Nenhum horário por cédula** (a ordem de leitura não deve permitir reconstruir a ordem de votação).
* Totais sempre **derivados** dos registros (não há contador separado que possa divergir).

## 7.4 Boletim de urna

* JSON canônico com eleição, seção, horário de emissão, total de cédulas, ocorrências, observações, hash final e nº
  de registros do ledger, impressões digitais das chaves e resultados por cargo; assinatura Ed25519 da apuração com
  contexto `urna3g/boletim/v1`. `hash_boletim = SHA-256(canônico)`; o PDF imprime um QR `BU1:<seção>:<hash>`.
* Gerar o boletim **encerra** a apuração (registro de encerramento); nenhuma cédula é aceita depois.

## 7.5 Mural (servidor)

* Para cada boletim aceito: `hash_cadeia[s] = SHA-256(hash_cadeia[s−1] | s | seção | hash_boletim)`, gênese
  `SHA-256("urna3g/mural/v1" || eleicao_id)`. Um segundo boletim **diferente** para a mesma seção é recusado
  (HTTP 409); o mesmo boletim reenviado é idempotente.

## 7.6 Antes × depois

| | Protótipo 2016 | Este trabalho |
|---|---|---|
| Primitiva no QR | RSA-1024 + OAEP (cifra) | Ed25519 (assinatura) |
| Quem tem a chave privada | verificação e apuração | só a urna (cédula) / só a apuração (boletim) |
| Autenticidade da cédula | nenhuma | sim |
| Id anti-duplicata | ~30 bits | 128 bits |
| Colisão (400 cédulas) | ≈ 7,5 × 10⁻⁵ | ≈ 2,3 × 10⁻³⁴ |
| QR (3 votos) | 175 caracteres, versão 8, correção L | 147 caracteres, versão 8, correção M |
| Integridade do cadastro | nenhuma | manifesto assinado, hashes de fotos, id em cada cédula |
| Registro da apuração | memória + CSV | ledger encadeado durável + boletim assinado |
| Biblioteca | PyCrypto (descontinuada) | `cryptography` (OpenSSL), mantida |
