# 01 — Resumo executivo

**Problema.** Urnas de 1ª geração (DRE), como a brasileira, gravam o voto apenas em meio digital: a integridade do
resultado depende inteiramente da confiança no software. A comunidade acadêmica propõe sistemas de 3ª geração, que
unem um registro físico conferível pelo eleitor a um registro digital, de modo que um erro de software não possa
causar um erro indetectável no resultado (princípio da independência do software). [FONTE: Brunazo & Gazziro 2014]

**Trabalho anterior.** Em 2016 o LAOB/UFABC construiu um protótipo de urna de 3ª geração (cédula impressa com texto e
código QR) e o usou numa eleição oficial do Conselho do CMCC/UFABC — a primeira urna de 3ª geração em instituição
pública brasileira segundo os autores. Em 2022, um estudo comparou quatro modelos de votação eletrônica sobre Ethereum
e concluiu que nenhum atende simultaneamente privacidade e robustez/escala. [FONTE]

**O que este trabalho faz.**
1. Revisa o código do protótipo e encontra que o QR era *cifrado* com RSA-1024 em vez de *assinado* — portanto não
   autenticava a cédula — além de um identificador anti-duplicata de ~30 bits e chaves privadas versionadas. [MEDIDO]
2. Reimplementa o sistema (Python ≥ 3.10, Ed25519, Qt 6, FastAPI): a urna assina cada cédula; verificação e apuração
   só têm a chave pública; o manifesto da eleição é assinado e seu SHA-256 vai em cada cédula; a apuração grava um
   ledger encadeado por hash e emite um boletim assinado. 59 testes automatizados, integração contínua. [MEDIDO]
3. Propõe e implementa um **modelo híbrido**: a votação continua offline e em papel; só os **hashes dos boletins**
   (um registro por seção) são ancorados numa blockchain permissionada Hyperledger Besu com consenso QBFT. [PROPOSTA
   + MEDIDO]
4. Avalia a camada de blockchain numa simulação local (4 validadores) e num **cluster real de 12 máquinas** do
   laboratório. [MEDIDO]

**Resultados principais.** [MEDIDO]
* Cédula com 3 cargos: 106 bytes de carga, 147 caracteres no QR (versão 8, correção M); assinatura em ~0,17 ms.
* Leitura óptica de 40 QR distintos (com rotação de 7° e desfoque): 40/40 com o detector ArUco do OpenCV; o detector
  clássico falhou em 3/40.
* Cluster de 12 validadores: 1 bloco a cada 2 s com todos no ar; com 3 fora, 23 blocos em 121 s; com 4 fora (limite
  teórico), a rede continua, mas aos solavancos (16 blocos em 182 s, pausas de 30–45 s); com 5 fora, para; ao
  religar um nó, voltou a produzir em 131 s. Cada nó usou 290–375 MB de RAM.
* Ensaio de eleição no cluster: 12 seções, 137 cédulas, rejeição de cédulas relidas e forjadas, 12 boletins
  ancorados entre os blocos 1072 e 1079 e eleição encerrada no bloco 1080.
* Três defeitos de integração só apareceram na simulação/implantação real (instrução PUSH0 incompatível com a
  versão da EVM da rede, preço de gás fixo em zero, endereço de bootnode por nome de host).

**Limitações.** Eleitores simulados no ensaio; validadores sob um único operador; sem verificação fim a fim; sem
teste com impressoras e leitores reais nas máquinas do cluster; permissionamento de nós não ativado.
