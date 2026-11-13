"""Setup de Urna — gera as chaves de uma seção (urna e apuração) e, opcionalmente, da autoridade."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from urna3g import crypto
from urna3g.config import Chaves
from urna3g.gui.comum import JanelaBase, botao, rotulo

_RE_SECAO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,15}$")


class JanelaSetupUrna(JanelaBase):
    def __init__(self, dir_chaves: Path):
        super().__init__("Setup de Urna")
        self.chaves = Chaves(Path(dir_chaves))
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(rotulo("Setup de Urna — chaves da seção", "titulo"))
        form = QFormLayout()
        self.campo_secao = QLineEdit()
        self.campo_secao.setPlaceholderText("ex.: 001")
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha2 = QLineEdit()
        self.campo_senha2.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Identificador da seção", self.campo_secao)
        form.addRow("Senha das chaves privadas (opcional)", self.campo_senha)
        form.addRow("Repita a senha", self.campo_senha2)
        lay.addLayout(form)
        linha = QHBoxLayout()
        b1 = botao("GERAR CHAVES DA SEÇÃO", "perigo")
        b1.clicked.connect(self.gerar_secao)
        b2 = botao("GERAR CHAVE DA AUTORIDADE")
        b2.clicked.connect(self.gerar_autoridade)
        b3 = botao("SAIR")
        b3.clicked.connect(self.close)
        linha.addWidget(b1)
        linha.addWidget(b2)
        linha.addStretch()
        linha.addWidget(b3)
        lay.addLayout(linha)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        lay.addWidget(self.log, 1)
        lay.addWidget(
            rotulo(
                f"Diretório: {self.chaves.dir}.  Distribua: secao-ID.key SOMENTE nas urnas da seção; "
                "secao-ID.pub nas máquinas de verificação e apuração; apuracao-ID.key SOMENTE no apurador; "
                "apuracao-ID.pub e autoridade.pub no servidor. autoridade.key fica offline com a comissão.",
                "dica",
            )
        )
        self.centralizar(w)
        self._listar()

    @classmethod
    def de_args(cls, args: argparse.Namespace) -> JanelaSetupUrna:
        return cls(Path(args.chaves))

    def _listar(self) -> None:
        self.log.append(f"Chaves públicas existentes em {self.chaves.dir}:")
        pubs = sorted(self.chaves.dir.glob("*.pub")) if self.chaves.dir.is_dir() else []
        if not pubs:
            self.log.append("  (nenhuma)")
        for p in pubs:
            try:
                fp = crypto.formatar_impressao(crypto.impressao_digital(crypto.carregar_publica(p)))
            except crypto.ErroChave as e:
                fp = f"ilegível ({e})"
            self.log.append(f"  {p.name:<28} {fp}")
        self.log.append("")

    def _senha(self) -> str | None:
        s1, s2 = self.campo_senha.text(), self.campo_senha2.text()
        if s1 != s2:
            raise ValueError("as senhas não coincidem")
        return s1 or None

    def _gerar(self, pares: list[tuple[Path, Path, str]], confirmar: bool) -> None:
        existentes = [p for p, _, _ in pares if p.exists()]
        if existentes:
            if confirmar:
                resp = QMessageBox.warning(
                    self,
                    "Chaves já existem",
                    "Já existem chaves para este papel. Sobrescrever invalida TODAS as cédulas/boletins já "
                    "assinados com elas.\n\nSobrescrever mesmo assim?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if resp != QMessageBox.StandardButton.Yes:
                    return
            else:
                raise FileExistsError(f"{existentes[0]} já existe")
        senha = self._senha()
        for priv_p, pub_p, papel in pares:
            priv = crypto.gerar_chave()
            crypto.salvar_privada(priv_p, priv, senha)
            crypto.salvar_publica(pub_p, priv.public_key())
            fp = crypto.formatar_impressao(crypto.impressao_digital(priv.public_key()))
            self.log.append(f"[{papel}] {priv_p.name} / {pub_p.name}\n    impressão digital: {fp}")
        self.log.append("")

    def gerar_secao(self, confirmar: bool = True) -> None:
        secao = self.campo_secao.text().strip()
        try:
            if not _RE_SECAO.match(secao):
                raise ValueError("identificador de seção inválido (letras, dígitos, '-', '_' e '.', até 16)")
            self._gerar(
                [
                    (self.chaves.secao_priv(secao), self.chaves.secao_pub(secao), f"urna da seção {secao}"),
                    (self.chaves.apuracao_priv(secao), self.chaves.apuracao_pub(secao), f"apuração da seção {secao}"),
                ],
                confirmar,
            )
        except (ValueError, OSError) as e:
            if confirmar:
                self.erro("Setup de Urna", str(e))
            else:
                raise

    def gerar_autoridade(self, confirmar: bool = True) -> None:
        try:
            par = (self.chaves.autoridade_priv(), self.chaves.autoridade_pub(), "autoridade eleitoral")
            self._gerar([par], confirmar)
        except (ValueError, OSError) as e:
            if confirmar:
                self.erro("Setup de Urna", str(e))
            else:
                raise
