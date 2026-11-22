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


def test_relatorio_do_lote():
    from urna3g.painel.lote import _agregar, _markdown

    sec = {"secao": "001", "maquina": ".101", "fase": "ancorado", "cedulas_emitidas": 20, "cedulas_no_boletim": 20,
           "duplicadas_rejeitadas": 1, "invalidas_rejeitadas": 0, "bloco": 50, "hash_boletim": "ab" * 32,
           "confere_na_cadeia": True, "t_votacao_s": 30.0, "t_apuracao_s": 4.0, "t_boletim_ate_ancorado_s": 2.5,
           "t_ancorado_desde_inicio_s": 40.0}
    ex = {"execucao": 1, "eleicao_id": "cd" * 32, "inicio": "2026-11-22T10:00:00", "duracao_total_s": 45.0,
          "sucesso": True, "cedulas_total": 20, "duplicadas_rejeitadas": 1, "invalidas_rejeitadas": 0,
          "secoes_ancoradas": 1, "secoes_total": 1, "boletins_conferem_na_cadeia": 1, "bloco_criacao": 40,
          "bloco_encerramento": 52, "t_ultima_ancoragem_s": 40.0, "erros": [],
          "eventos_rede": {"nos_sairam_do_ar": 0, "quorum_perdido": 0, "pausas_sem_bloco": 0,
                           "ancoragens_reenviadas": 0},
          "resultados": {"presidente": {"nome": "Presidente", "votos": {"99": 12, "67": 6, "branco": 1, "nulo": 1}}},
          "legenda": {"presidente": {"99": "Cascão (TM)", "67": "Minnie (DY)"}}, "secoes": [sec]}
    ag = _agregar([ex, {**ex, "execucao": 2, "duracao_total_s": 55.0}])
    assert ag["sucessos"] == 2 and ag["secoes_total"] == 2 and ag["boletins_conferem"] == 2
    assert ag["duracao"] == {"media": 50.0, "min": 45.0, "max": 55.0, "desvio": 7.1}
    md = _markdown({"execucoes_concluidas": 1, "rede": "teste", "gerado_em": "agora", "nos": 1, "execucoes_pedidas": 1,
                    "eleitores_por_secao": 20, "duracao_votacao_s": 30, "contrato": "0x0"}, [ex], _agregar([ex]))
    assert "| 1 | 10:00:00 | 45.0 | 20 |" in md and "Cascão 12, Minnie 6, branco 1, nulo 1" in md and "| sim |" in md


def test_coletor_nao_pula_blocos_quando_a_altura_avanca_durante_a_consulta(tmp_path):
    import asyncio

    p = Painel(_cfg(tmp_path))
    p.contrato = "0x" + "c" * 40
    p.altura = 100
    p.nos["node1"].estado, p.nos["node1"].bloco = "no_ar", 100
    pedidos = []

    async def rpc_falso(no_id, metodo, params=None):
        pedidos.append(params[0])
        p.altura += 3  # a rede produz blocos enquanto a consulta está em andamento
        return []

    p.rpc = rpc_falso

    async def duas_voltas():
        tarefa = asyncio.create_task(p.laco_contrato())
        await asyncio.sleep(4.5)
        tarefa.cancel()

    asyncio.run(duas_voltas())
    assert len(pedidos) >= 2
    assert int(pedidos[1]["fromBlock"], 16) == int(pedidos[0]["toBlock"], 16) + 1
