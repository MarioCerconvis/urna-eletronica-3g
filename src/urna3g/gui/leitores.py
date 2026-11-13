"""Fontes de leitura de QR para verificação e apuração.

* ``LeitorTeclado``: leitor USB tipo *keyboard wedge* (recomendado: barato, robusto, zero código de
  câmera). Ele "digita" o conteúdo do QR e envia ENTER; acumulamos as teclas e emitimos a linha.
* ``LeitorCamera``: webcam via OpenCV (como o zbar do protótipo), em uma thread separada.
"""

from __future__ import annotations

import time

from PySide6.QtCore import QEvent, QObject, Qt, QThread, QTimer, Signal


class LeitorTeclado(QObject):
    lido = Signal(str)

    def __init__(self, app: QObject, minimo: int = 8, timeout_ms: int = 1500, engolir: bool = True):
        super().__init__()
        self.buffer = ""
        self.minimo = minimo
        self.engolir = engolir
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(timeout_ms)
        self._timer.timeout.connect(self._limpar)
        app.installEventFilter(self)

    def _limpar(self) -> None:
        self.buffer = ""

    def eventFilter(self, obj: QObject, ev: QEvent) -> bool:  # noqa: N802 (API Qt)
        if ev.type() != QEvent.Type.KeyPress:
            return False
        k = ev.key()
        if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
            texto, self.buffer = self.buffer, ""
            self._timer.stop()
            if len(texto) >= self.minimo:
                self.lido.emit(texto)
                return True
            return False
        mods = ev.modifiers()
        if mods & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier):
            return False
        t = ev.text()
        if t and t.isprintable():
            self.buffer += t
            self._timer.start()
            return self.engolir
        return False


class LeitorCamera(QThread):
    lido = Signal(str)
    erro = Signal(str)

    def __init__(self, indice: int = 0, intervalo_repeticao: float = 3.0):
        super().__init__()
        self.indice = indice
        self.intervalo = intervalo_repeticao
        self._parar = False

    def run(self) -> None:  # noqa: D401
        try:
            import cv2

            from urna3g.scanner import decodificar_array
        except ImportError:
            self.erro.emit("OpenCV não instalado (pip install 'urna3g[camera]')")
            return
        cap = cv2.VideoCapture(self.indice)
        if not cap.isOpened():
            self.erro.emit(f"não foi possível abrir a câmera {self.indice}")
            return
        ultimos: dict[str, float] = {}
        try:
            while not self._parar:
                ok, quadro = cap.read()
                if not ok:
                    self.msleep(50)
                    continue
                agora = time.monotonic()
                for texto in decodificar_array(quadro):
                    if agora - ultimos.get(texto, 0.0) > self.intervalo:
                        ultimos[texto] = agora
                        self.lido.emit(texto)
                self.msleep(40)
        finally:
            cap.release()

    def parar(self) -> None:
        self._parar = True
        self.wait(3000)
