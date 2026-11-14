"""Painel ao vivo: sobe o app sem nenhum nó acessível e confere página, estado, decodificação de eventos."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("eth_abi")
from eth_abi import encode  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from urna3g.painel.app import criar_app  # noqa: E402
from urna3g.painel.coletor import TOPICOS, Painel  # noqa: E402
from urna3g.painel.config import NoCfg, PainelCfg  # noqa: E402


def _cfg(tmp_path, n=3):
    nos = [NoCfg(f"node{k}", k, "127.0.0.1", f"http://127.0.0.1:{1 + k}", f"0x{k:040x}", tmp_path / "key")
           for k in range(1, n + 1)]
    return PainelCfg("local", "teste", tmp_path, nos)


def test_app_sobe_sem_nos(tmp_path):
    with TestClient(criar_app(_cfg(tmp_path))) as cli:
        assert "Painel ao vivo" in cli.get("/").text
        assert cli.get("/static/painel.js").status_code == 200
        e = cli.get("/api/estado").json()
        assert e["rede"]["total"] == 3 and e["rede"]["quorum"] == 2
        assert {n["id"] for n in e["nos"]} == {"node1", "node2", "node3"}
        assert cli.post("/api/nos/nodeX/derrubar").status_code == 404
        assert cli.post("/api/nos/node1/explodir").status_code == 400
        assert cli.post("/api/ensaio", json={"eleitores": 1}).status_code == 422


def test_quorum_qbft(tmp_path):
    assert [Painel(_cfg(tmp_path, n)).quorum for n in (1, 4, 6, 7, 12, 13)] == [1, 3, 4, 5, 8, 9]


def test_decodifica_eventos_do_contrato(tmp_path):
    p = Painel(_cfg(tmp_path))
    topico = {v: k for k, v in TOPICOS.items()}
    eid = "ab" * 32
    p._log_contrato({"topics": [topico["EleicaoCriada"], "0x" + eid], "blockNumber": "0x10",
                     "data": "0x" + encode(["address", "uint256"], ["0x" + "1" * 40, 3]).hex()})
    assert p.eleicao["id"] == eid and p.eleicao["fase"] == "votacao"
    dados = encode(["string", "bytes32", "bytes32", "uint32", "address"],
                   ["007", b"\x01" * 32, b"\x02" * 32, 42, "0x" + f"{2:040x}"])
    p._log_contrato({"topics": [topico["BoletimRegistrado"], "0x" + eid], "blockNumber": "0x11",
                     "data": "0x" + dados.hex()})
    s = p.eleicao["secoes"]["007"]
    assert s["fase"] == "ancorado" and s["cedulas_apuradas"] == 42 and s["no"] == "node2" and s["bloco"] == 17
    p._log_contrato({"topics": [topico["EleicaoEncerrada"], "0x" + eid], "blockNumber": "0x12",
                     "data": "0x" + encode(["bytes32"], [b"\x03" * 32]).hex()})
    assert p.eleicao["encerrada"] and p.eleicao["fase"] == "encerrada"
    textos = [ev["texto"] for ev in p.eventos]
    assert any("ancorado no bloco #17 por node2" in t for t in textos)
