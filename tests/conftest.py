from pathlib import Path

import pytest

from urna3g import crypto
from urna3g.manifest import Eleicao

RAIZ = Path(__file__).resolve().parents[1]
DEMO = RAIZ / "exemplos" / "eleicao-demo" / "eleicao.json"


@pytest.fixture(scope="session")
def eleicao() -> Eleicao:
    e = Eleicao.carregar(DEMO)
    e.validar(verificar_fotos=True)
    return e


@pytest.fixture(scope="session")
def chave_secao():
    priv = crypto.gerar_chave()
    return priv, priv.public_key()


@pytest.fixture(scope="session")
def chave_apuracao():
    priv = crypto.gerar_chave()
    return priv, priv.public_key()


@pytest.fixture(scope="session")
def chave_autoridade():
    priv = crypto.gerar_chave()
    return priv, priv.public_key()
