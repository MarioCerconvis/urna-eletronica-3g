# 03 — Fundamentação teórica

## 3.1 Gerações de sistemas de votação eletrônica [FONTE: monografia 2016; Brunazo & Gazziro 2014; Rezende 2010]

| Geração | Nome | Característica | Exemplos citados |
|---|---|---|---|
| 1ª | DRE | voto só em memória digital; dependente do software | urna brasileira (UE2009) |
| 2ª | VVPAT / IVVR | registro em papel conferido pelo eleitor e guardado na seção; independente do software | SAES 3000 (Smartmatic, Venezuela, desde 2004) |
| 3ª | E2E / registro físico + digital unidos | o mesmo documento tem registro legível e digital; auditoria facilitada de ponta a ponta | Vot.Ar (Argentina, desde 2010, com chip RFID na cédula); Scantegrity II (EUA, 2009) |

* No Vot.Ar, os chips RFID foram responsáveis por várias vulnerabilidades (leitura à distância, gravação com
  celular); o registro impresso bastou para mitigar vários ataques. Por isso o protótipo UFABC usa **código QR
  impresso** em vez de RFID. [FONTE: Lima et al. 2017, citando Oro 2015]

## 3.2 Princípios para sistemas eleitorais digitais [FONTE: Brunazo & Gazziro 2014]

1. **Confiabilidade**: minimizar a confiança subjetiva (*confidence*) e maximizar a técnica (*trust*) (Pieters 2010,
   a partir de Luhmann).
2. **Soberania do eleitor e do candidato**: fiscalizar com recursos próprios e efetivos.
3. **Tripartição de poderes**: no Brasil a mesma entidade (Justiça Eleitoral) normatiza, administra, fiscaliza e
   julga o processo eleitoral.
4. **Inviolabilidade absoluta do voto**: ninguém (nem juízes) pode ligar voto a eleitor, e o eleitor não deve poder
   provar em quem votou. Consequências: **não identificar o eleitor no equipamento em que vota**; **não reter dados
   de rastreamento** (máquina de origem, horário exato, operador).
5. **Publicidade**: o *conteúdo* do voto é público e conferível; o *autor* é secreto.
6. **Independência do software** (Rivest & Wack 2006) e diretrizes VVSG §7.8 (NIST 2009): ao menos dois registros
   do voto, um fora do controle do processo digital; o eleitor confere a igualdade dos dois antes de sair; ao menos
   uma verificação diretamente pelo eleitor; identificadores únicos permitem correlacionar os registros depois.
7. **Disponibilidade absoluta**: a eleição não pode ser adiada por falha ou ataque (resistência a DoS).
8. **Desejáveis**: usabilidade, direito de refutação na seção, celeridade, recuperação simples, logística barata,
   treinamento, **distribuição matricial** (eleitor escolhe qualquer urna livre), eleitor escolhe a ordem dos cargos,
   plebiscitos.

Tabela de conformidade de 2014 (Brasil × Venezuela × Argentina) e a versão de 2017 (Brasil × Urna 3G UFABC) estão
em `14-figuras-e-tabelas.md`.

## 3.3 Criptografia usada

* **Cifra × assinatura.** Numa cifra assimétrica, a chave pública cifra e a privada decifra: garante sigilo, não
  autenticidade (qualquer um com a chave pública produz um texto cifrado válido). Numa assinatura, a chave privada
  assina e a pública verifica: garante autenticidade e integridade. Para a cédula, o conteúdo já é público
  (impresso em texto); o que se precisa provar é **que a cédula foi emitida por uma urna daquela seção**. Logo, a
  operação correta é a assinatura. [análise deste trabalho; a monografia 2016 descreve essa intenção]
* **Ed25519** (RFC 8032): assinatura em curva de Edwards, chaves de 32 bytes, assinaturas de 64 bytes, verificação
  rápida e determinística. Escolhida por produzir QR menores que RSA-2048 e por ser resistente a erros de
  implementação de *padding*. [decisão deste trabalho]
* **SHA-256** para identificadores (manifesto, boletim) e para encadeamento (ledger, mural).
* **Separação de domínio**: cada tipo de assinatura prefixa um contexto (`urna3g/cedula/v1`, `urna3g/boletim/v1`,
  `urna3g/eleicao/v1`) para impedir que uma assinatura válida num contexto seja reaproveitada em outro.
* **Cadeia de hashes**: cada registro inclui o hash do anterior; alterar, remover ou reordenar qualquer registro
  muda todos os hashes seguintes e é detectado recalculando a cadeia.

## 3.4 Paradoxo do aniversário (colisão de identificadores)

Com k cédulas e identificadores sorteados uniformemente em n valores:
P(nenhuma colisão) = ∏_{i=0}^{k−1} (1 − i/n) e P(≥1 colisão) ≈ k²/(2n). [FONTE: Lima et al. 2017, seção 4]
* Artigo de 2017: n = 2³⁰, k = 400 → ≈ 7,5 × 10⁻⁵ (figura 2 do artigo).
* Este trabalho: n = 2¹²⁸, k = 400 → ≈ 2,3 × 10⁻³⁴; mesmo com 10⁸ cédulas, ≈ 1,5 × 10⁻²³. [cálculo]

## 3.5 Blockchain e consenso [FONTE: Cunha 2022; documentação Hyperledger Besu]

* Blockchain: registro de transações em blocos encadeados por hash, replicado em pares; alterar um bloco invalida a
  cadeia seguinte. Histórico: Chaum 1979; Haber & Stornetta 1991; Bayer et al. 1993; Dai 1998; Nakamoto 2008.
* Ethereum (Buterin 2014): máquina virtual distribuída que executa *smart contracts*; cada transação consome *gas*.
* Provas de conhecimento zero (Blum, Feldman & Micali 1988): provar a validade de uma afirmação sem revelar o porquê
  (usadas no Open Vote Network).
* **Prova de Autoridade (PoA)** e **QBFT**: em redes permissionadas, um conjunto conhecido de validadores produz os
  blocos. O QBFT é um protocolo tolerante a falhas bizantinas: com n validadores, produz blocos enquanto houver
  quórum de ⌈2n/3⌉ e tolera até ⌊(n−1)/3⌋ validadores faltosos ou maliciosos. O proponente de cada bloco é escolhido
  em rodízio; se ele não responde, há troca de rodada (*round change*) com tempo de espera que **dobra a cada
  rodada** a partir de `requesttimeoutseconds` (4 s na configuração usada). O Clique (PoA usado em um dos trabalhos
  analisados em 2022) não tolera validadores bizantinos.
* "Trilema da escalabilidade": blockchains dificilmente atendem ao mesmo tempo descentralização, segurança e
  escalabilidade. [FONTE: Cunha 2022]

## 3.6 Critérios de avaliação de e-voting em blockchain [FONTE: Taş & Tanrıöver 2020, via Cunha 2022]

1. não produzir recibo; 2. não produzir resultados preliminares; 3. integridade dos dados; 4. privacidade/voto
anônimo; 5. somente eleitores registrados votam; 6. voto único; 7. robustez (escala); 8. confiabilidade (sem bugs,
processo de desenvolvimento); 9. verificabilidade.
