# 09 — Implementação

## 9.1 Tecnologias [MEDIDO — versões instaladas no ambiente de desenvolvimento]

| Camada | Tecnologia |
|---|---|
| Linguagem | Python 3.12 (compatível ≥ 3.10) |
| Criptografia | `cryptography` 50 (OpenSSL): Ed25519, SHA-256, PEM/PKCS#8 |
| QR / PDF | `qrcode`, Pillow, ReportLab 5.1 |
| Leitura de QR | leitor USB *keyboard wedge* (padrão) ou OpenCV 5.0 (`QRCodeDetectorAruco`) |
| Interface gráfica | PySide6 6.12 (Qt 6), modo quiosque, teclado numérico sem `xmodmap` |
| Servidor e painel | FastAPI 0.16x, Uvicorn, Server-Sent Events |
| Blockchain | Hyperledger Besu 26.11.0 (Docker), web3.py 8, solc 0.8.26 |
| Persistência | SQLite (ledger da apuração, mural) |
| Testes / qualidade | pytest, Ruff, GitHub Actions (Python 3.10 e 3.12, Qt *offscreen*) |
| Implantação | Docker/Compose (mural), script de quiosque com autostart, Ansible, scripts de rede Besu |

## 9.2 Tamanho do código [MEDIDO]

| Parte | Linhas |
|---|---|
| núcleo (`src/urna3g/*.py`) | 1 994 |
| interfaces gráficas (`gui/`) | 1 461 |
| servidor do mural (`server/`) | 307 |
| painel ao vivo (Python) | 955 |
| painel ao vivo (JS / CSS / HTML) | 570 / 304 / 197 |
| scripts de blockchain (Python) | 334 |
| contrato Solidity | 103 |
| scripts shell (implantação/rede) | 419 |
| testes | 1 026 |
| **protótipo original** (comparação) | 2 654 linhas de Python |

* 59 casos de teste automatizados (núcleo, CLI, servidor, interface gráfica *offscreen*, contrato em EVM local,
  painel), todos passando; integração contínua verde em Python 3.10 e 3.12.
* Histórico: 13 commits na branch `main` (12 deste trabalho + o commit original).

## 9.3 Interfaces

* **Votação**: lista de cargos (eleitor tecla o número do cargo), quadros de dígitos, foto/nome/partido do
  candidato, BRANCO / CORRIGE / CONFIRMA / NULO; cargos com vários votos impedem repetir o mesmo candidato; a urna
  gera, imprime e apaga o PDF (nada fica em disco); em falha de impressão, reimprime a mesma cédula.
* **Verificação**: lê o QR (USB ou câmera) e mostra o voto ou "VOTO INVÁLIDO"; exibe a impressão digital da chave
  da seção para conferência com a ata.
* **Apuração**: tabela projetável, contadores de repetidas/inválidas, hash do ledger, F10 = gerar boletim.
* **Setup de urna / eleição**: geração de chaves por papel; editor do manifesto (cargos, partidos, candidatos, fotos).
* **CLI** e `urna3g demo`, que simula uma eleição completa em disco (chaves → manifesto assinado → cédulas →
  apuração → boletim) para auditoria e ensino.

## 9.4 Painel ao vivo (ferramenta de observação) [implementado e testado]

* Roda no computador do operador (escuta só em 127.0.0.1); em modo cluster abre um túnel SSH por uma máquina-ponte
  (computador principal do cluster, alcançado por Tailscale) até a porta RPC de cada nó.
* Coleta a cada 1 s a altura de cada nó; a cada 4 s os pares (conexões P2P) e os validadores; a cada 2 s os eventos
  do contrato; a cada 8 s memória/carga das máquinas (via SSH) — e empurra tudo ao navegador por SSE.
* Mostra: **grafo** das máquinas (estado no ar / sincronizando / fora, conexões reais, anel de memória, pulso e
  partículas saindo do proponente de cada bloco — o proponente vem do campo `miner` do bloco QBFT); **linha do
  tempo** filtrável (nós caindo/voltando, quórum perdido/restabelecido, rede sem blocos, blocos com transações,
  fases das seções, eventos do contrato); indicadores (altura, ritmo, consenso com marca de quórum, estado,
  eleição, cédulas); passo a passo de cada seção; resultado parcial.
* Interação: clicar numa máquina abre detalhes e permite **desligar/religar o nó** (para/inicia o contêiner Besu), com
  aviso prévio do efeito sobre o quórum; **ensaio de eleição** com eleitores simulados (ver `00`, regras).
* Detecção de queda com **duas falhas consecutivas** (evita falso alarme por atraso momentâneo).
* Acessibilidade: tema claro/escuro, estados sempre com ícone + texto (nunca só cor), navegação por teclado,
  respeito a `prefers-reduced-motion`.

## 9.5 Implantação

* `verificar-cluster.sh`: checagem somente leitura das máquinas por SSH (sistema, RAM, disco, Docker, imagem,
  relógio, internet, porta 30303, firewall), listando o comando que resolve cada pendência.
* `gerar-rede.sh N`: genesis QBFT e chaves de N validadores com o próprio Besu.
* `implantar-cluster.sh`: distribui o genesis e **somente a chave de cada nó** para a sua máquina e liga os nós,
  começando pelo *bootnode*; `no-lab.sh` sobe um nó numa máquina (heap da JVM limitado a 1 GB).
* `simular.sh`: rede local completa + eleição de demonstração + ancoragem + teste de falhas, num comando.
* Ansible: distribui a cada terminal **apenas as chaves do seu papel** e remove chaves privadas indevidas.
