# 5. Modelo de implantação: 13 máquinas antigas + 1 servidor + LAN

## 5.1 Requisitos mínimos por máquina

| Papel | CPU/RAM | Periféricos | Software |
|---|---|---|---|
| Urna (votar) | x86_64, 2 GB | monitor, **teclado numérico USB** (sem teclado completo), impressora de etiquetas 62 mm (ex.: Brother QL-700) ou térmica 58/80 mm via CUPS | Debian/Ubuntu + `urna3g[gui]` |
| Verificação | x86_64, 2 GB | monitor, leitor de QR USB *keyboard wedge* (ou webcam + `camera`) | `urna3g[gui]` (ou `[gui,camera]`) |
| Apuração | x86_64, 2 GB | monitor + **projetor**, leitor de QR USB, impressora | `urna3g[gui]` |
| Servidor | qualquer | rede | Docker ou `urna3g[servidor]`; opcional Besu |
| Nó blockchain (opcional) | x86_64, 4 GB | rede | Besu (JVM) |

PySide6 exige x86_64 e glibc ≥ 2.28 (Ubuntu 20.04+/Debian 11+). Netbooks 32 bits (como os usados em 2016) servem
apenas como nós observadores leves ou ficam fora; a CLI roda em qualquer Python ≥ 3.10.

## 5.2 Alocação sugerida das 13 máquinas

Cenário A — **uma eleição com duas seções** (ex.: dois campi/prédios, como em 2016), apuração centralizada no laboratório:

| Qtde | Papel | Seção | Rede durante a votação |
|---|---|---|---|
| 4 | urna | 001 | **desconectada** |
| 4 | urna | 002 | **desconectada** |
| 2 | verificação | 001 / 002 | **desconectada** |
| 2 | apuração | 001 / 002 | desconectada durante a leitura; conecta à LAN só para enviar o boletim |
| 1 | reserva quente | — | pré-instalada com os três papéis; vira urna/verificação em minutos ("troca rápida", critério de 2014) |
| servidor | mural + distribuição + (opcional) nó Besu | — | LAN |

Cenário B — **ensaio da blockchain**: 4 urnas, 1 verificação, 1 apuração, 1 reserva, **4 validadores Besu** (um por
"parte"), 2 observadores; servidor com mural + observador. Mesmo software, só muda `PAPEL` no `terminal.conf`.

Distribuição matricial: eleitores escolhem qualquer urna livre da sua seção; todas assinam com a **mesma**
`secao-ID.key`, portanto a apuração não distingue — nem precisa — de qual urna veio a cédula.

## 5.3 Rede

```
   [cabines seção 001]  [cabines seção 002]  [verificação]        ← SEM cabo/Wi-Fi durante a votação
            |                    |                 |
            └── só pendrive com o pacote-eleicao.zip (antes) ──┘

   LAN do laboratório (switch, VLAN "eleicao", sem rota para a Internet durante o evento)
   ├── servidor  10.10.0.10   mural :8000, pacote.zip, (Besu RPC :8545)
   ├── apuração 001  10.10.0.21  (conecta só após GERAR BOLETIM)
   ├── apuração 002  10.10.0.22
   ├── validadores Besu 10.10.0.31–34  p2p :30303, RPC :8545
   └── estações dos fiscais (navegador no mural; opcionalmente `urna3g boletim verificar`)
```

Regras: (1) urnas e verificação **nunca** na rede durante a votação — nada a ganhar, muito a perder; (2) o pacote da
eleição chega por pendrive (ou pela LAN *antes* de abrir a seção, via `/api/eleicao/pacote.zip`, e a máquina é
desconectada); (3) boletins podem ir por LAN (`curl -X POST`) **ou** pendrive — o servidor só aceita boletins com
assinatura válida da chave de apuração da seção; (4) mural acessível aos fiscais na LAN; expor à Internet só atrás de
proxy TLS, depois da eleição.

## 5.4 Instalação

**Servidor** (`deploy/servidor/`): `docker compose up -d` com `dados/` contendo manifesto assinado, fotos e chaves
públicas. Ou sem Docker: `urna3g servidor --dados dados`.

**Terminais**: `sudo deploy/terminal/instalar.sh votar 001 QL-700` (idem `verificar`, `apurar`), depois copiar o
pacote e **somente as chaves do papel**:

| Papel | `/etc/urna3g/chaves/` |
|---|---|
| votar | `secao-001.key` (0600), `autoridade.pub` |
| verificar | `secao-001.pub`, `autoridade.pub` |
| apurar | `secao-001.pub`, `apuracao-001.key` (0600), `autoridade.pub` |

Autologin do usuário `urna` + o `.desktop` de autostart abre o módulo em tela cheia e o reabre se cair; sair exige
Ctrl+Shift+Q (mesário). O teclado numérico funciona direto (ENTER confirma, `-` branco, `+` corrige, `*` nulo).

**Ansible** (`deploy/ansible/`): `inventory.ini` com os grupos `urnas_001`, `urnas_002`, `verificadores`,
`apuradores`, `reserva`, `servidor` e `playbook.yml` que instala, distribui o pacote e **apenas as chaves do papel** a
partir de `chaves/` da máquina de controle (que deve ser a da comissão, offline do resto do tempo).

## 5.5 Reaproveitando máquinas antigas: desempenho esperado

* Qt 6 em Core 2 Duo / 2 GB: abertura em 2–4 s, ~120 MB de RAM; a interface é estática (sem animações).
* Assinar uma cédula: < 1 ms; gerar PDF + QR: ~50 ms; impressão térmica: 2–4 s (gargalo é a impressora).
* Apuração: verificação Ed25519 + inserção no ledger com `fsync`: < 20 ms por cédula; o ritmo é o do operador
  (~15 s/cédula em 2016, com leitor USB tende a 3–5 s).
* Besu QBFT com 4 validadores em máquinas de 4 GB: bloco a cada 2 s; registrar 2–50 boletins é irrelevante em carga.

## 5.6 Checklist de aceitação do laboratório

1. `urna3g demo` roda em cada máquina (valida Python, cryptography, reportlab).
2. `QT_QPA_PLATFORM=xcb urna3g gui votar --janela --sem-impressora ...` abre e emite PDF.
3. Impressora: cédula sai legível em 62×100 mm; QR lido pelo leitor USB na máquina de verificação.
4. Verificação recusa cédula de outra seção (gere uma com `urna3g cedula emitir --secao 002 ...`).
5. Apuração: releitura marca "JÁ APURADA"; F10 gera boletim; `curl` ao servidor devolve 201; mural mostra a seção.
6. Desligue a rede das urnas e repita 2–3: nada muda (prova de que a votação não depende da rede).
7. Simule queda de energia na apuração (desligue no meio): reabra; `urna3g apurar verificar-ledger` íntegro, contagem preservada.
