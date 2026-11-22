# 00 — Guia de escrita

## Tese central (uma frase)

É possível construir, com software livre e máquinas de laboratório comuns, um sistema eleitoral de **3ª geração**
(cédula de papel com registro digital assinado e conferível pelo eleitor) cuja apuração é **auditável por qualquer
fiscal** e cujo resultado é **ancorado numa blockchain permissionada** — sem nunca colocar votos individuais na
cadeia — e esse arranjo tolera a queda de até ⌊(n−1)/3⌋ das máquinas validadoras.

## Contribuições que o artigo pode reivindicar (todas sustentadas neste dossiê)

1. **Análise crítica do protótipo de 2016/2017** com base no código-fonte: o registro digital era *cifrado* com a
   chave pública (RSA-1024/OAEP) em vez de *assinado*, o que não autentica a cédula; identificador anti-duplicata
   de ~30 bits; chaves privadas versionadas no repositório (arquivo `05`).
2. **Reimplementação moderna** (Python ≥ 3.10) que corrige essas falhas: assinatura Ed25519 pela urna, nonce de
   128 bits, manifesto da eleição assinado com identificador SHA-256 embutido em cada cédula, ledger de apuração
   encadeado por hash e boletim de urna assinado (arquivos `06`, `07`, `09`).
3. **Modelo híbrido de blockchain derivado da análise de 2022**: em vez de votar on-chain (inviável em privacidade e
   escala segundo a comparação de quatro modelos Ethereum), ancoram-se só hashes públicos — um registro por seção
   (arquivo `08`).
4. **Avaliação experimental** numa rede Hyperledger Besu/QBFT, primeiro simulada (4 validadores em Docker) e depois
   num **cluster real de 12 máquinas**, com medição de vazão, tolerância a falhas e tempo de recuperação; e uma
   eleição-ensaio completa com 12 seções ancoradas (arquivos `10`, `11`).
5. **Painel de observação ao vivo** (grafo da rede, linha do tempo, injeção de falhas) como ferramenta de
   transparência e de ensino (arquivo `09`).

## Público e tom

Comunidade de segurança da informação e sistemas eleitorais (ex.: SBSeg/WTE, periódicos de segurança ou governo
digital). Tom técnico e factual. O projeto tem posição clara a favor do voto impresso conferível (princípios de
Brunazo & Gazziro, 2014), mas o artigo deve sustentar essa posição com critérios e evidências, não com opinião
política. Evitar qualquer referência partidária ou a figuras políticas.

## Regras de fidelidade (obrigatórias)

* **Não inventar números.** Todo valor está nos arquivos `05`, `11` ou em `anexos/`. Se faltar um dado, escrever
  que não foi medido.
* **Separar três naturezas de afirmação** (este dossiê marca cada uma):
  * **[FONTE]** — dito pelos documentos originais (artigo 2017, monografias 2016/2022, artigo 2014);
  * **[MEDIDO]** — medido neste trabalho, com procedimento descrito em `10`;
  * **[PROPOSTA]** — projetado, documentado, mas **não** testado (ex.: rede com validadores de partes distintas,
    verificação fim a fim, permissionamento de nós).
* **O ensaio de eleição usa eleitores simulados.** As cédulas são geradas por software num ritmo plausível; tudo o
  mais (assinaturas, apuração, rejeição de cédulas inválidas, transações na blockchain) é real. Além disso, no
  ensaio a **apuração roda no computador do operador**; a máquina K do cluster apenas **envia e valida** a
  transação de ancoragem da seção K, com a conta do seu validador. O artigo não deve dizer que "cada máquina
  apurou sua seção".
* **Os 12 validadores do cluster pertencem a um único operador.** Isso demonstra o mecanismo e a tolerância a
  falhas, não a descentralização entre partes desconfiadas — que é requisito do modelo proposto.
* **Use a bateria E1–E12 (22/11/2026) como fonte dos números** (`11`, `anexos/dados/`). As medições de 13–14/11
  são preliminares (uma execução por condição). Relate também os erros de método detectados e refeitos (`11` §11.14).
* **Hardware antigo, mas não "obsoleto":** as máquinas do cluster são x86-64 com 3,3–3,4 GB de RAM (uma com 5,1 GB)
  rodando Ubuntu 26.04. Não exagerar a precariedade.

## Divergências conhecidas entre as fontes (não propagar sem ressalva)

| Ponto | Artigo SBSeg 2017 | Monografia 2016 | Código original | Como tratar |
|---|---|---|---|---|
| Datas da eleição do CMCC | votação 20/07/2016; apuração 21/07/2016 13h20–13h47 | eleições "nos dias 25 e 26 de julho de 2016" | — | citar o artigo (mais preciso, com ata nº 02/2016) e mencionar que a monografia registra outra data |
| Nº de votantes / assinaturas | 64 votantes, 63 assinaturas | 84 votantes, 83 assinaturas | — | citar o artigo; registrar a divergência em nota |
| Tamanho da chave RSA | não especifica | 2048 bits | `generate_RSA(bits=1024)`; chaves do repositório têm 1024 bits | afirmar 1024 bits **no código** |
| Operação criptográfica do QR | "RSA_Kpub(voto)" — cifra com a chave pública | "chave privada … utilizada para **assinar** o voto" | cifra com a pública (PKCS#1 OAEP), decifra com a privada | o código e o artigo coincidem (cifra); a monografia descreve a intenção correta (assinatura) |
| Identificador anti-duplicata | "número aleatório de até 10 casas decimais", análise com n = 2³⁰ | "os.urandom, 16 bytes" | `random.SystemRandom().randint(0, 1000000000)` | afirmar ~30 bits **no código** |
| Endereço do código | github.com/mariogazziro/UrnaEletronica3G | github.com/ferfolima/UrnaEletronica3G | hoje em github.com/mariogazziro/urna_eletronica | citar o repositório vigente |
| Tamanho do QR na nova versão | — | — | docs/03 dizia ~142 caracteres (versão 7) e que o QR era menor que o do protótipo | **medido (E1): 147 caracteres, versão 8 — a mesma versão do QR do protótipo (175 caracteres, correção L)**; o ganho é correção M + autenticidade, não tamanho |

## Estrutura sugerida para um artigo de 8–12 páginas (SBC/IEEE)

1. Introdução (02) · 2. Fundamentação (03) · 3. Trabalhos relacionados (04) · 4. O protótipo de 2016 e suas
fragilidades (05) · 5. Arquitetura proposta (06, 07, 08) · 6. Implementação (09) · 7. Avaliação experimental (10, 11)
· 8. Discussão e limitações (12) · 9. Conclusão e trabalhos futuros (12).

Para um artigo curto (4–6 páginas), fundir 4 em 1 e 5+6, e manter na avaliação apenas o cluster de 12 nós.

## Autoria (a confirmar com os autores)

* Protótipo 2016/2017: Fernando Teodoro de Lima, Mario Alexandre Gazziro (orientador), com Antonio de Abreu
  Batista Jr. (UFMA), Paulo Matias (UFSCar) e João V. C. Costa no artigo de 2017.
* Análise de blockchain 2022: Rael Gugelmin Cunha (orientação de Mario Gazziro), MBA ICMC-USP.
* Reimplementação e experimentos de 2026: Mario Guerrero Cerconvis, com o Prof. Mario Gazziro (LAOB/UFABC).
* Laboratório: LAOB — UFABC, Bloco L, sala L403, Campus Santo André.
