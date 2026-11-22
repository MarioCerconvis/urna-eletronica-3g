"""E10 — Ensaio de eleição com falha transitória: 5 execuções; quando a apuração começa, 3 validadores sorteados
(de 12) param por 60 s e voltam. A rede mantém o quórum (9 ≥ 8), mas as seções desses 3 nós precisam esperar o
próprio nó para ancorar. Compara a latência de ancoragem das seções afetadas e não afetadas."""

from __future__ import annotations

import asyncio
import json
import random
import time

import cluster as C
from comum import RESULTADOS, gravar, resumo

from urna3g.painel.coletor import Painel
from urna3g.painel.config import carregar
from urna3g.painel.ensaio import Ensaio
from urna3g.painel.lote import _conferir_na_cadeia, _esperar, _resumo_execucao

REPS, ELEITORES, DURACAO, QUEDA_S, K_FORA = 5, 25, 30, 60, 3
rng = random.Random(1010)


async def falha(p: Painel, fora: list[str], registro: dict) -> None:
    await _esperar(lambda: any(s.get("fase") in ("apurando", "boletim") for s in p.eleicao.get("secoes", {}).values()), 300, 0.5)
    registro["parados_em"] = time.time()
    await asyncio.to_thread(C.parar, fora)
    await asyncio.sleep(QUEDA_S)
    await asyncio.to_thread(C.ligar, fora)
    registro["religados_em"] = time.time()


async def main_async() -> None:
    cfg = carregar(C.CFG_PATH, False)
    p = Painel(cfg)
    tarefas = await p.iniciar()
    am = C.Amostrador(RESULTADOS / "e12-recursos.jsonl")
    am.start()
    execs = []
    try:
        await _esperar(lambda: p.tunel_ativo and p.vivos() == len(p.nos) and p.altura > 0, 180)
        for rep in range(1, REPS + 1):
            am.rotulo = f"e10_r{rep}"
            fora = C.sorteio(rng, K_FORA)
            maq_fora = {C.ROT[i] for i in fora}
            reg: dict = {}
            ev_ini, altura0, vivos0, t0 = p._seq, p.altura, p.vivos(), time.time()
            await asyncio.gather(Ensaio(p, ELEITORES, DURACAO).executar(), falha(p, fora, reg))
            el = p.eleicao
            await _esperar(lambda el=el: el.get("encerrada") and all(s.get("fase") == "ancorado" and s.get("hash")
                                                                     for s in el.get("secoes", {}).values()), 300)
            t1 = time.time()
            conf = await asyncio.to_thread(_conferir_na_cadeia, p, el.get("id") or el.get("id_pendente"), el.get("secoes", {}))
            r = _resumo_execucao(rep, p, t0, t1, ev_ini, altura0, vivos0, conf)
            afet = [s["t_boletim_ate_ancorado_s"] for s in r["secoes"] if s["maquina"] in maq_fora]
            nafet = [s["t_boletim_ate_ancorado_s"] for s in r["secoes"] if s["maquina"] not in maq_fora]
            r.update({"maquinas_paradas": sorted(maq_fora), "queda_s": QUEDA_S,
                      "ancoragem_afetadas_s": afet, "ancoragem_nao_afetadas_s": nafet})
            execs.append(r)
            print(json.dumps({k: r[k] for k in ("execucao", "sucesso", "duracao_total_s", "secoes_ancoradas", "boletins_conferem_na_cadeia",
                                                "maquinas_paradas", "ancoragem_afetadas_s")}, ensure_ascii=False), flush=True)
            gravar("e10-ensaio-com-falhas", {"parcial": True, "execucoes": execs})
            await asyncio.to_thread(C.esperar_saudavel)
            await asyncio.sleep(10)
    finally:
        am.parar()
        for t in tarefas:
            t.cancel()
        if getattr(p, "tunel", None):
            p.tunel.encerrar()
        await p.http.aclose()
    afet = [x for e in execs for x in e["ancoragem_afetadas_s"] if x is not None]
    nafet = [x for e in execs for x in e["ancoragem_nao_afetadas_s"] if x is not None]
    print("->", gravar("e10-ensaio-com-falhas", {
        "metodo": f"{REPS} ensaios ({ELEITORES} eleitores/seção, votação {DURACAO} s); ao iniciar a apuração, {K_FORA} validadores sorteados param por {QUEDA_S} s (semente 1010)",
        "sucessos": sum(e["sucesso"] for e in execs), "ancoragem_secoes_afetadas_s": resumo(afet, 1),
        "ancoragem_secoes_nao_afetadas_s": resumo(nafet, 1), "duracao_total_s": resumo([e["duracao_total_s"] for e in execs], 1),
        "execucoes": execs}))


if __name__ == "__main__":
    with C.Tunel():
        asyncio.run(main_async())
