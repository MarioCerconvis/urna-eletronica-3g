# 04 — Estado da arte e trabalhos relacionados

Tudo abaixo é **[FONTE]**: vem dos documentos originais (artigo 2014, monografia 2016, artigo 2017, monografia 2022).
Referências completas e grau de verificação em `13-referencias.md`. O escritor pode verificar e complementar com
literatura mais recente, desde que marque o que acrescentou.

## 4.1 Sistemas em uso ou testados

| Sistema | País / ano | Geração | Pontos relevantes |
|---|---|---|---|
| Urna eletrônica (UE2009) | Brasil, desde 1996 | 1ª (DRE) | voto só digital; software fechado; vulnerabilidades encontradas pela UnB em 2012 (Aranha et al.) |
| SAES 3000 (Smartmatic) | Venezuela desde 2004; Bélgica, Equador | 2ª (VVPAT) | papel conferível; eleitor não confere o registro digital |
| Vot.Ar (MSA) | Argentina desde 2010; Equador | 3ª | cédula com chip RFID + impressão; RFID fonte de vulnerabilidades (Oro 2015) |
| Scantegrity II | EUA, 2009 | 3ª (E2E) | voto cifrado impresso; eleitor verifica processamento sem revelar conteúdo (Chaum et al. 2008) |
| i-Voting | Estônia, desde 2005 (nacional 2007) | votação pela Internet | cartão de identidade com dois pares RSA; múltiplos votos (vale o último) contra coação; não é E2E; falhas e risco de DoS apontados por Springall et al. 2014 |
| Protótipo Urna 3G UFABC | Brasil, 2016 | 3ª (papel + QR) | primeiro uso em instituição pública brasileira (eleição do CMCC/UFABC) — arquivo `05` |

* A Verified Voting reuniu em 2008 mais de trinta especialistas num posicionamento contrário à votação pela Internet
  [CT 2012]; o artigo de 2014 exclui sistemas pela Internet do escopo por esse motivo e pela exigência legal de
  cabine indevassável no Brasil, Venezuela e Argentina.

## 4.2 Protótipos acadêmicos de urnas citados em 2017

Karima et al. 2014 (microcontrolador + smart card), Culnane et al. 2015 (vVote, verificável), Puri et al. 2017
(urna indiana), Adida & Rivest 2006 (*Scratch & Vote*, voto criptográfico em papel), Ali & Murray 2016 (revisão de
sistemas E2E), Rivest 2002 (cifra homomórfica para votação), van de Graaf 2017 (ameaças de longo prazo ao sigilo),
Wang et al. 2017 (revisão de e-voting contemporâneo).

## 4.3 Votação eletrônica sobre Ethereum (análise sistemática de Cunha 2022)

Busca no Google Scholar, Sucupira Qualis e Impact Factor Journal com termos *ethereum*, *e-voting*, *blockchain*;
critérios de inclusão: específico para Ethereum, com código-fonte (ao menos trecho), voto único, preocupação mínima
com privacidade. Cinco trabalhos considerados; um (Fayemi et al. 2021) descartado da análise por não fornecer código.

| Trabalho | Rede usada | Resumo |
|---|---|---|
| Koç et al. 2018 — *Towards Secure E-Voting Using Ethereum Blockchain* | testnet Rinkeby | sistema simples; 3 eleitores; voto gravado com o endereço do eleitor e o candidato (consultável no Etherscan); sem controle de tempo/estado |
| Khoury et al. 2018 — *Decentralized Voting Platform Based on Ethereum Blockchain* | testnet Ropsten | registro por SMS (Oraclize + Twilio); aplicativo móvel; sem administrador da eleição; contagem consultável a qualquer momento |
| Christyono, Widjaja & Wicksana 2021 — *Go-Ethereum… using clique as proof-of-authority* | rede privada Geth/Clique, 3 mineradores | recriou a eleição de Jelupang (Indonésia, 2019): 26 candidatos, 15 725 eleitores; criar contas levou 13,4 h; projeção para 5,1 milhões de eleitores (Banten): 71 h de votação |
| McCorry, Shahandashti & Hao 2017 — *A Smart Contract for Boardroom Voting with Maximum Voter Privacy* (Open Vote Network) | testnet Ropsten | provas de conhecimento zero; fase de *commitment*; estados da eleição; 40 eleitores, 126 transações, 145 381 858 gas; limite de ~50–60 eleitores (gas de 4,7 M por bloco, 2016), ~383 com 30 M; exige que todos votem; código deixou de funcionar após mudança de protocolo em 2018 |
| Fayemi, Thompson & Ayeni 2021 — *KECCAK256 on Ethereum* | — | identificação do eleitor em sistema externo; sem código publicado (fora da análise) |

Custos relatados para o Open Vote Network: US$ 0,73 por eleitor e US$ 31,98 por eleição de 40 eleitores em 2016 (ether
a US$ 11); com o ether a US$ 2 703,57 (2022), ≈ US$ 7 858 pela mesma eleição (≈ US$ 196 por eleitor, divisão feita
neste dossiê).

Resultado da comparação (✓ = atende): ver tabela completa em `14-figuras-e-tabelas.md`. Em síntese:
* todos atendem "sem recibo", "só registrados" e "voto único";
* apenas o Open Vote Network atende privacidade e ausência de resultados parciais;
* **nenhum atende robustez** (escala);
* conclusão de Cunha 2022: nenhum modelo, no formato proposto, poderia substituir a urna brasileira; caminhos
  futuros: atualizar o Open Vote Network com as curvas elípticas nativas do Ethereum ou explorar redes focadas em
  privacidade.

## 4.4 Posicionamento deste trabalho

| Abordagem | Onde está o voto | Privacidade | Escala | Independência do software |
|---|---|---|---|---|
| DRE (1ª geração) | memória da urna | depende do software | alta | não |
| VVPAT (2ª) | memória + papel na seção | boa | alta | sim |
| 3ª geração UFABC 2016 | papel com QR (cifrado, não autenticado) | boa | alta | parcial (QR forjável) |
| Votação on-chain (Ethereum) | transações públicas | fraca, exceto com ZKP | baixa | depende do contrato e do cliente |
| **Este trabalho** | papel com QR **assinado**; cadeia guarda só hashes de boletins | boa (nenhum voto individual sai da seção em formato digital) | um registro por seção | sim: o papel é o registro primário; o digital é verificável por qualquer um |
