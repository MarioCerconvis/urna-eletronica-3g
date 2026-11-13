import numpy as np
import pytest

from urna3g import BRANCO
from urna3g.ballot import emitir
from urna3g.qr import gerar_qr
from urna3g.render import renderizar_boletim_pdf, renderizar_cedula_pdf
from urna3g.tally import Apuracao

cv2 = pytest.importorskip("cv2")


def _decodificar_qr(img):
    arr = np.array(img)[:, :, ::-1]  # RGB -> BGR
    texto, _, _ = cv2.QRCodeDetector().detectAndDecode(arr)
    return texto


def test_qr_e_legivel_pelo_opencv(eleicao, chave_secao):
    priv, _ = chave_secao
    c = emitir(eleicao, "001", [99, BRANCO, 82], priv)
    assert _decodificar_qr(gerar_qr(c.texto(), escala=6, borda=4)) == c.texto()


def test_scanner_le_lote_de_cedulas_inclusive_giradas(eleicao, chave_secao):
    """40 cédulas distintas, escala de webcam, com rotação e desfoque: nenhuma pode falhar."""
    from urna3g.scanner import decodificar_array

    priv, _ = chave_secao
    falhas = 0
    for i in range(40):
        t = emitir(eleicao, "001", [99 if i % 2 else 67, 96, 80 if i % 3 else BRANCO], priv).texto()
        im = np.ascontiguousarray(np.array(gerar_qr(t, escala=5, borda=4))[:, :, ::-1])
        h, w = im.shape[:2]
        m = cv2.getRotationMatrix2D((w / 2, h / 2), 7, 0.9)
        im = cv2.GaussianBlur(cv2.warpAffine(im, m, (w, h), borderValue=(255, 255, 255)), (3, 3), 0)
        falhas += decodificar_array(im) != [t]
    assert falhas == 0


def test_pdf_da_cedula(eleicao, chave_secao, tmp_path):
    priv, _ = chave_secao
    c = emitir(eleicao, "001", [99, 96, 80], priv)
    p = renderizar_cedula_pdf(c, eleicao, tmp_path / "cedula.pdf")
    dados = p.read_bytes()
    assert dados.startswith(b"%PDF") and len(dados) > 1500


def test_pdf_do_boletim(eleicao, chave_secao, chave_apuracao, tmp_path):
    priv, pub = chave_secao
    ap = Apuracao.abrir(eleicao, "001", pub, tmp_path / "ap.db")
    ap.processar(emitir(eleicao, "001", [99, 96, 80], priv).texto())
    b = ap.gerar_boletim(chave_apuracao[0])
    p = renderizar_boletim_pdf(b, tmp_path / "boletim.pdf")
    assert p.read_bytes().startswith(b"%PDF")
