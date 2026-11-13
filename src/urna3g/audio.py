"""Sons da urna (os mesmos WAV do protótipo), tocados sem bloquear a interface."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

ASSETS = Path(__file__).resolve().parent / "assets"
SONS = {"beep": ASSETS / "beep_urna.wav", "fim": ASSETS / "fim_urna.wav"}
_REPRODUTORES = (["paplay"], ["aplay", "-q"], ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet"])


def tocar(nome: str) -> bool:
    """Toca 'beep' (voto confirmado) ou 'fim' (cédula impressa / alerta). Silencioso se não houver áudio."""
    if os.environ.get("URNA3G_SEM_SOM"):
        return False
    arquivo = SONS[nome]
    for cmd in _REPRODUTORES:
        if shutil.which(cmd[0]):
            try:
                subprocess.Popen([*cmd, str(arquivo)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except OSError:
                continue
    return False
