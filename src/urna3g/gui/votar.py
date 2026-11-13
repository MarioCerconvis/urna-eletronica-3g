"""Módulo de votação — a tela que o eleitor usa na cabine.

Fluxo (igual ao protótipo de 2016, que já permitia ao eleitor escolher a ordem dos cargos):
  1. lista de cargos pendentes → eleitor tecla o número do cargo;
  2. digita o número do candidato (foto/nome/partido aparecem), ou BRANCO / NULO; CONFIRMA;
  3. quando todos os slots foram votados, a cédula é assinada e impressa; a tela volta ao início.

A urna **não guarda** cédula alguma em disco (o PDF temporário é apagado após a impressão):
nenhum registro digital do voto, nem da ordem de votação, fica na máquina.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from urna3g import BRANCO, NULO, audio, crypto
from urna3g.ballot import Cedula, emitir
from urna3g.config import Chaves, carregar_eleicao
from urna3g.gui import ErroGui
from urna3g.gui.comum import (
    APAGAR,
    BRANCO_T,
    CONFIRMA,
    CORRIGE,
    NULO_T,
    JanelaBase,
    botao,
    classificar_tecla,
    pedir_senha,
    pixmap,
    rotulo,
)
from urna3g.manifest import Eleicao, Slot
from urna3g.render import ErroImpressao, imprimir, renderizar_cedula_pdf

TEXTO_FIM = "Retire sua cédula, confira-a na máquina de verificação e deposite-a na urna lacrada."


class JanelaVotar(JanelaBase):
    cedula_emitida = Signal(str)
    PAG_CARGOS, PAG_DIGITOS, PAG_FIM = 0, 1, 2

    def __init__(
        self,
        eleicao: Eleicao,
        secao: str,
        privada: crypto.ChavePrivada,
        saida: Path,
        impressora: str | None = None,
        sem_impressora: bool = False,
        tempo_reinicio_ms: int = 5000,
    ):
        super().__init__(f"Votação — seção {secao}")
        self.eleicao = eleicao
        self.secao = secao
        self.privada = privada
        self.saida = Path(saida)
        self.impressora = impressora
        self.sem_impressora = sem_impressora
        self.tempo_reinicio_ms = tempo_reinicio_ms
        self.pendentes: dict[str, list[Slot]] = {}
        self.votos: dict[int, int] = {}
        self.cargo_atual: str | None = None
        self.slot_atual: Slot | None = None
        self.digitos: list[int] = []
        self.estado = "digitando"  # digitando | candidato | branco | nulo
        self.cedula_pendente: Cedula | None = None
        self.quadros: list[QLabel] = []
        self._montar()
        self._reiniciar()

    @classmethod
    def de_args(cls, args: argparse.Namespace) -> JanelaVotar:
        if not args.eleicao or not args.secao:
            raise ErroGui("o módulo votar exige --eleicao e --secao")
        ch = Chaves(Path(args.chaves))
        eleicao, _ = carregar_eleicao(args.eleicao, ch.autoridade_pub(), verificar_fotos=not args.sem_fotos)
        privada = crypto.carregar_privada(ch.secao_priv(args.secao), pedir_senha(args))
        return cls(eleicao, args.secao, privada, Path(args.saida), args.impressora, args.sem_impressora)

    # ------------------------------------------------------------------ construção
    def _montar(self) -> None:
        self.pilha = QStackedWidget()
        self.pilha.addWidget(self._pagina_cargos())
        self.pilha.addWidget(self._pagina_digitos())
        self.pilha.addWidget(self._pagina_fim())
        self.centralizar(self.pilha)

    def _pagina_cargos(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addWidget(rotulo("Selecione um cargo para votar", "titulo"))
        self.lista = QListWidget()
        self.lista.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        lay.addWidget(self.lista, 1)
        b = botao("VOTAR")
        b.clicked.connect(self._votar_selecionado)
        lay.addWidget(b, 0, Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(rotulo("Tecle o número do cargo, ou use as setas e CONFIRMA (ENTER)", "dica"))
        return w

    def _pagina_digitos(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        self.lbl_cargo = rotulo("", "titulo")
        lay.addWidget(self.lbl_cargo)
        self.linha_digitos = QHBoxLayout()
        self.linha_digitos.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.linha_digitos.setSpacing(18)
        lay.addLayout(self.linha_digitos)
        corpo = QHBoxLayout()
        self.lbl_foto = QLabel()
        self.lbl_foto.setFixedSize(262, 350)
        self.lbl_foto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_foto.setStyleSheet("border: 1px solid #ccc; background: white;")
        corpo.addWidget(self.lbl_foto)
        info = QVBoxLayout()
        esq = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        self.lbl_nome = rotulo("", "grande", esq)
        self.lbl_partido = rotulo("", "grande", esq)
        self.lbl_numero = rotulo("", "grande", esq)
        self.lbl_mensagem = rotulo("", "mensagem", esq)
        self.lbl_ajuda = rotulo("", "dica", esq)
        for lb in (self.lbl_nome, self.lbl_partido, self.lbl_numero, self.lbl_mensagem, self.lbl_ajuda):
            info.addWidget(lb)
        info.addStretch()
        corpo.addLayout(info, 1)
        lay.addLayout(corpo, 1)
        botoes = QHBoxLayout()
        bb = botao("BRANCO", "branco")
        bb.clicked.connect(self._branco)
        bc = botao("CORRIGE", "corrige")
        bc.clicked.connect(self._corrige)
        bf = botao("CONFIRMA", "confirma")
        bf.clicked.connect(self._confirma)
        botoes.addWidget(bb)
        botoes.addStretch()
        botoes.addWidget(bc)
        botoes.addStretch()
        botoes.addWidget(bf)
        lay.addLayout(botoes)
        lay.addWidget(rotulo("Teclado:   −  BRANCO      +  CORRIGE      ENTER  CONFIRMA      *  NULO", "dica"))
        return w

    def _pagina_fim(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.addStretch()
        self.lbl_fim = rotulo("IMPRIMINDO VOTO…", "titulo")
        self.lbl_fim_detalhe = rotulo(TEXTO_FIM, "subtitulo")
        lay.addWidget(self.lbl_fim)
        lay.addWidget(self.lbl_fim_detalhe)
        lay.addStretch()
        return w

    # ------------------------------------------------------------------ fluxo
    def _reiniciar(self) -> None:
        self.pendentes = {}
        for s in self.eleicao.slots():
            self.pendentes.setdefault(s.cargo_id, []).append(s)
        self.votos = {}
        self.cedula_pendente = None
        self.cargo_atual = None
        self.slot_atual = None
        self._atualizar_lista()
        self.pilha.setCurrentIndex(self.PAG_CARGOS)

    def _atualizar_lista(self) -> None:
        self.lista.clear()
        for i, cargo in enumerate(self.eleicao.cargos, start=1):
            if cargo.id not in self.pendentes:
                continue
            txt = f"{i}    {cargo.nome}"
            if cargo.votos_por_eleitor > 1:
                txt += f"    ({len(self.pendentes[cargo.id])} voto(s) restante(s))"
            item = QListWidgetItem(txt)
            item.setData(Qt.ItemDataRole.UserRole, cargo.id)
            self.lista.addItem(item)
        if self.lista.count():
            self.lista.setCurrentRow(0)

    def _votar_selecionado(self) -> None:
        item = self.lista.currentItem()
        if item is not None:
            self._abrir_cargo(item.data(Qt.ItemDataRole.UserRole))

    def _abrir_cargo(self, cargo_id: str) -> None:
        if cargo_id not in self.pendentes:
            return
        self.cargo_atual = cargo_id
        self.slot_atual = self.pendentes[cargo_id][0]
        cargo = self.eleicao.cargo(cargo_id)
        titulo = cargo.nome
        if cargo.votos_por_eleitor > 1:
            titulo += f"  —  {self.slot_atual.indice + 1}º de {cargo.votos_por_eleitor} votos"
        self.lbl_cargo.setText(titulo)
        for q in self.quadros:
            self.linha_digitos.removeWidget(q)
            q.deleteLater()
        self.quadros = []
        for _ in range(self.eleicao.digitos(cargo_id)):
            q = rotulo("", "digito")
            self.quadros.append(q)
            self.linha_digitos.addWidget(q)
        self._corrige()
        self.pilha.setCurrentIndex(self.PAG_DIGITOS)

    def _render_digitos(self) -> None:
        for i, q in enumerate(self.quadros):
            q.setText(str(self.digitos[i]) if i < len(self.digitos) else "")
            q.setProperty("ativo", "true" if i == len(self.digitos) else "false")
            q.style().unpolish(q)
            q.style().polish(q)

    def _limpar_candidato(self) -> None:
        for lb in (self.lbl_nome, self.lbl_partido, self.lbl_numero, self.lbl_mensagem, self.lbl_ajuda):
            lb.clear()
        self.lbl_foto.clear()

    def _corrige(self) -> None:
        self.digitos = []
        self.estado = "digitando"
        self._limpar_candidato()
        self._render_digitos()

    def _apagar(self) -> None:
        if self.estado in ("branco", "nulo"):
            self._corrige()
            return
        if self.digitos:
            self.digitos.pop()
        self.estado = "digitando"
        self._limpar_candidato()
        self._render_digitos()

    def _digito(self, d: int) -> None:
        if self.estado in ("branco", "nulo") or len(self.digitos) >= len(self.quadros):
            return
        self.digitos.append(d)
        self._render_digitos()
        if len(self.digitos) == len(self.quadros):
            self._mostrar_candidato()

    def _numero_digitado(self) -> int:
        return int("".join(map(str, self.digitos)))

    def _mostrar_candidato(self) -> None:
        assert self.cargo_atual is not None
        cand = self.eleicao.candidato(self.cargo_atual, self._numero_digitado())
        if cand is None:
            self.estado = "nulo"
            self.lbl_mensagem.setText("NÚMERO INEXISTENTE\nVOTO NULO")
            self.lbl_ajuda.setText("Tecle CONFIRMA para votar nulo, ou CORRIGE.")
            return
        self.estado = "candidato"
        partido = self.eleicao.partido(cand.partido)
        self.lbl_nome.setText(f"Nome:  {cand.nome}")
        self.lbl_partido.setText(f"Partido:  {partido.nome} ({partido.sigla})" if partido else "")
        self.lbl_numero.setText(f"Número:  {cand.numero}")
        foto = self.eleicao.caminho(cand.foto) if (cand.foto and self.eleicao.base_dir) else None
        self.lbl_foto.setPixmap(pixmap(foto, 262, 350))
        self.lbl_ajuda.setText("Tecle CONFIRMA para votar, ou CORRIGE.")

    def _branco(self) -> None:
        self._corrige()
        self.estado = "branco"
        self.lbl_mensagem.setText("VOTO EM BRANCO")
        self.lbl_ajuda.setText("Tecle CONFIRMA para votar em branco, ou CORRIGE.")

    def _nulo(self) -> None:
        self._corrige()
        self.estado = "nulo"
        self.lbl_mensagem.setText("VOTO NULO")
        self.lbl_ajuda.setText("Tecle CONFIRMA para votar nulo, ou CORRIGE.")

    def _confirma(self) -> None:
        if self.cargo_atual is None or self.slot_atual is None:
            return
        if self.estado == "digitando":
            self.lbl_mensagem.setText("Digite o número completo,\nou tecle BRANCO / NULO.")
            return
        if self.estado == "branco":
            valor = BRANCO
        elif self.estado == "nulo":
            valor = NULO
        else:
            valor = self._numero_digitado()
        if valor > 0:
            ja_votados = [
                self.votos[s.posicao]
                for s in self.eleicao.slots()
                if s.cargo_id == self.cargo_atual and s.posicao in self.votos
            ]
            if valor in ja_votados:
                self._corrige()
                self.lbl_mensagem.setText("Candidato já escolhido para este cargo.\nEscolha outro número.")
                return
        self.votos[self.slot_atual.posicao] = valor
        audio.tocar("beep")
        restantes = self.pendentes[self.cargo_atual]
        restantes.pop(0)
        if restantes:
            self._abrir_cargo(self.cargo_atual)
            return
        del self.pendentes[self.cargo_atual]
        if not self.pendentes:
            self._finalizar()
            return
        self._atualizar_lista()
        self.pilha.setCurrentIndex(self.PAG_CARGOS)

    def _finalizar(self) -> None:
        valores = [self.votos[p] for p in range(len(self.eleicao.slots()))]
        self.cedula_pendente = emitir(self.eleicao, self.secao, valores, self.privada)
        self.pilha.setCurrentIndex(self.PAG_FIM)
        self._imprimir()

    def _imprimir(self) -> None:
        cedula = self.cedula_pendente
        if cedula is None:
            return
        if self.sem_impressora:
            destino = self.saida / "cedulas" / f"cedula-{cedula.nonce_hex[:8]}.pdf"
            pdf = renderizar_cedula_pdf(cedula, self.eleicao, destino)
            self.lbl_fim.setText("VOTO REGISTRADO (modo de teste, sem impressora)")
            self.lbl_fim_detalhe.setText(f"PDF gerado em {pdf}")
        else:
            pdf = self.saida / "cedula-atual.pdf"  # sobrescrito a cada voto e apagado após imprimir
            renderizar_cedula_pdf(cedula, self.eleicao, pdf)
            try:
                imprimir(pdf, self.impressora)
            except ErroImpressao as e:
                self.lbl_fim.setText("FALHA NA IMPRESSÃO")
                self.lbl_fim_detalhe.setText(f"{e}\n\nChame o mesário. Tecle CONFIRMA para tentar imprimir novamente.")
                return
            finally:
                try:
                    pdf.unlink()
                except OSError:
                    pass
            self.lbl_fim.setText("IMPRIMINDO VOTO…")
            self.lbl_fim_detalhe.setText(TEXTO_FIM)
        audio.tocar("fim")
        self.cedula_emitida.emit(cedula.texto())
        self.cedula_pendente = None
        QTimer.singleShot(self.tempo_reinicio_ms, self._reiniciar)

    # ------------------------------------------------------------------ teclado
    def keyPressEvent(self, ev: QKeyEvent) -> None:  # noqa: N802
        pag = self.pilha.currentIndex()
        if pag == self.PAG_CARGOS and ev.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
            delta = -1 if ev.key() == Qt.Key.Key_Up else 1
            if self.lista.count():
                self.lista.setCurrentRow(max(0, min(self.lista.count() - 1, self.lista.currentRow() + delta)))
            return
        acao = classificar_tecla(ev)
        if acao is None:
            super().keyPressEvent(ev)
            return
        if pag == self.PAG_CARGOS:
            if acao.startswith("digito:"):
                d = int(acao.split(":")[1])
                if 1 <= d <= len(self.eleicao.cargos):
                    self._abrir_cargo(self.eleicao.cargos[d - 1].id)
            elif acao == CONFIRMA:
                self._votar_selecionado()
        elif pag == self.PAG_DIGITOS:
            if acao.startswith("digito:"):
                self._digito(int(acao.split(":")[1]))
            elif acao == CONFIRMA:
                self._confirma()
            elif acao == CORRIGE:
                self._corrige()
            elif acao == BRANCO_T:
                self._branco()
            elif acao == NULO_T:
                self._nulo()
            elif acao == APAGAR:
                self._apagar()
        elif pag == self.PAG_FIM and acao == CONFIRMA and self.cedula_pendente is not None:
            self._imprimir()
        ev.accept()
