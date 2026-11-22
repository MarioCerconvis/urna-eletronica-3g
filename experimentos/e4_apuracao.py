"""E4 — Custo computacional da apuração: tempo por cédula (ledger SQLite com fsync), verificação da cadeia e boletim.

Dois meios de armazenamento:
* HD mecânico (WD10SPZX, 5 400 rpm — típico de máquinas antigas): fsync real a cada cédula; 10 seções de 400.
* RAM (tmpfs /dev/shm): fsync sem custo — isola o custo de CPU; 10 seções de 400 e 3 de 5 000 (escala).
Mede só o computador; a leitura humana da cédula (≈ 15 s em 2016) não entra.
"""

from __future__ import annotations

import random
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from comum import RAIZ, gravar, resumo

from urna3g import BRANCO, NULO, crypto
from urna3g.ballot import emitir
from urna3g.manifest import Eleicao
from urna3g.tally import Apuracao

rng = random.Random(7)


def secao(e: Eleicao, n: int, dir_: Path, idx: int) -> dict:
    k, kap = crypto.gerar_chave(), crypto.gerar_chave()
    opcoes = {s.cargo_id: [c.numero for c in e.candidatos_do_cargo(s.cargo_id)] + [BRANCO, NULO] for s in e.slots()}
    textos = [emitir(e, "001", [rng.choice(opcoes[s.cargo_id]) for s in e.slots()], k).texto() for _ in range(n)]
    ap = Apuracao.abrir(e, "001", k.public_key(), dir_ / f"s{idx}.db")
    tempos = []
    for t in textos:
        a = time.perf_counter()
        r = ap.processar(t)
        tempos.append((time.perf_counter() - a) * 1000)
        assert r.aceita
    a = time.perf_counter()
    ap.ledger.verificar()
    t_verif = (time.perf_counter() - a) * 1000
    a = time.perf_counter()
    b = ap.gerar_boletim(kap)
    t_bol = (time.perf_counter() - a) * 1000
    assert b["total_cedulas"] == n
    ap.ledger.fechar()
    return {"tempos_ms": tempos, "verificar_ledger_ms": t_verif, "gerar_boletim_ms": t_bol,
            "tamanho_db_kb": round((dir_ / f"s{idx}.db").stat().st_size / 1024, 1)}


def main() -> None:
    e = Eleicao.carregar(RAIZ / "exemplos" / "eleicao-demo" / "eleicao.json")
    plano = [("hd_mecanico", Path.home(), ((400, 10),)), ("ram_tmpfs", Path("/dev/shm"), ((400, 10), (5000, 3)))]
    saida = {}
    for meio, base, tamanhos in plano:
        dir_ = Path(tempfile.mkdtemp(prefix="e4-", dir=str(base)))
        disco = subprocess.run(["findmnt", "-no", "SOURCE,FSTYPE", "-T", str(dir_)], capture_output=True, text=True).stdout.strip()
        saida[meio] = {"montagem": disco}
        try:
            for n, reps in tamanhos:
                todas, verif, bol, tam = [], [], [], []
                for i in range(reps):
                    r = secao(e, n, dir_, i + n)
                    todas += r["tempos_ms"]
                    verif.append(r["verificar_ledger_ms"])
                    bol.append(r["gerar_boletim_ms"])
                    tam.append(r["tamanho_db_kb"])
                saida[meio][f"secoes_de_{n}"] = {
                    "repeticoes": reps, "cedulas_medidas": len(todas), "processar_cedula_ms": resumo(todas, 3),
                    "verificar_ledger_ms": resumo(verif, 1), "gerar_boletim_ms": resumo(bol, 1),
                    "tamanho_ledger_kb": resumo(tam, 1), "tempo_computacional_por_secao_s": round(sum(todas) / reps / 1000, 2)}
                s_ = saida[meio][f"secoes_de_{n}"]
                print(f"{meio} {n} cédulas × {reps}: {s_['processar_cedula_ms']['media']} ms/cédula (p95 {s_['processar_cedula_ms']['p95']}), "
                      f"verificar {s_['verificar_ledger_ms']['media']} ms, boletim {s_['gerar_boletim_ms']['media']} ms, "
                      f"{s_['tempo_computacional_por_secao_s']} s/seção", flush=True)
        finally:
            shutil.rmtree(dir_, ignore_errors=True)
        gravar("e4-apuracao", {"parcial": True, "resultados": saida})
    print("->", gravar("e4-apuracao", {"metodo": "ledger com synchronous=FULL (fsync por cédula); emissão das cédulas fora da medição; HD mecânico vs RAM",
                                        "resultados": saida}))


if __name__ == "__main__":
    main()
