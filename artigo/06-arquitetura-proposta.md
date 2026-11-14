# 06 — Arquitetura proposta

## 6.1 Princípio de projeto

**A rede nunca transporta votos.** Urna, verificação e apuração funcionam desligadas da rede. Só o **boletim de urna
assinado** — um resumo público por definição — sai da seção em formato digital, e só o **hash** desse boletim vai para
a blockchain. Isso mantém o sigilo (nenhum registro individual nem a ordem de votação sai da seção) e tira o servidor
e a blockchain do caminho crítico do resultado. [PROPOSTA, implementada]

## 6.2 Fluxo de uma eleição

1. **Antes (comissão, offline):** gerar chaves (autoridade; urna da seção; apuração da seção) → cadastrar a eleição
   num manifesto JSON → assinar o manifesto com a chave da autoridade → distribuir o pacote (manifesto, assinatura,
   fotos, chaves públicas) e **apenas as chaves privadas de cada papel**.
2. **Votação (seção, sem rede):** eleitor se identifica ao mesário (papel) → escolhe qualquer urna livre e a ordem
   dos cargos → a urna assina e imprime a cédula (texto legível + QR) e **não grava nada** → o eleitor confere o QR
   numa máquina de verificação (que só tem a chave pública) → deposita na urna lacrada, que é chacoalhada.
3. **Apuração pública:** cada cédula é lida uma vez; a apuração verifica eleição, seção e assinatura; rejeita
   repetidas (nonce já visto) e inválidas; grava cada cédula aceita num **ledger encadeado por hash**; a tabela é
   projetada → conferência número de assinaturas × cédulas → **GERAR BOLETIM**: encerra a apuração e emite o boletim
   assinado (JSON, PDF com QR do hash, CSV).
4. **Publicação:** o boletim vai ao **mural** (servidor), que verifica a assinatura com a chave pública da apuração
   daquela seção, encadeia os boletins e publica a totalização; o hash do boletim é **ancorado na blockchain
   permissionada** pela máquina de apuração da seção.
5. **Auditoria:** qualquer fiscal verifica assinaturas, recalcula o ledger, reconta, confere o hash na cadeia e, em
   último caso, reconta o papel.

## 6.3 Componentes (pacote `urna3g`)

| Módulo | Responsabilidade |
|---|---|
| `crypto` | chaves Ed25519 em PEM (permissão 0600, senha opcional), assinar, verificar, impressão digital |
| `manifest` | eleição como JSON canônico imutável; id = SHA-256; validação; hashes das fotos; assinatura da autoridade |
| `ballot` | formato binário da cédula; emitir (assina), decodificar, verificar, descrever |
| `qr`, `render` | QR e PDFs de 62 mm (cédula e boletim); impressão via CUPS sem shell |
| `ledger` | SQLite *append-only* com cadeia de hashes (WAL + fsync), nonces únicos, verificação |
| `tally` | apuração: aceita / duplicada / inválida / encerrada; totais derivados do ledger; boletim; CSV |
| `boletim` | JSON canônico do boletim, assinatura, hash, QR `BU1:` |
| `scanner` | leitura de QR por imagem (OpenCV) |
| `cli` | `urna3g chaves | eleicao | cedula | apurar | boletim | servidor | painel | gui | demo` |
| `gui` | cinco telas em Qt 6 (votar, verificar, apurar, setup de urna, setup de eleição), modo quiosque |
| `server` | mural FastAPI: pacote da eleição, recepção de boletins, totalização pública |
| `painel` | painel web ao vivo: grafo da rede, linha do tempo, consenso, ensaio, injeção de falhas |

Tudo o que a interface gráfica faz existe na linha de comando, permitindo que um fiscal audite com as mesmas funções
ou escreva seu próprio verificador a partir dos formatos documentados (`07`).

## 6.4 Papéis e chaves

| Chave | Privada fica em | Pública vai para | Assina |
|---|---|---|---|
| autoridade | offline, com a comissão | todas as máquinas, servidor | o manifesto |
| seção (urna) | **somente** nas urnas da seção | verificação, apuração, servidor, fiscais | cada cédula |
| apuração | **somente** na máquina de apuração da seção | servidor, fiscais | o boletim |
| conta Ethereum do apurador | máquina de apuração | contrato (lista de apuradores autorizados) | a transação de ancoragem |

## 6.5 Mapeamento princípios → implementação

| Princípio | Como é atendido |
|---|---|
| Publicidade: voto impresso conferível | cédula com texto + QR; verificação em máquina separada com chave pública |
| Fiscal verifica igualdade dos registros | `urna3g cedula ler` (ou qualquer leitor que implemente o formato aberto) |
| Fiscal acompanha a contagem | tela de apuração projetada; ledger exportável |
| Inviolabilidade | urna não grava nada; sem horário por cédula; nonce aleatório; urna lacrada embaralhada |
| Independência do software | papel é o registro primário; recontagem manual sempre possível; apuração recalculável por software independente |
| Disponibilidade / troca rápida | qualquer máquina com a chave da seção vira urna; apuração retomável (ledger durável) |
| Distribuição matricial / ordem dos cargos / plebiscitos | herdados do protótipo |
| Transparência | código aberto, formatos documentados, mural público, hashes ancorados |

## 6.6 Modelo de ameaças [PROPOSTA; mitigações implementadas salvo indicação]

| Ameaça | Mitigação | Risco residual |
|---|---|---|
| cédula forjada fora da urna | assinatura Ed25519 da seção | roubo da chave da urna → conferir assinaturas × cédulas; recontagem em papel |
| mesma cédula apurada duas vezes | nonce de 128 bits com índice único no ledger | — |
| cédula de outra seção/eleição | id da eleição e seção dentro da mensagem assinada | — |
| urna imprime QR ≠ texto | verificação em outra máquina pelo eleitor; cédula divergente é descartada | depende de o eleitor verificar |
| cadastro adulterado numa máquina | manifesto assinado; hashes das fotos; id em cada cédula | — |
| alteração do ledger após a apuração | cadeia de hashes + hash final no boletim assinado + âncora na blockchain | reescrever tudo exige a chave de apuração e não altera a âncora já gravada |
| servidor comprometido | servidor só republica boletins verificáveis por qualquer um | indisponibilidade do mural (não afeta o resultado) |
| coação por foto da cédula | proibição de celular na cabine | procedimental (comum a todo VVPAT) |
| validadores da blockchain em conluio | QBFT tolera ⌊(n−1)/3⌋ bizantinos; validadores de partes distintas | **não testado**: no experimento todos os validadores tinham o mesmo operador |
| nó intruso na rede da blockchain | permissionamento de nós do Besu | **não ativado** no experimento |
