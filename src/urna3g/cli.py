"""Linha de comando ``urna3g``: tudo que a GUI faz, de forma scriptável e testável."""

from __future__ import annotations

import argparse
import getpass
import json
import random
import shutil
import sys
from pathlib import Path
from typing import Any

from urna3g import BRANCO, NULO, __version__, crypto
from urna3g import boletim as bmod
from urna3g.ballot import ErroCedula, descrever, emitir, ler
from urna3g.config import Chaves, carregar_eleicao
from urna3g.ledger import ErroLedger, Ledger
from urna3g.manifest import (
    Eleicao,
    ErroManifesto,
    assinar_manifesto,
    salvar_assinatura,
)
from urna3g.render import ErroImpressao, imprimir, renderizar_boletim_pdf, renderizar_cedula_pdf
from urna3g.tally import Apuracao


class ErroCli(Exception):
    pass


def _senha(args: argparse.Namespace, confirmar: bool = False) -> str | None:
    if not getattr(args, "senha", False):
        return None
    s = getpass.getpass("Senha da chave privada: ")
    if confirmar and getpass.getpass("Confirme a senha: ") != s:
        raise ErroCli("as senhas não coincidem")
    return s


def _eleicao(args: argparse.Namespace) -> Eleicao:
    pub = getattr(args, "autoridade", None)
    eleicao, situacao = carregar_eleicao(args.eleicao, pub, verificar_fotos=not getattr(args, "sem_fotos", False))
    if situacao == "sem_assinatura":
        print("aviso: manifesto sem assinatura da autoridade", file=sys.stderr)
    return eleicao


# ----------------------------------------------------------------------------- chaves

def cmd_chaves_gerar(args: argparse.Namespace) -> int:
    ch = Chaves(Path(args.saida))
    pares: list[tuple[Path, Path, str]] = []
    if args.autoridade:
        pares.append((ch.autoridade_priv(), ch.autoridade_pub(), "autoridade"))
    for secao in args.secao or []:
        pares.append((ch.secao_priv(secao), ch.secao_pub(secao), f"urna da seção {secao}"))
        pares.append((ch.apuracao_priv(secao), ch.apuracao_pub(secao), f"apuração da seção {secao}"))
    if not pares:
        raise ErroCli("informe --secao ID [ID...] e/ou --autoridade")
    for priv_p, _, _ in pares:
        if priv_p.exists() and not args.forcar:
            raise ErroCli(f"{priv_p} já existe (use --forcar para sobrescrever — isso invalida cédulas já emitidas!)")
    senha = _senha(args, confirmar=True)
    for priv_p, pub_p, papel in pares:
        priv = crypto.gerar_chave()
        crypto.salvar_privada(priv_p, priv, senha)
        crypto.salvar_publica(pub_p, priv.public_key())
        fp = crypto.formatar_impressao(crypto.impressao_digital(priv.public_key()))
        print(f"[{papel}]\n  privada: {priv_p}\n  pública: {pub_p}\n  impressão digital: {fp}")
    print("\nATENÇÃO: copie para cada máquina SOMENTE as chaves do seu papel (ver docs/05-implantacao-lab.md).")
    return 0


def cmd_chaves_info(args: argparse.Namespace) -> int:
    p = Path(args.arquivo)
    if p.suffix == ".key":
        pub = crypto.carregar_privada(p, _senha(args)).public_key()
    else:
        pub = crypto.carregar_publica(p)
    print(crypto.formatar_impressao(crypto.impressao_digital(pub)))
    return 0


# ----------------------------------------------------------------------------- eleição

def cmd_eleicao_validar(args: argparse.Namespace) -> int:
    e = Eleicao.carregar(args.manifesto)
    e.validar(verificar_fotos=args.fotos)
    print(f"OK  {e.nome}  id={e.id}")
    print(f"    {len(e.cargos)} cargo(s), {len(e.partidos)} partido(s), {len(e.candidatos)} candidato(s), "
          f"{len(e.slots())} voto(s) por cédula")
    return 0


def cmd_eleicao_id(args: argparse.Namespace) -> int:
    print(Eleicao.carregar(args.manifesto).id)
    return 0


def cmd_eleicao_assinar(args: argparse.Namespace) -> int:
    manifesto = Path(args.manifesto)
    e = Eleicao.carregar(manifesto)
    e.validar(verificar_fotos=True)
    e = e.preencher_hashes_fotos()
    e.salvar(manifesto)  # regrava com os hashes das fotos
    priv = crypto.carregar_privada(args.chave, _senha(args))
    sig_path = salvar_assinatura(manifesto.with_suffix(".sig"), assinar_manifesto(e, priv))
    print(f"manifesto assinado: {sig_path}\nid da eleição: {e.id}")
    return 0


def cmd_eleicao_verificar(args: argparse.Namespace) -> int:
    e, situacao = carregar_eleicao(args.manifesto, args.pub, verificar_fotos=True, exigir_assinatura=True)
    print(f"assinatura válida ({situacao}); id={e.id}")
    return 0


# ----------------------------------------------------------------------------- cédula

def _parse_votos(texto: str, eleicao: Eleicao) -> list[int]:
    valores: list[int] = []
    for parte in texto.split(","):
        parte = parte.strip().lower()
        if parte in ("b", "branco"):
            valores.append(BRANCO)
        elif parte in ("n", "nulo"):
            valores.append(NULO)
        else:
            try:
                valores.append(int(parte))
            except ValueError as e:
                raise ErroCli(f"voto inválido: {parte!r}") from e
    if len(valores) != len(eleicao.slots()):
        raise ErroCli(f"a eleição tem {len(eleicao.slots())} voto(s) por cédula; recebidos {len(valores)}")
    return valores


def cmd_cedula_emitir(args: argparse.Namespace) -> int:
    eleicao = _eleicao(args)
    priv = crypto.carregar_privada(args.chave, _senha(args))
    cedula = emitir(eleicao, args.secao, _parse_votos(args.votos, eleicao), priv)
    print(cedula.texto())
    if args.pdf:
        p = renderizar_cedula_pdf(cedula, eleicao, args.pdf)
        print(f"pdf: {p}", file=sys.stderr)
        if args.imprimir:
            imprimir(p, args.impressora)
    return 0


def cmd_cedula_ler(args: argparse.Namespace) -> int:
    eleicao = _eleicao(args)
    pub = crypto.carregar_publica(args.pub)
    textos = [args.texto] if args.texto else [ln for ln in sys.stdin.read().splitlines() if ln.strip()]
    status = 0
    for t in textos:
        try:
            c = ler(t, eleicao, pub, secao_esperada=args.secao)
        except ErroCedula as e:
            print(f"INVÁLIDA: {e}")
            status = 1
            continue
        print(f"VÁLIDA  seção {c.secao}  id {c.nonce_hex[:16]}")
        for titulo, desc in descrever(c, eleicao):
            print(f"  {titulo}: {desc}")
    return status


# ----------------------------------------------------------------------------- apuração

def _apuracao(args: argparse.Namespace) -> tuple[Eleicao, Apuracao]:
    eleicao = _eleicao(args)
    pub = crypto.carregar_publica(args.pub)
    return eleicao, Apuracao.abrir(eleicao, args.secao, pub, args.db)


def _textos_de_imagens(caminhos: list[str]) -> list[str]:
    try:
        from urna3g.scanner import decodificar_imagem
    except ImportError as e:  # pragma: no cover
        raise ErroCli("leitura de imagens requer: pip install 'urna3g[camera]'") from e
    textos: list[str] = []
    for c in caminhos:
        textos.extend(decodificar_imagem(c))
    return textos


def cmd_apurar_ler(args: argparse.Namespace) -> int:
    eleicao, ap = _apuracao(args)
    textos = list(args.textos)
    if args.imagem:
        textos += _textos_de_imagens(args.imagem)
    if not textos and not sys.stdin.isatty():
        textos = [ln for ln in sys.stdin.read().splitlines() if ln.strip()]
    for t in textos:
        r = ap.processar(t)
        print(f"{r.status.value.upper():10s} {r.motivo}")
    print(f"total apurado: {ap.total_cedulas()}  hash do ledger: {ap.ledger.hash_final[:32]}…")
    return 0


def _imprimir_totais(eleicao: Eleicao, ap: Apuracao) -> None:
    totais = ap.totais()
    for cargo in eleicao.cargos:
        print(f"\n{cargo.nome}")
        for valor, n in sorted(totais[cargo.id].items(), key=lambda kv: (kv[0] <= 0, kv[0])):
            print(f"  {eleicao.descrever_voto(cargo.id, valor):<40} {n:>5}")
    print(f"\ncédulas: {ap.total_cedulas()}   ocorrências: {dict(ap.ledger.ocorrencias())}")
    for o in ap.observacoes():
        print(f"  * {o}")


def cmd_apurar_totais(args: argparse.Namespace) -> int:
    eleicao, ap = _apuracao(args)
    _imprimir_totais(eleicao, ap)
    return 0


def cmd_apurar_boletim(args: argparse.Namespace) -> int:
    eleicao, ap = _apuracao(args)
    priv = crypto.carregar_privada(args.chave_apuracao, _senha(args))
    b = ap.gerar_boletim(priv, encerrar=not args.nao_encerrar)
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    base = saida / f"boletim-{args.secao}"
    bmod.salvar(b, base.with_suffix(".json"))
    renderizar_boletim_pdf(b, base.with_suffix(".pdf"))
    ap.exportar_csv(base.with_suffix(".csv"))
    _imprimir_totais(eleicao, ap)
    print(f"\nboletim: {base}.json / .pdf / .csv\nhash do boletim: {bmod.hash_boletim(b)}")
    if args.imprimir:
        imprimir(base.with_suffix(".pdf"), args.impressora)
    return 0


def cmd_apurar_verificar_ledger(args: argparse.Namespace) -> int:
    eleicao = _eleicao(args)
    ledger = Ledger(args.db, eleicao.id, args.secao)
    n = ledger.verificar()
    print(f"ledger íntegro: {n} registro(s), hash final {ledger.hash_final}")
    return 0


def cmd_boletim_verificar(args: argparse.Namespace) -> int:
    b = bmod.carregar(args.arquivo)
    bmod.verificar(b, crypto.carregar_publica(args.pub))
    print(f"assinatura válida  seção {b['secao']}  cédulas {b['total_cedulas']}  hash {bmod.hash_boletim(b)}")
    return 0


# ----------------------------------------------------------------------------- servidor / gui

def cmd_servidor(args: argparse.Namespace) -> int:
    try:
        import uvicorn

        from urna3g.server.app import criar_app
    except ImportError as e:
        raise ErroCli("servidor requer: pip install 'urna3g[servidor]'") from e
    uvicorn.run(criar_app(Path(args.dados)), host=args.host, port=args.porta, log_level="info")
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    try:
        from urna3g.gui import executar
    except ImportError as e:
        raise ErroCli("a interface gráfica requer: pip install 'urna3g[gui]'") from e
    return executar(args)


# ----------------------------------------------------------------------------- demo

def cmd_demo(args: argparse.Namespace) -> int:
    """Simula a eleição inteira em disco: chaves → manifesto assinado → cédulas → apuração → boletim."""
    raiz = Path(__file__).resolve().parents[2] / "exemplos" / "eleicao-demo"
    saida = Path(args.saida)
    if saida.exists() and any(saida.iterdir()):
        raise ErroCli(f"{saida} não está vazio")
    shutil.copytree(raiz, saida / "eleicao")
    ch = Chaves(saida / "chaves")
    secao = "001"
    chaves: dict[str, crypto.ChavePrivada] = {}
    for nome, priv_p, pub_p in (
        ("autoridade", ch.autoridade_priv(), ch.autoridade_pub()),
        ("secao", ch.secao_priv(secao), ch.secao_pub(secao)),
        ("apuracao", ch.apuracao_priv(secao), ch.apuracao_pub(secao)),
    ):
        chaves[nome] = crypto.gerar_chave()
        crypto.salvar_privada(priv_p, chaves[nome])
        crypto.salvar_publica(pub_p, chaves[nome].public_key())
    manifesto = saida / "eleicao" / "eleicao.json"
    e = Eleicao.carregar(manifesto).preencher_hashes_fotos()
    e.salvar(manifesto)
    salvar_assinatura(manifesto.with_suffix(".sig"), assinar_manifesto(e, chaves["autoridade"]))
    eleicao, situacao = carregar_eleicao(manifesto, ch.autoridade_pub(), exigir_assinatura=True)
    print(f"1. manifesto {situacao}: {eleicao.nome}  id={eleicao.id[:16]}…")

    rng = random.Random(args.semente)  # noqa: S311 — simulação, não é uso criptográfico
    (saida / "cedulas").mkdir()
    textos: list[str] = []
    for i in range(args.eleitores):
        votos = []
        for slot in eleicao.slots():
            opcoes = [c.numero for c in eleicao.candidatos_do_cargo(slot.cargo_id)] * 4 + [BRANCO, NULO]
            votos.append(rng.choice(opcoes))
        c = emitir(eleicao, secao, votos, chaves["secao"])
        if i < args.pdfs:
            renderizar_cedula_pdf(c, eleicao, saida / "cedulas" / f"cedula-{i + 1:03d}.pdf")
        textos.append(c.texto())
    (saida / "cedulas" / "qrcodes.txt").write_text("\n".join(textos) + "\n")
    n_pdf = min(args.pdfs, len(textos))
    print(f"2. {len(textos)} cédulas emitidas e assinadas ({n_pdf} em PDF em {saida / 'cedulas'})")

    ap = Apuracao.abrir(eleicao, secao, chaves["secao"].public_key(), saida / f"apuracao-{secao}.db")
    aceitas = sum(ap.processar(t).aceita for t in textos)
    dup = ap.processar(textos[0]).status.value
    falsa = emitir(eleicao, secao, [BRANCO] * len(eleicao.slots()), crypto.gerar_chave())
    forjada = ap.processar(falsa.texto())
    print(f"3. apuração: {aceitas} aceitas; releitura → {dup}; cédula forjada → {forjada.status.value}")
    try:
        from urna3g.qr import gerar_qr
        from urna3g.scanner import decodificar_pil

        lidos = sum(decodificar_pil(gerar_qr(t, escala=5, borda=3)) == [t] for t in textos[:5])
        print(f"   auto-teste de QR (OpenCV): {lidos}/5 códigos decodificados")
    except ImportError:
        print("   (OpenCV ausente: auto-teste de QR pulado)")

    b = ap.gerar_boletim(chaves["apuracao"])
    base = saida / f"boletim-{secao}"
    bmod.salvar(b, base.with_suffix(".json"))
    renderizar_boletim_pdf(b, base.with_suffix(".pdf"))
    ap.exportar_csv(base.with_suffix(".csv"))
    bmod.verificar(b, chaves["apuracao"].public_key())
    print(f"4. boletim assinado e verificado: {base}.json  hash {bmod.hash_boletim(b)[:16]}…")
    print(f"   ledger íntegro ({ap.ledger.verificar()} registros), hash final {ap.ledger.hash_final[:16]}…")
    _imprimir_totais(eleicao, ap)
    return 0


# ----------------------------------------------------------------------------- parser

def _add_eleicao_args(p: argparse.ArgumentParser, pub_secao: bool = False, secao: bool = True) -> None:
    p.add_argument("--eleicao", required=True, type=Path, metavar="eleicao.json", help="manifesto da eleição")
    p.add_argument("--autoridade", type=Path, metavar="autoridade.pub", help="chave pública que assinou o manifesto")
    p.add_argument("--sem-fotos", action="store_true", help="não exigir/verificar os arquivos de foto")
    if secao:
        p.add_argument("--secao", required=True, help="identificador da seção eleitoral")
    if pub_secao:
        p.add_argument("--pub", required=True, type=Path, metavar="secao-ID.pub", help="chave pública da urna da seção")


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="urna3g", description="Urna eletrônica de 3ª geração (UFABC/LAOB)")
    parser.add_argument("--version", action="version", version=f"urna3g {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # chaves
    p = sub.add_parser("chaves", help="gerar e inspecionar chaves")
    s = p.add_subparsers(dest="sub", required=True)
    g = s.add_parser("gerar", help="gera chaves da autoridade e/ou de seções (urna + apuração)")
    g.add_argument("--secao", nargs="*", metavar="ID")
    g.add_argument("--autoridade", action="store_true")
    g.add_argument("--saida", default="chaves", type=Path)
    g.add_argument("--senha", action="store_true", help="proteger as chaves privadas com senha")
    g.add_argument("--forcar", action="store_true")
    g.set_defaults(func=cmd_chaves_gerar)
    i = s.add_parser("info", help="impressão digital de uma chave (.pub ou .key)")
    i.add_argument("arquivo", type=Path)
    i.add_argument("--senha", action="store_true")
    i.set_defaults(func=cmd_chaves_info)

    # eleição
    p = sub.add_parser("eleicao", help="validar, identificar e assinar o manifesto")
    s = p.add_subparsers(dest="sub", required=True)
    v = s.add_parser("validar")
    v.add_argument("manifesto", type=Path)
    v.add_argument("--fotos", action="store_true", help="também verificar arquivos/hashes das fotos")
    v.set_defaults(func=cmd_eleicao_validar)
    x = s.add_parser("id")
    x.add_argument("manifesto", type=Path)
    x.set_defaults(func=cmd_eleicao_id)
    a = s.add_parser("assinar", help="preenche hashes das fotos e grava eleicao.sig")
    a.add_argument("manifesto", type=Path)
    a.add_argument("--chave", required=True, type=Path, metavar="autoridade.key")
    a.add_argument("--senha", action="store_true")
    a.set_defaults(func=cmd_eleicao_assinar)
    vf = s.add_parser("verificar")
    vf.add_argument("manifesto", type=Path)
    vf.add_argument("--pub", required=True, type=Path, metavar="autoridade.pub")
    vf.set_defaults(func=cmd_eleicao_verificar)

    # cédula
    p = sub.add_parser("cedula", help="emitir (urna) e ler (verificação) cédulas")
    s = p.add_subparsers(dest="sub", required=True)
    em = s.add_parser("emitir")
    _add_eleicao_args(em)
    em.add_argument("--chave", required=True, type=Path, metavar="secao-ID.key")
    em.add_argument("--senha", action="store_true")
    em.add_argument("--votos", required=True, help='ex.: "99,branco,82" (um por slot, em ordem)')
    em.add_argument("--pdf", type=Path)
    em.add_argument("--imprimir", action="store_true")
    em.add_argument("--impressora")
    em.set_defaults(func=cmd_cedula_emitir)
    le = s.add_parser("ler")
    _add_eleicao_args(le, pub_secao=True, secao=False)
    le.add_argument("--secao", help="exigir que a cédula seja desta seção")
    le.add_argument("texto", nargs="?", help="conteúdo do QR (ou via stdin, um por linha)")
    le.set_defaults(func=cmd_cedula_ler)

    # apuração
    p = sub.add_parser("apurar", help="apuração de uma seção (ledger + boletim)")
    s = p.add_subparsers(dest="sub", required=True)
    for nome, func, ajuda in (
        ("ler", cmd_apurar_ler, "processa códigos QR (argumentos, stdin ou --imagem)"),
        ("totais", cmd_apurar_totais, "mostra os totais atuais"),
        ("boletim", cmd_apurar_boletim, "encerra e emite o boletim assinado (json/pdf/csv)"),
    ):
        q = s.add_parser(nome, help=ajuda)
        _add_eleicao_args(q, pub_secao=True)
        q.add_argument("--db", required=True, type=Path, help="arquivo SQLite do ledger da seção")
        if nome == "ler":
            q.add_argument("textos", nargs="*")
            q.add_argument("--imagem", nargs="*", help="arquivo(s) de imagem com QR (requer OpenCV)")
        if nome == "boletim":
            q.add_argument("--chave-apuracao", required=True, type=Path, metavar="apuracao-ID.key")
            q.add_argument("--senha", action="store_true")
            q.add_argument("--saida", default="saida", type=Path)
            q.add_argument("--nao-encerrar", action="store_true", help="boletim parcial (não encerra a apuração)")
            q.add_argument("--imprimir", action="store_true")
            q.add_argument("--impressora")
        q.set_defaults(func=func)
    vl = s.add_parser("verificar-ledger", help="recalcula a cadeia de hashes do ledger")
    _add_eleicao_args(vl)
    vl.add_argument("--db", required=True, type=Path)
    vl.set_defaults(func=cmd_apurar_verificar_ledger)

    # boletim
    p = sub.add_parser("boletim", help="verificar boletins")
    s = p.add_subparsers(dest="sub", required=True)
    bv = s.add_parser("verificar")
    bv.add_argument("arquivo", type=Path)
    bv.add_argument("--pub", required=True, type=Path, metavar="apuracao-ID.pub")
    bv.set_defaults(func=cmd_boletim_verificar)

    # servidor
    p = sub.add_parser("servidor", help="mural público + recepção de boletins (FastAPI)")
    p.add_argument("--dados", default="dados", type=Path, help="diretório com eleicao.json, eleicao.sig e chaves/")
    p.add_argument("--host", default="0.0.0.0")  # noqa: S104 — serviço de LAN por definição
    p.add_argument("--porta", default=8000, type=int)
    p.set_defaults(func=cmd_servidor)

    # gui
    p = sub.add_parser("gui", help="interfaces gráficas (PySide6)")
    p.add_argument("modulo", choices=["votar", "verificar", "apurar", "setup-eleicao", "setup-urna"])
    p.add_argument("--eleicao", type=Path, metavar="eleicao.json")
    p.add_argument("--secao")
    p.add_argument("--chaves", type=Path, default=Path("chaves"), help="diretório de chaves (ver convenção)")
    p.add_argument("--saida", type=Path, default=Path("saida"), help="PDFs, ledger e boletins")
    p.add_argument("--impressora", help="nome da fila CUPS (padrão: impressora padrão)")
    p.add_argument("--sem-impressora", action="store_true", help="só gera PDF (testes)")
    p.add_argument("--camera", type=int, metavar="N", help="usar webcam N (OpenCV) em vez de leitor USB")
    p.add_argument("--janela", action="store_true", help="não abrir em tela cheia")
    p.add_argument("--senha", action="store_true")
    p.add_argument("--sem-fotos", action="store_true")
    p.set_defaults(func=cmd_gui)

    # demo
    p = sub.add_parser("demo", help="simula uma eleição completa em disco")
    p.add_argument("--saida", default="demo-urna", type=Path)
    p.add_argument("--eleitores", default=40, type=int)
    p.add_argument("--pdfs", default=5, type=int, help="quantas cédulas também gerar em PDF")
    p.add_argument("--semente", default=None, type=int)
    p.set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (ErroCli, ErroManifesto, ErroCedula, ErroLedger, ErroImpressao, crypto.ErroChave, bmod.ErroBoletim) as e:
        print(f"erro: {e}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())


def _json(obj: Any) -> str:  # utilitário pequeno usado em testes/depuração
    return json.dumps(obj, indent=2, ensure_ascii=False)
