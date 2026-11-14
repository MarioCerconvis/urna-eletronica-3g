# 10 — Metodologia experimental

Todas as medições foram feitas em **13 e 14 de novembro de 2026**.

## 10.1 Ambientes

| Ambiente | Hardware / software | Papel |
|---|---|---|
| **A — Desenvolvimento** | Dell OptiPlex 9020, Intel Core i7-4770 (4 núcleos / 8 threads, 3,4 GHz), 27 GB RAM, Ubuntu 24.04.5, Docker 29.1.3, Python 3.12.3 | testes automatizados, demonstração, leitura de QR, simulação da rede |
| **B — Rede local simulada** | no ambiente A: 4 contêineres Besu 26.11.0 numa rede Docker com IPs fixos (172.28.0.11–14) | validação funcional da rede QBFT e do contrato |
| **C — Cluster do LAOB/UFABC** | 12 máquinas x86-64, Ubuntu 26.04, 3,3–3,4 GB RAM (uma com 5,1 GB), 61–86 GB de disco livre, rede local 192.168.0.0/24; computador principal 192.168.0.100 (15 GB RAM) como ponte; Docker instalado via apt; Besu 26.11.0 em contêiner, um nó por máquina, heap da JVM limitado a 1 GB | avaliação em máquinas reais |

* O cluster tem 13 máquinas; uma (192.168.0.107) ficou fora por não aceitar SSH por chave. Os 12 nós usados:
  .101–.106 e .108–.113.
* Acesso remoto ao cluster: Tailscale até o computador principal, e SSH dele para os nós.
* Relógios dos nós sincronizados por NTP (verificado antes do experimento).

## 10.2 Procedimentos

**P1 — Testes automatizados.** `pytest` com 59 casos (criptografia, manifesto, cédula, ledger e apuração,
renderização e QR, CLI, servidor, interface gráfica *offscreen*, contrato em EVM local, painel). Integração contínua no
GitHub Actions em Python 3.10 e 3.12.

**P2 — Demonstração ponta a ponta.** `urna3g demo` com 40 eleitores: gera chaves, assina o manifesto, emite 40 cédulas,
apura, relê uma cédula, apresenta uma cédula forjada com outra chave, emite e verifica o boletim, verifica o ledger.

**P3 — Leitura óptica de QR.** 40 cédulas distintas; QR gerado em várias escalas (4, 5, 6, 8, 10 px por módulo) e
zonas de silêncio (3 e 4 módulos); decodificação com `cv2.QRCodeDetector` e `cv2.QRCodeDetectorAruco`; variante com
rotação de 7°, escala 0,9 e desfoque gaussiano 3×3 (condição de webcam).

**P4 — Rede local (ambiente B).** Geração do genesis e das chaves com `besu operator generate-blockchain-config`;
implantação do contrato; criação de eleição; registro de boletim por apurador autorizado e tentativas por conta não
autorizada e seção repetida; consulta em nó diferente do que gravou. Tolerância: parar 1 e depois 2 de 4 validadores
(`docker stop`), medir a altura de bloco em janelas de 12–60 s, religar e medir o tempo até o próximo bloco (sondagem a
cada 1 s), para paradas de 10 s e 60 s.

**P5 — Cluster, 4 validadores** (.101–.104). Mesmo roteiro funcional de P4, com a ancoragem enviada por túnel SSH a
partir do ambiente A.

**P6 — Cluster, 12 validadores.** Subida escalonada (nó 1 primeiro, depois os demais em sequência). Medições:
tempo até o primeiro bloco; vazão com 12/12; tolerância com 4 fora (limite teórico, janela de 30 s e depois 180 s com
amostras a cada 15 s), 3 fora (120 s), 5 fora (abaixo do quórum); tempo de recuperação ao religar um nó; memória do
contêiner (`docker stats`). Os testes de falha foram executados dentro de uma sessão `tmux` no computador principal.

**P7 — Ensaio de eleição pelo painel.** Botão "Iniciar ensaio": 1 seção por máquina; eleitores simulados (número e
ritmo aleatórios em torno do valor escolhido); cédulas assinadas; apuração com inserção aleatória de uma releitura
(50% das seções) e de uma cédula forjada (25%); boletim assinado; ancoragem enviada pelo RPC do nó da seção com a
conta do seu validador; encerramento com o hash da cadeia de boletins. Executado: na rede local com injeção de falha
(2 de 4 nós parados durante o ensaio) e no cluster com 12 seções. Um segundo ensaio no cluster foi iniciado pelo
operador humano e seus registros foram conferidos lendo o contrato diretamente de um nó.

## 10.3 Métricas

* Vazão: blocos produzidos por janela de tempo (esperado: 1 a cada 2 s = 15 por 30 s).
* Tolerância: produção sim/não e vazão com f validadores fora.
* Recuperação: tempo entre religar o nó que devolve o quórum e o próximo bloco.
* Integridade: igualdade entre o hash do boletim local e o registrado na cadeia; igualdade de altura entre nós.
* Custo de recursos: memória por nó Besu.
* Correção funcional: aceitação/rejeição esperada de cédulas e transações.
