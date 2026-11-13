"""Impressão: cédula (62×100 mm, como a Brother QL-700 do protótipo) e boletim de urna em PDF."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from urna3g import boletim as boletim_mod
from urna3g.ballot import Cedula, descrever
from urna3g.manifest import Eleicao
from urna3g.qr import gerar_qr

LARGURA = 62 * mm
ALTURA_CEDULA = 100 * mm
MARGEM = 3 * mm


class ErroImpressao(RuntimeError):
    pass


def _cortar(texto: str, maximo: int) -> str:
    return texto if len(texto) <= maximo else texto[: maximo - 1] + "…"


def renderizar_cedula_pdf(cedula: Cedula, eleicao: Eleicao, caminho: Path | str) -> Path:
    """Registro legível em cima, linha 'dobre aqui', QR embaixo (figura 1 do artigo de 2017)."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(caminho), pagesize=(LARGURA, ALTURA_CEDULA))
    c.setTitle("Cédula")
    y = ALTURA_CEDULA - 6 * mm
    c.setFont("Helvetica-Bold", 8)
    c.drawString(MARGEM, y, _cortar(eleicao.nome, 38))
    y -= 3.6 * mm
    c.setFont("Helvetica", 6)
    c.drawString(MARGEM, y, f"Secao {cedula.secao}   eleicao {eleicao.id[:16]}")
    y -= 5 * mm

    linhas = descrever(cedula, eleicao)
    y_dobra = 52 * mm
    disponivel = y - y_dobra - 2 * mm
    passo = min(8.5 * mm, disponivel / max(1, len(linhas)))
    tam = 8 if passo >= 7 * mm else max(5, int(passo / mm * 1.05))
    for titulo, desc in linhas:
        c.setFont("Helvetica-Bold", tam)
        c.drawString(MARGEM, y, _cortar(titulo + ":", 40))
        y -= passo * 0.45
        c.setFont("Helvetica", tam)
        c.drawString(MARGEM + 2 * mm, y, _cortar(desc, 36))
        y -= passo * 0.55

    c.setFont("Helvetica", 7)
    c.drawCentredString(LARGURA / 2, y_dobra - 2 * mm, "_ _ _ _ _ _ Dobre aqui _ _ _ _ _ _")

    lado = 45 * mm
    img = gerar_qr(cedula.texto(), escala=4, borda=1)
    c.drawImage(ImageReader(img), (LARGURA - lado) / 2, 3.5 * mm, lado, lado)
    c.setFont("Helvetica", 5)
    c.drawCentredString(LARGURA / 2, 1.5 * mm, f"id {cedula.nonce_hex[:16]}")
    c.showPage()
    c.save()
    return caminho


def renderizar_boletim_pdf(boletim: dict[str, Any], caminho: Path | str) -> Path:
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    linhas: list[tuple[str, str]] = []
    for cargo in boletim["resultados"].values():
        linhas.append(("H", cargo["nome"]))
        for chave, n in cargo["votos"].items():
            if chave == "branco":
                desc = "Branco"
            elif chave == "nulo":
                desc = "Nulo"
            else:
                desc = f"{chave} - {cargo['legenda'].get(chave, '')}"
            linhas.append(("L", f"{_cortar(desc, 28):<30}{n:>5}"))
    altura_texto = 32 * mm + len(linhas) * 3.6 * mm + 12 * mm + len(boletim.get("observacoes", [])) * 3.2 * mm
    altura = max(100 * mm, altura_texto + 40 * mm)
    c = canvas.Canvas(str(caminho), pagesize=(LARGURA, altura))
    c.setTitle("Boletim de urna")
    y = altura - 6 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(LARGURA / 2, y, "BOLETIM DE URNA")
    y -= 4 * mm
    c.setFont("Helvetica", 6.5)
    for txt in (
        _cortar(boletim["eleicao_nome"], 40),
        f"Secao {boletim['secao']}   emitido {boletim['emitido_em']}",
        f"Eleicao {boletim['eleicao_id'][:32]}",
        f"Cedulas apuradas: {boletim['total_cedulas']}",
    ):
        c.drawString(MARGEM, y, txt)
        y -= 3.2 * mm
    y -= 2 * mm
    for tipo, txt in linhas:
        if tipo == "H":
            y -= 1 * mm
            c.setFont("Helvetica-Bold", 7.5)
            c.drawString(MARGEM, y, _cortar(txt, 36))
        else:
            c.setFont("Courier", 7)
            c.drawString(MARGEM, y, txt)
        y -= 3.6 * mm
    y -= 2 * mm
    c.setFont("Helvetica", 5.5)
    for obs in boletim.get("observacoes", []):
        c.drawString(MARGEM, y, _cortar("* " + obs, 60))
        y -= 3.2 * mm
    c.drawString(MARGEM, y, "Hash do ledger:")
    y -= 2.8 * mm
    c.setFont("Courier", 5)
    hf = boletim["ledger"]["hash_final"]
    c.drawString(MARGEM, y, hf[:32])
    y -= 2.4 * mm
    c.drawString(MARGEM, y, hf[32:])
    y -= 3 * mm
    c.setFont("Helvetica", 5.5)
    c.drawString(MARGEM, y, "Hash do boletim:")
    y -= 2.8 * mm
    c.setFont("Courier", 5)
    hb = boletim_mod.hash_boletim(boletim)
    c.drawString(MARGEM, y, hb[:32])
    y -= 2.4 * mm
    c.drawString(MARGEM, y, hb[32:])
    lado = 28 * mm
    img = gerar_qr(boletim_mod.texto_qr(boletim), escala=3, borda=1)
    c.drawImage(ImageReader(img), (LARGURA - lado) / 2, 4 * mm, lado, lado)
    c.showPage()
    c.save()
    return caminho


def imprimir(caminho: Path | str, impressora: str | None = None, copias: int = 1) -> None:
    """Envia ao CUPS via ``lp`` (sem shell; argumentos como lista, ao contrário do original)."""
    if shutil.which("lp") is None:
        raise ErroImpressao("comando 'lp' (CUPS) não encontrado")
    cmd = ["lp", "-n", str(int(copias))]
    if impressora:
        cmd += ["-d", impressora]
    cmd.append(str(caminho))
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
    except subprocess.CalledProcessError as e:
        raise ErroImpressao(e.stderr.decode(errors="replace").strip() or "falha ao imprimir") from e
    except subprocess.TimeoutExpired as e:
        raise ErroImpressao("tempo esgotado ao enviar para a impressora") from e
