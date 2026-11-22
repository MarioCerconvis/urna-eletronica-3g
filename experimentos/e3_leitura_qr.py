"""E3 — Robustez da leitura óptica do QR: 1 000 cédulas distintas × 6 condições × 2 detectores do OpenCV.

n = 1 000 por condição dá intervalo de confiança de Wilson (95%) com meia-largura ≤ 3,1 p.p. no pior caso
(taxa 50%) e ≤ 0,6 p.p. para taxas acima de 99%.
"""

from __future__ import annotations

import random
import time

import cv2
import numpy as np
from comum import RAIZ, gravar, resumo, wilson

from urna3g import BRANCO, NULO, crypto
from urna3g.ballot import emitir
from urna3g.manifest import Eleicao
from urna3g.qr import gerar_qr

N = 1000
rng = random.Random(2026)
np_rng = np.random.default_rng(2026)


def bgr(img) -> np.ndarray:  # noqa: ANN001
    return np.ascontiguousarray(np.array(img.convert("RGB"))[:, :, ::-1])


def rotacionar(im: np.ndarray, graus: float, escala: float = 1.0) -> np.ndarray:
    h, w = im.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), graus, escala)
    return cv2.warpAffine(im, m, (w, h), borderValue=(255, 255, 255))


def jpeg(im: np.ndarray, q: int) -> np.ndarray:
    ok, buf = cv2.imencode(".jpg", im, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(buf, cv2.IMREAD_COLOR)


def ruido(im: np.ndarray, sigma: float) -> np.ndarray:
    return np.clip(im.astype(np.float32) + np_rng.normal(0, sigma, im.shape), 0, 255).astype(np.uint8)


def webcam(im: np.ndarray) -> np.ndarray:
    """QR ocupando ~190 px num quadro 640×480 cinza, ruído de sensor e JPEG q=70 (webcam barata)."""
    q = cv2.resize(im, (190, 190), interpolation=cv2.INTER_AREA)
    quadro = np.full((480, 640, 3), 170, np.uint8)
    y, x = rng.randint(40, 250), rng.randint(40, 410)
    quadro[y:y + 190, x:x + 190] = q
    return jpeg(ruido(quadro, 8), 70)


def perspectiva(im: np.ndarray) -> np.ndarray:
    """Perspectiva leve + rotação de até ±25°. Acrescenta margem branca antes, para a rotação não cortar o QR
    (uma primeira execução sem margem cortou os cantos a partir de ~15° e foi descartada)."""
    m = int(0.3 * im.shape[1])
    im = cv2.copyMakeBorder(im, m, m, m, m, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    h, w = im.shape[:2]
    d = 0.08 * (w - 2 * m)
    src = np.float32([[0, 0], [w, 0], [w, h], [0, h]])
    dst = np.float32([[rng.uniform(0, d), rng.uniform(0, d)], [w - rng.uniform(0, d), rng.uniform(0, d)],
                      [w - rng.uniform(0, d), h - rng.uniform(0, d)], [rng.uniform(0, d), h - rng.uniform(0, d)]])
    return rotacionar(cv2.warpPerspective(im, cv2.getPerspectiveTransform(src, dst), (w, h),
                                          borderValue=(255, 255, 255)), rng.uniform(-25, 25))


def desbotado(im: np.ndarray) -> np.ndarray:
    """Impressão térmica desbotada: contraste reduzido a 35% em torno do cinza claro + ruído."""
    f = 200 + (im.astype(np.float32) - 255) * 0.35
    return ruido(np.clip(f, 0, 255).astype(np.uint8), 6)


CONDICOES = {
    "limpo_4px_modulo": lambda t: bgr(gerar_qr(t, escala=4, borda=4)),
    "resolucao_minima_2px_modulo": lambda t: bgr(gerar_qr(t, escala=2, borda=4)),
    "rotacao_7graus_desfoque": lambda t: cv2.GaussianBlur(rotacionar(bgr(gerar_qr(t, escala=5, borda=4)), 7, 0.9),
                                                          (3, 3), 0),
    "perspectiva_e_rotacao_ate_25graus": lambda t: perspectiva(bgr(gerar_qr(t, escala=5, borda=4))),
    "webcam_640x480_ruido_jpeg70": lambda t: webcam(bgr(gerar_qr(t, escala=5, borda=4))),
    "termica_desbotada_35pct_contraste": lambda t: desbotado(bgr(gerar_qr(t, escala=4, borda=4))),
}
DETECTORES = {"QRCodeDetector": cv2.QRCodeDetector(), "QRCodeDetectorAruco": cv2.QRCodeDetectorAruco()}


def main() -> None:
    e = Eleicao.carregar(RAIZ / "exemplos" / "eleicao-demo" / "eleicao.json")
    k = crypto.gerar_chave()
    opcoes = {s.cargo_id: [c.numero for c in e.candidatos_do_cargo(s.cargo_id)] + [BRANCO, NULO] for s in e.slots()}
    textos = [emitir(e, "001", [rng.choice(opcoes[s.cargo_id]) for s in e.slots()], k).texto() for _ in range(N)]
    res = {}
    for cond, gerar in CONDICOES.items():
        imagens = [gerar(t) for t in textos]
        res[cond] = {}
        for nome, det in DETECTORES.items():
            acertos, tempos = 0, []
            for t, im in zip(textos, imagens, strict=True):
                a = time.perf_counter()
                try:
                    lido, _, _ = det.detectAndDecode(im)
                except cv2.error:
                    lido = ""
                tempos.append((time.perf_counter() - a) * 1000)
                acertos += lido == t
            res[cond][nome] = {"acertos": acertos, "n": N, **wilson(acertos, N), "tempo_ms": resumo(tempos, 2)}
            print(f"{cond:38s} {nome:20s} {acertos}/{N}  IC95 {res[cond][nome]['ic95']}  {res[cond][nome]['tempo_ms']['mediana']} ms")
        cv2.imwrite(str(RAIZ / "resultados" / f"e3-exemplo-{cond}.png"), imagens[0])
    print("->", gravar("e3-leitura-qr", {"metodo": f"{N} cédulas distintas (3 cargos, votos sorteados), mesmas cédulas em todas as condições; sucesso = texto decodificado idêntico; IC de Wilson 95%; semente 2026",
                                          "condicoes": list(CONDICOES), "resultados": res}))


if __name__ == "__main__":
    main()
