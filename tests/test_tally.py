import sqlite3
from dataclasses import replace

import pytest

from urna3g import BRANCO, NULO, crypto
from urna3g import boletim as bmod
from urna3g.ballot import Cedula, emitir
from urna3g.ledger import ErroLedger, Ledger
from urna3g.tally import Apuracao, Status


@pytest.fixture
def apuracao(eleicao, chave_secao, tmp_path):
    _, pub = chave_secao
    return Apuracao.abrir(eleicao, "001", pub, tmp_path / "ap.db")


def test_abertura_registrada(apuracao):
    regs = apuracao.ledger.registros()
    assert [r.tipo for r in regs] == ["abertura"]
    assert apuracao.ledger.verificar() == 1


def test_fluxo_completo(apuracao, eleicao, chave_secao, chave_apuracao):
    priv, pub = chave_secao
    votos = [[99, 96, 80], [99, 78, 82], [67, 66, BRANCO], [NULO, 96, 82], [99, BRANCO, 80]]
    textos = [emitir(eleicao, "001", v, priv).texto() for v in votos]
    for t in textos:
        assert apuracao.processar(t).status is Status.ACEITA
    # releitura da mesma cédula não conta
    r = apuracao.processar(textos[0])
    assert r.status is Status.DUPLICADA
    # cédula de outra seção / chave
    outra = emitir(eleicao, "002", [67, 78, 82], priv).texto()
    assert apuracao.processar(outra).status is Status.INVALIDA
    forjada = emitir(eleicao, "001", [67, 78, 82], crypto.gerar_chave()).texto()
    assert apuracao.processar(forjada).status is Status.INVALIDA
    assert apuracao.processar("lixo").status is Status.INVALIDA

    assert apuracao.total_cedulas() == 5
    t = apuracao.totais()
    assert t["presidente"][99] == 3 and t["presidente"][67] == 1 and t["presidente"][NULO] == 1
    assert t["senador"][96] == 2 and t["senador"][78] == 1 and t["senador"][66] == 1 and t["senador"][BRANCO] == 1
    assert t["deputado"][80] == 2 and t["deputado"][82] == 2 and t["deputado"][BRANCO] == 1
    assert apuracao.ledger.ocorrencias() == {"duplicada": 1, "invalida": 3}

    priv_ap, pub_ap = chave_apuracao
    b = apuracao.gerar_boletim(priv_ap)
    bmod.verificar(b, pub_ap)
    assert b["total_cedulas"] == 5
    assert b["resultados"]["presidente"]["votos"] == {"67": 1, "99": 3, "branco": 0, "nulo": 1}
    assert b["ledger"]["hash_final"] == apuracao.ledger.hash_final
    assert b["chave_publica_secao"] == crypto.impressao_digital(pub)
    assert bmod.texto_qr(b).startswith("BU1:001:")
    with pytest.raises(bmod.ErroBoletim):
        bmod.verificar(b, crypto.gerar_chave().public_key())
    adulterado = dict(b)
    adulterado["total_cedulas"] = 6
    with pytest.raises(bmod.ErroBoletim):
        bmod.verificar(adulterado, pub_ap)

    # após o boletim a apuração está encerrada
    assert apuracao.encerrada
    nova = emitir(eleicao, "001", [67, 78, 82], priv).texto()
    assert apuracao.processar(nova).status is Status.ENCERRADA
    assert apuracao.total_cedulas() == 5
    assert apuracao.ledger.registros()[-1].tipo == "encerramento"
    assert apuracao.ledger.verificar() == 7  # abertura + 5 cédulas + encerramento


def test_csv(apuracao, eleicao, chave_secao, tmp_path):
    priv, _ = chave_secao
    apuracao.processar(emitir(eleicao, "001", [99, 96, 80], priv).texto())
    p = apuracao.exportar_csv(tmp_path / "b.csv")
    linhas = p.read_text(encoding="utf-8").splitlines()
    assert linhas[0] == "cargo,voto,descricao,quantidade"
    assert "Presidente,99,99 - Cascão (TM),1" in linhas


def test_numero_inexistente_vira_nulo_com_observacao(apuracao, eleicao, chave_secao):
    priv, _ = chave_secao
    base = Cedula(eleicao.id_curto, "001", (12, 96, 80), b"\x01" * 16)
    assinada = Cedula(base.eleicao_id_curto, base.secao, base.votos, base.nonce, crypto.assinar(priv, base.mensagem()))
    assert apuracao.processar(assinada.texto()).status is Status.ACEITA
    assert apuracao.totais()["presidente"][NULO] == 1
    assert any("inexistente" in o for o in apuracao.observacoes())


def test_adulteracao_do_ledger_e_detectada(apuracao, eleicao, chave_secao):
    priv, _ = chave_secao
    for v in ([99, 96, 80], [67, 78, 82]):
        apuracao.processar(emitir(eleicao, "001", v, priv).texto())
    assert apuracao.ledger.verificar() == 3
    con = sqlite3.connect(apuracao.ledger.caminho)
    outro = emitir(eleicao, "001", [67, 96, 80], priv).texto()
    con.execute("UPDATE registros SET dados=? WHERE seq=2", (outro,))
    con.commit()
    con.close()
    with pytest.raises(ErroLedger, match="alterado"):
        apuracao.ledger.verificar()


def test_remocao_de_registro_e_detectada(apuracao, eleicao, chave_secao):
    priv, _ = chave_secao
    for v in ([99, 96, 80], [67, 78, 82], [67, 66, 82]):
        apuracao.processar(emitir(eleicao, "001", v, priv).texto())
    con = sqlite3.connect(apuracao.ledger.caminho)
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("DELETE FROM cedulas WHERE seq=3")
    con.execute("DELETE FROM registros WHERE seq=3")
    con.commit()
    con.close()
    with pytest.raises(ErroLedger):
        apuracao.ledger.verificar()


def test_ledger_de_outra_eleicao_recusado(apuracao, eleicao, chave_secao):
    _, pub = chave_secao
    outra = replace(eleicao, nome="Outra")
    with pytest.raises(ErroLedger):
        Ledger(apuracao.ledger.caminho, outra.id, "001")
    with pytest.raises(ErroLedger):
        Ledger(apuracao.ledger.caminho, eleicao.id, "002")
    # reabrir a mesma seção funciona e mantém o estado
    ap2 = Apuracao.abrir(eleicao, "001", pub, apuracao.ledger.caminho)
    assert ap2.ledger.verificar() == len(apuracao.ledger.registros())
