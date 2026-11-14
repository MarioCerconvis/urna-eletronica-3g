"""Testa o contrato RegistroEleitoral em uma EVM em memória (web3[tester]).

Pulado automaticamente se o extra ``blockchain`` não estiver instalado ou se o artefato compilado
``deploy/blockchain/contracts/RegistroEleitoral.json`` não existir (gere com ``deploy/blockchain/compilar.py``).
"""

import json
from pathlib import Path

import pytest

from urna3g import boletim as bmod
from urna3g.ballot import emitir
from urna3g.tally import Apuracao

web3 = pytest.importorskip("web3")
pytest.importorskip("eth_tester")

ARTEFATO = Path(__file__).resolve().parents[1] / "deploy" / "blockchain" / "contracts" / "RegistroEleitoral.json"
if not ARTEFATO.is_file():
    pytest.skip("contrato não compilado (rode deploy/blockchain/compilar.py)", allow_module_level=True)


@pytest.fixture
def cadeia():
    from web3 import EthereumTesterProvider, Web3

    w3 = Web3(EthereumTesterProvider())
    art = json.loads(ARTEFATO.read_text())
    autoridade, apurador, intruso = w3.eth.accounts[:3]
    fab = w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"])
    tx = fab.constructor().transact({"from": autoridade})
    end = w3.eth.get_transaction_receipt(tx).contractAddress
    return w3, w3.eth.contract(address=end, abi=art["abi"]), autoridade, apurador, intruso


def _reverte(fn, conta):
    with pytest.raises(Exception, match="revert|execution"):
        fn.transact({"from": conta})


def test_ancoragem_de_boletim(cadeia, eleicao, chave_secao, chave_apuracao, tmp_path):
    w3, c, autoridade, apurador, intruso = cadeia
    eid = bytes.fromhex(eleicao.id)
    c.functions.criarEleicao(eid, [apurador]).transact({"from": autoridade})
    _reverte(c.functions.criarEleicao(eid, [apurador]), autoridade)  # já existe

    priv, pub = chave_secao
    ap = Apuracao.abrir(eleicao, "001", pub, tmp_path / "ap.db")
    for v in ([99, 96, 80], [67, 78, 82]):
        ap.processar(emitir(eleicao, "001", v, priv).texto())
    b = ap.gerar_boletim(chave_apuracao[0])
    hb, hl = bytes.fromhex(bmod.hash_boletim(b)), bytes.fromhex(b["ledger"]["hash_final"])

    _reverte(c.functions.registrarBoletim(eid, "001", hb, hl, 2), intruso)  # não autorizado
    c.functions.registrarBoletim(eid, "001", hb, hl, 2).transact({"from": apurador})
    _reverte(c.functions.registrarBoletim(eid, "001", hb, hl, 2), apurador)  # seção repetida
    assert c.functions.secoes(eid).call() == ["001"]
    hb2, hl2, total, bloco, quem = c.functions.boletim(eid, "001").call()
    assert hb2 == hb and hl2 == hl and total == 2 and bloco > 0 and quem == apurador

    _reverte(c.functions.encerrar(eid, b"\x01" * 32), apurador)  # só a autoridade
    c.functions.encerrar(eid, b"\x01" * 32).transact({"from": autoridade})
    _reverte(c.functions.registrarBoletim(eid, "002", hb, hl, 1), apurador)  # encerrada
    _, existe, encerrada, mural, n = c.functions.eleicao(eid).call()
    assert existe and encerrada and mural == b"\x01" * 32 and n == 1
    eventos = c.events.BoletimRegistrado().get_logs(from_block=0)
    assert len(eventos) == 1 and eventos[0]["args"]["secao"] == "001"


def test_script_ancorar_fluxo_completo(eleicao, chave_secao, chave_apuracao, tmp_path, monkeypatch, capsys):
    """Exercita deploy/blockchain/ancorar.py (implantar → criar → registrar → consultar → encerrar)."""
    import sys

    from eth_account import Account
    from web3 import EthereumTesterProvider, Web3

    sys.path.insert(0, str(ARTEFATO.parents[1]))
    import ancorar

    w3 = Web3(EthereumTesterProvider())
    conta = Account.create()
    w3.eth.send_transaction({"from": w3.eth.accounts[0], "to": conta.address, "value": 10**20})
    monkeypatch.setattr(ancorar, "_web3", lambda rpc: w3)
    chave = tmp_path / "key"
    chave.write_text(conta.key.hex())
    manifesto = eleicao.base_dir / "eleicao.json"

    priv, pub = chave_secao
    ap = Apuracao.abrir(eleicao, "001", pub, tmp_path / "ap.db")
    ap.processar(emitir(eleicao, "001", [99, 96, 80], priv).texto())
    caminho_b = bmod.salvar(ap.gerar_boletim(chave_apuracao[0]), tmp_path / "b.json")

    base = ["--chave-arquivo", str(chave)]
    assert ancorar.main([*base, "implantar"]) == 0
    end = capsys.readouterr().out.split("em ")[1].split()[0]
    base += ["--contrato", end]
    assert ancorar.main([*base, "criar", "--eleicao", str(manifesto), "--apuradores", conta.address]) == 0
    assert ancorar.main([*base, "registrar", "--boletim", str(caminho_b)]) == 0
    with pytest.raises(SystemExit, match="secao ja registrada"):
        ancorar.main([*base, "registrar", "--boletim", str(caminho_b)])
    capsys.readouterr()
    assert ancorar.main(["--contrato", end, "consultar", "--eleicao", str(manifesto), "--boletim", str(caminho_b)]) == 0
    saida = capsys.readouterr().out
    assert "confere com" in saida and saida.rstrip().endswith("SIM")
    assert ancorar.main([*base, "encerrar", "--eleicao", str(manifesto), "--mural-hash", "ab" * 32]) == 0
