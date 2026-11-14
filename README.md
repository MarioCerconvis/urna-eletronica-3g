# Urna Eletrônica de 3ª Geração — urna3g

Reimplementação moderna do protótipo de **urna eletrônica de terceira geração** do LAOB/UFABC
(Lima, Gazziro *et al.*, SBSeg 2017; usado na eleição do Conselho do CMCC em 2016): o eleitor vota em uma
máquina isolada, recebe uma **cédula impressa** com o voto legível **e** um código QR **assinado**, confere o QR
em uma segunda máquina, deposita a cédula na urna lacrada e, na apuração pública, cada cédula é lida uma única
vez, totalizada em um **ledger encadeado por hash** e resumida em um **boletim de urna assinado**, publicado em um
mural e — opcionalmente — ancorado em uma blockchain permissionada do laboratório.

* Projeto original: <http://professor.ufabc.edu.br/~mario.gazziro/project2.html> · código de 2016 preservado na branch
  [`legacy-2017`](../../tree/legacy-2017)
* Estudo sobre blockchain em urnas (Cunha & Gazziro, 2022): <http://professor.ufabc.edu.br/~mario.gazziro/project22.html>

| | Protótipo 2016/2017 | urna3g (esta branch) |
|---|---|---|
| Linguagem / GUI | Python 2.7, PySide (Qt 4), GTK | Python ≥ 3.10, PySide6 (Qt 6) + CLI completa |
| QR | RSA-1024 **cifra** o voto; chave privada nas máquinas de verificação/apuração | **Assinatura Ed25519** pela urna; verificação/apuração só têm a chave pública |
| Anti-duplicata | `randint(0, 10⁹)` | nonce de 128 bits |
| Cadastro | SQLite copiado à mão | manifesto JSON **assinado**, com id SHA-256 em cada cédula |
| Apuração | dicionário em memória + CSV | ledger SQLite encadeado (WAL/fsync) + boletim JSON assinado + PDF + CSV |
| Rede | — | servidor FastAPI: pacote da eleição, recepção de boletins, mural público, totalização |
| Testes / CI | nenhum | 53 testes (núcleo, CLI, servidor, GUI offscreen), GitHub Actions |

## Instalação

```bash
git clone https://github.com/MarioCerconvis/urna-eletronica-3g.git
cd urna-eletronica-3g
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[gui,camera,servidor,dev]"     # escolha os extras: gui, camera (OpenCV), servidor, blockchain
pytest                                           # QT_QPA_PLATFORM=offscreen em máquinas sem display
```

## Experimente em 30 segundos

```bash
urna3g demo --saida /tmp/demo-urna --eleitores 40
```

Gera chaves, assina o manifesto de exemplo (Turma da Mônica × Disneylândia, como em 2016), emite 40 cédulas
assinadas (5 em PDF), apura, detecta releitura e cédula forjada, emite e verifica o boletim.

## Fluxo real (uma seção)

```bash
# 1. comissão (offline): chaves + manifesto assinado
urna3g chaves gerar --autoridade --secao 001 --saida chaves --senha
urna3g gui setup-eleicao --saida minha-eleicao            # ou edite exemplos/eleicao-demo/eleicao.json
urna3g eleicao assinar minha-eleicao/eleicao/eleicao.json --chave chaves/autoridade.key

# 2. urna (cabine, sem rede; só secao-001.key + autoridade.pub em chaves/)
urna3g gui votar --eleicao minha-eleicao/eleicao/eleicao.json --secao 001 --chaves chaves --impressora QL-700

# 3. verificação (outra máquina; só secao-001.pub)
urna3g gui verificar --eleicao ... --secao 001 --chaves chaves           # leitor USB ou --camera 0

# 4. apuração pública (secao-001.pub + apuracao-001.key); F10 emite o boletim
urna3g gui apurar --eleicao ... --secao 001 --chaves chaves --saida saida

# 5. mural (servidor da LAN)
urna3g servidor --dados deploy/servidor/dados
curl -X POST --data-binary @saida/boletim-001.json http://servidor:8000/api/boletins
```

Qualquer fiscal confere com `urna3g boletim verificar`, `urna3g apurar verificar-ledger` e `urna3g cedula ler`.

## Painel ao vivo

Um painel web, aberto **no seu computador** (`127.0.0.1`), que mostra o cluster como um grafo: cada ponto é uma
máquina, as linhas são as conexões reais entre os nós Besu e cada bloco aparece saindo de quem o propôs. Ao lado,
a linha do tempo de tudo o que acontece (nós caindo e voltando, quórum, blocos com transações, cada fase de cada
seção), indicadores de consenso e ritmo, o andamento das seções e o resultado parcial. Clicar numa máquina abre
os detalhes e os botões para desligá-la ou religá-la; o botão **Iniciar ensaio** roda uma eleição em que a seção K
é apurada e ancorada pela máquina K.

```bash
pip install -e ".[painel]"
urna3g painel --config exemplos/painel-cluster.json --abrir   # cluster, via máquina-ponte (SSH/Tailscale)
urna3g painel --local --abrir                                 # rede local de deploy/blockchain/besu/rede-local.sh
```

No ensaio, assinaturas, apuração e transações são reais; só os eleitores são simulados. Numa eleição oficial as
urnas ficam offline e o painel mostraria apenas as fases por seção.

## Documentação

| | |
|---|---|
| [docs/01-fundamentos.md](docs/01-fundamentos.md) | O que os artigos e monografias estabelecem (gerações, princípios, protocolo, blockchain) |
| [docs/02-arquitetura.md](docs/02-arquitetura.md) | Componentes, mapeamento princípios → implementação, modelo de ameaças, eficiência, limitações |
| [docs/03-criptografia.md](docs/03-criptografia.md) | Chaves, formato da cédula/QR, manifesto, ledger, boletim, mural |
| [docs/04-blockchain.md](docs/04-blockchain.md) | O que (não) ancorar em blockchain, a partir da análise de 2022; rede permissionada no cluster |
| [docs/05-implantacao-lab.md](docs/05-implantacao-lab.md) | **Modelo para 13 máquinas antigas + 1 servidor + LAN**: papéis, rede, instalação, Ansible |
| [docs/06-procedimentos-eleicao.md](docs/06-procedimentos-eleicao.md) | Checklist operacional: antes, durante e depois da votação |
| [deploy/](deploy/) | Dockerfile/compose do servidor, instalador de terminal quiosque, Ansible, blockchain (Besu + contrato) |

## Estrutura

```
src/urna3g/        núcleo (crypto, manifest, ballot, ledger, tally, boletim, render, qr, scanner, audio, config, cli)
src/urna3g/gui/    PySide6: votar, verificar, apurar, setup_urna, setup_eleicao, leitores (USB/câmera)
src/urna3g/server/ FastAPI: mural e recepção de boletins
tests/             pytest (núcleo, CLI, servidor, GUI offscreen)
exemplos/          eleição de demonstração
docs/  deploy/     documentação e implantação
```

## Licença e autoria

Trabalho do LAOB/UFABC (Prof. Mario Gazziro e colaboradores). O repositório original não declara licença;
a definição fica a cargo dos autores antes de uma publicação ampla.
