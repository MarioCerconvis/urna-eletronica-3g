import shutil

import pytest
from conftest import DEMO

from urna3g.cli import main


@pytest.fixture
def ambiente(tmp_path):
    """Chaves + manifesto assinado em um diretório temporário."""
    shutil.copytree(DEMO.parent, tmp_path / "eleicao")
    ch = tmp_path / "chaves"
    assert main(["chaves", "gerar", "--secao", "001", "--autoridade", "--saida", str(ch)]) == 0
    manifesto = tmp_path / "eleicao" / "eleicao.json"
    assert main(["eleicao", "assinar", str(manifesto), "--chave", str(ch / "autoridade.key")]) == 0
    assert main(["eleicao", "verificar", str(manifesto), "--pub", str(ch / "autoridade.pub")]) == 0
    return tmp_path, manifesto, ch


def test_chaves_nao_sobrescreve(ambiente, capsys):
    tmp, _, ch = ambiente
    assert main(["chaves", "gerar", "--secao", "001", "--saida", str(ch)]) == 2
    assert "já existe" in capsys.readouterr().err
    assert main(["chaves", "info", str(ch / "secao-001.pub")]) == 0


def test_validar_e_id(ambiente, capsys):
    _, manifesto, _ = ambiente
    assert main(["eleicao", "validar", str(manifesto), "--fotos"]) == 0
    assert main(["eleicao", "id", str(manifesto)]) == 0
    saida = capsys.readouterr().out
    assert "OK" in saida and len(saida.strip().splitlines()[-1]) == 64


def test_fluxo_cedula_apuracao_boletim(ambiente, capsys):
    tmp, manifesto, ch = ambiente
    base = ["--eleicao", str(manifesto), "--autoridade", str(ch / "autoridade.pub"), "--secao", "001"]
    textos = []
    for votos in ("99,96,80", "67,branco,82", "nulo,78,80"):
        assert main(["cedula", "emitir", *base, "--chave", str(ch / "secao-001.key"), "--votos", votos,
                     "--pdf", str(tmp / f"c{len(textos)}.pdf")]) == 0
        textos.append(capsys.readouterr().out.strip().splitlines()[-1])
    assert all(t.startswith("U3G1:") for t in textos)
    assert (tmp / "c0.pdf").stat().st_size > 1000

    assert main(["cedula", "ler", *base, "--pub", str(ch / "secao-001.pub"), textos[0]]) == 0
    assert "Cascão" in capsys.readouterr().out
    assert main(["cedula", "ler", *base, "--pub", str(ch / "secao-001.pub"), "U3G1:AAAA"]) == 1

    db = tmp / "ap.db"
    ap = [*base, "--pub", str(ch / "secao-001.pub"), "--db", str(db)]
    assert main(["apurar", "ler", *ap, *textos, textos[0]]) == 0
    out = capsys.readouterr().out
    assert out.count("ACEITA") == 3 and "DUPLICADA" in out
    assert main(["apurar", "totais", *ap]) == 0
    assert "cédulas: 3" in capsys.readouterr().out
    cmd = ["apurar", "boletim", *ap, "--chave-apuracao", str(ch / "apuracao-001.key"), "--saida", str(tmp / "s")]
    assert main(cmd) == 0
    assert (tmp / "s" / "boletim-001.json").is_file() and (tmp / "s" / "boletim-001.pdf").is_file()
    bol = str(tmp / "s" / "boletim-001.json")
    assert main(["boletim", "verificar", bol, "--pub", str(ch / "apuracao-001.pub")]) == 0
    assert main(["boletim", "verificar", str(tmp / "s" / "boletim-001.json"), "--pub", str(ch / "secao-001.pub")]) == 2
    assert main(["apurar", "verificar-ledger", *base, "--db", str(db)]) == 0
    assert "íntegro" in capsys.readouterr().out
    # encerrada: nada mais entra
    assert main(["apurar", "ler", *ap, textos[1]]) == 0
    assert "ENCERRADA" in capsys.readouterr().out


def test_erros_viram_codigo_2(tmp_path, capsys):
    assert main(["eleicao", "validar", str(tmp_path / "nao-existe.json")]) == 2
    assert "erro:" in capsys.readouterr().err


def test_demo(tmp_path, capsys):
    assert main(["demo", "--saida", str(tmp_path / "demo"), "--eleitores", "12", "--pdfs", "1", "--semente", "7"]) == 0
    out = capsys.readouterr().out
    assert "boletim assinado e verificado" in out and "ledger íntegro" in out
    assert (tmp_path / "demo" / "boletim-001.pdf").is_file()
    assert main(["demo", "--saida", str(tmp_path / "demo")]) == 2  # diretório não vazio
