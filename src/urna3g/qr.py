"""Geração de códigos QR (PIL)."""

from __future__ import annotations

import qrcode
from PIL import Image
from qrcode.constants import ERROR_CORRECT_M


def gerar_qr(texto: str, escala: int = 4, borda: int = 2) -> Image.Image:
    """Retorna a imagem RGB do QR. Correção 'M' tolera manchas de impressão térmica."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M, box_size=escala, border=borda)
    qr.add_data(texto)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


def versao_qr(texto: str) -> int:
    """Versão (1..40) necessária — útil para garantir legibilidade por webcams."""
    qr = qrcode.QRCode(error_correction=ERROR_CORRECT_M)
    qr.add_data(texto)
    qr.make(fit=True)
    return int(qr.version)
