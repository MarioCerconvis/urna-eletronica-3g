# 4. Blockchain: o que ancorar (e o que não) — aplicando a análise de 2022

## 4.1 Lições da monografia (Cunha & Gazziro, 2022)

Os quatro modelos de e-voting sobre Ethereum analisados falham em pelo menos um critério essencial; **nenhum**
atende robustez (escala/custo). Os problemas estruturais de **votar on-chain**:

| Problema | Por quê | Consequência para o projeto |
|---|---|---|
| Privacidade | toda transação expõe remetente, dado e horário; a ligação eleitor↔endereço vive em algum sistema externo | **jamais** gravar votos individuais em uma cadeia |
| Resultados parciais | contadores públicos durante a votação (comportamento adaptativo/abortivo) | só publicar depois do encerramento da seção |
| Escala e custo | gas por eleitor; 15 725 eleitores → 13 h só para criar contas; US$ ~196/eleitor na mainnet de 2022 | ancorar **um** registro por seção, não por eleitor |
| Rede de teste ≠ garantia | testnets são reiniciadas | rede própria (permissionada) ou mainnet — nunca testnet |
| PoA privada "perde a descentralização" | validadores da mesma entidade | validadores de **stakeholders distintos** (ver 4.3) |
| Interface web / Internet | navegador e dispositivo comprometidos, MITM, DDoS | a urna continua **offline**; a blockchain nunca toca na votação |

A blockchain entra, portanto, exatamente onde ela é boa: **tornar público e imutável um pequeno conjunto de
compromissos**, de modo que ninguém — nem a comissão — consiga reescrever o resultado depois.

## 4.2 O que o urna3g ancora

Tudo que vai para a cadeia já é público e **não contém votos individuais**:

| Registro | Quando | Conteúdo (bytes32) |
|---|---|---|
| Criação da eleição | antes da votação | `eleicaoId` = SHA-256 do manifesto assinado (o mesmo id que está em cada cédula) + endereços dos apuradores autorizados |
| Boletim de seção | após `GERAR BOLETIM` | `hashBoletim` (SHA-256 do JSON canônico assinado), `hashLedger` (hash final da cadeia de cédulas), `totalCedulas` |
| Encerramento | após a última seção | `hashMural` (cadeia do servidor sobre todos os boletins) |

Com isso um fiscal com o boletim impresso/JSON em mãos verifica em três passos: (1) a assinatura Ed25519 do
apurador (`urna3g boletim verificar`), (2) que o hash do boletim está na cadeia, no bloco *N*, registrado por um
apurador autorizado, (3) que a soma dos boletins publicados reproduz a totalização. Em caso de dúvida, a recontagem
das cédulas de papel continua sendo a autoridade final (independência do software).

## 4.3 Rede permissionada no cluster de 13 máquinas

Topologia proposta (detalhes em `05-implantacao-lab.md`): usar **Hyperledger Besu com QBFT** (BFT: tolera ⌊(n−1)/3⌋
validadores maliciosos) — Clique/PoA, usado por Christyono *et al.*, não tolera validadores bizantinos e está
depreciado no Geth.

* **4 validadores** (3 permitem 0 falhas; 4 toleram 1; 7 toleram 2) operados por partes **mutuamente desconfiadas**:
  comissão eleitoral, representante de cada chapa/categoria, DCE/entidade estudantil, auditor externo (ex.: outro
  laboratório). Cada parte gera e guarda a chave do seu nó; o `genesis.json` lista os validadores.
* Os demais nós do cluster rodam como **nós observadores** (RPC), um por chapa/fiscal, que apenas replicam e
  servem consultas. Com 13 máquinas: 4 validadores + até 9 observadores (ou menos, liberando máquinas para
  urnas; o cluster não precisa ser 100 % blockchain).
* Bloco a cada 2 s, `chainId` próprio, sem gas price (`--min-gas-price=0`), contas dos apuradores pré-alocadas no
  genesis para pagar o gas (zero) — custo monetário nulo, ao contrário da mainnet.
* **Alternativa mínima** sem blockchain: o mural já é uma cadeia de hashes assinada; publicar o `hash_cadeia` final
  em um meio externo não editável (ata registrada, jornal, repositório git assinado, Twitter/Mastodon da comissão)
  oferece imutabilidade prática para uma eleição universitária. A blockchain permissionada agrega a **replicação
  entre partes adversárias** e um registro consultável por máquina.

## 4.4 Contrato e ferramentas

`deploy/blockchain/contracts/RegistroEleitoral.sol` (Solidity 0.8): `criarEleicao(eleicaoId, apuradores[])`,
`registrarBoletim(eleicaoId, secao, hashBoletim, hashLedger, totalCedulas)` (só apurador autorizado, uma vez por
seção, enquanto não encerrada), `encerrar(eleicaoId, hashMural)` (só a autoridade que criou) e funções de consulta.
Eventos permitem reconstruir tudo a partir dos logs.

`deploy/blockchain/ancorar.py` (extra `blockchain`, usa web3.py): `criar`, `registrar --boletim boletim-001.json`,
`encerrar --mural-hash …`, `consultar`. O script recalcula o hash do boletim com o próprio `urna3g.boletim`, então
o que vai para a cadeia é exatamente o que o fiscal verifica localmente.

`deploy/blockchain/besu/` traz a configuração QBFT (`qbftConfigFile.json`), o gerador de rede para N validadores,
o gerenciador da rede local (`rede-local.sh`) e o script de nó para cada máquina do cluster (`no-lab.sh`).

> Estado (2026-11-14): **simulado com sucesso** numa rede Besu QBFT de 4 validadores em Docker nesta máquina
> (`deploy/blockchain/simular.sh`). Ancoragem, recusas do contrato, consulta em outro nó, queda de 1 nó (a rede
> continua), queda de 2 (a rede para) e recuperação foram medidos; números em `deploy/blockchain/README.md`. O
> contrato e o `ancorar.py` têm testes automáticos em EVM local. Em seguida rodou no cluster do LAOB com 12
> validadores em máquinas reais (resultados em `deploy/blockchain/README.md`).

## 4.5 O que fica explicitamente fora

* Votos individuais, nonces de cédulas, ordem de apuração, horários por cédula — **nunca** on-chain.
* Identidade de eleitores — não existe em nenhum componente digital do sistema (identificação é com o mesário, em papel).
* Tokens/carteiras para eleitores — eliminados por projeto (eram a origem dos problemas de privacidade nos quatro modelos analisados).
