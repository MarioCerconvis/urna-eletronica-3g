# 1. Fundamentos: o que os documentos do projeto estabelecem

Síntese dos documentos de referência do projeto (todos em `professor.ufabc.edu.br/~mario.gazziro/`):

| Documento | Autores | Ano | O que fixa |
|---|---|---|---|
| *Critérios para Avaliação de Sistemas Eleitorais Digitais* (SBSeg 2014) | A. Brunazo Filho, M. Gazziro | 2014 | Os **princípios** que um sistema eleitoral digital deve atender e a tabela de conformidade |
| Monografia *Urna Eletrônica de 3ª Geração* (TG Eng. de Informação, UFABC) | F. T. de Lima (orient. M. Gazziro) | 2016 | A arquitetura em 5 módulos, as bibliotecas, o estudo de caso (eleição do Conselho do CMCC) |
| *Urna eletrônica de terceira geração: um protótipo para eleições auditáveis* (SBSeg 2017) | Lima, Gazziro, Batista Jr., Matias, Costa | 2017 | O **protocolo** de voto, a análise de colisão de identificadores, o relato da eleição real |
| Monografia *A Privacidade e a Segurança de Dados no Uso de Blockchains em Urnas Eletrônicas* (MBA ICMC-USP) | R. G. Cunha (orient. M. Gazziro) | 2022 | Comparação sistemática de 4 modelos de e-voting em Ethereum sob 9 critérios |

## 1.1 Gerações de urnas

* **1ª geração — DRE** (*Direct Recording Electronic*): o voto só existe em memória digital. É o modelo brasileiro desde 1996. Toda a confiança recai no software. O Tribunal Constitucional alemão (2009) considerou esse modelo incompatível com o **princípio da publicidade**: o cidadão comum precisa poder acompanhar os passos essenciais da eleição sem conhecimento técnico.
* **2ª geração — VVPAT/IVVR**: a máquina imprime um registro em papel que o eleitor confere; o papel fica na seção e permite recontagem independente do software.
* **3ª geração — E2E / registro físico + digital unidos**: o mesmo papel carrega o texto legível **e** um registro digital (QR, ou RFID no caso argentino Vot.Ar — cujos chips foram fonte de vulnerabilidades; o papel impresso bastou para mitigá-las). O eleitor pode conferir o registro digital *antes de sair da seção*, e a apuração é feita lendo os registros digitais, com o papel como lastro.

## 1.2 Princípios (Brunazo & Gazziro, 2014)

1. **Soberania do eleitor e do candidato** — fiscalizar com recursos próprios, sem depender de peritos.
2. **Tripartição** — quem normatiza, administra, fiscaliza e julga não deveria ser a mesma entidade.
3. **Inviolabilidade absoluta do voto** — ninguém, nem juiz, pode ligar voto a eleitor; nem o eleitor pode *provar* seu voto. Consequências diretas para o projeto: **não identificar o eleitor na máquina em que vota** e **não reter dados de rastreamento** (máquina de origem, horário exato, operador).
4. **Publicidade** — o *conteúdo* do voto é público e conferível; o *autor* é secreto.
5. **Independência do software** (Rivest & Wack, 2006) — "um erro não detectado no software não pode causar um erro indetectável no resultado". Exige ≥ 2 registros do voto, um deles fora do controle do processo digital, conferível pelo eleitor antes de sair. Diretrizes VVSG (NIST) §7.8.
6. **Disponibilidade absoluta** — a eleição não pode parar; resistência a DoS, troca rápida de equipamento.
7. Desejáveis: usabilidade, direito de refutação na seção, celeridade, recuperação simples, logística barata, **distribuição matricial** (o eleitor escolhe uma urna livre), eleitor escolhe a ordem dos cargos, plebiscitos.

Modelo de **segurança por transparência** (software aberto, procedimentos públicos) *versus* **segurança por ofuscamento**.

## 1.3 O protótipo UFABC (2016–2017)

Cinco módulos, executados nesta ordem:

| Módulo | O que faz | Onde roda |
|---|---|---|
| **Ajuste de Urna** | gera o par de chaves da seção | comissão |
| **Ajuste de Eleição** | cadastra partidos/chapas, cargos (com *n* votos por cargo) e candidatos com foto | comissão |
| **Votação** | eleitor escolhe a ordem dos cargos, digita o número, confirma; imprime a cédula (texto + QR) | cabine (netbook + teclado numérico + impressora) |
| **Verificação** | lê o QR e mostra o voto, para comparar com o texto impresso | **outra** máquina da seção |
| **Apuração** | lê cada cédula da urna lacrada uma única vez (identificador aleatório), totaliza na tela (projetor) e imprime o **boletim de urna** | mesa de apuração |

Protocolo: inicialização (chaves + cadastros) → votação (identificação com o mesário, cabine, impressão, **verificação em outra máquina**, depósito em urna lacrada e **chacoalhada** para embaralhar) → transporte → contagem pública cédula a cédula → boletim → conferência assinaturas × cédulas.

Estudo de caso: eleição do Conselho do CMCC (UFABC), julho/2016 — 12 vagas, 2 campi, 64 eleitores apurados em 15 min (≈15 s/cédula), primeira urna de 3ª geração usada em instituição pública brasileira. Estimativa para seção de 400 eleitores: 1h30 de apuração.

Fragilidades do protótipo que esta reimplementação corrige (ver `02-arquitetura.md` e `03-criptografia.md`):

* O QR era **cifrado** com a chave pública (RSA-1024 OAEP) e decifrado nas máquinas de verificação/apuração com a chave **privada**. Isso não autentica nada: qualquer um com a chave pública forja cédulas "válidas", e a chave privada acabava em várias máquinas. A monografia descrevia a intenção correta ("a urna **assina**"), mas o código fazia o oposto.
* Identificador anti-dupla-contagem de ~30 bits (`randint(0, 10⁹)`); a monografia pretendia 16 bytes.
* Chaves privadas versionadas no repositório; Python 2.7/Qt 4/PyCrypto (todos descontinuados); `shell=True` em chamadas de impressão; cadastro em SQLite mutável copiado entre máquinas sem verificação de integridade.

## 1.4 Blockchain em urnas (Cunha & Gazziro, 2022)

Critérios de Taş & Tanrıöver (2020) aplicados a quatro modelos sobre Ethereum (Koç 2018; Khoury 2018; Christyono 2021 — Go-Ethereum/Clique PoA; McCorry 2017 — *Open Vote Network*):

| Critério | Resultado geral |
|---|---|
| Não produzir recibo | todos ✓ |
| Não produzir resultados preliminares | só Open Vote Network ✓ (fase de *commitment*) |
| Integridade | ✓ na *mainnet*; **redes de teste não garantem nada**; rede privada PoA perde a descentralização |
| Privacidade/anonimato | só Open Vote Network ✓ (provas de conhecimento zero); nos demais, `msg.sender` + parâmetro do voto + horário ficam públicos |
| Só registrados / voto único | todos ✓ |
| **Robustez (escala)** | **nenhum** ✓ — 383 eleitores no limite de gas; 15 725 eleitores → 13 h só para criar contas; custo ≈ US$ 196 por eleitor na mainnet de 2022 |
| Confiabilidade | só Open Vote Network tem repositório/processo — mas não roda mais na rede atual |
| Verificabilidade | ✓ (trivialmente, porque é tudo público, exceto no ONV) |

Conclusões que orientam este projeto:

1. **Voto individual on-chain é má ideia** para privacidade (endereço + horário + conteúdo), para o sigilo antes do fim da votação e para escala/custo.
2. O que a blockchain faz bem é **imutabilidade e auditabilidade pública de poucos registros**: manifesto, chaves públicas, boletins de urna assinados e hashes de ledger.
3. Uma rede **permissionada** (PoA/QBFT) só tem valor se os validadores forem **entidades mutuamente desconfiadas** (comissão, chapas, DCE, auditor externo); 13 nós da mesma pessoa é descentralização de fachada.
4. Independência do software continua valendo: a blockchain **não substitui** o papel; ela ancora o resultado digital para que ninguém possa reescrevê-lo depois.

Essa é a base do modelo híbrido descrito em `04-blockchain.md`: **papel + QR assinado na seção, ledger encadeado por hash na apuração, boletim assinado publicado no mural e ancorado em uma rede permissionada do laboratório.**
