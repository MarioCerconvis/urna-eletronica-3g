"""Utilidades compartilhadas pelos experimentos: estatística, Wilson, gravação de resultados, metadados."""

from __future__ import annotations

import json
import math
import platform
import statistics
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
RESULTADOS = RAIZ / "resultados"


def resumo(valores: list[float], casas: int = 4) -> dict[str, Any]:
    v = sorted(x for x in valores if x is not None)
    if not v:
        return {"n": 0}

    def pct(p: float) -> float:
        k = (len(v) - 1) * p
        f, c = math.floor(k), math.ceil(k)
        return v[f] + (v[c] - v[f]) * (k - f)

    return {"n": len(v), "media": round(statistics.mean(v), casas), "mediana": round(pct(0.5), casas),
            "desvio": round(statistics.stdev(v), casas) if len(v) > 1 else 0.0, "min": round(v[0], casas),
            "p95": round(pct(0.95), casas), "p99": round(pct(0.99), casas), "max": round(v[-1], casas),
            "ic95_media": [round(statistics.mean(v) - 1.96 * statistics.stdev(v) / math.sqrt(len(v)), casas),
                           round(statistics.mean(v) + 1.96 * statistics.stdev(v) / math.sqrt(len(v)), casas)]
            if len(v) > 1 else None}


def wilson(acertos: int, n: int, z: float = 1.96) -> dict[str, float]:
    if n == 0:
        return {"taxa": 0.0, "ic95": [0.0, 0.0]}
    p = acertos / n
    den = 1 + z * z / n
    centro = (p + z * z / (2 * n)) / den
    meia = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return {"taxa": round(p, 4), "ic95": [round(max(0.0, centro - meia), 4), round(min(1.0, centro + meia), 4)]}


def ambiente() -> dict[str, Any]:
    cpu = next((ln.split(":", 1)[1].strip() for ln in open("/proc/cpuinfo") if ln.startswith("model name")), "?")
    try:
        commit = subprocess.run(["git", "-C", str(RAIZ), "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True, check=False).stdout.strip()
    except OSError:
        commit = "?"
    return {"cpu": cpu, "python": platform.python_version(), "so": platform.platform(), "commit": commit}


def gravar(nome: str, dados: dict[str, Any]) -> Path:
    RESULTADOS.mkdir(exist_ok=True)
    caminho = RESULTADOS / f"{nome}.json"
    dados = {"experimento": nome, "gerado_em": datetime.now().isoformat(timespec="seconds"), "ambiente": ambiente(),
             **dados}
    caminho.write_text(json.dumps(dados, indent=2, ensure_ascii=False, default=str))
    return caminho
