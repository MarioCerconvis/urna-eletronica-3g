# 08 — Camada de blockchain: o que ancorar e como

## 8.1 Lições aplicadas da análise de 2022 [FONTE: Cunha 2022 → decisão deste trabalho]

| Problema de votar on-chain | Decisão |
|---|---|
| transação expõe remetente, conteúdo e horário | **nunca** gravar votos individuais |
| contadores públicos durante a votação influenciam eleitores | publicar só após o encerramento da seção |
| custo e tempo por eleitor (gas; 13,4 h só para criar contas de 15 725 eleitores) | **um registro por seção** |
| testnets são reiniciadas | rede própria, nunca testnet |
| PoA privada perde a descentralização | validadores de partes distintas (proposta) |
| interface web/Internet na votação | urna continua offline; a cadeia nunca toca a votação |

## 8.2 O que vai para a cadeia (tudo já público, nenhum voto individual)

| Registro | Quando | Conteúdo |
|---|---|---|
| criação da eleição | antes da votação | id da eleição (SHA-256 do manifesto) + endereços dos apuradores autorizados |
| boletim de seção | após o boletim | hash do boletim, hash final do ledger da seção, nº de cédulas |
| encerramento | após a última seção | hash da cadeia do mural |

Verificação por um fiscal com o boletim em mãos: (1) assinatura Ed25519 do apurador; (2) o hash do boletim está na
cadeia, num bloco, registrado por um apurador autorizado; (3) a soma dos boletins reproduz a totalização. Em caso de
dúvida, a recontagem do papel continua sendo a autoridade final.

## 8.3 Contrato `RegistroEleitoral` (Solidity 0.8, 103 linhas) [implementado; ver `anexos/RegistroEleitoral.sol`]

* `criarEleicao(eleicaoId, apuradores[])` — quem cria vira a autoridade daquela eleição.
* `registrarBoletim(eleicaoId, secao, hashBoletim, hashLedger, totalCedulas)` — só apurador autorizado; uma vez por
  seção; recusado após o encerramento.
* `encerrar(eleicaoId, hashMural)` — só a autoridade.
* Consultas `boletim()`, `secoes()`, `eleicao()` e eventos `EleicaoCriada`, `BoletimRegistrado`, `EleicaoEncerrada`.
* Compilado com solc 0.8.26 para a EVM **London** (ver defeito PUSH0 em `11`).

## 8.4 Rede

* **Hyperledger Besu 26.11.0, consenso QBFT**, bloco a cada 2 s, `requesttimeoutseconds` = 4, `zeroBaseFee` e
  `min-gas-price` 0 (custo monetário nulo), `chainId` próprio, saldo de teste no genesis para as contas dos
  validadores. Um contêiner Docker por máquina. [MEDIDO — configuração usada]
* Proposta para uma eleição real: **4 validadores** operados por partes mutuamente desconfiadas (comissão, chapas,
  entidade estudantil, auditor externo) e as demais máquinas como **observadoras** (replicam e servem consultas).
  Com 13 máquinas, 4 validadores + até 9 observadores. [PROPOSTA, não testada]
* Experimento: 12 validadores do mesmo operador, para medir tolerância a falhas (n = 12 → quórum 8, tolera 4).

## 8.5 Alternativa mínima sem blockchain

O mural já é uma cadeia de hashes; publicar o hash final num meio externo não editável (ata registrada, repositório
git assinado, canal oficial da comissão) dá imutabilidade prática numa eleição universitária. A blockchain
permissionada acrescenta **replicação entre partes adversárias** e um registro consultável por máquina.
