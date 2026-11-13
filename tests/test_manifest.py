import shutil
from dataclasses import replace

import pytest
from conftest import DEMO

from urna3g import BRANCO, NULO, crypto
from urna3g.manifest import (
    Candidato,
    Cargo,
    Eleicao,
    ErroManifesto,
    Partido,
    assinar_manifesto,
    carregar_assinatura,
    salvar_assinatura,
    verificar_manifesto,
)


def test_id_estavel_e_sensivel(eleicao):
    assert len(eleicao.id) == 64
    assert eleicao.id == Eleicao.from_dict(eleicao.to_dict()).id
    assert len(eleicao.id_curto) == 8
    outra = replace(eleicao, nome=eleicao.nome + " (2ª edição)")
    assert outra.id != eleicao.id


def test_roundtrip_json(eleicao, tmp_path):
    p = replace(eleicao).salvar(tmp_path / "e.json")  # cópia: salvar() ajusta base_dir
    e2 = Eleicao.carregar(p)
    assert e2 == eleicao
    assert e2.base_dir == tmp_path


def test_slots_e_digitos(eleicao):
    slots = eleicao.slots()
    assert [s.cargo_id for s in slots] == ["presidente", "senador", "deputado"]
    assert [s.posicao for s in slots] == [0, 1, 2]
    assert eleicao.digitos("presidente") == 2
    cargos = [replace(c, votos_por_eleitor=2) if c.id == "senador" else c for c in eleicao.cargos]
    dupla = replace(eleicao, cargos=cargos)
    assert [(s.cargo_id, s.indice) for s in dupla.slots()] == [
        ("presidente", 0), ("senador", 0), ("senador", 1), ("deputado", 0)
    ]


def test_descrever_voto(eleicao):
    assert eleicao.descrever_voto("presidente", BRANCO) == "Branco"
    assert eleicao.descrever_voto("presidente", NULO) == "Nulo"
    assert eleicao.descrever_voto("presidente", 99) == "99 - Cascão (TM)"
    assert "inexistente" in eleicao.descrever_voto("presidente", 12)


@pytest.mark.parametrize(
    "mutacao, trecho",
    [
        (lambda e: replace(e, cargos=e.cargos + [Cargo("presidente", "Outro")]), "duplicado"),
        (lambda e: replace(e, cargos=e.cargos + [Cargo("Cargo Ruim!", "X")]), "id de cargo inválido"),
        (lambda e: replace(e, cargos=[]), "sem cargos"),
        (lambda e: replace(e, candidatos=e.candidatos + [Candidato(11, "Z", "vereador", 92)]), "cargo inexistente"),
        (lambda e: replace(e, candidatos=e.candidatos + [Candidato(11, "Z", "presidente", 10)]), "partido inexistente"),
        (lambda e: replace(e, candidatos=e.candidatos + [Candidato(99, "Z", "presidente", 94)]), "repetido"),
        (
            lambda e: replace(
                e,
                cargos=[replace(c, digitos=2) for c in e.cargos],
                candidatos=e.candidatos + [Candidato(1234, "Z", "presidente", 94)],
            ),
            "excede",
        ),
        (lambda e: replace(e, partidos=e.partidos + [Partido(92, "Dup", "DP")]), "partido duplicado"),
        (lambda e: replace(e, secoes=["001", "sec ao"]), "seção inválido"),
        (lambda e: replace(e, formato=7), "formato"),
    ],
)
def test_validacoes(eleicao, mutacao, trecho):
    with pytest.raises(ErroManifesto, match=trecho):
        mutacao(eleicao).validar()


def test_assinatura_do_manifesto(eleicao, chave_autoridade, tmp_path):
    priv, pub = chave_autoridade
    sig = assinar_manifesto(eleicao, priv)
    assert verificar_manifesto(eleicao, pub, sig)
    p = salvar_assinatura(tmp_path / "e.sig", sig)
    assert carregar_assinatura(p) == sig
    adulterada = replace(eleicao, candidatos=eleicao.candidatos[:-1])
    assert not verificar_manifesto(adulterada, pub, sig)
    assert not verificar_manifesto(eleicao, crypto.gerar_chave().public_key(), sig)


def test_hashes_de_fotos(eleicao, tmp_path):
    destino = tmp_path / "eleicao"
    shutil.copytree(DEMO.parent, destino)
    e = Eleicao.carregar(destino / "eleicao.json").preencher_hashes_fotos()
    assert all(c.foto_sha256 for c in e.candidatos)
    e.salvar(destino / "eleicao.json")
    e = Eleicao.carregar(destino / "eleicao.json")
    e.validar(verificar_fotos=True)
    # troca a foto de um candidato → detectado
    foto = destino / e.candidatos[0].foto
    foto.write_bytes(b"\x89PNG adulterada")
    with pytest.raises(ErroManifesto, match="foto alterada"):
        e.validar(verificar_fotos=True)
    foto.unlink()
    with pytest.raises(ErroManifesto, match="não encontrada"):
        e.validar(verificar_fotos=True)
