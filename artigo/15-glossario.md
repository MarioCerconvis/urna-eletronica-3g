# 15 — Glossário

| Termo | Significado |
|---|---|
| DRE | *Direct Recording Electronic*: urna que grava o voto diretamente em memória digital (1ª geração) |
| VVPAT / IVVR | registro em papel conferível pelo eleitor (*Voter Verifiable Paper Audit Trail* / *Independent Voter Verifiable Record*) — 2ª geração |
| E2E | verificabilidade fim a fim (*end-to-end*): o eleitor verifica que seu voto foi contado sem revelá-lo |
| Independência do software | um erro não detectado no software não pode causar erro indetectável no resultado |
| VVSG | *Voluntary Voting System Guidelines* (NIST/EAC, EUA) |
| Cédula | papel impresso pela urna com o voto legível e o QR assinado |
| Boletim de urna (BU) | resultado da seção, assinado pela máquina de apuração |
| Manifesto | arquivo JSON com cargos, partidos/chapas, candidatos e seções; seu SHA-256 é o id da eleição |
| Ledger | registro *append-only* da apuração, encadeado por hash |
| Mural | servidor que recebe boletins assinados, encadeia e publica a totalização |
| Nonce | número aleatório de 128 bits que identifica cada cédula e impede dupla contagem |
| Ed25519 | algoritmo de assinatura digital em curva de Edwards (RFC 8032) |
| Impressão digital | SHA-256 de uma chave pública, exibida para conferência humana |
| QBFT | protocolo de consenso tolerante a falhas bizantinas usado no Hyperledger Besu |
| Quórum | número mínimo de validadores para produzir blocos: ⌈2n/3⌉ |
| Proponente | validador da vez que propõe o próximo bloco (rodízio) |
| Troca de rodada | quando o proponente não responde, a rede espera e passa a vez; a espera dobra a cada rodada |
| Validador / observador | nó que participa do consenso / nó que só replica e serve consultas |
| Ancoragem | gravar na blockchain o hash de um documento para provar que ele existia e não mudou |
| Ensaio | eleição de teste disparada pelo painel, com eleitores simulados e todo o resto real |
| Ponte | máquina por onde o computador do operador alcança os nós do cluster (SSH) |
| CMCC | Centro de Matemática, Computação e Cognição (UFABC) |
| LAOB | laboratório da UFABC (Bloco L, sala L403, Santo André) onde o projeto é desenvolvido |
