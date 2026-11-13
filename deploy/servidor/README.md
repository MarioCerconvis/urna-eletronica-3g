# Servidor do mural

```bash
mkdir -p deploy/servidor/dados/chaves
cp caminho/da/eleicao/eleicao.json caminho/da/eleicao/eleicao.sig deploy/servidor/dados/
cp -r caminho/da/eleicao/fotos deploy/servidor/dados/
cp chaves/autoridade.pub chaves/apuracao-*.pub chaves/secao-*.pub deploy/servidor/dados/chaves/
docker compose -f deploy/servidor/docker-compose.yml up -d --build
```

* Mural público: `http://SERVIDOR:8000/` · API: `/docs`
* Pacote para os terminais: `http://SERVIDOR:8000/api/eleicao/pacote.zip`
* Envio do boletim pelo apurador (via LAN ou pendrive + qualquer máquina):

```bash
curl -fsS -X POST --data-binary @saida/boletim-001.json http://SERVIDOR:8000/api/boletins
```

Sem Docker: `pip install 'urna3g[servidor]' && urna3g servidor --dados deploy/servidor/dados`.
Para expor fora da LAN, coloque um nginx/caddy com TLS na frente e limite a taxa de `POST /api/boletins`.
