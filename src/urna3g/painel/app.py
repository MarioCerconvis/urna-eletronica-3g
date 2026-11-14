"""Servidor do painel (FastAPI): página, fluxo SSE ao vivo e ações. Escuta só em 127.0.0.1."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from urna3g.painel import infra
from urna3g.painel.coletor import Painel
from urna3g.painel.config import PainelCfg
from urna3g.painel.ensaio import Ensaio

ESTATICO = Path(__file__).resolve().parent / "static"


class PedidoEnsaio(BaseModel):
    eleitores: int = Field(25, ge=3, le=400)
    duracao: float = Field(45, ge=10, le=900)


def criar_app(cfg: PainelCfg) -> FastAPI:
    painel = Painel(cfg)
    estado: dict = {"ensaio": None, "tarefas": []}

    @asynccontextmanager
    async def vida(app: FastAPI):
        estado["tarefas"] = await painel.iniciar()
        yield
        for t in estado["tarefas"]:
            t.cancel()
        if getattr(painel, "tunel", None):
            painel.tunel.encerrar()
        await painel.http.aclose()

    app = FastAPI(title="urna3g — painel ao vivo", lifespan=vida, docs_url=None, redoc_url=None)
    app.state.painel = painel
    app.mount("/static", StaticFiles(directory=ESTATICO), name="static")

    @app.get("/")
    async def pagina() -> FileResponse:
        return FileResponse(ESTATICO / "index.html")

    @app.get("/api/estado")
    async def api_estado() -> dict:
        return painel.snapshot()

    @app.get("/api/eventos")
    async def api_eventos() -> list:
        return list(painel.eventos)

    @app.get("/api/stream")
    async def stream(request: Request) -> StreamingResponse:
        fila: asyncio.Queue = asyncio.Queue()
        painel.assinantes.add(fila)

        async def gerar():
            try:
                yield painel.json_sse(painel.snapshot())
                yield painel.json_sse({"t": "historico", "eventos": list(painel.eventos)[-300:]})
                while True:
                    if await request.is_disconnected():
                        break
                    try:
                        msg = await asyncio.wait_for(fila.get(), timeout=15)
                        yield painel.json_sse(msg)
                    except asyncio.TimeoutError:
                        yield ": ping\n\n"
            finally:
                painel.assinantes.discard(fila)

        return StreamingResponse(gerar(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/nos/{no_id}/{acao}")
    async def api_acao_no(no_id: str, acao: str) -> dict:
        if acao not in ("derrubar", "religar"):
            raise HTTPException(400, "ação inválida")
        no = painel.cfg_por_id.get(no_id)
        if no is None:
            raise HTTPException(404, "nó desconhecido")
        verbo = "Desligando" if acao == "derrubar" else "Religando"
        painel.evento("maquina", f"{verbo} o nó {painel.nos[no_id].rotulo} (pedido pelo operador)", "info", [no_id])
        ok, msg = await infra.acao_no(cfg, no, acao)
        if not ok:
            painel.evento("maquina", f"Falha ao {acao} {painel.nos[no_id].rotulo}: {msg}", "critical", [no_id])
            raise HTTPException(500, msg)
        return {"ok": True}

    @app.post("/api/ensaio")
    async def api_ensaio(pedido: PedidoEnsaio) -> dict:
        if painel.ensaio_ativo:
            raise HTTPException(409, "já há um ensaio em andamento")
        e = Ensaio(painel, pedido.eleitores, pedido.duracao)
        estado["ensaio"] = e
        e.iniciar()
        return {"ok": True}

    @app.post("/api/ensaio/parar")
    async def api_parar() -> dict:
        if estado["ensaio"]:
            estado["ensaio"].parar()
        return {"ok": True}

    return app
