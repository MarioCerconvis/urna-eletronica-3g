import os
from dataclasses import replace

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["URNA3G_SEM_SOM"] = "1"

pytest.importorskip("PySide6")
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from urna3g import BRANCO, NULO, crypto  # noqa: E402
from urna3g import boletim as bmod
from urna3g.ballot import emitir, ler  # noqa: E402
from urna3g.gui.apurar import JanelaApurar  # noqa: E402
from urna3g.gui.setup_eleicao import JanelaSetupEleicao, slug  # noqa: E402
from urna3g.gui.setup_urna import JanelaSetupUrna  # noqa: E402
from urna3g.gui.verificar import JanelaVerificar  # noqa: E402
from urna3g.gui.votar import JanelaVotar  # noqa: E402
from urna3g.manifest import Eleicao  # noqa: E402


@pytest.fixture(scope="session")
def app():
    return QApplication.instance() or QApplication([])


@pytest.fixture(autouse=True)
def sem_dialogos(monkeypatch):
    """QMessageBox é modal e travaria a suíte offscreen; registramos as mensagens em vez de exibir."""
    from urna3g.gui.comum import JanelaBase

    erros: list[str] = []
    monkeypatch.setattr(JanelaBase, "erro", lambda self, titulo, texto: erros.append(f"{titulo}: {texto}"))
    return erros


def teclas(j, *ks):
    for k in ks:
        QTest.keyClick(j, k)


def test_fluxo_de_votacao(app, eleicao, chave_secao, tmp_path):
    priv, pub = chave_secao
    j = JanelaVotar(eleicao, "001", priv, tmp_path, sem_impressora=True, tempo_reinicio_ms=0)
    emitidas = []
    j.cedula_emitida.connect(emitidas.append)
    j.show()
    assert j.lista.count() == 3
    teclas(j, Qt.Key.Key_1)  # Presidente
    assert j.pilha.currentIndex() == JanelaVotar.PAG_DIGITOS and len(j.quadros) == 2
    teclas(j, Qt.Key.Key_9, Qt.Key.Key_9)
    assert "Cascão" in j.lbl_nome.text() and j.estado == "candidato"
    teclas(j, Qt.Key.Key_Return)
    assert j.pilha.currentIndex() == JanelaVotar.PAG_CARGOS and j.lista.count() == 2
    teclas(j, Qt.Key.Key_3, Qt.Key.Key_Minus)  # Deputado em branco (numeração dos cargos é estável)
    assert j.estado == "branco"
    teclas(j, Qt.Key.Key_Enter)
    teclas(j, Qt.Key.Key_2, Qt.Key.Key_1, Qt.Key.Key_2)  # Senador: 12 não existe → nulo
    assert j.estado == "nulo" and "INEXISTENTE" in j.lbl_mensagem.text()
    teclas(j, Qt.Key.Key_Return)
    assert len(emitidas) == 1
    c = ler(emitidas[0], eleicao, pub, secao_esperada="001")
    assert c.votos == (99, NULO, BRANCO)
    assert list((tmp_path / "cedulas").glob("cedula-*.pdf"))
    QTest.qWait(30)
    assert j.pilha.currentIndex() == JanelaVotar.PAG_CARGOS and j.lista.count() == 3


def test_corrige_apaga_e_confirma_incompleto(app, eleicao, chave_secao, tmp_path):
    priv, _ = chave_secao
    j = JanelaVotar(eleicao, "001", priv, tmp_path, sem_impressora=True)
    j.show()
    teclas(j, Qt.Key.Key_1, Qt.Key.Key_6)
    teclas(j, Qt.Key.Key_Return)  # incompleto
    assert "completo" in j.lbl_mensagem.text() and j.pilha.currentIndex() == JanelaVotar.PAG_DIGITOS
    teclas(j, Qt.Key.Key_7)
    assert "Minnie" in j.lbl_nome.text()
    teclas(j, Qt.Key.Key_Backspace)
    assert j.digitos == [6] and j.lbl_nome.text() == ""
    teclas(j, Qt.Key.Key_Plus)
    assert j.digitos == [] and j.estado == "digitando"
    teclas(j, Qt.Key.Key_Asterisk)
    assert j.estado == "nulo"
    teclas(j, Qt.Key.Key_Escape)  # não fecha a janela em modo quiosque
    assert j.isVisible()


def test_nao_repete_candidato_em_cargo_com_dois_votos(app, eleicao, chave_secao, tmp_path):
    priv, pub = chave_secao
    e2 = replace(eleicao, cargos=[replace(c, votos_por_eleitor=2) if c.id == "senador" else c for c in eleicao.cargos])
    j = JanelaVotar(e2, "001", priv, tmp_path, sem_impressora=True, tempo_reinicio_ms=0)
    emitidas = []
    j.cedula_emitida.connect(emitidas.append)
    j.show()
    teclas(j, Qt.Key.Key_2, Qt.Key.Key_9, Qt.Key.Key_6, Qt.Key.Key_Return)
    assert "2º de 2" in j.lbl_cargo.text()
    teclas(j, Qt.Key.Key_9, Qt.Key.Key_6, Qt.Key.Key_Return)
    assert "já escolhido" in j.lbl_mensagem.text()
    teclas(j, Qt.Key.Key_7, Qt.Key.Key_8, Qt.Key.Key_Return)
    teclas(j, Qt.Key.Key_1, Qt.Key.Key_6, Qt.Key.Key_7, Qt.Key.Key_Return)
    teclas(j, Qt.Key.Key_3, Qt.Key.Key_8, Qt.Key.Key_0, Qt.Key.Key_Return)
    assert len(emitidas) == 1
    assert ler(emitidas[0], e2, pub).votos == (67, 96, 78, 80)


def test_verificar(app, eleicao, chave_secao):
    priv, pub = chave_secao
    j = JanelaVerificar(eleicao, "001", pub)
    texto = emitir(eleicao, "001", [99, 96, 80], priv).texto()
    assert j.processar(texto) and "Cascão" in j.lbl_voto.text()
    assert not j.processar(emitir(eleicao, "002", [99, 96, 80], priv).texto())
    assert "INVÁLIDO" in j.lbl_voto.text()
    assert not j.processar("lixo")


def test_leitor_teclado_simula_scanner_usb(app, eleicao, chave_secao):
    priv, pub = chave_secao
    j = JanelaVerificar(eleicao, "001", pub)
    j.show()
    j.activateWindow()
    texto = emitir(eleicao, "001", [67, 78, 82], priv).texto()
    QTest.keyClicks(j, texto)
    QTest.keyClick(j, Qt.Key.Key_Return)
    assert "Minnie" in j.lbl_voto.text()
    j.leitor.deleteLater()


def test_apurar(app, eleicao, chave_secao, chave_apuracao, tmp_path):
    priv, pub = chave_secao
    priv_ap, pub_ap = chave_apuracao
    j = JanelaApurar(eleicao, "001", pub, priv_ap, tmp_path, sem_impressora=True)
    t1 = emitir(eleicao, "001", [99, 96, 80], priv).texto()
    assert j.processar(t1).aceita
    assert not j.processar(t1).aceita and "JÁ APURADA" in j.lbl_mensagem.text()
    assert j.processar(emitir(eleicao, "001", [67, 78, 82], priv).texto()).aceita
    assert not j.processar("U3G1:xx").aceita
    assert j.tabela.rowCount() == 7 + 2 * 3  # 7 candidatos + branco/nulo por cargo
    assert "Cédulas apuradas: 2" in j.lbl_total.text()
    b = j.gerar_boletim(confirmar=False)
    assert b is not None
    bmod.verificar(b, pub_ap)
    assert (tmp_path / "boletim-001.json").is_file() and (tmp_path / "boletim-001.pdf").is_file()
    assert not j.btn_boletim.isEnabled()
    assert j.processar(emitir(eleicao, "001", [67, 78, 82], priv).texto()).status.value == "encerrada"
    assert j.gerar_boletim(confirmar=False) is None
    j.close()


def test_setup_urna(app, tmp_path):
    j = JanelaSetupUrna(tmp_path / "chaves")
    j.campo_secao.setText("007")
    j.gerar_secao(confirmar=False)
    for nome in ("secao-007.key", "secao-007.pub", "apuracao-007.key", "apuracao-007.pub"):
        assert (tmp_path / "chaves" / nome).is_file()
    crypto.carregar_privada(tmp_path / "chaves" / "secao-007.key")
    with pytest.raises(FileExistsError):
        j.gerar_secao(confirmar=False)
    j.campo_secao.setText("sec ao")
    with pytest.raises(ValueError):
        j.gerar_secao(confirmar=False)
    j.campo_senha.setText("abc")
    j.campo_senha2.setText("abc")
    j.gerar_autoridade(confirmar=False)
    with pytest.raises(crypto.ErroChave):
        crypto.carregar_privada(tmp_path / "chaves" / "autoridade.key")
    assert crypto.carregar_privada(tmp_path / "chaves" / "autoridade.key", senha="abc")


def test_setup_eleicao(app, tmp_path, eleicao, sem_dialogos):
    assert slug("Deputado Federal") == "deputado-federal"
    caminho = tmp_path / "nova" / "eleicao.json"
    j = JanelaSetupEleicao(caminho)
    j.campo_nome.setText("Conselho do CMCC")
    j.campo_secoes.setText("001, 002")
    j.cargo_nome.setText("Representante discente")
    j.cargo_votos.setValue(2)
    j.cadastrar_cargo()
    j.partido_numero.setValue(10)
    j.partido_nome.setText("Chapa Única")
    j.partido_sigla.setText("CU")
    j.partido_foto.setText(str(eleicao.caminho("fotos/turma-monica92.png")))
    j.cadastrar_partido()
    assert j.cand_cargo.count() == 1 and j.cand_partido.count() == 1
    for numero, nome in ((11, "Ana"), (12, "Bruno"), (13, "Carla")):
        j.cand_numero.setValue(numero)
        j.cand_nome.setText(nome)
        j.cadastrar_candidato()
    j.cand_numero.setValue(11)
    j.cand_nome.setText("Repetido")
    j.cadastrar_candidato()  # número repetido → recusado com diálogo de erro
    assert len(j.eleicao.candidatos) == 3 and any("Já existe" in e for e in sem_dialogos)
    assert j.salvar(mostrar=False)
    e = Eleicao.carregar(caminho)
    e.validar(verificar_fotos=True)
    assert e.nome == "Conselho do CMCC" and e.secoes == ["001", "002"]
    assert e.cargos[0].votos_por_eleitor == 2 and len(e.slots()) == 2
    assert e.partidos[0].foto == "fotos/turma-monica92.png" and (tmp_path / "nova" / "fotos").is_dir()
    j.apagar(confirmar=False)
    assert not j.eleicao.cargos and not j.validar(mostrar=False)
