# 2. Arquitetura da reimplementação

## 2.1 Visão geral

```
            ANTES DA ELEIÇÃO (comissão, offline)                 DIA DA ELEIÇÃO (seção, SEM rede)                     DEPOIS (LAN do laboratório)

  ┌──────────────────────┐    pacote-eleicao.zip        ┌───────────────┐  cédula (papel)  ┌──────────────┐   cédulas      ┌──────────────┐
  │ Setup de Eleição     │  (eleicao.json + .sig +      │  URNA         │ ───────────────▶ │ VERIFICAÇÃO  │ ──▶ urna  ──▶  │  APURAÇÃO    │
  │ Setup de Urna        │   fotos + chaves públicas)   │  secao-ID.key │  texto + QR      │  secao-ID.pub│    lacrada     │  secao-ID.pub│
  │ autoridade.key       │ ───────── USB / LAN ────────▶│  (assina)     │  assinado        │  (confere)   │   (embaralha)  │  apuracao.key│
  └──────────────────────┘                              └───────────────┘                  └──────────────┘                └──────┬───────┘
                                                          nada fica em disco                 só chave pública                       │ boletim-ID.json
                                                                                                                                    │ (assinado) + ledger hash
                                                                                                                                    ▼
                                                                                       ┌──────────────────────────────────────────────────────┐
                                                                                       │ SERVIDOR (mural): verifica assinatura, encadeia,     │
                                                                                       │ publica totalização; âncora opcional em blockchain    │
                                                                                       └──────────────────────────────────────────────────────┘
```

Princípio de projeto herdado do artigo de 2017 e reforçado aqui: **a rede nunca transporta votos**. Urna, verificação e apuração funcionam desligadas da rede; só o *boletim assinado* (um resumo público por definição) viaja até o servidor. Isso elimina o servidor como ponto único de falha/ataque sobre o resultado e mantém o princípio da inviolabilidade (nenhum registro individual sai da seção em formato digital).

## 2.2 Componentes (pacote `urna3g`)

| Módulo | Responsabilidade | Depende de |
|---|---|---|
| `crypto` | Ed25519: gerar/salvar/carregar chaves (PEM, 0600, senha opcional), assinar, verificar, impressão digital | `cryptography` |
| `manifest` | `Eleicao` (cargos, partidos, candidatos, seções) ↔ JSON canônico; **id = SHA-256**; validação; hashes de fotos; assinatura do manifesto | `crypto` |
| `ballot` | Formato binário da cédula, `emitir` (assina), `decodificar`, `verificar`, `ler`, `descrever` | `crypto`, `manifest` |
| `qr`, `render` | QR (PIL) e PDFs 62 mm (cédula e boletim); `imprimir` via `lp` sem shell | `qrcode`, `reportlab` |
| `ledger` | SQLite *append-only* com cadeia de hashes, nonces únicos, ocorrências, `verificar()` | — |
| `tally` | `Apuracao`: processa leituras (aceita/duplicada/inválida/encerrada), totais, observações, boletim assinado, CSV | `ledger`, `ballot`, `boletim` |
| `boletim` | JSON canônico do boletim, assinatura, hash, QR `BU1:` | `crypto` |
| `scanner` | Decodificação de QR em imagens/quadros (OpenCV) — opcional | `opencv` |
| `audio` | Beeps do protótipo via `paplay`/`aplay` sem bloquear | — |
| `config` | Convenção de nomes das chaves; carga + validação + verificação de assinatura do manifesto | — |
| `cli` | `urna3g chaves|eleicao|cedula|apurar|boletim|servidor|gui|demo` | tudo acima |
| `gui.*` | PySide6: `votar`, `verificar`, `apurar`, `setup_urna`, `setup_eleicao`, leitores (USB "teclado" e câmera) | `PySide6` |
| `server.app` | FastAPI: distribuição do pacote, recepção de boletins, mural HTML/JSON, totalização | `fastapi` |

Tudo que a GUI faz existe também na CLI (mesmas funções do núcleo), o que permite **auditoria independente**: um fiscal pode recontar um ledger ou verificar um boletim com `urna3g apurar verificar-ledger` / `urna3g boletim verificar` em qualquer computador — ou escrever seu próprio verificador a partir do formato documentado em `03-criptografia.md`.

## 2.3 Mapeamento princípios → implementação

| Princípio (2014) | Como é atendido |
|---|---|
| Publicidade: voto impresso conferível | Cédula com texto legível + QR; verificação em máquina separada com **chave pública** |
| Fiscal verifica igualdade dos registros | Qualquer leitor de QR + `urna3g cedula ler` mostra o conteúdo assinado |
| Fiscal acompanha a contagem | Tela de apuração (projetor) atualizada cédula a cédula; ledger exportável |
| Inviolabilidade do voto | Urna não grava nada; sem timestamps por cédula; nonce aleatório (sem ordem); seção embaralha a urna lacrada |
| Independência do software | O papel permanece como registro primário; recontagem manual sempre possível; apuração recalculável a partir do ledger por software independente |
| Disponibilidade / troca rápida | Qualquer máquina com `secao-ID.key` vira urna; sem estado persistente para recuperar; apuração retomável (ledger durável, WAL + fsync) |
| Distribuição matricial, ordem dos cargos | Eleitor escolhe a urna livre e a ordem dos cargos (herdado de 2016) |
| Plebiscitos | Cargo com candidatos "Sim"/"Não" (`digitos` = 1) |
| Transparência | Código aberto, formatos documentados, mural público com boletins e hashes |

## 2.4 Modelo de ameaças (resumo)

| Ameaça | Mitigação | Residual |
|---|---|---|
| Cédula forjada fora da urna | Assinatura Ed25519 da seção; só urnas têm a chave privada | Roubo da chave da urna → forja indetectável digitalmente; **conta-se assinaturas × cédulas** e recontagem em papel |
| Mesma cédula apurada 2× | Nonce de 128 bits, índice único no ledger | — |
| Cédula de outra seção/eleição | `id` da eleição e seção dentro da assinatura | — |
| Urna imprime QR ≠ texto | Verificação em **outra** máquina pelo eleitor; cédula divergente é descartada e o eleitor revota | Depende do eleitor verificar; fiscais amostram |
| Cadastro adulterado em uma máquina | Manifesto assinado pela autoridade; hashes de fotos; `id` em toda cédula | — |
| Alteração do ledger após a apuração | Cadeia de hashes + boletim assinado com o hash final publicado/ancorado | Reescrever ledger **e** boletim exige a chave de apuração; recontagem em papel resolve |
| Servidor comprometido | Servidor não decide nada: só republica boletins verificáveis por qualquer um (chaves públicas) | Indisponibilidade do mural (DoS) — não afeta o resultado |
| Coação por foto da cédula | Igual a qualquer VVPAT: proibição de celular na cabine; cédula fica na urna | Procedimental |
| Reordenação dos votos para quebrar o sigilo | Sem horários; urna lacrada embaralhada; ordem de leitura ≠ ordem de votação | — |

## 2.5 Eficiência

* **QR menor**: ~143 caracteres (versão 7–8) contra ~175 do RSA-1024 em base64, com correção *M*; melhor leitura em webcams de 640×480 e em etiquetas térmicas de 62 mm.
* **Verificação em microssegundos** (Ed25519) e dedupe O(1) por índice único; a totalização recalculada a partir do ledger custa milissegundos para centenas de cédulas.
* **Sem banco de dados compartilhado**: o manifesto é um JSON imutável carregado uma vez; nada de SQLite copiado à mão entre 13 máquinas.
* **Leitor USB "teclado"** dispensa câmera e OpenCV nas máquinas antigas (OpenCV continua disponível como opção).
* **Impressão temporária**: a urna gera, imprime e apaga o PDF; não há acúmulo em disco.

## 2.6 Limitações conhecidas e próximos passos

1. **Verificação fim-a-fim (E2E)** continua fora do escopo (como em 2017): o eleitor confere a cédula, mas não recebe um recibo que prove a inclusão sem revelar o voto. Caminhos: cifra homomórfica/mix-nets (Rivest 2002) ou o esquema de *commitments* do Open Vote Network.
2. **Chave da urna em hardware**: hoje é um PEM (opcionalmente cifrado com senha) no disco da urna; em produção, token USB/TPM.
3. **Acessibilidade**: sem áudio de candidatos nem alto contraste; a base Qt permite adicionar.
4. **Máquinas 32 bits**: PySide6 exige x86_64; a CLI roda em qualquer lugar e uma GUI Tk de contingência seria pequena de escrever sobre o mesmo núcleo.
5. **Licença**: o repositório original não declara licença; definir com os autores antes de publicar.
