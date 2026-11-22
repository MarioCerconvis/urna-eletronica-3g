"""Ensaio de eleição para o painel: cada seção K é apurada e ancorada pela máquina K.

O que é real e o que é simulado (a interface mostra isso):
* REAL: assinatura Ed25519 das cédulas e do boletim, ledger da apuração, rejeição de cédulas repetidas/forjadas,
  transações na blockchain do cluster — cada boletim é enviado pelo RPC da máquina da seção, assinado com a
  conta do validador dela, e o painel só o marca como ancorado quando o evento aparece na cadeia.
* SIMULADO: os eleitores. As cédulas são geradas neste computador, num ritmo que imita uma seção real.
  Numa eleição oficial as urnas ficam OFFLINE e nenhum contador de votos é transmitido: o painel mostraria
  só as fases por seção (apuração, boletim, ancoragem).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import random
import shutil
import tempfile
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from typing import Any

from urna3g import BRANCO, NULO, crypto
from urna3g import boletim as bmod
from urna3g.ballot import emitir
from urna3g.config import Chaves
from urna3g.manifest import Eleicao, assinar_manifesto, salvar_assinatura
from urna3g.painel.config import RAIZ_REPO
from urna3g.tally import Apuracao, Status

DEMO = RAIZ_REPO / "exemplos" / "eleicao-demo"


class ErroEnsaio(RuntimeError):
    pass


def _web3(url: str):
    from web3 import Web3

    return Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 15}))


def _enviar(w3, conta, fn) -> Any:  # noqa: ANN001
    tx = fn.build_transaction({"from": conta.address, "nonce": w3.eth.get_transaction_count(conta.address, "pending"),
                               "gasPrice": w3.eth.gas_price, "chainId": w3.eth.chain_id})
    tx["gas"] = int(w3.eth.estimate_gas(tx) * 1.2)
    h = w3.eth.send_raw_transaction(conta.sign_transaction(tx).raw_transaction)
    rec = w3.eth.wait_for_transaction_receipt(h, timeout=180)
    if rec.status != 1:
        raise ErroEnsaio(f"transação revertida {h.hex()}")
    return rec


class Ensaio:
    def __init__(self, painel, eleitores: int = 25, duracao: float = 45.0):  # noqa: ANN001
        self.p = painel
        self.eleitores = max(3, min(int(eleitores), 400))
        self.duracao = max(10.0, min(float(duracao), 900.0))
        self.dir = Path(tempfile.mkdtemp(prefix="urna3g-ensaio-"))
        self.tarefa: asyncio.Task | None = None

    # ------------------------------------------------------------------ util
    def _secao(self, sec: str) -> dict[str, Any]:
        return self.p.eleicao["secoes"][sec]

    def _fase(self, sec: str, fase: str, **extra: Any) -> None:
        import time

        s = self._secao(sec)
        s.update({"fase": fase, **extra})
        s.setdefault("tempos", {})[fase] = time.time()

    async def _thread(self, fn, *a):  # noqa: ANN001
        return await asyncio.to_thread(fn, *a)

    def _artefato(self) -> dict[str, Any]:
        if not self.p.cfg.artefato.is_file():
            raise ErroEnsaio(f"contrato não compilado: {self.p.cfg.artefato}")
        return json.loads(self.p.cfg.artefato.read_text())

    def _conta(self, no_id: str):  # noqa: ANN202
        from eth_account import Account

        return Account.from_key(self.p.cfg_por_id[no_id].chave.read_text().strip())

    # ------------------------------------------------------------------ preparação
    def _preparar(self) -> tuple[Eleicao, dict[str, crypto.ChavePrivada], crypto.ChavePrivada]:
        shutil.copytree(DEMO, self.dir / "eleicao")
        secoes = [f"{n.indice:03d}" for n in self.p.cfg.nos]
        m = self.dir / "eleicao" / "eleicao.json"
        e = Eleicao.carregar(m)
        e = replace(e, nome=f"Ensaio ao vivo — {datetime.now():%d/%m/%Y %H:%M:%S}", secoes=secoes,
                    data=f"{datetime.now():%Y-%m-%d}")
        e = e.preencher_hashes_fotos()
        e.salvar(m)
        ch = Chaves(self.dir / "chaves")
        aut = crypto.gerar_chave()
        crypto.salvar_privada(ch.autoridade_priv(), aut)
        salvar_assinatura(m.with_suffix(".sig"), assinar_manifesto(e, aut))
        chaves_secao = {s: crypto.gerar_chave() for s in secoes}
        return Eleicao.carregar(m), chaves_secao, crypto.gerar_chave()

    def _garantir_contrato(self, url: str, conta) -> str:  # noqa: ANN001
        if self.p.contrato:
            return self.p.contrato
        art = self._artefato()
        w3 = _web3(url)
        rec = _enviar(w3, conta, w3.eth.contract(abi=art["abi"], bytecode=art["bytecode"]).constructor())
        return rec.contractAddress.lower()

    def _contrato(self, url: str):  # noqa: ANN202
        w3 = _web3(url)
        return w3, w3.eth.contract(address=w3.to_checksum_address(self.p.contrato), abi=self._artefato()["abi"])

    # ------------------------------------------------------------------ execução
    async def executar(self) -> None:
        p = self.p
        p.ensaio_ativo = True
        try:
            eleicao, chaves_secao, chave_apuracao = await self._thread(self._preparar)
            mapa = {f"{n.indice:03d}": n.id for n in p.cfg.nos}
            p.eleicao.update({
                "id": None, "id_pendente": eleicao.id, "nome": eleicao.nome, "fase": "preparando", "encerrada": False,
                "total_secoes": len(mapa), "resultados": {}, "ensaio": True,
                "cargos": [{"id": c.id, "nome": c.nome} for c in eleicao.cargos],
                "legenda": {c.id: {str(x.numero): f"{x.nome} ({eleicao.partido(x.partido).sigla})"
                                   for x in eleicao.candidatos_do_cargo(c.id)} for c in eleicao.cargos},
                "secoes": {s: {"secao": s, "no": nid, "fase": "aguardando", "cedulas": 0, "apuradas": 0}
                           for s, nid in mapa.items()},
            })
            p.evento("eleicao", f"Ensaio iniciado: {len(mapa)} seções, {self.eleitores} eleitores por seção. "
                                f"Manifesto assinado (id {eleicao.id[:12]}…)", "info")
            coord = p.no_vivo()
            if coord is None:
                raise ErroEnsaio("nenhum nó no ar para coordenar o ensaio")
            url, conta = p.cfg_por_id[coord].rpc, self._conta(coord)
            novo = not p.contrato
            p.contrato = await self._thread(self._garantir_contrato, url, conta)
            if novo:
                p.evento("blockchain", f"Contrato RegistroEleitoral implantado em {p.contrato[:12]}…", "good", [coord])
            apuradores = [n.endereco for n in p.cfg.nos]

            def criar() -> None:
                w3, c = self._contrato(url)
                _enviar(w3, conta, c.functions.criarEleicao(bytes.fromhex(eleicao.id),
                                                            [w3.to_checksum_address(a) for a in apuradores]))

            await self._thread(criar)
            p.eleicao["fase"] = "votacao"
            resultados = await asyncio.gather(*(self._secao_fluxo(s, nid, eleicao, chaves_secao[s], chave_apuracao)
                                                for s, nid in mapa.items()), return_exceptions=True)
            for (s, nid), r in zip(mapa.items(), resultados, strict=True):
                if isinstance(r, Exception):
                    self._fase(s, "erro")
                    p.evento("eleicao", f"Seção {s}: falhou ({str(r)[:120]})", "critical", [nid])
            # encerramento: hash encadeado dos boletins (como o mural do servidor)
            cadeia = hashlib.sha256(b"urna3g/mural/v1" + eleicao.id.encode()).hexdigest()
            for i, s in enumerate(sorted(mapa), start=1):
                hb_s = self._secao(s).get("hash_boletim", "")
                cadeia = hashlib.sha256(f"{cadeia}|{i}|{s}|{hb_s}".encode()).hexdigest()
            while True:
                coord = p.no_vivo()
                if coord and p.vivos() >= p.quorum:
                    try:
                        def encerrar(coord: str = coord) -> None:
                            w3, c = self._contrato(p.cfg_por_id[coord].rpc)
                            _enviar(w3, self._conta(coord), c.functions.encerrar(bytes.fromhex(eleicao.id),
                                                                                 bytes.fromhex(cadeia)))
                        await self._thread(encerrar)
                        break
                    except Exception as e:  # noqa: BLE001
                        p.evento("sistema", f"Encerramento adiado: {e}", "warning")
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            p.evento("eleicao", "Ensaio interrompido pelo operador", "warning")
            raise
        except Exception as e:  # noqa: BLE001
            p.evento("sistema", f"Ensaio falhou: {e}", "critical")
        finally:
            p.ensaio_ativo = False
            shutil.rmtree(self.dir, ignore_errors=True)

    async def _secao_fluxo(self, sec: str, nid: str, eleicao: Eleicao, chave: crypto.ChavePrivada,
                           chave_ap: crypto.ChavePrivada) -> None:
        p, rot = self.p, self.p.nos[nid].rotulo
        await asyncio.sleep(random.uniform(0, 4))
        # 1. votação (eleitores simulados; cédulas assinadas de verdade)
        self._fase(sec, "votando", inicio=datetime.now().strftime("%H:%M:%S"))
        p.evento("eleicao", f"Seção {sec} ({rot}): votação aberta", "info", [nid], {"secao": sec})
        textos: list[str] = []
        n = max(3, int(self.eleitores * random.uniform(0.75, 1.15)))
        for _ in range(n):
            await asyncio.sleep(self.duracao / n * random.uniform(0.4, 1.6))
            votos = []
            for slot in eleicao.slots():
                nums = [c.numero for c in eleicao.candidatos_do_cargo(slot.cargo_id)]
                votos.append(random.choices(nums + [BRANCO, NULO], weights=[8] * len(nums) + [1, 1])[0])
            textos.append(emitir(eleicao, sec, votos, chave).texto())
            self._secao(sec)["cedulas"] = len(textos)
        self._fase(sec, "encerrada")
        p.evento("eleicao", f"Seção {sec} ({rot}): votação encerrada com {len(textos)} cédulas", "info", [nid],
                 {"secao": sec})
        # 2. apuração (ledger real; inclui releituras e uma cédula forjada de vez em quando)
        await asyncio.sleep(random.uniform(1, 3))
        self._fase(sec, "apurando")
        leituras = list(textos)
        if random.random() < 0.5:
            leituras.insert(random.randrange(len(leituras)), random.choice(textos))
        if random.random() < 0.25:
            leituras.insert(random.randrange(len(leituras)), emitir(eleicao, sec, [BRANCO] * len(eleicao.slots()),
                                                                     crypto.gerar_chave()).texto())
        loop = asyncio.get_running_loop()

        def apurar() -> dict[str, Any]:
            """Roda numa thread própria: o ledger SQLite (com fsync) não pode travar o laço do painel."""
            import time

            ap = Apuracao.abrir(eleicao, sec, chave.public_key(), self.dir / f"apuracao-{sec}.db")
            try:
                for t in leituras:
                    time.sleep(random.uniform(0.08, 0.25))
                    r = ap.processar(t)
                    sd = self._secao(sec)
                    if r.status is Status.DUPLICADA:
                        sd["duplicadas"] = sd.get("duplicadas", 0) + 1
                        loop.call_soon_threadsafe(p.evento, "eleicao",
                                                  f"Seção {sec}: cédula lida duas vezes — rejeitada (já apurada)",
                                                  "warning", [nid])
                    elif r.status is Status.INVALIDA:
                        sd["invalidas"] = sd.get("invalidas", 0) + 1
                        loop.call_soon_threadsafe(p.evento, "eleicao",
                                                  f"Seção {sec}: cédula com assinatura inválida — rejeitada",
                                                  "serious", [nid])
                    self._secao(sec)["apuradas"] = ap.total_cedulas()
                return ap.gerar_boletim(chave_ap)
            finally:
                ap.ledger.fechar()

        b = await asyncio.to_thread(apurar)
        hb = bmod.hash_boletim(b)
        self._fase(sec, "boletim", hash_boletim=hb, total=b["total_cedulas"])
        self._acumular(b)
        p.evento("eleicao", f"Seção {sec} ({rot}): boletim assinado — {b['total_cedulas']} cédulas, hash {hb[:12]}…",
                 "info", [nid], {"secao": sec})
        # 3. ancoragem PELA MÁQUINA DA SEÇÃO
        self._fase(sec, "ancorando")
        avisado = False
        while True:
            if p.nos[nid].estado == "no_ar" and p.vivos() >= p.quorum:
                try:
                    def registrar() -> None:
                        w3, c = self._contrato(p.cfg_por_id[nid].rpc)
                        _enviar(w3, self._conta(nid), c.functions.registrarBoletim(
                            bytes.fromhex(b["eleicao_id"]), sec, bytes.fromhex(hb),
                            bytes.fromhex(b["ledger"]["hash_final"]), int(b["total_cedulas"])))
                    await self._thread(registrar)
                    break
                except Exception as e:  # noqa: BLE001
                    if "ja registrada" in str(e):
                        break
                    if not avisado:
                        msg = f"Seção {sec}: ancoragem falhou ({str(e)[:80]}); tentando de novo"
                        p.evento("eleicao", msg, "warning", [nid])
                        avisado = True
            elif not avisado:
                motivo = f"nó {rot} fora do ar" if p.nos[nid].estado != "no_ar" else "rede sem quórum"
                p.evento("eleicao", f"Seção {sec}: aguardando para ancorar ({motivo})", "warning", [nid])
                avisado = True
            await asyncio.sleep(4)

    def _acumular(self, b: dict[str, Any]) -> None:
        res = self.p.eleicao["resultados"]
        for cargo_id, r in b["resultados"].items():
            alvo = res.setdefault(cargo_id, {"nome": r["nome"], "votos": {}})
            for k, v in r["votos"].items():
                alvo["votos"][k] = alvo["votos"].get(k, 0) + int(v)

    def iniciar(self) -> None:
        self.tarefa = asyncio.create_task(self.executar())

    def parar(self) -> None:
        if self.tarefa and not self.tarefa.done():
            self.tarefa.cancel()
