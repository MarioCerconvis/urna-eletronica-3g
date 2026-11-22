"""Lote de ensaios sem interface: roda N eleições-ensaio em sequência e grava um relatório (JSON + Markdown).

Reaproveita exatamente o coletor e o ensaio do painel. Ao fim de cada ensaio, confere na blockchain (por um nó
diferente do coordenador) se cada boletim registrado tem o mesmo hash do boletim assinado localmente.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from urna3g.painel.coletor import Painel
from urna3g.painel.config import PainelCfg
from urna3g.painel.ensaio import Ensaio


async def _esperar(cond, timeout: float, passo: float = 1.0) -> bool:  # noqa: ANN001
    fim = time.time() + timeout
    while time.time() < fim:
        if cond():
            return True
        await asyncio.sleep(passo)
    return cond()


def _conferir_na_cadeia(p: Painel, eleicao_id: str, secoes: dict[str, Any]) -> dict[str, Any]:
    from web3 import Web3

    vivos = [n for n in p.nos.values() if n.estado == "no_ar"]
    if not vivos:
        return {"erro": "nenhum nó no ar"}
    no = vivos[-1]
    w3 = Web3(Web3.HTTPProvider(p.cfg_por_id[no.id].rpc, request_kwargs={"timeout": 15}))
    art = json.loads(p.cfg.artefato.read_text())
    c = w3.eth.contract(address=w3.to_checksum_address(p.contrato), abi=art["abi"])
    eid = bytes.fromhex(eleicao_id)
    _, existe, encerrada, mural, n_secoes = c.functions.eleicao(eid).call()
    por_secao = {}
    for sec, s in secoes.items():
        hb, hl, total, bloco, quem = c.functions.boletim(eid, sec).call()
        por_secao[sec] = {
            "hash_cadeia": hb.hex(), "cedulas_cadeia": total, "bloco_cadeia": bloco,
            "confere": bool(s.get("hash_boletim")) and hb.hex() == s.get("hash_boletim"),
        }
    return {"lido_no": no.rotulo, "existe": existe, "encerrada": encerrada, "secoes_na_cadeia": n_secoes,
            "hash_mural": mural.hex(), "por_secao": por_secao}


def _resumo_execucao(i: int, p: Painel, t0: float, t1: float, ev_ini: int, altura0: int, vivos0: int,
                     conf: dict[str, Any]) -> dict[str, Any]:
    el = p.eleicao
    eventos = [ev for ev in p.eventos if ev["seq"] > ev_ini]
    textos = [ev["texto"] for ev in eventos]
    secoes = []
    for sec, s in sorted(el.get("secoes", {}).items()):
        tempos = s.get("tempos", {})
        cs = conf.get("por_secao", {}).get(sec, {})
        secoes.append({
            "secao": sec,
            "maquina": p.nos[s["no"]].rotulo if s.get("no") in p.nos else s.get("no"),
            "fase": s.get("fase"),
            "cedulas_emitidas": s.get("cedulas", 0),
            "cedulas_no_boletim": s.get("total"),
            "duplicadas_rejeitadas": s.get("duplicadas", 0),
            "invalidas_rejeitadas": s.get("invalidas", 0),
            "bloco": s.get("bloco"),
            "hash_boletim": s.get("hash_boletim"),
            "confere_na_cadeia": cs.get("confere"),
            "t_votacao_s": round(tempos["encerrada"] - tempos["votando"], 1) if {"votando", "encerrada"} <= tempos.keys() else None,
            "t_apuracao_s": round(tempos["boletim"] - tempos["apurando"], 1) if {"apurando", "boletim"} <= tempos.keys() else None,
            "t_boletim_ate_ancorado_s": round(tempos["ancorado"] - tempos["boletim"], 1) if {"boletim", "ancorado"} <= tempos.keys() else None,
            "t_ancorado_desde_inicio_s": round(tempos["ancorado"] - t0, 1) if "ancorado" in tempos else None,
        })
    n_sec = len(secoes)
    ancoradas = sum(1 for s in secoes if s["fase"] == "ancorado")
    conferem = sum(1 for s in secoes if s["confere_na_cadeia"])
    falhou = any(t.startswith("Ensaio falhou") for t in textos) or any(": falhou" in t for t in textos)
    t_anc = [s["t_ancorado_desde_inicio_s"] for s in secoes if s["t_ancorado_desde_inicio_s"] is not None]
    return {
        "execucao": i,
        "eleicao_id": el.get("id") or el.get("id_pendente"),
        "nome": el.get("nome"),
        "inicio": datetime.fromtimestamp(t0).isoformat(timespec="seconds"),
        "duracao_total_s": round(t1 - t0, 1),
        "sucesso": (not falhou) and ancoradas == n_sec and conferem == n_sec and bool(el.get("encerrada")),
        "nos_no_ar_inicio": vivos0,
        "nos_no_ar_fim": p.vivos(),
        "altura_inicio": altura0,
        "bloco_criacao": el.get("bloco_criacao"),
        "bloco_encerramento": el.get("bloco_encerramento"),
        "secoes_total": n_sec,
        "secoes_ancoradas": ancoradas,
        "boletins_conferem_na_cadeia": conferem,
        "cedulas_total": sum(s["cedulas_emitidas"] for s in secoes),
        "duplicadas_rejeitadas": sum(s["duplicadas_rejeitadas"] for s in secoes),
        "invalidas_rejeitadas": sum(s["invalidas_rejeitadas"] for s in secoes),
        "t_primeira_ancoragem_s": min(t_anc) if t_anc else None,
        "t_ultima_ancoragem_s": max(t_anc) if t_anc else None,
        "eventos_rede": {
            "nos_sairam_do_ar": sum("saiu do ar" in t for t in textos),
            "quorum_perdido": sum(t.startswith("Quórum perdido") for t in textos),
            "pausas_sem_bloco": sum(t.startswith("Nenhum bloco novo") for t in textos),
            "ancoragens_reenviadas": sum("ancoragem falhou" in t for t in textos),
        },
        "erros": [t for t in textos if "falhou" in t],
        "resultados": el.get("resultados", {}),
        "legenda": el.get("legenda", {}),
        "conferencia_cadeia": {k: v for k, v in conf.items() if k != "por_secao"},
        "secoes": secoes,
    }


def _stats(valores: list[float]) -> dict[str, float | None]:
    v = [x for x in valores if x is not None]
    if not v:
        return {"media": None, "min": None, "max": None, "desvio": None}
    return {"media": round(statistics.mean(v), 1), "min": round(min(v), 1), "max": round(max(v), 1),
            "desvio": round(statistics.stdev(v), 1) if len(v) > 1 else 0.0}


def _markdown(meta: dict[str, Any], execs: list[dict[str, Any]], agreg: dict[str, Any]) -> str:
    L = [f"# Resultado de {meta['execucoes_concluidas']} ensaios de eleição — {meta['rede']}", "",
         f"Gerado em {meta['gerado_em']} por `urna3g ensaio-lote`.", "",
         "## Configuração", "",
         "| Parâmetro | Valor |", "|---|---|",
         f"| Rede | {meta['rede']} ({meta['nos']} validadores Besu/QBFT) |",
         f"| Execuções pedidas / concluídas | {meta['execucoes_pedidas']} / {meta['execucoes_concluidas']} |",
         f"| Eleitores por seção (alvo) | {meta['eleitores_por_secao']} (o ensaio sorteia entre 75% e 115%) |",
         f"| Duração da votação | {meta['duracao_votacao_s']:g} s |",
         f"| Contrato | `{meta['contrato']}` |", "",
         "Eleitores simulados; assinaturas, apuração, rejeição de cédulas e transações na blockchain são reais. "
         "Em cada execução, a seção K tem seu boletim ancorado pelo nó K (conta do validador K) e conferido depois "
         "lendo o contrato por outro nó.", "",
         "## Resumo", "",
         "| Indicador | Valor |", "|---|---|",
         f"| Execuções com sucesso | {agreg['sucessos']} de {len(execs)} |",
         f"| Seções ancoradas | {agreg['secoes_ancoradas']} de {agreg['secoes_total']} |",
         f"| Boletins que conferem com a blockchain | {agreg['boletins_conferem']} de {agreg['secoes_total']} |",
         f"| Cédulas apuradas (total) | {agreg['cedulas_total']} |",
         f"| Cédulas relidas rejeitadas | {agreg['duplicadas_total']} |",
         f"| Cédulas forjadas rejeitadas | {agreg['invalidas_total']} |",
         f"| Duração por execução (s) | média {agreg['duracao']['media']} · mín {agreg['duracao']['min']} · máx {agreg['duracao']['max']} · desvio {agreg['duracao']['desvio']} |",
         f"| Apuração por seção (s) | média {agreg['apuracao']['media']} · mín {agreg['apuracao']['min']} · máx {agreg['apuracao']['max']} |",
         f"| Do boletim assinado à ancoragem (s) | média {agreg['ancoragem']['media']} · mín {agreg['ancoragem']['min']} · máx {agreg['ancoragem']['max']} |",
         f"| Nós que saíram do ar / quórum perdido | {agreg['nos_sairam']} / {agreg['quorum_perdido']} |", "",
         "## Execuções", "",
         "| # | Início | Duração (s) | Cédulas | Relidas | Forjadas | Ancoradas | Conferem | Blocos (criação → encerramento) | Última ancoragem (s) | Resultado |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
    for e in execs:
        L.append(f"| {e['execucao']} | {e['inicio'][11:]} | {e['duracao_total_s']} | {e['cedulas_total']} | "
                 f"{e['duplicadas_rejeitadas']} | {e['invalidas_rejeitadas']} | {e['secoes_ancoradas']}/{e['secoes_total']} | "
                 f"{e['boletins_conferem_na_cadeia']}/{e['secoes_total']} | {e['bloco_criacao']} → {e['bloco_encerramento']} | "
                 f"{e['t_ultima_ancoragem_s']} | {'sucesso' if e['sucesso'] else 'FALHA'} |")
    L += ["", "## Votação simulada por execução", ""]
    for e in execs:
        partes = []
        for cid, r in e["resultados"].items():
            leg = e["legenda"].get(cid, {})
            votos = r["votos"]
            itens = [f"{leg.get(k, k).split(' (')[0]} {v}" for k, v in sorted(votos.items(), key=lambda kv: -kv[1])
                     if k not in ("branco", "nulo")]
            partes.append(f"{r['nome']}: {', '.join(itens)}, branco {votos.get('branco', 0)}, nulo {votos.get('nulo', 0)}")
        L.append(f"* **Execução {e['execucao']}** ({e['cedulas_total']} cédulas) — " + " · ".join(partes))
    L += ["", "## Detalhe por seção", ""]
    for e in execs:
        L += [f"### Execução {e['execucao']} — eleição `{(e['eleicao_id'] or '')[:16]}…`", "",
              "| Seção | Máquina | Cédulas | Relidas | Forjadas | Votação (s) | Apuração (s) | Até ancorar (s) | Bloco | Hash do boletim | Confere |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
        for s in e["secoes"]:
            L.append(f"| {s['secao']} | {s['maquina']} | {s['cedulas_emitidas']} | {s['duplicadas_rejeitadas']} | "
                     f"{s['invalidas_rejeitadas']} | {s['t_votacao_s']} | {s['t_apuracao_s']} | {s['t_boletim_ate_ancorado_s']} | "
                     f"{s['bloco']} | `{(s['hash_boletim'] or '')[:16]}…` | {'sim' if s['confere_na_cadeia'] else 'NÃO'} |")
        if e["erros"]:
            L += ["", "Erros: " + "; ".join(e["erros"])]
        L.append("")
    return "\n".join(L) + "\n"


def _agregar(execs: list[dict[str, Any]]) -> dict[str, Any]:
    secs = [s for e in execs for s in e["secoes"]]
    return {
        "sucessos": sum(e["sucesso"] for e in execs),
        "secoes_total": len(secs),
        "secoes_ancoradas": sum(s["fase"] == "ancorado" for s in secs),
        "boletins_conferem": sum(bool(s["confere_na_cadeia"]) for s in secs),
        "cedulas_total": sum(e["cedulas_total"] for e in execs),
        "duplicadas_total": sum(e["duplicadas_rejeitadas"] for e in execs),
        "invalidas_total": sum(e["invalidas_rejeitadas"] for e in execs),
        "duracao": _stats([e["duracao_total_s"] for e in execs]),
        "apuracao": _stats([s["t_apuracao_s"] for s in secs]),
        "ancoragem": _stats([s["t_boletim_ate_ancorado_s"] for s in secs]),
        "nos_sairam": sum(e["eventos_rede"]["nos_sairam_do_ar"] for e in execs),
        "quorum_perdido": sum(e["eventos_rede"]["quorum_perdido"] for e in execs),
    }


async def rodar_lote(cfg: PainelCfg, n: int, eleitores: int, duracao: float, saida: Path,
                     pausa: float = 10.0) -> dict[str, Any]:
    p = Painel(cfg)
    tarefas = await p.iniciar()
    saida.parent.mkdir(parents=True, exist_ok=True)
    meta: dict[str, Any] = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"), "rede": cfg.nome, "modo": cfg.modo,
        "nos": len(cfg.nos), "execucoes_pedidas": n, "execucoes_concluidas": 0,
        "eleitores_por_secao": eleitores, "duracao_votacao_s": duracao, "contrato": cfg.contrato,
    }
    execs: list[dict[str, Any]] = []
    try:
        ok = await _esperar(lambda: p.tunel_ativo and p.altura > 0 and p.vivos() >= p.quorum, 120)
        if not ok:
            raise RuntimeError(f"rede indisponível: {p.vivos()} de {len(p.nos)} nós no ar, quórum {p.quorum}")
        print(f"rede pronta: {p.vivos()}/{len(p.nos)} nós, bloco {p.altura}", flush=True)
        for i in range(1, n + 1):
            ev_ini, altura0, vivos0, t0 = p._seq, p.altura, p.vivos(), time.time()
            print(f"[{datetime.now():%H:%M:%S}] execução {i}/{n}…", flush=True)
            await Ensaio(p, eleitores, duracao).executar()
            el = p.eleicao
            await _esperar(lambda el=el: el.get("encerrada") and all(
                s.get("fase") == "ancorado" and s.get("hash") for s in el.get("secoes", {}).values()), 90)
            t1 = time.time()
            meta["contrato"] = p.contrato
            try:
                conf = await asyncio.to_thread(_conferir_na_cadeia, p, el.get("id") or el.get("id_pendente"),
                                               el.get("secoes", {}))
            except Exception as e:  # noqa: BLE001
                conf = {"erro": str(e)}
            r = _resumo_execucao(i, p, t0, t1, ev_ini, altura0, vivos0, conf)
            execs.append(r)
            meta["execucoes_concluidas"] = len(execs)
            agreg = _agregar(execs)
            dados = {"meta": meta, "agregado": agreg, "execucoes": execs}
            saida.with_suffix(".json").write_text(json.dumps(dados, indent=2, ensure_ascii=False, default=str))
            saida.with_suffix(".md").write_text(_markdown(meta, execs, agreg))
            print(f"   {'ok' if r['sucesso'] else 'FALHA'}: {r['cedulas_total']} cédulas, "
                  f"{r['secoes_ancoradas']}/{r['secoes_total']} ancoradas, {r['boletins_conferem_na_cadeia']} conferem, "
                  f"{r['duracao_total_s']} s", flush=True)
            if i < n:
                await asyncio.sleep(pausa)
    finally:
        for t in tarefas:
            t.cancel()
        await asyncio.gather(*tarefas, return_exceptions=True)  # deixa os subprocessos encerrarem antes do laço fechar
        if getattr(p, "tunel", None):
            p.tunel.encerrar()
        await p.http.aclose()
    return {"meta": meta, "agregado": _agregar(execs) if execs else {}, "execucoes": execs}
