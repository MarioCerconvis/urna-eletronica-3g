"""E5 — Distribuição do intervalo entre blocos em operação normal (12/12 no ar), a partir do histórico da cadeia.

Usa os blocos 17815–19315 (até 22/11/2026 16:07, antes dos testes de falha), com os 12 validadores no
ar. Intervalos acima de 60 s são desligamentos do cluster (houve um, de 8,2 dias) e são contados à parte.

"""

from __future__ import annotations

import os
import sys
from collections import Counter

os.environ.setdefault("URNA3G_PORTA", "19400")
import cluster as C  # noqa: E402
from comum import gravar, resumo  # noqa: E402

DE, ATE = (int(sys.argv[1]), int(sys.argv[2])) if len(sys.argv) > 2 else (17815, 19315)


def main() -> None:
    with C.Tunel():
        ts = C.timestamps(DE, ATE)
    todos = [b - a for a, b in zip(ts, ts[1:], strict=False)]
    lacunas = [x for x in todos if x > 60]
    inter = [x for x in todos if x <= 60]
    cont = Counter(inter)
    r = {"blocos": f"{DE}..{ATE}", "intervalos": len(inter), "lacunas_acima_60s": len(lacunas), "intervalo_s": resumo(inter, 3),
         "distribuicao_s": {str(k): v for k, v in sorted(cont.items())},
         "fracao_exatamente_2s": round(cont.get(2, 0) / len(inter), 4),
         "periodo_s": ts[-1] - ts[0] - sum(lacunas), "blocos_por_min": round(len(inter) * 60 / (ts[-1] - ts[0] - sum(lacunas)), 2)}
    print(r)
    print("->", gravar("e5-intervalo-blocos", {"metodo": f"timestamps (resolução 1 s) dos blocos {DE}–{ATE}: 12/12 no ar, antes dos testes de falha; uma lacuna de desligamento do cluster (> 60 s) excluída e contada à parte",
                                                "resultados": r}))


if __name__ == "__main__":
    main()
