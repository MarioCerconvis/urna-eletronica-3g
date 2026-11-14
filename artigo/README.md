# Dossiê para artigo — Urna eletrônica de 3ª geração com ancoragem em blockchain permissionada

Este diretório reúne **todo o material necessário para escrever um artigo científico completo** sobre o projeto,
sem consultar nenhuma outra fonte. Ele não é o artigo: é a matéria-prima organizada por seção, com cada número
acompanhado da sua origem.

## Como usar (para o agente ou a pessoa que vai escrever)

1. Leia `00-guia-de-escrita.md` primeiro: tese central, contribuições, público, regras de fidelidade e as
   divergências conhecidas entre fontes.
2. Os arquivos `01` a `12` seguem a ordem de um artigo empírico (contexto → fundamentos → estado da arte →
   trabalho anterior → proposta → implementação → método → resultados → discussão).
3. `13-referencias.md` traz todas as referências com o grau de verificação de cada uma.
4. `14-figuras-e-tabelas.md` traz as figuras sugeridas (com diagramas-fonte) e tabelas prontas.
5. `anexos/` traz dados brutos das medições, trechos de código e a especificação dos formatos.

## Mapa dos arquivos

| Arquivo | Conteúdo | Vira, no artigo |
|---|---|---|
| `00-guia-de-escrita.md` | tese, contribuições, público-alvo, regras, divergências entre fontes | — (orientação) |
| `01-resumo-executivo.md` | o projeto em uma página | Resumo / Abstract |
| `02-contexto-e-motivacao.md` | o problema da urna de 1ª geração, transparência, o caso brasileiro | Introdução |
| `03-fundamentacao-teorica.md` | gerações de urnas, princípios, independência do software, criptografia, BFT | Fundamentação |
| `04-estado-da-arte.md` | sistemas e trabalhos relacionados, incluindo e-voting em Ethereum | Trabalhos relacionados |
| `05-trabalho-anterior-prototipo-2016.md` | o protótipo UFABC, a eleição real de 2016 e as fragilidades encontradas | Trabalho anterior / Motivação |
| `06-arquitetura-proposta.md` | arquitetura, fluxos, decisões de projeto, modelo de ameaças | Proposta |
| `07-criptografia-e-formatos.md` | chaves, formato da cédula, ledger, boletim, mural, cálculo de colisão | Proposta (detalhe técnico) |
| `08-blockchain-ancoragem.md` | por que e o que ancorar; contrato; rede QBFT | Proposta (camada de auditoria) |
| `09-implementacao.md` | tecnologias, módulos, testes, painel ao vivo, implantação | Implementação |
| `10-metodologia-experimental.md` | ambientes de teste, procedimentos e métricas | Metodologia |
| `11-resultados.md` | todas as medições, com tabelas | Resultados |
| `12-discussao-limitacoes-futuro.md` | interpretação, ameaças à validade, ética, limitações, trabalhos futuros | Discussão / Conclusão |
| `13-referencias.md` | bibliografia | Referências |
| `14-figuras-e-tabelas.md` | figuras e tabelas | Figuras e tabelas |
| `15-glossario.md` | termos e siglas | — (apoio) |
| `anexos/` | dados brutos, código, especificações | Apêndices / material suplementar |

## Fontes primárias usadas para montar este dossiê

* Página do projeto 2016/2017: <http://professor.ufabc.edu.br/~mario.gazziro/project2.html>
  (artigo SBSeg 2017 `paper2.pdf`, monografia de 2016 `monografia2.pdf`, certificado de extensão `certificado2.pdf`,
  vídeo e link do código).
* Página do estudo sobre blockchain: <http://professor.ufabc.edu.br/~mario.gazziro/project22.html>
  (monografia MBA ICMC-USP 2022 `monografia22.pdf` e slides `apresentacao22.pdf`).
* Código original: <https://github.com/mariogazziro/urna_eletronica> (commit único `56c372d`, 2021-05-22).
* Reimplementação deste trabalho: <https://github.com/MarioCerconvis/urna-eletronica-3g> (branch `main`;
  o código original está preservado na branch `legacy-2017`), documentação em `docs/` e `deploy/`.
* Medições feitas em 13–14/nov/2026 neste computador e no cluster do LAOB/UFABC (detalhes em `10` e `11`).
