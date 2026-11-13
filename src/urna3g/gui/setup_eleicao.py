"""Setup de Eleição — cadastro de cargos, partidos/chapas e candidatos; grava o manifesto JSON."""

from __future__ import annotations

import argparse
import re
import shutil
import unicodedata
from dataclasses import replace
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QSpinBox,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from urna3g.gui.comum import JanelaBase, botao, rotulo
from urna3g.manifest import Candidato, Cargo, Eleicao, ErroManifesto, Partido


def slug(texto: str) -> str:
    base = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")
    return base[:32] or "cargo"


class JanelaSetupEleicao(JanelaBase):
    def __init__(self, caminho: Path):
        super().__init__("Setup de Eleição")
        self.caminho = Path(caminho)
        if self.caminho.is_file():
            self.eleicao = Eleicao.carregar(self.caminho)
        else:
            self.eleicao = Eleicao(nome="Nova eleição", base_dir=self.caminho.parent)
        self.fotos_pendentes: dict[str, Path] = {}  # destino relativo → origem absoluta

        self.abas = QTabWidget()
        self.abas.addTab(self._aba_eleicao(), "Eleição")
        self.abas.addTab(self._aba_cargos(), "Cargos")
        self.abas.addTab(self._aba_partidos(), "Partidos / Chapas")
        self.abas.addTab(self._aba_candidatos(), "Candidatos")
        self.abas.addTab(self._aba_resumo(), "Resumo e gravação")
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(rotulo("Setup de Eleição", "titulo"))
        lay.addWidget(self.abas, 1)
        self.centralizar(w)
        self._atualizar_listas()

    @classmethod
    def de_args(cls, args: argparse.Namespace) -> JanelaSetupEleicao:
        caminho = Path(args.eleicao) if args.eleicao else Path(args.saida) / "eleicao" / "eleicao.json"
        return cls(caminho)

    # ------------------------------------------------------------------ abas
    def _aba_eleicao(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        self.campo_nome = QLineEdit(self.eleicao.nome)
        self.campo_data = QLineEdit(self.eleicao.data)
        self.campo_data.setPlaceholderText("AAAA-MM-DD")
        self.campo_secoes = QLineEdit(", ".join(self.eleicao.secoes))
        self.campo_secoes.setPlaceholderText("ex.: 001, 002")
        form.addRow("Nome da eleição", self.campo_nome)
        form.addRow("Data", self.campo_data)
        form.addRow("Seções (separadas por vírgula)", self.campo_secoes)
        form.addRow(rotulo(f"Arquivo: {self.caminho}", "dica"))
        return w

    def _aba_cargos(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        form = QFormLayout()
        self.cargo_nome = QLineEdit()
        self.cargo_votos = QSpinBox()
        self.cargo_votos.setRange(1, 20)
        self.cargo_digitos = QSpinBox()
        self.cargo_digitos.setRange(0, 6)
        self.cargo_digitos.setSpecialValueText("automático")
        form.addRow("Nome do cargo", self.cargo_nome)
        form.addRow("Votos por eleitor", self.cargo_votos)
        form.addRow("Dígitos (0 = automático)", self.cargo_digitos)
        b = botao("CADASTRAR CARGO")
        b.clicked.connect(self.cadastrar_cargo)
        form.addRow(b)
        lay.addLayout(form, 1)
        self.lista_cargos, col = self._lista_com_remover(self.remover_cargo)
        lay.addLayout(col, 1)
        return w

    def _aba_partidos(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        form = QFormLayout()
        self.partido_numero = QSpinBox()
        self.partido_numero.setRange(1, 99999)
        self.partido_nome = QLineEdit()
        self.partido_sigla = QLineEdit()
        self.partido_presidente = QLineEdit()
        self.partido_foto = QLineEdit()
        self.partido_foto.setReadOnly(True)
        bf = botao("ESCOLHER FOTO")
        bf.clicked.connect(lambda: self._escolher_foto(self.partido_foto))
        form.addRow("Número", self.partido_numero)
        form.addRow("Nome", self.partido_nome)
        form.addRow("Sigla", self.partido_sigla)
        form.addRow("Presidente", self.partido_presidente)
        form.addRow("Foto/símbolo", self.partido_foto)
        form.addRow(bf)
        b = botao("CADASTRAR PARTIDO")
        b.clicked.connect(self.cadastrar_partido)
        form.addRow(b)
        lay.addLayout(form, 1)
        self.lista_partidos, col = self._lista_com_remover(self.remover_partido)
        lay.addLayout(col, 1)
        return w

    def _aba_candidatos(self) -> QWidget:
        w = QWidget()
        lay = QHBoxLayout(w)
        form = QFormLayout()
        self.cand_numero = QSpinBox()
        self.cand_numero.setRange(1, 999999)
        self.cand_nome = QLineEdit()
        self.cand_titulo = QLineEdit()
        self.cand_cargo = QComboBox()
        self.cand_partido = QComboBox()
        self.cand_foto = QLineEdit()
        self.cand_foto.setReadOnly(True)
        bf = botao("ESCOLHER FOTO")
        bf.clicked.connect(lambda: self._escolher_foto(self.cand_foto))
        form.addRow("Número", self.cand_numero)
        form.addRow("Nome", self.cand_nome)
        form.addRow("Título de eleitor (opcional)", self.cand_titulo)
        form.addRow("Cargo", self.cand_cargo)
        form.addRow("Partido / chapa", self.cand_partido)
        form.addRow("Foto", self.cand_foto)
        form.addRow(bf)
        b = botao("CADASTRAR CANDIDATO")
        b.clicked.connect(self.cadastrar_candidato)
        form.addRow(b)
        lay.addLayout(form, 1)
        self.lista_candidatos, col = self._lista_com_remover(self.remover_candidato)
        lay.addLayout(col, 1)
        return w

    def _aba_resumo(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.resumo = QTextEdit()
        self.resumo.setReadOnly(True)
        lay.addWidget(self.resumo, 1)
        linha = QHBoxLayout()
        b1 = botao("VALIDAR")
        b1.clicked.connect(self.validar)
        b2 = botao("SALVAR", "confirma")
        b2.clicked.connect(self.salvar)
        b3 = botao("APAGAR ELEIÇÃO", "perigo")
        b3.clicked.connect(self.apagar)
        b4 = botao("SAIR")
        b4.clicked.connect(self.close)
        for b in (b1, b2, b3):
            linha.addWidget(b)
        linha.addStretch()
        linha.addWidget(b4)
        lay.addLayout(linha)
        lay.addWidget(rotulo("Após salvar, assine o manifesto com a chave da autoridade: "
                             "urna3g eleicao assinar eleicao.json --chave chaves/autoridade.key", "dica"))
        return w

    def _lista_com_remover(self, acao) -> tuple[QListWidget, QVBoxLayout]:  # noqa: ANN001
        lista = QListWidget()
        col = QVBoxLayout()
        col.addWidget(lista, 1)
        b = botao("REMOVER SELECIONADO", "perigo")
        b.clicked.connect(acao)
        col.addWidget(b)
        return lista, col

    # ------------------------------------------------------------------ ações
    def _escolher_foto(self, campo: QLineEdit) -> None:
        nome, _ = QFileDialog.getOpenFileName(self, "Escolher foto", "", "Imagens (*.png *.jpg *.jpeg *.gif *.bmp)")
        if nome:
            campo.setText(nome)

    def _registrar_foto(self, origem: str) -> str | None:
        """Agenda a cópia da foto para <base>/fotos/ e devolve o caminho relativo."""
        if not origem:
            return None
        src = Path(origem)
        base = self.caminho.parent
        try:
            return str(src.resolve().relative_to(base.resolve()))
        except ValueError:
            pass
        destino = f"fotos/{slug(src.stem)}{src.suffix.lower()}"
        self.fotos_pendentes[destino] = src
        return destino

    def _sincronizar_cabecalho(self) -> None:
        secoes = [s.strip() for s in self.campo_secoes.text().split(",") if s.strip()]
        self.eleicao = replace(
            self.eleicao, nome=self.campo_nome.text().strip(), data=self.campo_data.text().strip(), secoes=secoes
        )

    def cadastrar_cargo(self) -> None:
        nome = self.cargo_nome.text().strip()
        if not nome:
            return self.erro("Cargo", "Informe o nome do cargo.")
        digitos = self.cargo_digitos.value() or None
        cargo = Cargo(slug(nome), nome, self.cargo_votos.value(), digitos)
        if any(c.id == cargo.id for c in self.eleicao.cargos):
            return self.erro("Cargo", f"Já existe um cargo com o id {cargo.id!r}.")
        self.eleicao = replace(self.eleicao, cargos=[*self.eleicao.cargos, cargo])
        self.cargo_nome.clear()
        self._atualizar_listas()
        return None

    def cadastrar_partido(self) -> None:
        if not self.partido_nome.text().strip() or not self.partido_sigla.text().strip():
            return self.erro("Partido", "Informe nome e sigla.")
        p = Partido(
            self.partido_numero.value(),
            self.partido_nome.text().strip(),
            self.partido_sigla.text().strip(),
            self.partido_presidente.text().strip(),
            self._registrar_foto(self.partido_foto.text()),
        )
        if any(x.numero == p.numero for x in self.eleicao.partidos):
            return self.erro("Partido", f"Já existe o partido número {p.numero}.")
        self.eleicao = replace(self.eleicao, partidos=[*self.eleicao.partidos, p])
        for c in (self.partido_nome, self.partido_sigla, self.partido_presidente, self.partido_foto):
            c.clear()
        self._atualizar_listas()
        return None

    def cadastrar_candidato(self) -> None:
        if not self.cand_nome.text().strip():
            return self.erro("Candidato", "Informe o nome.")
        if self.cand_cargo.currentIndex() < 0 or self.cand_partido.currentIndex() < 0:
            return self.erro("Candidato", "Cadastre antes um cargo e um partido.")
        c = Candidato(
            self.cand_numero.value(),
            self.cand_nome.text().strip(),
            self.cand_cargo.currentData(),
            int(self.cand_partido.currentData()),
            self.cand_titulo.text().strip() or None,
            self._registrar_foto(self.cand_foto.text()),
        )
        if any(x.cargo == c.cargo and x.numero == c.numero for x in self.eleicao.candidatos):
            return self.erro("Candidato", f"Já existe o número {c.numero} para este cargo.")
        self.eleicao = replace(self.eleicao, candidatos=[*self.eleicao.candidatos, c])
        for campo in (self.cand_nome, self.cand_titulo, self.cand_foto):
            campo.clear()
        self._atualizar_listas()
        return None

    def _remover(self, lista: QListWidget, atributo: str) -> None:
        i = lista.currentRow()
        if i < 0:
            return
        itens = list(getattr(self.eleicao, atributo))
        del itens[i]
        self.eleicao = replace(self.eleicao, **{atributo: itens})
        self._atualizar_listas()

    def remover_cargo(self) -> None:
        self._remover(self.lista_cargos, "cargos")

    def remover_partido(self) -> None:
        self._remover(self.lista_partidos, "partidos")

    def remover_candidato(self) -> None:
        self._remover(self.lista_candidatos, "candidatos")

    def _atualizar_listas(self) -> None:
        self.lista_cargos.clear()
        for c in self.eleicao.cargos:
            self.lista_cargos.addItem(f"{c.nome}  [{c.id}]  votos/eleitor={c.votos_por_eleitor}")
        self.lista_partidos.clear()
        for p in self.eleicao.partidos:
            self.lista_partidos.addItem(f"{p.numero}  {p.sigla} — {p.nome}")
        self.lista_candidatos.clear()
        for c in self.eleicao.candidatos:
            self.lista_candidatos.addItem(f"{c.numero}  {c.nome}  ({c.cargo}, partido {c.partido})")
        self.cand_cargo.clear()
        for c in self.eleicao.cargos:
            self.cand_cargo.addItem(c.nome, c.id)
        self.cand_partido.clear()
        for p in self.eleicao.partidos:
            self.cand_partido.addItem(f"{p.numero} {p.sigla}", p.numero)
        self._resumo()

    def _resumo(self, extra: str = "") -> None:
        e = self.eleicao
        self.resumo.setPlainText(
            f"{e.nome} ({e.data or 'sem data'})\nseções: {', '.join(e.secoes) or '-'}\n"
            f"{len(e.cargos)} cargo(s), {len(e.partidos)} partido(s), {len(e.candidatos)} candidato(s), "
            f"{len(e.slots())} voto(s) por cédula\nid (atual): {e.id}\n{extra}"
        )

    def validar(self, mostrar: bool = True) -> bool:
        self._sincronizar_cabecalho()
        try:
            self.eleicao.validar()
        except ErroManifesto as err:
            self._resumo(f"\nINVÁLIDO: {err}")
            if mostrar:
                self.erro("Validação", str(err))
            return False
        self._resumo("\nVÁLIDO")
        return True

    def salvar(self, mostrar: bool = True) -> bool:
        if not self.validar(mostrar):
            return False
        base = self.caminho.parent
        (base / "fotos").mkdir(parents=True, exist_ok=True)
        for destino, origem in self.fotos_pendentes.items():
            shutil.copyfile(origem, base / destino)
        self.fotos_pendentes = {}
        self.eleicao.salvar(self.caminho)
        self._resumo(f"\nSALVO em {self.caminho}\nid: {self.eleicao.id}")
        if mostrar:
            QMessageBox.information(self, "Eleição salva", f"{self.caminho}\n\nid: {self.eleicao.id}")
        return True

    def apagar(self, confirmar: bool = True) -> None:
        if confirmar:
            resp = QMessageBox.warning(
                self, "Apagar eleição", "Remover todos os cargos, partidos e candidatos deste manifesto?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No,
            )
            if resp != QMessageBox.StandardButton.Yes:
                return
        self.eleicao = replace(self.eleicao, cargos=[], partidos=[], candidatos=[])
        self.fotos_pendentes = {}
        self._atualizar_listas()
