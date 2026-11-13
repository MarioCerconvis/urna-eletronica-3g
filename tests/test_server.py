import json
import shutil

import pytest
from conftest import DEMO

from urna3g import BRANCO, crypto
from urna3g import boletim as bmod
from urna3g.ballot import emitir
from urna3g.config import Chaves
from urna3g.manifest import Eleicao, assinar_manifesto, salvar_assinatura
from urna3g.tally import Apuracao

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from urna3g.server.app import criar_app  # noqa: E402


@pytest.fixture
def servidor(tmp_path):
    dados = tmp_path / "dados"
    shutil.copytree(DEMO.parent, dados)
    ch = Chaves(dados / "chaves")
    aut = crypto.gerar_chave()
    crypto.salvar_publica(ch.autoridade_pub(), aut.public_key())
    e = Eleicao.carregar(dados / "eleicao.json").preencher_hashes_fotos()
    e.salvar(dados / "eleicao.json")
    salvar_assinatura(dados / "eleicao.sig", assinar_manifesto(e, aut))
    chaves = {}
    for secao in ("001", "002"):
        urna, ap = crypto.gerar_chave(), crypto.gerar_chave()
        crypto.salvar_publica(ch.secao_pub(secao), urna.public_key())
        crypto.salvar_publica(ch.apuracao_pub(secao), ap.public_key())
        chaves[secao] = (urna, ap)
    return TestClient(criar_app(dados)), e, chaves, tmp_path


def _boletim(e, secao, urna, ap, tmp_path, votos):
    apur = Apuracao.abrir(e, secao, urna.public_key(), tmp_path / f"ap-{secao}.db")
    for v in votos:
        assert apur.processar(emitir(e, secao, v, urna).texto()).aceita
    return apur.gerar_boletim(ap)


def test_distribuicao(servidor):
    cli, e, _, _ = servidor
    r = cli.get("/api/eleicao")
    assert r.status_code == 200 and r.json()["id"] == e.id and r.json()["situacao_assinatura"] == "assinado"
    assert cli.get("/saude").json()["ok"]
    ch = cli.get("/api/chaves").json()
    assert set(ch["apuracao"]) == {"001", "002"} and ch["autoridade"]
    assert cli.get("/api/chaves/apuracao-001.pub").text.startswith("-----BEGIN PUBLIC KEY-----")
    assert cli.get("/api/chaves/../etc.pub").status_code in (400, 404)
    pacote = cli.get("/api/eleicao/pacote.zip")
    assert pacote.status_code == 200 and pacote.content[:2] == b"PK"


def test_recebe_boletins_e_totaliza(servidor):
    cli, e, chaves, tmp = servidor
    b1 = _boletim(e, "001", *chaves["001"], tmp, [[99, 96, 80], [99, 78, 82], [67, BRANCO, 80]])
    b2 = _boletim(e, "002", *chaves["002"], tmp, [[67, 66, 82], [99, 96, 80]])
    r = cli.post("/api/boletins", content=json.dumps(b1))
    assert r.status_code == 201, r.text
    assert r.json()["secao"] == "001" and r.json()["seq"] == 1
    # idempotente para o mesmo boletim
    assert cli.post("/api/boletins", content=json.dumps(b1)).status_code == 200
    assert cli.post("/api/boletins", content=json.dumps(b2)).status_code == 201

    t = cli.get("/api/totalizacao").json()
    assert t["total_cedulas"] == 5 and t["secoes_recebidas"] == ["001", "002"]
    assert t["resultados"]["presidente"]["votos"] == {"67": 2, "99": 3, "branco": 0, "nulo": 0}
    assert t["resultados"]["senador"]["votos"]["96"] == 2 and t["resultados"]["senador"]["votos"]["branco"] == 1
    assert t["mural"]["registros"] == 2
    pagina = cli.get("/").text
    assert e.nome in pagina and "Cascão" in pagina and "Aguardando" not in pagina
    assert cli.get("/api/boletins/001").json()["total_cedulas"] == 3
    assert cli.get("/api/boletins/009").status_code == 404
    assert len(cli.get("/api/mural").json()["registros"]) == 2


def test_rejeicoes(servidor):
    cli, e, chaves, tmp = servidor
    b = _boletim(e, "001", *chaves["001"], tmp, [[99, 96, 80]])
    adulterado = dict(b)
    adulterado["total_cedulas"] = 999
    assert cli.post("/api/boletins", content=json.dumps(adulterado)).status_code == 400
    # assinado por chave errada
    falso = bmod.assinar(b, crypto.gerar_chave())
    assert cli.post("/api/boletins", content=json.dumps(falso)).status_code == 400
    # seção desconhecida
    outra = dict(b)
    outra["secao"] = "777"
    outra = bmod.assinar(outra, chaves["001"][1])
    assert cli.post("/api/boletins", content=json.dumps(outra)).status_code == 403
    # outra eleição
    outra_e = dict(b)
    outra_e["eleicao_id"] = "0" * 64
    assert cli.post("/api/boletins", content=json.dumps(bmod.assinar(outra_e, chaves["001"][1]))).status_code == 400
    assert cli.post("/api/boletins", content=b"nao e json").status_code == 400
    assert cli.post("/api/boletins", content=json.dumps([1, 2])).status_code == 400
    # boletim válido e depois um DIFERENTE para a mesma seção → conflito
    assert cli.post("/api/boletins", content=json.dumps(b)).status_code == 201
    b_novo = _boletim(e, "001", *chaves["001"], tmp / "x", [[67, 78, 82], [67, 78, 82]])
    assert cli.post("/api/boletins", content=json.dumps(b_novo)).status_code == 409
    assert cli.get("/api/totalizacao").json()["total_cedulas"] == 1
