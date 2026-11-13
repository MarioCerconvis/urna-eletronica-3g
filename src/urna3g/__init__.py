"""urna3g — Urna eletrônica de 3ª geração (UFABC/LAOB).

Reimplementação moderna do protótipo de 2016/2017 (Lima, Gazziro et al., SBSeg 2017):
cédula impressa com registro legível + código QR *assinado* (Ed25519), módulo de
verificação independente, apuração com *ledger* encadeado por hash e boletim de urna
assinado. Consulte ``docs/`` para fundamentos, arquitetura e implantação.
"""

__version__ = "2.0.0a1"

# Valores especiais de um slot de voto (mantidos do protótipo original)
BRANCO = 0
NULO = -1
