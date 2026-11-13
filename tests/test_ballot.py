from dataclasses import replace

import pytest

from urna3g import BRANCO, NULO, crypto
from urna3g.ballot import (
    PREFIXO,
    Cedula,
    ErroCedula,
    decodificar,
    descrever,
    emitir,
    ler,
    verificar,
)
from urna3g.qr import versao_qr


def test_roundtrip(eleicao, chave_secao):
    priv, pub = chave_secao
    c = emitir(eleicao, "001", [99, BRANCO, NULO], priv)
    txt = c.texto()
    assert txt.startswith(PREFIXO)
    assert len(txt) < 160, "QR precisa continuar pequeno para webcams"
    assert versao_qr(txt) <= 8
    d = decodificar(txt)
    assert d == c
    verificar(d, eleicao, pub, secao_esperada="001")
    assert ler(txt, eleicao, pub).votos == (99, 0, -1)
    assert descrever(d, eleicao) == [
        ("Presidente", "99 - Cascão (TM)"),
        ("Senador", "Branco"),
        ("Deputado", "Nulo"),
    ]


def test_nonce_unico(eleicao, chave_secao):
    priv, _ = chave_secao
    nonces = {emitir(eleicao, "001", [67, 78, 82], priv).nonce for _ in range(500)}
    assert len(nonces) == 500


def test_rejeita_chave_errada(eleicao, chave_secao):
    priv, _ = chave_secao
    txt = emitir(eleicao, "001", [67, 78, 82], priv).texto()
    outra = crypto.gerar_chave().public_key()
    with pytest.raises(ErroCedula, match="assinatura"):
        ler(txt, eleicao, outra)


def test_rejeita_outra_eleicao_e_secao(eleicao, chave_secao):
    priv, pub = chave_secao
    txt = emitir(eleicao, "002", [67, 78, 82], priv).texto()
    outra_eleicao = replace(eleicao, nome="Outra")
    with pytest.raises(ErroCedula, match="outra eleição"):
        ler(txt, outra_eleicao, pub)
    with pytest.raises(ErroCedula, match="seção"):
        ler(txt, eleicao, pub, secao_esperada="001")


def test_rejeita_adulteracao(eleicao, chave_secao):
    priv, pub = chave_secao
    txt = emitir(eleicao, "001", [67, 78, 82], priv).texto()
    corpo = txt[len(PREFIXO):]
    # altera um caractere no meio do payload (votos) → assinatura não confere
    i = 20
    alterado = corpo[:i] + ("A" if corpo[i] != "A" else "B") + corpo[i + 1:]
    with pytest.raises(ErroCedula):
        ler(PREFIXO + alterado, eleicao, pub)
    with pytest.raises(ErroCedula, match="truncada"):
        decodificar(PREFIXO + corpo[:-20])
    with pytest.raises(ErroCedula, match="prefixo"):
        decodificar("https://exemplo.com/")
    with pytest.raises(ErroCedula):
        decodificar(PREFIXO + "!!!não é base64!!!")
    with pytest.raises(ErroCedula, match="excedentes"):
        decodificar(PREFIXO + corpo + "AAAA")


def test_emitir_valida_conteudo(eleicao, chave_secao):
    priv, _ = chave_secao
    with pytest.raises(ErroCedula, match="inexistente"):
        emitir(eleicao, "001", [12, 78, 82], priv)
    with pytest.raises(ErroCedula, match="esperados 3"):
        emitir(eleicao, "001", [99, 78], priv)
    with pytest.raises(ErroCedula, match="seção"):
        emitir(eleicao, "", [99, 78, 82], priv)
    with pytest.raises(ErroCedula, match="não assinada"):
        Cedula(eleicao.id_curto, "001", (99, 78, 82), b"\0" * 16).texto()
