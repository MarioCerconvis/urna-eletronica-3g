"""Convenções de arquivos (chaves, manifesto) compartilhadas por CLI e GUI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from urna3g import crypto
from urna3g.manifest import Eleicao, ErroManifesto, carregar_assinatura, verificar_manifesto


@dataclass(frozen=True)
class Chaves:
    """Diretório de chaves. Convenção de nomes::

        autoridade.key / autoridade.pub        assina o manifesto (fica OFFLINE, com a comissão)
        secao-<ID>.key / secao-<ID>.pub        assina cédulas (a .key só existe nas urnas da seção)
        apuracao-<ID>.key / apuracao-<ID>.pub  assina o boletim (a .key só existe no apurador)
    """

    dir: Path

    def autoridade_priv(self) -> Path:
        return self.dir / "autoridade.key"

    def autoridade_pub(self) -> Path:
        return self.dir / "autoridade.pub"

    def secao_priv(self, secao: str) -> Path:
        return self.dir / f"secao-{secao}.key"

    def secao_pub(self, secao: str) -> Path:
        return self.dir / f"secao-{secao}.pub"

    def apuracao_priv(self, secao: str) -> Path:
        return self.dir / f"apuracao-{secao}.key"

    def apuracao_pub(self, secao: str) -> Path:
        return self.dir / f"apuracao-{secao}.pub"


def carregar_eleicao(
    manifesto: Path | str,
    autoridade_pub: Path | str | None = None,
    verificar_fotos: bool = True,
    exigir_assinatura: bool = False,
) -> tuple[Eleicao, str]:
    """Carrega + valida o manifesto e confere ``eleicao.sig`` se houver chave da autoridade.

    Retorna (eleicao, situacao) onde situacao ∈ {"assinado", "sem_assinatura", "sem_chave"}.
    """
    manifesto = Path(manifesto)
    eleicao = Eleicao.carregar(manifesto)
    eleicao.validar(verificar_fotos=verificar_fotos)
    sig_path = manifesto.with_suffix(".sig")
    if autoridade_pub is not None and Path(autoridade_pub).is_file():
        if not sig_path.is_file():
            if exigir_assinatura:
                raise ErroManifesto(f"manifesto sem assinatura ({sig_path.name} não encontrado)")
            return eleicao, "sem_assinatura"
        pub = crypto.carregar_publica(autoridade_pub)
        if not verificar_manifesto(eleicao, pub, carregar_assinatura(sig_path)):
            raise ErroManifesto("assinatura do manifesto NÃO confere com a chave da autoridade")
        return eleicao, "assinado"
    if exigir_assinatura:
        raise ErroManifesto("chave pública da autoridade não informada/encontrada")
    return eleicao, "sem_chave"
