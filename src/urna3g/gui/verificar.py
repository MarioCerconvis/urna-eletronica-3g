"""Módulo de verificação — máquina SEPARADA da urna, onde o eleitor confere o QR da cédula.

Diferença crucial em relação ao protótipo: aqui só existe a **chave pública** da seção. A
máquina de verificação não consegue forjar cédulas; apenas confere a assinatura e mostra o
conteúdo, para o eleitor comparar com o texto impresso.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QVBoxLayout, QWidget

from urna3g import audio, crypto
from urna3g.ballot import ErroCedula, descrever, ler
from urna3g.config import Chaves, carregar_eleicao
from urna3g.gui import ErroGui
from urna3g.gui.comum import JanelaBase, rotulo
from urna3g.gui.leitores import LeitorCamera, LeitorTeclado
from urna3g.manifest import Eleicao

DICA = "Aproxime o código QR da sua cédula do leitor"


class JanelaVerificar(JanelaBase):
    def __init__(
        self,
        eleicao: Eleicao,
        secao: str,
        publica: crypto.ChavePublica,
        camera: int | None = None,
        tempo_limpar_ms: int = 8000,
    ):
        super().__init__(f"Verificação — seção {secao}")
        self.eleicao = eleicao
        self.secao = secao
        self.publica = publica
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(rotulo("Seu voto", "titulo"))
        self.lbl_voto = rotulo("", "ok")
        lay.addWidget(self.lbl_voto, 1)
        self.lbl_status = rotulo(DICA, "subtitulo")
        lay.addWidget(self.lbl_status)
        fp = crypto.formatar_impressao(crypto.impressao_digital(publica))
        lay.addWidget(rotulo(f"{eleicao.nome} · seção {secao} · chave pública da urna: {fp}", "dica"))
        self.centralizar(w)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(tempo_limpar_ms)
        self._timer.timeout.connect(self._limpar)
        app = QApplication.instance()
        self.leitor = LeitorTeclado(app) if app is not None else None
        if self.leitor is not None:
            self.leitor.lido.connect(self.processar)
        self.camera: LeitorCamera | None = None
        if camera is not None:
            self.camera = LeitorCamera(camera)
            self.camera.lido.connect(self.processar)
            self.camera.erro.connect(lambda m: self.lbl_status.setText(f"Câmera: {m}"))
            self.camera.start()

    @classmethod
    def de_args(cls, args: argparse.Namespace) -> JanelaVerificar:
        if not args.eleicao or not args.secao:
            raise ErroGui("o módulo verificar exige --eleicao e --secao")
        ch = Chaves(Path(args.chaves))
        eleicao, _ = carregar_eleicao(args.eleicao, ch.autoridade_pub(), verificar_fotos=not args.sem_fotos)
        return cls(eleicao, args.secao, crypto.carregar_publica(ch.secao_pub(args.secao)), args.camera)

    def _estilo(self, nome: str) -> None:
        self.lbl_voto.setObjectName(nome)
        self.lbl_voto.style().unpolish(self.lbl_voto)
        self.lbl_voto.style().polish(self.lbl_voto)

    def processar(self, texto: str) -> bool:
        try:
            cedula = ler(texto, self.eleicao, self.publica, secao_esperada=self.secao)
        except ErroCedula as e:
            self._estilo("mensagem")
            self.lbl_voto.setText("VOTO INVÁLIDO\n\nEsta cédula não pertence a esta seção ou eleição.")
            self.lbl_status.setText(f"Motivo: {e}")
            audio.tocar("fim")
            self._timer.start()
            return False
        self._estilo("ok")
        self.lbl_voto.setText("\n\n".join(f"{titulo}:   {desc}" for titulo, desc in descrever(cedula, self.eleicao)))
        self.lbl_status.setText(f"Cédula válida (id {cedula.nonce_hex[:16]}). Compare com o texto impresso.")
        audio.tocar("beep")
        self._timer.start()
        return True

    def _limpar(self) -> None:
        self.lbl_voto.clear()
        self.lbl_status.setText(DICA)

    def closeEvent(self, ev: QCloseEvent) -> None:  # noqa: N802
        if self.camera is not None:
            self.camera.parar()
        super().closeEvent(ev)
