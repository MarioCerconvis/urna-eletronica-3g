"""Módulo de apuração — lê as cédulas da urna lacrada, uma a uma, e emite o boletim assinado."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QKeyEvent
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from urna3g import audio, crypto
from urna3g import boletim as bmod
from urna3g.config import Chaves, carregar_eleicao
from urna3g.gui import ErroGui
from urna3g.gui.comum import JanelaBase, botao, pedir_senha, rotulo
from urna3g.gui.leitores import LeitorCamera, LeitorTeclado
from urna3g.manifest import Eleicao
from urna3g.render import ErroImpressao, imprimir, renderizar_boletim_pdf
from urna3g.tally import Apuracao, Resultado, Status


class JanelaApurar(JanelaBase):
    def __init__(
        self,
        eleicao: Eleicao,
        secao: str,
        publica_secao: crypto.ChavePublica,
        privada_apuracao: crypto.ChavePrivada,
        saida: Path,
        impressora: str | None = None,
        sem_impressora: bool = False,
        camera: int | None = None,
    ):
        super().__init__(f"Apuração — seção {secao}")
        self.eleicao = eleicao
        self.secao = secao
        self.privada = privada_apuracao
        self.saida = Path(saida)
        self.saida.mkdir(parents=True, exist_ok=True)
        self.impressora = impressora
        self.sem_impressora = sem_impressora
        self.apuracao = Apuracao.abrir(eleicao, secao, publica_secao, self.saida / f"apuracao-{secao}.db")

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(rotulo(f"Apuração — seção {secao}", "titulo"))
        contadores = QHBoxLayout()
        self.lbl_total = rotulo("", "subtitulo")
        self.lbl_ocorrencias = rotulo("", "dica")
        contadores.addWidget(self.lbl_total)
        contadores.addWidget(self.lbl_ocorrencias)
        lay.addLayout(contadores)
        self.tabela = QTableWidget(0, 3)
        self.tabela.setHorizontalHeaderLabels(["Cargo", "Voto", "Quantidade"])
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(self.tabela, 1)
        self.lbl_mensagem = rotulo("Leia as cédulas uma a uma. Repetidas e inválidas não são contadas.", "ok")
        lay.addWidget(self.lbl_mensagem)
        self.lbl_ledger = rotulo("", "dica")
        lay.addWidget(self.lbl_ledger)
        linha = QHBoxLayout()
        linha.addStretch()
        self.btn_boletim = botao("GERAR BOLETIM  (F10)", "perigo")
        self.btn_boletim.clicked.connect(self.gerar_boletim)
        linha.addWidget(self.btn_boletim)
        linha.addStretch()
        lay.addLayout(linha)
        self.centralizar(w)

        app = QApplication.instance()
        self.leitor = LeitorTeclado(app) if app is not None else None
        if self.leitor is not None:
            self.leitor.lido.connect(self.processar)
        self.camera: LeitorCamera | None = None
        if camera is not None:
            self.camera = LeitorCamera(camera)
            self.camera.lido.connect(self.processar)
            self.camera.erro.connect(lambda m: self._mensagem(f"Câmera: {m}", ok=False))
            self.camera.start()
        self._atualizar()

    @classmethod
    def de_args(cls, args: argparse.Namespace) -> JanelaApurar:
        if not args.eleicao or not args.secao:
            raise ErroGui("o módulo apurar exige --eleicao e --secao")
        ch = Chaves(Path(args.chaves))
        eleicao, _ = carregar_eleicao(args.eleicao, ch.autoridade_pub(), verificar_fotos=not args.sem_fotos)
        pub = crypto.carregar_publica(ch.secao_pub(args.secao))
        priv = crypto.carregar_privada(ch.apuracao_priv(args.secao), pedir_senha(args))
        return cls(eleicao, args.secao, pub, priv, Path(args.saida), args.impressora, args.sem_impressora, args.camera)

    # ------------------------------------------------------------------ estado
    def _mensagem(self, texto: str, ok: bool = True) -> None:
        self.lbl_mensagem.setObjectName("ok" if ok else "mensagem")
        self.lbl_mensagem.style().unpolish(self.lbl_mensagem)
        self.lbl_mensagem.style().polish(self.lbl_mensagem)
        self.lbl_mensagem.setText(texto)

    def _atualizar(self) -> None:
        totais = self.apuracao.totais()
        linhas: list[tuple[str, str, int]] = []
        for cargo in self.eleicao.cargos:
            for valor, n in sorted(totais[cargo.id].items(), key=lambda kv: (kv[0] <= 0, kv[0])):
                linhas.append((cargo.nome, self.eleicao.descrever_voto(cargo.id, valor), n))
        self.tabela.setRowCount(len(linhas))
        for i, (c, v, n) in enumerate(linhas):
            self.tabela.setItem(i, 0, QTableWidgetItem(c))
            self.tabela.setItem(i, 1, QTableWidgetItem(v))
            item = QTableWidgetItem(str(n))
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.tabela.setItem(i, 2, item)
        oc = self.apuracao.ledger.ocorrencias()
        self.lbl_total.setText(f"Cédulas apuradas: {self.apuracao.total_cedulas()}")
        self.lbl_ocorrencias.setText(f"repetidas: {oc.get('duplicada', 0)}   inválidas: {oc.get('invalida', 0)}")
        self.lbl_ledger.setText(
            f"ledger: {len(self.apuracao.ledger.registros())} registros · hash {self.apuracao.ledger.hash_final[:32]}…"
        )
        if self.apuracao.encerrada:
            self.btn_boletim.setEnabled(False)
            self.btn_boletim.setText("APURAÇÃO ENCERRADA")

    def processar(self, texto: str) -> Resultado:
        r = self.apuracao.processar(texto)
        if r.status is Status.ACEITA:
            audio.tocar("beep")
            self._mensagem(f"Cédula aceita (registro #{r.seq}, id {r.cedula.nonce_hex[:16] if r.cedula else ''})")
        elif r.status is Status.DUPLICADA:
            audio.tocar("fim")
            self._mensagem("CÉDULA JÁ APURADA — não contada novamente", ok=False)
        elif r.status is Status.INVALIDA:
            audio.tocar("fim")
            self._mensagem(f"CÉDULA INVÁLIDA — {r.motivo}", ok=False)
        else:
            audio.tocar("fim")
            self._mensagem(r.motivo, ok=False)
        self._atualizar()
        return r

    def gerar_boletim(self, confirmar: bool = True) -> dict[str, Any] | None:
        if self.apuracao.encerrada:
            return None
        if confirmar:
            resp = QMessageBox.question(
                self,
                "Encerrar apuração",
                f"Encerrar a apuração da seção {self.secao} com {self.apuracao.total_cedulas()} cédula(s) e emitir o "
                "boletim?\n\nDepois disso nenhuma cédula será aceita.",
            )
            if resp != QMessageBox.StandardButton.Yes:
                return None
        b = self.apuracao.gerar_boletim(self.privada)
        base = self.saida / f"boletim-{self.secao}"
        bmod.salvar(b, base.with_suffix(".json"))
        pdf = renderizar_boletim_pdf(b, base.with_suffix(".pdf"))
        self.apuracao.exportar_csv(base.with_suffix(".csv"))
        h = bmod.hash_boletim(b)
        if not self.sem_impressora:
            try:
                imprimir(pdf, self.impressora)
            except ErroImpressao as e:
                self.erro("Impressão", f"Boletim gerado em {pdf}, mas a impressão falhou: {e}")
        self._atualizar()
        self._mensagem(f"BOLETIM EMITIDO — hash {h[:32]}…")
        if confirmar:
            QMessageBox.information(
                self,
                "Boletim emitido",
                f"Arquivos:\n{base}.json\n{base}.pdf\n{base}.csv\n\nHash do boletim:\n{h}\n\n"
                f"Hash final do ledger:\n{b['ledger']['hash_final']}",
            )
        return b

    def keyPressEvent(self, ev: QKeyEvent) -> None:  # noqa: N802
        if ev.key() == Qt.Key.Key_F10:
            self.gerar_boletim()
            return
        super().keyPressEvent(ev)

    def closeEvent(self, ev: QCloseEvent) -> None:  # noqa: N802
        if self.camera is not None:
            self.camera.parar()
        self.apuracao.ledger.fechar()
        super().closeEvent(ev)
