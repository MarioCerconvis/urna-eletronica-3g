# 6. Procedimentos operacionais (checklist)

Baseado nas fases do protocolo do artigo de 2017 e nas lições da eleição do CMCC/2016 (ex.: a diferença de uma
assinatura entre a lista e as cédulas — por isso o item "conferência assinaturas × cédulas" está em negrito).

## Antes (comissão, D-7 a D-1)

- [ ] Gerar `autoridade` e `secao-ID`/`apuracao-ID` para cada seção (`urna3g chaves gerar --senha`), em máquina offline.
- [ ] Guardar `autoridade.key` em mídia removível lacrada; registrar na ata as **impressões digitais** de todas as chaves públicas.
- [ ] Cadastrar a eleição (`urna3g gui setup-eleicao`), conferir fotos/números com as chapas, `urna3g eleicao validar --fotos`.
- [ ] Assinar o manifesto (`urna3g eleicao assinar`), registrar o **id da eleição** na ata, publicar `eleicao.json` + `.sig` + chaves públicas (mural).
- [ ] Instalar/atualizar os terminais; copiar pacote e chaves **do papel**; `chmod 600 *.key`.
- [ ] Testar impressão, leitor USB, som; imprimir e colar na cabine a legenda do teclado e a lista de números dos candidatos.
- [ ] Preparar urnas de lona/caixa lacráveis, lacres numerados, lista de assinaturas, cabines indevassáveis.
- [ ] Ensaio geral com a reserva quente: votar → verificar → apurar → enviar boletim ao mural.

## Abertura da seção (D, 30 min antes)

- [ ] Urnas e verificação **sem rede**. Ligar; o quiosque abre sozinho em tela cheia.
- [ ] Na tela de verificação conferir a impressão digital da chave da seção com a ata.
- [ ] Emitir **cédula de teste** em cada urna, verificar, e **anular/arquivar** à vista dos fiscais (não vai para a urna).
- [ ] Mostrar a urna de cédulas vazia aos fiscais; lacrar; anotar os números dos lacres.

## Votação

1. Eleitor se identifica ao **mesário** (papel: lista/assinatura) — nunca na urna.
2. Entra em qualquer cabine livre; vota na ordem que quiser; a urna imprime a cédula e **nada grava**.
3. Eleitor leva a cédula à **máquina de verificação**; se o QR não corresponder ao texto, a cédula é inutilizada à
   vista do mesário (registrar em ata) e o eleitor vota de novo.
4. Eleitor dobra a cédula e a deposita na urna lacrada; o mesário **chacoalha** a urna periodicamente.
5. Celulares não entram na cabine (coação por foto é a ameaça residual de qualquer VVPAT).
6. Falha de impressora: a tela mostra "FALHA NA IMPRESSÃO"; o mesário resolve e tecla CONFIRMA para reimprimir a
   **mesma** cédula (mesmo nonce). Se a máquina morrer, a reserva quente assume com a mesma `secao-ID.key`.

## Encerramento e transporte

- [ ] Encerrar no horário; fotografar lacres; registrar nº de assinaturas por seção.
- [ ] Desligar urnas (não há nada a salvar). Transportar urnas lacradas e a máquina de apuração para a sala pública.

## Apuração pública (fiscais presentes, tela projetada)

- [ ] Romper o lacre à vista de todos; ler cédula a cédula; a tela atualiza e sinaliza repetidas/inválidas.
- [ ] Qualquer cédula cujo QR não leia: contagem manual pelo texto impresso, registrada em ata (o texto é o registro primário).
- [ ] Ao final: **conferir nº de cédulas apuradas × nº de assinaturas**; divergência vai para a ata com decisão da comissão.
- [ ] F10 → GERAR BOLETIM: imprime, grava `boletim-ID.json/.pdf/.csv`; ler em voz alta o hash do boletim e o hash do ledger; fiscais fotografam o QR `BU1:`.
- [ ] Enviar o boletim ao mural (LAN ou pendrive): `curl -X POST --data-binary @boletim-ID.json http://servidor:8000/api/boletins`.
- [ ] Fiscais verificam no mural: assinatura, hash, totalização; opcionalmente `urna3g boletim verificar` nas próprias máquinas.
- [ ] (Opcional) Ancorar na blockchain: `python deploy/blockchain/ancorar.py registrar --boletim boletim-ID.json ...`.

## Depois

- [ ] Guardar as cédulas de papel lacradas pelo prazo definido em edital (recontagem é sempre possível).
- [ ] Publicar `boletim-*.json`, `eleicao.json`, `.sig`, chaves públicas e, se houver, endereço do contrato/bloco.
- [ ] Destruir `secao-ID.key` das urnas (ou regenerar para a próxima eleição) — uma chave vazada depois da eleição
      não altera cédulas já apuradas, mas evita confusão futura.
- [ ] Exportar o ledger (`apuracao-ID.db`) junto com o boletim para auditoria independente.
