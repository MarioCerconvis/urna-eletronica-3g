"""Servidor (FastAPI) — roda no servidor do laboratório, na LAN.

Papel deliberadamente *limitado* (ver docs/02-arquitetura.md): o servidor **nunca recebe
votos**. Ele distribui o manifesto assinado antes da eleição e, depois da apuração, recebe
o **boletim assinado** de cada seção, verifica a assinatura com a chave pública do apurador
daquela seção, encadeia os boletins em um mural (hash chain) e publica a totalização para
qualquer fiscal conferir — inclusive refazendo a soma a partir dos boletins publicados.
"""

from __future__ import annotations

import base64
import hashlib
import html
import io
import json
import sqlite3
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from urna3g import __version__, crypto
from urna3g import boletim as bmod
from urna3g.config import Chaves, carregar_eleicao
from urna3g.manifest import Eleicao, carregar_assinatura

LIMITE_CORPO = 1_000_000  # 1 MB — um boletim tem poucos KB


class Mural:
    """Boletins recebidos + cadeia de hashes do servidor (SQLite)."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS boletins (
        seq           INTEGER PRIMARY KEY,
        secao         TEXT NOT NULL UNIQUE,
        hash          TEXT NOT NULL,
        conteudo      TEXT NOT NULL,
        recebido_em   TEXT NOT NULL,
        hash_anterior TEXT NOT NULL,
        hash_cadeia   TEXT NOT NULL UNIQUE
    );
    """

    def __init__(self, caminho: Path, eleicao_id: str):
        self.eleicao_id = eleicao_id
        self.con = sqlite3.connect(str(caminho), isolation_level=None, check_same_thread=False)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.execute("PRAGMA synchronous=FULL")
        self.con.executescript(self._SCHEMA)

    @property
    def genesis(self) -> str:
        return hashlib.sha256(b"urna3g/mural/v1" + self.eleicao_id.encode()).hexdigest()

    def ultimo(self) -> tuple[int, str]:
        row = self.con.execute("SELECT seq, hash_cadeia FROM boletins ORDER BY seq DESC LIMIT 1").fetchone()
        return (row[0], row[1]) if row else (0, self.genesis)

    def obter(self, secao: str) -> dict[str, Any] | None:
        row = self.con.execute("SELECT conteudo FROM boletins WHERE secao=?", (secao,)).fetchone()
        return json.loads(row[0]) if row else None

    def registrar(self, boletim: dict[str, Any]) -> dict[str, Any]:
        h = bmod.hash_boletim(boletim)
        self.con.execute("BEGIN IMMEDIATE")
        try:
            seq_ant, cadeia_ant = self.ultimo()
            seq = seq_ant + 1
            cadeia = hashlib.sha256(f"{cadeia_ant}|{seq}|{boletim['secao']}|{h}".encode()).hexdigest()
            agora = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            self.con.execute(
                "INSERT INTO boletins(seq, secao, hash, conteudo, recebido_em, hash_anterior, hash_cadeia) "
                "VALUES (?,?,?,?,?,?,?)",
                (seq, boletim["secao"], h, json.dumps(boletim, ensure_ascii=False), agora, cadeia_ant, cadeia),
            )
            self.con.execute("COMMIT")
        except BaseException:
            self.con.execute("ROLLBACK")
            raise
        return {"seq": seq, "secao": boletim["secao"], "hash": h, "hash_cadeia": cadeia, "recebido_em": agora}

    def listar(self) -> list[dict[str, Any]]:
        cur = self.con.execute(
            "SELECT seq, secao, hash, recebido_em, hash_anterior, hash_cadeia FROM boletins ORDER BY seq"
        )
        return [
            {"seq": s, "secao": sec, "hash": h, "recebido_em": r, "hash_anterior": ha, "hash_cadeia": hc}
            for s, sec, h, r, ha, hc in cur
        ]

    def boletins(self) -> list[dict[str, Any]]:
        return [json.loads(c) for (c,) in self.con.execute("SELECT conteudo FROM boletins ORDER BY seq")]


def totalizar(eleicao: Eleicao, boletins: list[dict[str, Any]]) -> dict[str, Any]:
    resultados: dict[str, Any] = {}
    for cargo in eleicao.cargos:
        votos: dict[str, int] = {str(c.numero): 0 for c in eleicao.candidatos_do_cargo(cargo.id)}
        votos.update({"branco": 0, "nulo": 0})
        legenda = {}
        for c in eleicao.candidatos_do_cargo(cargo.id):
            p = eleicao.partido(c.partido)
            legenda[str(c.numero)] = f"{c.nome} ({p.sigla})" if p else c.nome
        resultados[cargo.id] = {"nome": cargo.nome, "votos": votos, "legenda": legenda}
    total = 0
    for b in boletins:
        total += int(b.get("total_cedulas", 0))
        for cargo_id, res in b.get("resultados", {}).items():
            if cargo_id not in resultados:
                continue
            for chave, n in res.get("votos", {}).items():
                resultados[cargo_id]["votos"][chave] = resultados[cargo_id]["votos"].get(chave, 0) + int(n)
    return {
        "eleicao_id": eleicao.id,
        "eleicao_nome": eleicao.nome,
        "secoes_esperadas": list(eleicao.secoes),
        "secoes_recebidas": [b["secao"] for b in boletins],
        "total_cedulas": total,
        "resultados": resultados,
    }


def criar_app(dados: Path | str) -> FastAPI:
    dados = Path(dados)
    chaves = Chaves(dados / "chaves")
    manifesto = dados / "eleicao.json"
    eleicao, situacao = carregar_eleicao(manifesto, chaves.autoridade_pub(), verificar_fotos=False)
    assinatura = carregar_assinatura(manifesto.with_suffix(".sig")) if manifesto.with_suffix(".sig").is_file() else None
    autoridade_fp = (
        crypto.impressao_digital(crypto.carregar_publica(chaves.autoridade_pub()))
        if chaves.autoridade_pub().is_file()
        else None
    )
    mural = Mural(dados / "mural.db", eleicao.id)

    app = FastAPI(title="urna3g — mural da eleição", version=__version__, docs_url="/docs")
    app.state.eleicao = eleicao
    app.state.mural = mural

    def pub_apuracao(secao: str) -> crypto.ChavePublica | None:
        p = chaves.apuracao_pub(secao)
        return crypto.carregar_publica(p) if p.is_file() else None

    def secoes_conhecidas() -> list[str]:
        return sorted(p.name[len("apuracao-") : -len(".pub")] for p in chaves.dir.glob("apuracao-*.pub"))

    # ------------------------------------------------------------------ distribuição
    @app.get("/saude")
    def saude() -> dict[str, Any]:
        return {"ok": True, "versao": __version__, "eleicao_id": eleicao.id}

    @app.get("/api/eleicao")
    def api_eleicao() -> dict[str, Any]:
        return {
            "id": eleicao.id,
            "situacao_assinatura": situacao,
            "manifesto": eleicao.to_dict(),
            "assinatura": base64.b64encode(assinatura).decode() if assinatura else None,
            "autoridade": autoridade_fp,
        }

    @app.get("/api/eleicao/pacote.zip")
    def api_pacote() -> Response:
        """Manifesto + assinatura + fotos + chave da autoridade, para carregar nos terminais."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(manifesto, "eleicao/eleicao.json")
            if assinatura:
                z.write(manifesto.with_suffix(".sig"), "eleicao/eleicao.sig")
            for obj in [*eleicao.partidos, *eleicao.candidatos]:
                if obj.foto and eleicao.caminho(obj.foto).is_file():
                    z.write(eleicao.caminho(obj.foto), f"eleicao/{obj.foto}")
            if chaves.autoridade_pub().is_file():
                z.write(chaves.autoridade_pub(), "chaves/autoridade.pub")
            for secao in secoes_conhecidas():
                z.write(chaves.apuracao_pub(secao), f"chaves/apuracao-{secao}.pub")
                if chaves.secao_pub(secao).is_file():
                    z.write(chaves.secao_pub(secao), f"chaves/secao-{secao}.pub")
        return Response(buf.getvalue(), media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="pacote-eleicao.zip"'})

    @app.get("/api/chaves")
    def api_chaves() -> dict[str, Any]:
        out: dict[str, Any] = {"autoridade": autoridade_fp, "apuracao": {}, "secao": {}}
        for secao in secoes_conhecidas():
            pub = pub_apuracao(secao)
            if pub:
                out["apuracao"][secao] = crypto.impressao_digital(pub)
            if chaves.secao_pub(secao).is_file():
                out["secao"][secao] = crypto.impressao_digital(crypto.carregar_publica(chaves.secao_pub(secao)))
        return out

    @app.get("/api/chaves/{nome}.pub", response_class=PlainTextResponse)
    def api_chave_pem(nome: str) -> str:
        if not nome.replace("-", "").replace("_", "").isalnum():
            raise HTTPException(400, "nome inválido")
        p = chaves.dir / f"{nome}.pub"
        if not p.is_file():
            raise HTTPException(404, "chave não encontrada")
        return p.read_text()

    # ------------------------------------------------------------------ boletins
    @app.post("/api/boletins", status_code=201)
    async def api_receber_boletim(request: Request) -> JSONResponse:
        corpo = await request.body()
        if len(corpo) > LIMITE_CORPO:
            raise HTTPException(413, "boletim grande demais")
        try:
            b = json.loads(corpo)
        except json.JSONDecodeError as e:
            raise HTTPException(400, "JSON inválido") from e
        if not isinstance(b, dict) or not isinstance(b.get("secao"), str):
            raise HTTPException(400, "boletim malformado")
        if b.get("eleicao_id") != eleicao.id:
            raise HTTPException(400, "boletim de outra eleição")
        pub = pub_apuracao(b["secao"])
        if pub is None:
            raise HTTPException(403, f"seção {b['secao']!r} desconhecida (sem chave pública de apuração cadastrada)")
        try:
            bmod.verificar(b, pub)
        except bmod.ErroBoletim as e:
            raise HTTPException(400, str(e)) from e
        existente = mural.obter(b["secao"])
        if existente is not None:
            if bmod.hash_boletim(existente) == bmod.hash_boletim(b):
                return JSONResponse({"detail": "boletim já registrado", "hash": bmod.hash_boletim(b)},
                                    status_code=200)
            raise HTTPException(409, "já existe um boletim diferente para esta seção; retificação exige a comissão")
        return JSONResponse(mural.registrar(b), status_code=201)

    @app.get("/api/boletins")
    def api_boletins() -> list[dict[str, Any]]:
        return mural.listar()

    @app.get("/api/boletins/{secao}")
    def api_boletim(secao: str) -> dict[str, Any]:
        b = mural.obter(secao)
        if b is None:
            raise HTTPException(404, "boletim não recebido")
        return b

    @app.get("/api/totalizacao")
    def api_totalizacao() -> dict[str, Any]:
        t = totalizar(eleicao, mural.boletins())
        t["mural"] = {"registros": mural.ultimo()[0], "hash_cadeia": mural.ultimo()[1]}
        return t

    @app.get("/api/mural")
    def api_mural() -> dict[str, Any]:
        return {"genesis": mural.genesis, "registros": mural.listar(), "hash_cadeia": mural.ultimo()[1]}

    # ------------------------------------------------------------------ página pública
    @app.get("/", response_class=HTMLResponse)
    def pagina() -> str:
        t = totalizar(eleicao, mural.boletins())
        esc = html.escape
        partes = [
            "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>",
            f"<title>Mural — {esc(eleicao.nome)}</title>",
            "<meta name='viewport' content='width=device-width,initial-scale=1'>",
            "<style>body{font-family:system-ui,sans-serif;max-width:960px;margin:2rem auto;padding:0 1rem;color:#222}"
            "table{border-collapse:collapse;margin:.5rem 0 1.5rem}"
            "td,th{border:1px solid #ccc;padding:.3rem .6rem;text-align:left}"
            "th{background:#f3f3f3}code{font-size:.85em;word-break:break-all}.ok{color:#176b2a}.pend{color:#9a6700}"
            "h2{margin-top:2rem}small{color:#666}</style></head><body>",
            f"<h1>{esc(eleicao.nome)}</h1>",
            f"<p><small>id da eleição <code>{eleicao.id}</code><br>manifesto: {esc(situacao)}"
            + (f" · autoridade <code>{autoridade_fp}</code>" if autoridade_fp else "")
            + f"<br>urna3g {__version__} · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</small></p>",
            "<h2>Totalização</h2>",
            f"<p>Seções recebidas: <b>{len(t['secoes_recebidas'])}</b>"
            + (f" de {len(t['secoes_esperadas'])}" if t["secoes_esperadas"] else "")
            + f" · cédulas: <b>{t['total_cedulas']}</b></p>",
        ]
        for cargo in t["resultados"].values():
            partes.append(f"<h3>{esc(cargo['nome'])}</h3><table><tr><th>Voto</th><th>Quantidade</th></tr>")
            for chave, n in cargo["votos"].items():
                nome = {"branco": "Branco", "nulo": "Nulo"}.get(chave) or f"{chave} — {cargo['legenda'].get(chave, '')}"
                partes.append(f"<tr><td>{esc(nome)}</td><td>{n}</td></tr>")
            partes.append("</table>")
        partes.append("<h2>Boletins por seção</h2><table><tr><th>#</th><th>Seção</th><th>Cédulas</th>"
                      "<th>Hash do boletim</th><th>Hash do ledger</th><th>Recebido</th></tr>")
        for reg, b in zip(mural.listar(), mural.boletins(), strict=True):
            partes.append(
                f"<tr><td>{reg['seq']}</td><td><a href='/api/boletins/{esc(b['secao'])}'>{esc(b['secao'])}</a></td>"
                f"<td>{b['total_cedulas']}</td><td><code>{reg['hash']}</code></td>"
                f"<td><code>{esc(b['ledger']['hash_final'])}</code></td><td>{esc(reg['recebido_em'])}</td></tr>"
            )
        partes.append("</table>")
        pendentes = [s for s in t["secoes_esperadas"] if s not in t["secoes_recebidas"]]
        if pendentes:
            partes.append(f"<p class='pend'>Aguardando: {esc(', '.join(pendentes))}</p>")
        partes.append(
            f"<p><small>Cadeia do mural: <code>{mural.ultimo()[1]}</code> ({mural.ultimo()[0]} registros). "
            "Qualquer pessoa pode baixar os boletins (<a href='/api/boletins'>/api/boletins</a>), conferir as "
            "assinaturas com as chaves públicas (<a href='/api/chaves'>/api/chaves</a>) e refazer a soma.</small></p>"
            "</body></html>"
        )
        return "".join(partes)

    return app
