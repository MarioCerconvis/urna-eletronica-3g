# 02 — Contexto e motivação (base para a Introdução)

## O problema da urna de 1ª geração

* O Brasil adota urna eletrônica desde 1996. Em 1996, mais de 32 milhões de eleitores (um terço do eleitorado)
  votaram em mais de 70 mil urnas, em 57 cidades com mais de 200 mil eleitores. [FONTE: monografia 2016, citando TSE]
* O equipamento brasileiro é do modelo **DRE** (*Direct Recording Electronic*): o voto é mostrado na tela, confirmado
  e gravado diretamente em memória digital; a apuração é eletrônica e o resultado é transmitido para totalização.
  [FONTE: monografia 2016]
* Nesse modelo, a confiabilidade do resultado depende inteiramente da confiança no software instalado. O artigo de
  2017 afirma que o Brasil era, então, o único país a usar urnas de 1ª geração sem possibilidade de auditoria por
  outro meio. [FONTE: Lima et al. 2017, citando Filho et al. 2015]
* Entre 2006 e 2012, Holanda, Alemanha, EUA, Canadá, Rússia, Bélgica, Argentina, México e Paraguai abandonaram o
  modelo DRE; Índia e Equador em 2014. [FONTE: monografia 2016]
* Em 2012, uma equipe da UnB conseguiu reordenar cronologicamente os votos gravados pela urna brasileira num teste
  público, comprometendo o sigilo para quem anotasse a ordem dos eleitores. [FONTE: monografia 2016; Aranha et al.]
* Em 2009 o Tribunal Constitucional Federal da Alemanha decidiu que máquinas DRE sem voto impresso conferível violam
  o **princípio da publicidade**: o cidadão comum, sem conhecimento técnico, deve poder controlar os passos
  essenciais da votação e da apuração. [FONTE: Brunazo & Gazziro 2014, citando a decisão 2 BvC 3/07]

## Por que isso importa (argumento central)

* "Um sistema eleitoral é independente do software se um erro não detectado no software não puder causar um erro
  indetectável no resultado da apuração ou na inviolabilidade do voto." (Rivest & Wack 2006) [FONTE]
* Validar exaustivamente o software usado em centenas de milhares de urnas é complexo e financeiramente proibitivo
  para os fiscais; auditoria por especialistas não substitui o direito do eleitor comum de auditar com os próprios
  meios. [FONTE: Brunazo & Gazziro 2014]
* A confiança subjetiva não pode ser imposta; deve ser conquistada pela demonstração objetiva da confiabilidade
  técnica — "segurança por transparência" em oposição a "segurança por ofuscamento". [FONTE: Brunazo & Gazziro 2014]

## O papel da blockchain no debate

* Com a popularização de blockchains programáveis (Ethereum), surgiram propostas de votação eletrônica sobre elas,
  argumentando que imutabilidade, auditabilidade e descentralização trariam transparência e facilitariam a
  recontagem. [FONTE: Cunha 2022]
* Experiências comerciais (Serra Leoa 2018; aplicativo Voatz no condado de Utah, EUA, 2020) usaram soluções
  proprietárias, reproduzindo críticas feitas a sistemas fechados. [FONTE: Cunha 2022]
* A análise de 2022 mostra que votar *dentro* da cadeia cria problemas de privacidade (remetente, conteúdo e horário
  ficam públicos), de resultados parciais e de escala/custo. Daí a pergunta deste trabalho: **onde a blockchain
  acrescenta garantia sem violar o sigilo do voto?**

## Lacuna e pergunta de pesquisa

* O protótipo de 2016 demonstrou o conceito numa eleição real, mas (como mostra a revisão do código, arquivo `05`)
  seu registro digital não era autenticado, e o software dependia de bibliotecas descontinuadas (Python 2.7, Qt 4,
  PyCrypto).
* As propostas sobre Ethereum colocam o voto na cadeia e falham em privacidade ou escala.
* **Pergunta:** é possível manter a votação offline e em papel (3ª geração), autenticar criptograficamente cada
  cédula, tornar a apuração auditável por qualquer fiscal e ainda obter da blockchain uma garantia de
  imutabilidade do resultado — usando apenas máquinas de laboratório comuns?

## Frases de abertura possíveis (o escritor pode adaptar)

* "Eleições transparentes constituem um dos grandes pilares de uma democracia sólida" [Cunha 2022, resumo].
* "Muitos sistemas de votação eletrônica, entre eles o atual sistema brasileiro, funcionam como uma caixa preta"
  [Lima et al. 2017, citando van de Graaf 2017].
