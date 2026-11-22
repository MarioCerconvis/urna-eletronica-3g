# 10 — Metodologia experimental

Medições preliminares em **13–14/11/2026** (§10.2, P1–P7) e a **bateria principal E1–E12 em 22/11/2026** (§10.4).

## 10.1 Ambientes

| Ambiente | Hardware / software | Papel |
|---|---|---|
| **A — Desenvolvimento** | Dell OptiPlex 9020, Intel Core i7-4770 (4 núcleos / 8 threads, 3,4 GHz), 27 GB RAM, Ubuntu 24.04.5, Docker 29.1.3, Python 3.12.3 | testes automatizados, demonstração, leitura de QR, simulação da rede |
| **B — Rede local simulada** | no ambiente A: 4 contêineres Besu 26.11.0 numa rede Docker com IPs fixos (172.28.0.11–14) | validação funcional da rede QBFT e do contrato |
| **D — Computador principal do cluster** | Intel Core i7-4790 (4c/8t, 3,6 GHz), 15 GB RAM, Ubuntu 24.04.4, na rede dos nós (192.168.0.100) | orquestrou E6–E11 (e o final de E7) em modo direto, dentro de uma sessão `tmux` |
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

## 10.4 Bateria principal E1–E12 (22/11/2026)

Cada experimento é um script em `experimentos/` que grava um JSON em `resultados/` (cópia em `anexos/dados/`) com
método, ambiente (CPU, versão, commit) e dados brutos; parciais são gravados a cada repetição. Sementes fixas
tornam os sorteios reprodutíveis. `experimentos/relatorio.py` consolida tudo em `RELATORIO-EXPERIMENTOS.md`.

| Exp. | Pergunta | Tamanho de amostra e justificativa | Onde |
|---|---|---|---|
| E1 | tamanho da cédula e do QR por nº de votos | determinístico: 1 medição por configuração (1, 2, 3, 5, 10, 20, 40 votos × seção de 3 e 16 bytes) + QR do protótipo | PC-A |
| E2 | custo das operações criptográficas | 10 000 execuções por operação após 500 de aquecimento (erro-padrão < 0,1% da média) | PC-A |
| E3 | robustez da leitura óptica | 1 000 cédulas distintas × 6 condições × 2 detectores; IC de Wilson 95% com meia-largura ≤ 3,1 p.p. no pior caso e ≤ 0,4 p.p. perto de 100% | PC-A |
| E4 | custo computacional da apuração | 10 seções de 400 cédulas no HD mecânico e na RAM; 3 seções de 5 000 na RAM | PC-A |
| E5 | regularidade dos blocos | 1 499 intervalos consecutivos do histórico (12/12 no ar) | PC-A → cluster |
| E6 | ensaio completo nominal | 10 ensaios × 12 seções = 120 ancoragens (25 eleitores-alvo, votação de 30 s) | D |
| E7 | vazão com k validadores fora | k = 0…4; 5 repetições por k, cada uma com nós **sorteados** (a vazão depende de quais caem); janela de 120 s; rede saudável antes de cada repetição | PC-A (8 repetições) e D (17) |
| E8 | recuperação após perda de quórum | paradas de 10, 30, 60 s (5 repetições) e 120 s (3, por ser a mais longa); 5 de 12 parados, religa-se 1 | D |
| E9 | gás e capacidade da ancoragem | gás de cada operação (n = 3 600 registros); 3 rajadas de 1 200 transações (12 contas × 100, cada uma pelo próprio nó) | D |
| E10 | ensaio com queda transitória | 5 ensaios; 3 validadores sorteados param 60 s ao iniciar a apuração | D |
| E11 | convergência após reinício completo | 5 reinícios escalonados + 5 simultâneos dos 12 nós | D |
| E12 | memória e CPU por nó | `docker stats` de todos os nós a cada 60 s durante E6–E11 (1 563 amostras) | D |

Procedimentos-chave:
* **Falhas** são injetadas com `docker stop -t 2 besu` / `docker start besu` em cada máquina (desligamento do nó, não
  comportamento bizantino).
* **Vazão e pausas** vêm dos timestamps dos blocos produzidos na janela (resolução de 1 s).
* **Recuperação (E8):** tempo entre o comando que religa o 8º validador e a primeira altura maior que a da parada
  (sondagem a cada 1 s); registra-se também quando o RPC do nó religado responde.
* **Ensaios (E6, E10):** mesmo código do botão "Iniciar ensaio" do painel, sem interface (`urna3g ensaio-lote`);
  conferência final de cada boletim lendo o contrato por outro nó. Eleitores simulados; a apuração roda na máquina
  orquestradora (D), e a ancoragem da seção K sai pelo nó K com a conta do validador K.
* **Capacidade (E9):** cada conta assina e envia 100 transações sem pausa (gás estimado uma vez); latência de
  inclusão = timestamp do bloco − instante do envio (relógios sincronizados por NTP).
* A fila de E7–E11 começou no PC-A e foi transferida para a máquina D após 8 repetições de E7 (retomada com a mesma
  sequência de sorteios); o método de medição é idêntico nos dois.
