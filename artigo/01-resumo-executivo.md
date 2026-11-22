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

**Resultados principais.** [MEDIDO — bateria E1–E12, 22/11/2026]
* Cédula com 3 votos: 106 bytes, QR de 147 caracteres na **versão 8** — a mesma versão do QR do protótipo, mas com
  correção de erro M (em vez de L) e autenticada. Emitir uma cédula: 0,12 ms; ler e verificar: 0,20 ms.
* Leitura óptica: **6 000/6 000** QR lidos com o detector ArUco do OpenCV em 6 condições degradadas (webcam com
  ruído e JPEG, rotação de até 25°, impressão desbotada…); o detector clássico ficou entre 82,6% e 99,7%.
* Apuração: ~0,3 ms de CPU por cédula; 45 s de máquina por seção de 400 mesmo gravando num HD mecânico com
  confirmação física — menos de 1% do tempo da contagem pública.
* Rede de 12 validadores: 1 499/1 499 blocos a exatamente 2 s em operação normal; produziu em todas as 25
  repetições com até 4 nós fora (vazão de 30 → 25 → 20 → 18 → 14 blocos/min para 0–4 fora) e parou com 5.
  **A pausa máxima foi 14 s exatamente quando dois nós desligados eram vizinhos no rodízio do proponente (15/15).**
* Depois de perder o quórum, a recuperação é **quantizada em degraus de ≈ 38, 70, 135, 263 e 518 s** (temporizador de
  rodada dobrando a partir de 4 s): 1 min sem quórum chegou a custar 8,6 min sem blocos.
* **10/10 ensaios de eleição** (12 seções cada): 2 750 cédulas, 120/120 boletins ancorados e idênticos aos registrados
  na cadeia, 56 releituras e 31 cédulas forjadas rejeitadas; do boletim à ancoragem 2,5 s em média. Com 3 nós caindo
  60 s durante a apuração, 5/5 ensaios concluíram; as seções afetadas esperaram o próprio nó (~72 s).
* Capacidade: rajadas de 1 200 registros a 28 tx/s foram absorvidas sem fila (todas no bloco seguinte); 27 tx/s é
  limite inferior. Registrar um boletim custa ~126 600 de gás. Cada nó usou em média 389 MiB de RAM.
* Defeitos encontrados só ao executar em rede real (PUSH0 × EVM London, preço de gás fixo, bootnode por nome, perda de
  eventos no coletor) e erros de método detectados e refeitos (corte de imagem no E3, janela com cluster desligado no
  E5, medição de latência no E9).

**Limitações.** Eleitores simulados no ensaio; validadores sob um único operador; sem verificação fim a fim; sem
teste com impressoras e leitores reais nas máquinas do cluster; permissionamento de nós não ativado.
