"""Base visual compartilhada: estilo, janela em modo quiosque e mapeamento do teclado numérico."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeyEvent, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow, QMessageBox, QPushButton, QWidget

ASSETS = Path(__file__).resolve().parents[1] / "assets"
ICONE = ASSETS / "icon.png"

ESTILO = """
QWidget { font-family: 'Helvetica', 'DejaVu Sans', 'Liberation Sans', sans-serif; font-size: 13pt; }
QMainWindow { background: #fafafa; }
QLabel#titulo { font-size: 30pt; font-weight: 600; }
QLabel#subtitulo { font-size: 18pt; }
QLabel#grande { font-size: 20pt; }
QLabel#mensagem { font-size: 22pt; font-weight: 600; color: #b00020; }
QLabel#ok { font-size: 22pt; font-weight: 600; color: #176b2a; }
QLabel#dica { font-size: 11pt; color: #555; }
QLabel#digito { border: 3px solid #333; border-radius: 8px; background: white; font-size: 44pt; min-width: 84px;
                max-width: 84px; min-height: 104px; max-height: 104px; qproperty-alignment: AlignCenter; }
QLabel#digito[ativo="true"] { border-color: #2d2dff; }
QListWidget { font-size: 24pt; }
QTableWidget { font-size: 14pt; }
QPushButton { border: 2px solid #2d2dff; border-radius: 6px; padding: 8px 18px; min-width: 150px; min-height: 40px;
              font-size: 14pt; font-weight: 600;
              background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #ffffff, stop:1 #dddddd); }
QPushButton:pressed { background: #cfd8ff; }
QPushButton#branco { border-color: #777777; }
QPushButton#corrige { border-color: #ffc800; }
QPushButton#confirma { border-color: #00aa00; }
QPushButton#perigo { border-color: #ee7543; }
"""


def aplicar_estilo(app: QApplication) -> None:
    app.setStyleSheet(ESTILO)
    if ICONE.is_file():
        app.setWindowIcon(QIcon(str(ICONE)))


def rotulo(texto: str = "", nome: str | None = None, alinhar: Qt.AlignmentFlag = Qt.AlignmentFlag.AlignCenter,
           quebrar: bool = True) -> QLabel:
    lb = QLabel(texto)
    if nome:
        lb.setObjectName(nome)
    lb.setAlignment(alinhar)
    lb.setWordWrap(quebrar)
    lb.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return lb


def botao(texto: str, nome: str | None = None) -> QPushButton:
    b = QPushButton(texto)
    if nome:
        b.setObjectName(nome)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)  # teclas sempre vão para a janela, nunca para o botão
    return b


def pixmap(caminho: Path | None, largura: int, altura: int) -> QPixmap:
    if caminho is None or not Path(caminho).is_file():
        return QPixmap()
    pm = QPixmap(str(caminho))
    if pm.isNull():
        return pm
    return pm.scaled(largura, altura, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)


# ------------------------------------------------------------------ teclado numérico
# Legenda a imprimir e colar na cabine (substitui o xmodmap do protótipo):
#   0-9  dígitos   |  ENTER = CONFIRMA  |  -  = BRANCO  |  +  = CORRIGE  |  *  = NULO  |  BACKSPACE = apaga 1 dígito
# Letras do protótipo original continuam valendo: a=confirma b=branco c=corrige n=nulo.
CONFIRMA, CORRIGE, BRANCO_T, NULO_T, APAGAR = "confirma", "corrige", "branco", "nulo", "apagar"


def classificar_tecla(ev: QKeyEvent) -> str | None:
    k = ev.key()
    if Qt.Key.Key_0 <= k <= Qt.Key.Key_9:
        return f"digito:{k - Qt.Key.Key_0}"
    if k in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
        return CONFIRMA
    if k == Qt.Key.Key_Minus:
        return BRANCO_T
    if k == Qt.Key.Key_Plus:
        return CORRIGE
    if k == Qt.Key.Key_Asterisk:
        return NULO_T
    if k in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete):
        return APAGAR
    t = ev.text().lower()
    return {"a": CONFIRMA, "b": BRANCO_T, "c": CORRIGE, "n": NULO_T}.get(t)


class JanelaBase(QMainWindow):
    """Janela em modo quiosque: tela cheia, sem fechar com ESC; sair exige Ctrl+Shift+Q."""

    def __init__(self, titulo: str):
        super().__init__()
        self.setWindowTitle(f"urna3g — {titulo}")
        if ICONE.is_file():
            self.setWindowIcon(QIcon(str(ICONE)))
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def mostrar(self, tela_cheia: bool = True) -> None:
        if tela_cheia:
            self.showFullScreen()
        else:
            self.resize(1100, 720)
            self.show()
        self.activateWindow()
        self.setFocus()

    def keyPressEvent(self, ev: QKeyEvent) -> None:  # noqa: N802 (API Qt)
        mods = ev.modifiers()
        if ev.key() == Qt.Key.Key_Q and (mods & Qt.KeyboardModifier.ControlModifier) and (
            mods & Qt.KeyboardModifier.ShiftModifier
        ):
            self.close()
            return
        ev.accept()  # ESC e outras teclas não fazem nada

    def erro(self, titulo: str, texto: str) -> None:
        QMessageBox.critical(self, titulo, texto)

    def centralizar(self, w: QWidget) -> None:
        self.setCentralWidget(w)
        w.setFocusPolicy(Qt.FocusPolicy.NoFocus)


def pedir_senha(args: object) -> str | None:
    """Se ``--senha`` foi passado, pede a senha da chave privada em um diálogo (campo mascarado)."""
    if not getattr(args, "senha", False):
        return None
    from PySide6.QtWidgets import QInputDialog, QLineEdit

    senha, ok = QInputDialog.getText(None, "urna3g", "Senha da chave privada:", QLineEdit.EchoMode.Password)
    if not ok:
        raise RuntimeError("operação cancelada: senha não informada")
    return senha
