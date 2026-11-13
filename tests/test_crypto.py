import os
import stat

import pytest

from urna3g import crypto


def test_assinar_e_verificar():
    priv = crypto.gerar_chave()
    pub = priv.public_key()
    sig = crypto.assinar(priv, b"voto")
    assert len(sig) == 64
    assert crypto.verificar(pub, b"voto", sig)
    assert not crypto.verificar(pub, b"voto!", sig)
    assert not crypto.verificar(pub, b"voto", sig[:-1] + bytes([sig[-1] ^ 1]))
    outra = crypto.gerar_chave().public_key()
    assert not crypto.verificar(outra, b"voto", sig)


def test_arquivos_pem_roundtrip(tmp_path):
    priv = crypto.gerar_chave()
    p = crypto.salvar_privada(tmp_path / "chaves" / "secao.key", priv)
    q = crypto.salvar_publica(tmp_path / "chaves" / "secao.pub", priv.public_key())
    assert stat.S_IMODE(os.stat(p).st_mode) == 0o600
    priv2 = crypto.carregar_privada(p)
    pub2 = crypto.carregar_publica(q)
    assert crypto.publica_bytes(priv2.public_key()) == crypto.publica_bytes(pub2)
    assert crypto.impressao_digital(pub2) == crypto.impressao_digital(priv.public_key())


def test_senha_protege_chave(tmp_path):
    priv = crypto.gerar_chave()
    p = crypto.salvar_privada(tmp_path / "s.key", priv, senha="segredo")
    assert b"ENCRYPTED" in p.read_bytes()
    with pytest.raises(crypto.ErroChave):
        crypto.carregar_privada(p)  # sem senha
    with pytest.raises(crypto.ErroChave):
        crypto.carregar_privada(p, senha="errada")
    assert crypto.carregar_privada(p, senha="segredo")


def test_chave_de_tipo_errado_rejeitada(tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = rsa_key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    (tmp_path / "rsa.key").write_bytes(pem)
    with pytest.raises(crypto.ErroChave):
        crypto.carregar_privada(tmp_path / "rsa.key")
    with pytest.raises(crypto.ErroChave):
        crypto.carregar_privada(tmp_path / "inexistente.key")


def test_impressao_digital_formatada():
    pub = crypto.gerar_chave().public_key()
    fp = crypto.impressao_digital(pub)
    assert len(fp) == 64
    txt = crypto.formatar_impressao(fp)
    assert txt.replace(" ", "").lower() == fp
    assert len(txt.split()) == 8
