"""Consolida resultados/*.json num relatório único: resultados/RELATORIO-EXPERIMENTOS.md."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict

from comum import RESULTADOS, resumo


def _ips() -> list[str]:
    import os
    from pathlib import Path

    cfg = Path(os.environ.get("URNA3G_PAINEL_CFG", Path.home() / "Desktop/UFABC/cluster-rede-12/painel.json"))
    return json.loads(cfg.read_text())["ips"] if cfg.is_file() else []


def carregar(nome: str) -> dict | None:
    p = RESULTADOS / f"{nome}.json"
    return json.loads(p.read_text()) if p.is_file() else None


def f(x, casas: int = 2) -> str:  # noqa: ANN001
    if x is None:
        return "—"
    if isinstance(x, float):
        return f"{x:.{casas}f}".replace(".", ",")
    return str(x)


def ms(r: dict, casas: int = 3) -> str:
    return f"{f(r['media'], casas)} ± {f(r['desvio'], casas)} (p95 {f(r['p95'], casas)})"


def secao_e1(L: list[str]) -> None:
    d = carregar("e1-tamanho-cedula")
    if not d:
        return
    L += ["## E1 — Tamanho da cédula e do QR", "", d["metodo"], "",
          "| Votos por cédula | Bytes (seção de 3 B) | Caracteres no QR | Versão do QR (M) | Bytes (seção de 16 B) | Versão (M) |",
          "|---|---|---|---|---|---|"]
    linhas = defaultdict(dict)
    for ln in d["nova_versao"]:
        linhas[ln["votos"]][ln["secao_bytes"]] = ln
    for v, por in sorted(linhas.items()):
        a, b = por[3], por[16]
        L.append(f"| {v} | {a['bytes_binarios']} | {a['caracteres_qr']} | {a['versao_qr_M']} ({a['modulos_lado']}×{a['modulos_lado']}) | "
                 f"{b['bytes_binarios']} | {b['versao_qr_M']} |")
    p = d["prototipo_2016"]
    L += ["", f"Protótipo de 2016 (RSA-1024-OAEP em base64): {p['bytes_cifrados']} bytes cifrados, {p['caracteres_qr']} caracteres, "
          f"QR versão {p['versao_qr_L']} com correção L (versão {p['versao_qr_M']} se fosse M). A cédula nova com 3 votos ocupa a "
          "mesma versão 8, mas com correção M (≈15% de recuperação, contra ≈7% da L) e com autenticidade.", ""]


def secao_e2(L: list[str]) -> None:
    d = carregar("e2-desempenho-cripto")
    if not d:
        return
    nomes = {"ed25519_assinar_106B": "Ed25519 — assinar (106 B)", "ed25519_verificar_106B": "Ed25519 — verificar",
             "emitir_cedula_completa": "Emitir cédula completa (montar + assinar)",
             "ler_cedula_decodificar_e_verificar": "Ler cédula (decodificar + verificar)",
             "prototipo_rsa1024_oaep_cifrar": "Protótipo: RSA-1024 OAEP cifrar", "prototipo_rsa1024_oaep_decifrar": "Protótipo: RSA-1024 OAEP decifrar",
             "referencia_rsa2048_pss_assinar": "Referência: RSA-2048 PSS assinar", "referencia_rsa2048_pss_verificar": "Referência: RSA-2048 PSS verificar"}
    L += ["## E2 — Desempenho criptográfico", "", f"{d['metodo']}; {d['ambiente']['cpu']}.", "",
          "| Operação | Média ± desvio (ms) | Mediana | p99 | Operações/s |", "|---|---|---|---|---|"]
    for k, r in d["operacoes"].items():
        L.append(f"| {nomes.get(k, k)} | {f(r['media'], 4)} ± {f(r['desvio'], 4)} | {f(r['mediana'], 4)} | {f(r['p99'], 4)} | {f(r['ops_por_s'], 0)} |")
    L.append("")


def secao_e3(L: list[str]) -> None:
    d = carregar("e3-leitura-qr")
    if not d:
        return
    L += ["## E3 — Leitura óptica do QR", "", d["metodo"], "",
          "| Condição | QRCodeDetector (IC 95%) | QRCodeDetectorAruco (IC 95%) | Tempo mediano Aruco (ms) |", "|---|---|---|---|"]
    for cond, r in d["resultados"].items():
        a, b = r["QRCodeDetector"], r["QRCodeDetectorAruco"]
        L.append(f"| {cond.replace('_', ' ')} | {a['acertos']}/{a['n']} ({f(a['ic95'][0]*100,1)}–{f(a['ic95'][1]*100,1)}%) | "
                 f"{b['acertos']}/{b['n']} ({f(b['ic95'][0]*100,1)}–{f(b['ic95'][1]*100,1)}%) | {f(b['tempo_ms']['mediana'],1)} |")
    L += ["", "Exemplos de cada condição: `resultados/e3-exemplo-*.png`.", ""]


def secao_e4(L: list[str]) -> None:
    d = carregar("e4-apuracao")
    if not d:
        return
    L += ["## E4 — Custo computacional da apuração", "", d.get("metodo", ""), "",
          "| Meio | Seção | Repetições | Processar 1 cédula (ms, média ± desvio, p95) | Verificar ledger (ms) | Gerar boletim (ms) | Tempo de máquina por seção (s) |",
          "|---|---|---|---|---|---|---|"]
    for meio, r in d["resultados"].items():
        for chave, s in r.items():
            if not chave.startswith("secoes_de_"):
                continue
            L.append(f"| {meio.replace('_', ' ')} ({r['montagem']}) | {chave.split('_')[-1]} cédulas | {s['repeticoes']} | {ms(s['processar_cedula_ms'])} | "
                     f"{f(s['verificar_ledger_ms']['media'],1)} | {f(s['gerar_boletim_ms']['media'],1)} | {f(s['tempo_computacional_por_secao_s'],2)} |")
    L += ["", "Referência: em 2016 a leitura humana levou ≈ 15 s por cédula; o custo de máquina é desprezível frente a isso, "
          "mesmo com HD mecânico.", ""]


def secao_e5(L: list[str]) -> None:
    d = carregar("e5-intervalo-blocos")
    if not d:
        return
    r = d["resultados"]
    i = r["intervalo_s"]
    L += ["## E5 — Intervalo entre blocos (12/12 no ar)", "", d["metodo"], "",
          f"* {r['intervalos']} intervalos (blocos {r['blocos']}), {f(r['blocos_por_min'],2)} blocos/min.",
          f"* Intervalo: média {f(i['media'],3)} s, desvio {f(i['desvio'],3)} s, p99 {f(i['p99'],1)} s, máximo {f(i['max'],0)} s.",
          f"* Fração de intervalos de exatamente 2 s: {f(r['fracao_exatamente_2s']*100,2)}%. Distribuição: {r['distribuicao_s']}.", ""]


def secao_e6(L: list[str]) -> None:
    d = carregar("e6-ensaios-nominais")
    if not d:
        return
    a = d["agregado"]
    L += ["## E6 — Ensaios nominais (12 seções cada)", "",
          "Relatório detalhado: `resultados/e6-ensaios-nominais.md`.", "",
          "| Indicador | Valor |", "|---|---|",
          f"| Execuções com sucesso | {a['sucessos']} de {len(d['execucoes'])} |",
          f"| Seções ancoradas / boletins que conferem na cadeia | {a['secoes_ancoradas']} / {a['boletins_conferem']} de {a['secoes_total']} |",
          f"| Cédulas | {a['cedulas_total']} (relidas rejeitadas {a['duplicadas_total']}, forjadas rejeitadas {a['invalidas_total']}) |",
          f"| Duração por execução (s) | média {f(a['duracao']['media'],1)}, desvio {f(a['duracao']['desvio'],1)}, mín {f(a['duracao']['min'],1)}, máx {f(a['duracao']['max'],1)} |",
          f"| Do boletim assinado à ancoragem (s) | média {f(a['ancoragem']['media'],1)}, mín {f(a['ancoragem']['min'],1)}, máx {f(a['ancoragem']['max'],1)} |",
          f"| Nós que saíram do ar / quórum perdido | {a['nos_sairam']} / {a['quorum_perdido']} |", ""]
    anc = [s["t_boletim_ate_ancorado_s"] for e in d["execucoes"] for s in e["secoes"] if s["t_boletim_ate_ancorado_s"] is not None]
    if anc:
        r = resumo(anc, 2)
        L += [f"Latência de ancoragem por seção (n = {r['n']}): média {f(r['media'])} s, mediana {f(r['mediana'])} s, p95 {f(r['p95'])} s, "
              f"IC95 da média {f(r['ic95_media'][0])}–{f(r['ic95_media'][1])} s.", ""]


def secao_e7(L: list[str]) -> None:
    d = carregar("e7-tolerancia")
    if not d or "por_k" not in d:
        return
    L += ["## E7 — Vazão com validadores fora (12 validadores, quórum 8)", "", d["metodo"], "",
          "| Nós fora | No ar | Blocos/min (média ± desvio, mín–máx) | Maior intervalo entre blocos (s, média; máx) | Produziu em todas as repetições |",
          "|---|---|---|---|---|"]
    for k, r in d["por_k"].items():
        b, m = r["blocos_por_min"], r["maior_intervalo_s"]
        L.append(f"| {k} | {12 - int(k)} | {f(b['media'],1)} ± {f(b['desvio'],1)} ({f(b['min'],1)}–{f(b['max'],1)}) | "
                 f"{f(m.get('media'),1)}; {f(m.get('max'),0)} | {'sim' if r['produziu_em_todas'] else 'NÃO'} |")
    ordem = [f".{ip.rsplit('.', 1)[1]}" for ip in _ips()]
    pos = {m: i for i, m in enumerate(ordem)}

    def vizinhos(fora: list[str]) -> bool:
        idx = {pos[m] for m in fora if m in pos}
        return any(((i + 1) % len(ordem)) in idx for i in idx)

    L += ["", "Por repetição (ordem de rodízio do proponente = " + " → ".join(ordem) + "):", "",
          "| Nós fora | Rep. | Quais | Vizinhos no rodízio | Blocos/min | Maior pausa (s) |", "|---|---|---|---|---|---|"]
    for e in d["execucoes"]:
        if e["k_fora"] >= 2:
            L.append(f"| {e['k_fora']} | {e['rep']} | {', '.join(e['fora'])} | {'sim' if vizinhos(e['fora']) else 'não'} | "
                     f"{f(e['blocos_por_min'],1)} | {e['maior_intervalo_s']} |")
    L.append("")


def _secao_tolerancia_fixa(L: list[str], nome: str, titulo: str, n_val: int) -> None:
    d = carregar(nome)
    if not d or "por_k" not in d:
        return
    L += [f"## {titulo}", "", d["metodo"], "",
          "| Nós fora | No ar | Quais | Blocos em 120 s por repetição | Média ± desvio | Intervalos entre blocos observados (s) |",
          "|---|---|---|---|---|---|"]
    for k, r in d["por_k"].items():
        reps = [e for e in d["execucoes"] if str(e["k_fora"]) == k]
        inter = sorted({i for e in reps for i in e.get("intervalos_s", [])})
        b = r["blocos"]
        L.append(f"| {k} | {n_val - int(k)} | {', '.join(r['fora']) or 'nenhum'} | {', '.join(str(e['blocos']) for e in reps)} | "
                 f"{f(b['media'], 1)} ± {f(b['desvio'], 1)} | {', '.join(str(i) for i in inter) or '— (sem blocos)'} |")
    L.append("")


def secao_e7b(L: list[str]) -> None:
    _secao_tolerancia_fixa(L, "e7b-tolerancia-consecutivos",
                           "E7b — Vazão com validadores CONSECUTIVOS no rodízio fora (12 validadores, quórum 8)", 12)


def secao_e7l(L: list[str]) -> None:
    _secao_tolerancia_fixa(L, "e7l-tolerancia-local", "E7L — Vazão da rede local de 4 validadores (quórum 3)", 4)


def secao_e8(L: list[str]) -> None:
    d = carregar("e8-recuperacao")
    if not d or "por_duracao" not in d:
        return
    L += ["## E8 — Recuperação após perda de quórum", "", d["metodo"], "",
          "| Parada (s) | n | Próximo bloco após religar (s): média ± desvio (mín–máx) | RPC do nó religado (s, média) |", "|---|---|---|---|"]
    for dur, r in d["por_duracao"].items():
        p = r["proximo_bloco_s"]
        L.append(f"| {dur} | {p['n']} | {f(p['media'],1)} ± {f(p['desvio'],1)} ({f(p['min'],1)}–{f(p['max'],1)}) | {f(r['rpc_religado_s'].get('media'),1)} |")
    L += ["", "Valores individuais (s): " + "; ".join(
        f"{dur} s → " + " · ".join(f(e['proximo_bloco_s'], 1) for e in d['execucoes'] if str(e['parada_s']) == dur)
        for dur in d["por_duracao"]) + ".",
          "Os tempos formam degraus (≈ 38, 70, 135, 263, 518 s) com diferenças de 4 s × 2ʳ: o temporizador de rodada do QBFT.", ""]


def secao_e9(L: list[str]) -> None:
    d = carregar("e9-capacidade")
    if not d or "gas" not in d:
        return
    g = d["gas"]
    L += ["## E9 — Custo em gás e capacidade de ancoragem", "", d["metodo"], "",
          "| Operação do contrato | Gás |", "|---|---|",
          f"| Implantar | {g['implantar']} |",
          f"| Criar eleição (12 apuradores) | {f(g['criar_eleicao_12_apuradores']['media'],0)} |",
          f"| Registrar boletim | média {f(g['registrar_boletim']['media'],0)} (mín {f(g['registrar_boletim']['min'],0)}, máx {f(g['registrar_boletim']['max'],0)}; n = {g['registrar_boletim']['n']}) |",
          f"| Encerrar | {f(g['encerrar']['media'],0)} |", "",
          "| Repetição | Enviadas / incluídas | Taxa oferecida (tx/s) | Envio (s) | Vazão na cadeia (tx/s) | Blocos (vazios no meio) | Tx por bloco (média; máx) | Latência de inclusão (s: mediana; p95; máx) |",
          "|---|---|---|---|---|---|---|---|"]
    for r in d["repeticoes"]:
        lat = r["latencia_inclusao_s"]
        L.append(f"| {r['rep']} | {r['transacoes_enviadas']} / {r['incluidas']} | {f(r.get('taxa_oferecida_tx_s'),1)} | {f(r['tempo_envio_s'],1)} | "
                 f"{f(r['tx_por_s_na_cadeia'],1)} | {r['blocos_usados']} ({r.get('blocos_vazios_no_intervalo', '—')}) | "
                 f"{f(r['tx_por_bloco']['media'],1)}; {f(r['tx_por_bloco']['max'],0)} | {f(lat['mediana'],1)}; {f(lat['p95'],1)}; {f(lat['max'],1)} |")
    L.append("")


def secao_e10(L: list[str]) -> None:
    d = carregar("e10-ensaio-com-falhas")
    if not d or "sucessos" not in d:
        return
    a, n = d["ancoragem_secoes_afetadas_s"], d["ancoragem_secoes_nao_afetadas_s"]
    L += ["## E10 — Ensaios com queda transitória de 3 validadores", "", d["metodo"], "",
          f"* Execuções com sucesso: {d['sucessos']} de {len(d['execucoes'])}; duração média {f(d['duracao_total_s']['media'],1)} s.",
          f"* Do boletim à ancoragem — seções cujo nó caiu: média {f(a['media'],1)} s (máx {f(a['max'],1)}, n = {a['n']}); "
          f"seções não afetadas: média {f(n['media'],1)} s (máx {f(n['max'],1)}, n = {n['n']}).", ""]


def secao_e11(L: list[str]) -> None:
    d = carregar("e11-reinicio")
    if not d or "por_modo" not in d:
        return
    L += ["## E11 — Convergência após reinício completo dos 12 nós", "", d["metodo"], "",
          "| Modo | Espalhamento dos starts (s) | Todos respondem (s) | Primeiro bloco (s) | Malha completa, 11 pares (s) |", "|---|---|---|---|---|"]
    for m, r in d["por_modo"].items():
        L.append(f"| {m} | {f(r['espalhamento_starts_s'].get('media'),1)} | {f(r['todos_respondem_s'].get('media'),1)} ± {f(r['todos_respondem_s'].get('desvio'),1)} | "
                 f"{f(r['primeiro_bloco_s'].get('media'),1)} ± {f(r['primeiro_bloco_s'].get('desvio'),1)} (máx {f(r['primeiro_bloco_s'].get('max'),1)}) | "
                 f"{f(r['malha_completa_s'].get('media'),1)} ± {f(r['malha_completa_s'].get('desvio'),1)} |")
    L.append("")


def secao_e12(L: list[str]) -> None:
    p = RESULTADOS / "e12-recursos.jsonl"
    if not p.is_file():
        return
    mem, cpu = defaultdict(list), defaultdict(list)
    for ln in p.read_text().splitlines():
        a = json.loads(ln)
        v = a["mem"]
        mib = float(v[:-3]) * (1024 if v.endswith("GiB") else 1) if v.endswith(("MiB", "GiB")) else None
        if mib:
            mem[a["ip"]].append(mib)
        try:
            cpu[a["ip"]].append(float(a["cpu"].rstrip("%")))
        except ValueError:
            pass
    todas_m = [x for v in mem.values() for x in v]
    todas_c = [x for v in cpu.values() for x in v]
    if not todas_m:
        return
    L += ["## E12 — Recursos por nó Besu durante os testes", "",
          f"Amostras de `docker stats` a cada 60 s em todos os nós durante E6–E11: {len(todas_m)} amostras de memória.", "",
          f"* Memória por nó: média {f(statistics.mean(todas_m),0)} MiB, p95 {f(resumo(todas_m)['p95'],0)} MiB, máximo {f(max(todas_m),0)} MiB "
          "(máquinas de 3,3–3,4 GB; heap da JVM limitado a 1 GB).",
          f"* CPU por nó: média {f(statistics.mean(todas_c),1)}%, p95 {f(resumo(todas_c)['p95'],1)}%, máximo {f(max(todas_c),1)}% "
          "(percentual de um núcleo, como reporta o Docker).", ""]


def secao_e13(L: list[str]) -> None:
    d = carregar("e13-custo-ancoragem")
    if not d or "por_funcao" not in d:
        return
    L += ["## E13 — Gás e latência de inclusão de cada transação de ancoragem (uma por vez)", "", d["metodo"], "",
          "| Transação | n | Gás (média ± desvio; mín–máx) | Latência de inclusão (s): média ± desvio (mediana; p95; máx) |",
          "|---|---|---|---|"]
    rot = {"implantar": "Implantar contrato", "criarEleicao": "criarEleicao (12 apuradores)",
           "registrarBoletim": "registrarBoletim (todas)", "encerrar": "encerrar"}
    linhas = [(rot[k], v) for k, v in d["por_funcao"].items()]
    linhas.insert(3, ("  primeiro boletim de cada eleição", d["registrar_primeira_secao"]))
    linhas.insert(4, ("  demais boletins", d["registrar_demais_secoes"]))
    for nome, v in linhas:
        g, lat = v["gas"], v["latencia_recibo_s"]
        L.append(f"| {nome} | {g['n']} | {f(g['media'], 0)} ± {f(g['desvio'], 0)}; {f(g['min'], 0)}–{f(g['max'], 0)} | "
                 f"{f(lat['media'], 2)} ± {f(lat['desvio'], 2)} ({f(lat['mediana'], 2)}; {f(lat['p95'], 2)}; {f(lat['max'], 2)}) |")
    L += ["", "Com blocos a cada 2 s e envio em fase aleatória, a espera pelo bloco seguinte é uniforme entre 0 e 2 s "
          "(média 1 s, desvio 0,58 s): todas as transações entraram no primeiro bloco depois do envio.", ""]


def main() -> None:
    L = ["# Relatório consolidado dos experimentos", "",
         "Gerado por `experimentos/relatorio.py` a partir de `resultados/*.json`. Cada seção indica método e tamanho de amostra. "
         "Os scripts de cada experimento estão em `experimentos/` e podem ser reexecutados.", ""]
    for fn in (secao_e1, secao_e2, secao_e3, secao_e4, secao_e5, secao_e6, secao_e7, secao_e7b, secao_e7l, secao_e8,
               secao_e9, secao_e10, secao_e11, secao_e12, secao_e13):
        try:
            fn(L)
        except Exception as e:  # noqa: BLE001
            L += [f"_(falha ao consolidar {fn.__name__}: {e})_", ""]
    (RESULTADOS / "RELATORIO-EXPERIMENTOS.md").write_text("\n".join(L) + "\n")
    print(RESULTADOS / "RELATORIO-EXPERIMENTOS.md")


if __name__ == "__main__":
    main()
