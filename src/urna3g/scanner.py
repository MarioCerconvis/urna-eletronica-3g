"""Leitura de QR a partir de imagens (OpenCV, opcional). Leitores USB 'teclado' não precisam disto.

Usa ``cv2.QRCodeDetectorAruco`` (OpenCV ≥ 4.8) quando disponível: em testes com 40 cédulas limpas, o detector
clássico ``QRCodeDetector`` deixou de *detectar* 3 códigos, enquanto o baseado em ArUco leu todos, inclusive com
rotação de 7° e desfoque (condições de webcam). O clássico fica como segunda tentativa.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

try:
    import cv2
except ImportError as e:  # pragma: no cover
    raise ImportError("instale o extra: pip install 'urna3g[camera]'") from e

_DETECTORES: list[object] = []
if hasattr(cv2, "QRCodeDetectorAruco"):
    _DETECTORES.append(cv2.QRCodeDetectorAruco())
_DETECTORES.append(cv2.QRCodeDetector())


def decodificar_array(bgr: np.ndarray) -> list[str]:
    """Retorna os textos de todos os QR encontrados no quadro (BGR); lista vazia se nenhum."""
    for det in _DETECTORES:
        try:
            ok, textos, _, _ = det.detectAndDecodeMulti(bgr)
        except cv2.error:
            ok, textos = False, []
        if ok:
            achados = [t for t in textos if t]
            if achados:
                return achados
        try:
            texto, _, _ = det.detectAndDecode(bgr)
        except cv2.error:
            texto = ""
        if texto:
            return [texto]
    return []


def decodificar_pil(img: Image.Image) -> list[str]:
    arr = np.array(img.convert("RGB"))[:, :, ::-1]
    return decodificar_array(np.ascontiguousarray(arr))


def decodificar_imagem(caminho: Path | str) -> list[str]:
    img = cv2.imread(str(caminho))
    if img is None:
        raise ValueError(f"não foi possível abrir a imagem {caminho}")
    return decodificar_array(img)
