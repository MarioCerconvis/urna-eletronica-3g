# 12 — Discussão, limitações e trabalhos futuros

## 12.1 Interpretação dos resultados

* **A falha mais grave do protótipo era conceitual, não de implementação**: cifrar o voto com a chave pública não
  prova a origem da cédula. Com assinatura, a chave privada fica só na urna e qualquer um pode verificar — inclusive
  fiscais com software próprio. Isso aproxima o sistema do princípio da soberania do eleitor (fiscalizar com recursos
  próprios).
* **A cédula assinada continua pequena** (QR versão 8) e legível por câmera comum, preservando a vantagem de custo
  do protótipo.
* **A blockchain como âncora, não como urna**: um registro por seção elimina os problemas de privacidade, resultados
  parciais e escala apontados em 2022. O custo é que a cadeia não prova o conteúdo de cada voto — essa prova continua
  no papel e no ledger, que é o que o princípio da independência do software pede.
* **Tolerância a falhas na prática** (E7, E8): o QBFT se comportou como a teoria prevê — produziu em todas as 25
  repetições com até 4 de 12 fora e parou com 5 —, mas com dois efeitos que a teoria do quórum não mostra:
  1. **A vizinhança no rodízio pesa mais que o número de falhas.** A pausa máxima foi 14 s em todos (e só nos) casos
     com dois validadores desligados consecutivos na ordem de proposição, e 6 s nos demais (15/15). Distribuir as
     máquinas de cada parte de forma intercalada na ordem dos validadores reduz o impacto de falhas correlacionadas
     (ex.: um bloco do laboratório sem energia).
  2. **A recuperação depois de perder o quórum é quantizada e pode ser longa.** Os tempos caíram em degraus de
     ≈ 38, 70, 135, 263 e 518 s — o temporizador de rodada dobrando a partir de 4 s. Um minuto sem quórum custou
     até 8,6 min sem blocos depois que o quórum voltou. Operar com folga de quórum e ajustar o temporizador são
     requisitos operacionais.
* **A ancoragem não é gargalo** (E6, E9): 2,5 s em média do boletim à confirmação, e a rede absorveu rajadas de
  1 200 registros (ver `11` §11.12) — muito acima das dezenas de seções de uma eleição universitária.
* **A apuração não é gargalo computacional** (E4): ~0,3 ms de CPU por cédula; mesmo gravando no HD mecânico com
  confirmação física, 45 s por seção de 400 — menos de 1% do tempo da contagem pública manual.
* **A leitura óptica é robusta com o detector certo** (E3): 6 000/6 000 com o detector ArUco em condições degradadas,
  contra 82,6–99,7% do detector clássico — a escolha do detector importa mais que a resolução da câmera.
* **Máquinas modestas bastam** (E12): um nó Besu usou em média 389 MiB (máx. 692 MiB) em máquinas de 3,4 GB.
* **Observabilidade como transparência**: o painel ao vivo torna visíveis consenso, quedas e ancoragens para leigos;
  pode servir em audiências públicas de apuração e em ensino.

## 12.2 Ameaças à validade

* **Eleitores simulados** no ensaio (ritmo e escolhas aleatórias); não há medida de usabilidade com pessoas.
* **Apuração do ensaio no computador do operador**, não nas máquinas do cluster; as máquinas apenas enviam e validam
  as transações de suas seções.
* **Validadores sob um único operador**: os resultados de tolerância valem para falhas por desligamento
  (*crash*), não para comportamento bizantino nem conluio.
* **Rede local de laboratório** (baixa latência); resultados podem piorar em redes geograficamente distribuídas.
* **Amostras moderadas** nos testes de rede: 5 repetições por condição (3 para paradas de 120 s). Suficiente para
  revelar os padrões (degraus, efeito de vizinhança), não para estimar com precisão a frequência de cada degrau.
* **Falhas por desligamento**, não bizantinas, e injetadas por `docker stop` (encerramento limpo do processo).
* **Orquestração dentro da rede do cluster** (máquina D) para E6–E11: latências de rede menores que as de partes
  geograficamente distribuídas.
* **Impressão e leitura física** não foram testadas nas máquinas do cluster; a leitura óptica foi medida com imagens
  geradas por software (com rotação e desfoque), não com papel térmico real.

## 12.3 Considerações éticas e de privacidade

* Nenhum dado pessoal foi usado; candidatos e partidos são fictícios (personagens de quadrinhos herdados do
  protótipo).
* Por princípio, o sistema **não transmite telemetria da votação**: o contador de cédulas por seção no painel existe
  **apenas no ensaio**. Numa eleição oficial o painel mostraria só as fases por seção (apuração, boletim, ancoragem).
* Ancorar só hashes evita que dados da votação fiquem permanentemente públicos numa cadeia imutável.

## 12.4 Limitações conhecidas

1. Sem **verificação fim a fim** (E2E): o eleitor confere a cédula, mas não recebe um recibo que prove inclusão sem
   revelar o voto (mesma limitação declarada em 2017).
2. **Chave da urna em arquivo** (PEM, opcionalmente cifrado com senha); o ideal é token/TPM.
3. **Permissionamento de nós** do Besu não ativado: qualquer máquina na rede do laboratório pode se conectar como par.
4. RPC dos nós exposto na rede interna durante o experimento.
5. **Arquivos do ensaio não são preservados** (cédulas, boletins, ledgers ficam em diretório temporário); só os hashes
   permanecem na cadeia — limita a auditoria pós-ensaio.
6. Sem acessibilidade para eleitores com deficiência (áudio, alto contraste).
7. Interface gráfica exige x86-64 (PySide6).
8. Licença do código original não declarada.

## 12.5 Trabalhos futuros

* Validadores operados por partes distintas (comissão, chapas, entidade estudantil, auditor) e permissionamento de nós.
* Apuração executada em cada máquina do cluster, com ledger e boletim gravados localmente.
* Preservar os artefatos do ensaio e oferecer verificação pela interface (QR, boletim, conferência com a cadeia).
* Ensaio com pessoas e impressoras/leitores reais; medir tempo de votação e de apuração por cédula (comparar com os
  ≈ 15 s/cédula de 2016).
* Reduzir `requesttimeoutseconds` (ex.: 1–2 s) e medir o efeito nos degraus de recuperação; testar comportamento
  bizantino; intercalar validadores de partes distintas na ordem de rodízio e medir sob falhas correlacionadas.
* Verificação E2E com *commitments* ou cifra homomórfica (Rivest 2002; Open Vote Network).
* Chaves em hardware; acessibilidade.

## 12.6 Conclusão (pontos para o fechamento)

* O conceito de 2016 (papel + QR, verificação em outra máquina, apuração pública) se mantém; o que mudou foi a
  garantia criptográfica e a auditabilidade.
* A lição de 2022 (não votar on-chain) leva a um uso modesto e útil da blockchain: imutabilidade e replicação de poucos
  registros públicos.
* Um laboratório com máquinas comuns sustentou uma rede de 12 validadores e uma eleição-ensaio completa, com
  tolerância a falhas medida.
