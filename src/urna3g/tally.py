"""Apuração: lê cédulas (QR), descarta duplicatas/inválidas, totaliza e emite o boletim."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from urna3g import BRANCO, NULO, __version__, crypto
from urna3g import boletim as boletim_mod
from urna3g.ballot import Cedula, ErroCedula, decodificar, ler
from urna3g.ledger import Ledger
from urna3g.manifest import Eleicao


class Status(str, Enum):
    ACEITA = "aceita"
    DUPLICADA = "duplicada"
    INVALIDA = "invalida"
    ENCERRADA = "encerrada"


@dataclass(frozen=True)
class Resultado:
    status: Status
    motivo: str = ""
    cedula: Cedula | None = None
    seq: int | None = None

    @property
    def aceita(self) -> bool:
        return self.status is Status.ACEITA


class Apuracao:
    """Estado da apuração de UMA seção, persistido no ledger."""

    def __init__(self, eleicao: Eleicao, secao: str, publica_secao: crypto.ChavePublica, ledger: Ledger):
        self.eleicao = eleicao
        self.secao = secao
        self.publica_secao = publica_secao
        self.ledger = ledger

    @classmethod
    def abrir(
        cls, eleicao: Eleicao, secao: str, publica_secao: crypto.ChavePublica, caminho_db: Path | str
    ) -> Apuracao:
        ledger = Ledger(caminho_db, eleicao.id, secao)
        ap = cls(eleicao, secao, publica_secao, ledger)
        if not ledger.registros():
            ledger.anexar(
                "abertura",
                json.dumps(
                    {
                        "eleicao": eleicao.nome,
                        "eleicao_id": eleicao.id,
                        "secao": secao,
                        "chave_publica_secao": crypto.impressao_digital(publica_secao),
                        "software": f"urna3g {__version__}",
                    },
                    sort_keys=True,
                    ensure_ascii=False,
                ),
            )
        return ap

    # ------------------------------------------------------------------ leitura
    @property
    def encerrada(self) -> bool:
        return self.ledger.meta("encerrada") == "1"

    def processar(self, texto: str) -> Resultado:
        """Processa UM código lido. Nunca levanta exceção por conteúdo ruim: devolve o status."""
        if self.encerrada:
            self.ledger.ocorrencia("apos_encerramento")
            return Resultado(Status.ENCERRADA, "apuração já encerrada; nenhuma cédula é mais aceita")
        try:
            cedula = ler(texto, self.eleicao, self.publica_secao, secao_esperada=self.secao)
        except ErroCedula as e:
            self.ledger.ocorrencia("invalida", str(e))
            return Resultado(Status.INVALIDA, str(e))
        if self.ledger.contem_nonce(cedula.nonce):
            self.ledger.ocorrencia("duplicada", cedula.nonce_hex[:16])
            return Resultado(Status.DUPLICADA, "cédula já apurada", cedula)
        reg = self.ledger.anexar("cedula", cedula.texto(), nonce=cedula.nonce)
        return Resultado(Status.ACEITA, "", cedula, reg.seq)

    def cedulas(self) -> list[Cedula]:
        return [decodificar(r.dados) for r in self.ledger.registros("cedula")]

    def total_cedulas(self) -> int:
        return len(self.ledger.registros("cedula"))

    # ------------------------------------------------------------------ totais
    def totais(self) -> dict[str, Counter[int]]:
        """cargo_id → Counter{numero|BRANCO|NULO: quantidade}, sempre com todos os candidatos."""
        contagem: dict[str, Counter[int]] = {}
        for cargo in self.eleicao.cargos:
            c: Counter[int] = Counter({BRANCO: 0, NULO: 0})
            for cand in self.eleicao.candidatos_do_cargo(cargo.id):
                c[cand.numero] = 0
            contagem[cargo.id] = c
        for cedula in self.cedulas():
            for slot, valor in zip(self.eleicao.slots(), cedula.votos, strict=True):
                if valor not in (BRANCO, NULO) and self.eleicao.candidato(slot.cargo_id, valor) is None:
                    valor = NULO  # número inexistente conta como nulo (registrado em observacoes())
                contagem[slot.cargo_id][valor] += 1
        return contagem

    def observacoes(self) -> list[str]:
        obs: list[str] = []
        inexistentes: Counter[tuple[str, int]] = Counter()
        for cedula in self.cedulas():
            for slot, valor in zip(self.eleicao.slots(), cedula.votos, strict=True):
                if valor not in (BRANCO, NULO) and self.eleicao.candidato(slot.cargo_id, valor) is None:
                    inexistentes[(slot.cargo_id, valor)] += 1
        for (cargo_id, valor), n in sorted(inexistentes.items()):
            obs.append(
                f"{n} voto(s) com número inexistente ({valor}) para {self.eleicao.cargo(cargo_id).nome}, "
                "contabilizado(s) como nulo"
            )
        oc = self.ledger.ocorrencias()
        if oc.get("invalida"):
            obs.append(f"{oc['invalida']} leitura(s) de cédula inválida (outra eleição/seção ou assinatura ruim)")
        if oc.get("duplicada"):
            obs.append(f"{oc['duplicada']} leitura(s) repetida(s) de cédula já apurada")
        return obs

    # ------------------------------------------------------------------ encerramento
    def encerrar(self) -> None:
        if self.encerrada:
            return
        self.ledger.anexar(
            "encerramento",
            json.dumps({"total_cedulas": self.total_cedulas()}, sort_keys=True),
        )
        self.ledger.set_meta("encerrada", "1")

    def gerar_boletim(self, privada_apuracao: crypto.ChavePrivada, encerrar: bool = True) -> dict[str, Any]:
        """Monta e assina o boletim. Por padrão encerra a apuração (nenhuma cédula a mais)."""
        if encerrar:
            self.encerrar()
        totais = self.totais()
        resultados: dict[str, Any] = {}
        for cargo in self.eleicao.cargos:
            votos: dict[str, int] = {}
            legenda: dict[str, str] = {}
            for cand in self.eleicao.candidatos_do_cargo(cargo.id):
                votos[str(cand.numero)] = totais[cargo.id][cand.numero]
                partido = self.eleicao.partido(cand.partido)
                legenda[str(cand.numero)] = f"{cand.nome} ({partido.sigla})" if partido else cand.nome
            votos["branco"] = totais[cargo.id][BRANCO]
            votos["nulo"] = totais[cargo.id][NULO]
            resultados[cargo.id] = {
                "nome": cargo.nome,
                "votos_por_eleitor": cargo.votos_por_eleitor,
                "votos": votos,
                "legenda": legenda,
            }
        self.ledger.verificar()
        corpo: dict[str, Any] = {
            "formato": boletim_mod.FORMATO,
            "software": f"urna3g {__version__}",
            "eleicao_id": self.eleicao.id,
            "eleicao_nome": self.eleicao.nome,
            "secao": self.secao,
            "emitido_em": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_cedulas": self.total_cedulas(),
            "ocorrencias": dict(sorted(self.ledger.ocorrencias().items())),
            "observacoes": self.observacoes(),
            "ledger": {"registros": len(self.ledger.registros()), "hash_final": self.ledger.hash_final},
            "chave_publica_secao": crypto.impressao_digital(self.publica_secao),
            "chave_publica_apuracao": crypto.impressao_digital(privada_apuracao.public_key()),
            "resultados": resultados,
        }
        return boletim_mod.assinar(corpo, privada_apuracao)

    def exportar_csv(self, caminho: Path | str) -> Path:
        caminho = Path(caminho)
        totais = self.totais()
        with caminho.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["cargo", "voto", "descricao", "quantidade"])
            for cargo in self.eleicao.cargos:
                for valor, n in sorted(totais[cargo.id].items(), key=lambda kv: (kv[0] <= 0, kv[0])):
                    w.writerow([cargo.nome, valor, self.eleicao.descrever_voto(cargo.id, valor), n])
        return caminho
