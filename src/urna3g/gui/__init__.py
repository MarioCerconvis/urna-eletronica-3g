"""Interfaces gráficas (PySide6/Qt 6) dos cinco módulos do protótipo original."""

from __future__ import annotations

import argparse
import sys


class ErroGui(Exception):
    pass


def executar(args: argparse.Namespace) -> int:
    from PySide6.QtWidgets import QApplication, QMessageBox

    from urna3g.gui import comum

    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("urna3g")
    comum.aplicar_estilo(app)
    try:
        if args.modulo == "votar":
            from urna3g.gui.votar import JanelaVotar as Janela
        elif args.modulo == "verificar":
            from urna3g.gui.verificar import JanelaVerificar as Janela
        elif args.modulo == "apurar":
            from urna3g.gui.apurar import JanelaApurar as Janela
        elif args.modulo == "setup-urna":
            from urna3g.gui.setup_urna import JanelaSetupUrna as Janela
        else:
            from urna3g.gui.setup_eleicao import JanelaSetupEleicao as Janela
        janela = Janela.de_args(args)
    except Exception as e:  # noqa: BLE001 — qualquer falha de configuração vira diálogo + código 2
        QMessageBox.critical(None, "urna3g — erro de configuração", str(e))
        print(f"erro: {e}", file=sys.stderr)
        return 2
    janela.mostrar(tela_cheia=not args.janela)
    return app.exec()
