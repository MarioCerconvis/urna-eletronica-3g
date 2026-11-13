# Terminais (urnas, verificação, apuração)

`instalar.sh` prepara uma máquina Debian/Ubuntu x86_64 como terminal em modo quiosque.
O teclado numérico funciona **sem xmodmap** (o Qt trata as teclas do teclado numérico):

| Tecla | Função |
|---|---|
| 0–9 | dígitos |
| ENTER | CONFIRMA |
| `-` | BRANCO |
| `+` | CORRIGE (limpa) |
| `*` | NULO |
| BACKSPACE | apaga um dígito |
| Ctrl+Shift+Q | fecha (mesário) |

Imprima esta legenda e cole na cabine (como recomenda o artigo de 2017 para a lista de candidatos).
Os arquivos `xmodmap-legado.modmap` e `xmodpad-legado.sh` são o mapeamento do protótipo de 2016,
mantidos só para referência histórica.

Leitor de QR: use um leitor USB tipo *keyboard wedge* (configurado com sufixo ENTER). Alternativamente
`CAMERA=0` em `/etc/urna3g/terminal.conf` usa a webcam via OpenCV.
