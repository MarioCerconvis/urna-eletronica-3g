# 05 — O protótipo de 2016/2017 e suas fragilidades

## 5.1 Descrição [FONTE: Lima et al. 2017; monografia Lima 2016]

* Software em Python 2.7.6 com PySide 1.2.1 (Qt 4), SQLAlchemy 1.0.14 (SQLite), PyCrypto, PyQRCode 1.1, Pillow,
  zbar 0.10 (leitura de QR por webcam), ReportLab (PDF); Ubuntu 14; webcam e impressora simples (cédulas de 62 × 100 mm,
  impressora de etiquetas citada no código: Brother QL-700).
* Cinco módulos, executados nesta ordem:
  1. **Ajuste de Urna** — gera o par de chaves da seção;
  2. **Ajuste de Eleição** — cadastra partidos/chapas (número de dois dígitos), cargos (com nº de votos por eleitor,
     ex.: dois senadores) e candidatos com foto;
  3. **Votação** — eleitor escolhe a ordem dos cargos, digita o número do candidato num teclado numérico, confirma;
     a máquina imprime a cédula (texto + QR);
  4. **Verificação** — outra máquina lê o QR e mostra o voto para o eleitor comparar com o texto;
  5. **Apuração** — lê cada cédula uma única vez (identificador aleatório no QR), totaliza na tela (projetável) e
     imprime o boletim de urna.
* Protocolo: inicialização (chaves e cadastros) → votação (identificação com o mesário e assinatura na lista;
  impressão; verificação em outra máquina; depósito em urna lacrada, que é **chacoalhada** para embaralhar) →
  transporte → contagem pública → boletim → conferência do número de assinaturas com o total de votos.
* Registro digital: "QR contendo a concatenação S1 = RSA_Kpub(voto) e S2" (S2 número pseudoaleatório).
* Divergência entre registro textual e digital → considerar o digital errôneo e contar manualmente.

## 5.2 A eleição real [FONTE: Lima et al. 2017]

* Portaria nº 25 de 23/06/2016 do CMCC/UFABC; votação em 20/07/2016, das 10h às 13h e das 15h às 19h, nos campi de
  Santo André e São Bernardo do Campo; 12 vagas (2 discentes de graduação, 2 de pós-graduação, 2 técnico-
  administrativos e respectivos suplentes) para o Conselho do CMCC.
* Equipamento: netbooks do NTI, teclado numérico e monitor para o eleitor (sem acesso a teclado completo). [FONTE: monografia 2016]
* Apuração em 21/07/2016, das 13h20 às 13h47 (ata nº 02/2016): 64 eleitores votantes e 63 assinaturas (falha dos
  mesários em colher uma); diferença considerada irrelevante para o resultado. Resultado divulgado em 22/07/2016.
* Apuração eletrônica levou 15 minutos, ≈ 15 s por cédula (retirar da urna, apresentar ao leitor, atualizar a
  tabela projetada). Estimativa para uma seção de 400 eleitores: 1h30.
* "Primeiro uso de uma urna de terceira geração em uma instituição pública brasileira."
* **Atenção:** a monografia de 2016 registra 84 votantes, 83 assinaturas e eleições em 25 e 26/07/2016 — ver
  divergências em `00-guia-de-escrita.md`.
* O trabalho foi apresentado em evento de extensão da UFABC: "Democracia e Sociedade da Informação: Urnas
  Eletrônicas de Terceira Geração" (EV045-2018, 16/08/2018, 4 h). [FONTE: certificado]

## 5.3 Fragilidades encontradas na revisão do código (este trabalho) [MEDIDO — leitura do código, commit 56c372d]

| # | Fragilidade | Evidência no código | Consequência |
|---|---|---|---|
| 1 | QR **cifrado**, não assinado | `Votar/main.py`: `PKCS1_OAEP.new(RSA.importKey(publickey)).encrypt(...)`; verificação/apuração decifram com `privatekey.pem` | qualquer pessoa com a chave pública (que é pública) forja cédulas aceitas pela apuração; a chave **privada** precisa estar em todas as máquinas de verificação e apuração |
| 2 | RSA de 1024 bits | `SetupUrna/generateKey.py`: `generate_RSA(bits=1024)`; chaves do repositório com 1024 bits | tamanho abaixo do recomendado atualmente |
| 3 | Identificador anti-duplicata de ~30 bits | `random.SystemRandom().randint(0, 1000000000)` | probabilidade de colisão ≈ 7,5 × 10⁻⁵ por seção de 400 eleitores (a monografia pretendia 16 bytes) |
| 4 | Chaves privadas no repositório | `files/privatekey.pem` versionado | quem clona o repositório tem a chave das cédulas de exemplo |
| 5 | Cadastro sem integridade | SQLite `files/eleicoesdb.db` copiado manualmente para cada máquina | troca de candidato/foto numa máquina não é detectada |
| 6 | Apuração sem registro durável | contagem em dicionário na memória + CSV | queda de energia perde a apuração; não há trilha verificável |
| 7 | Execução de comando com `shell=True` | `subprocess.Popen("lp '{0}'".format(...), shell=True)` | injeção de comando se o caminho for controlado |
| 8 | Pilha descontinuada | Python 2.7, PySide (Qt 4), PyCrypto (sem manutenção desde 2013), GTK 2 | não instala em sistemas atuais |
| 9 | Nenhum teste automatizado | — | regressões invisíveis |

Observação justa para o artigo: o protocolo e a operação do protótipo (papel como registro primário, verificação em
outra máquina, urna lacrada, conferência de assinaturas) estavam corretos; as fragilidades são de implementação
criptográfica e de engenharia, e foram descobertas com a vantagem do tempo e de ferramentas atuais.

## 5.4 Números do código original [MEDIDO]

* 66 arquivos; 2 654 linhas de Python em 5 módulos (com `model.py` e `eleicoesDB.py` duplicados e divergentes em cada
  módulo).
* Banco de exemplo: 3 cargos, 2 partidos (Turma da Mônica, Disneylândia), 6 candidatos com foto.
