"""E1 — Tamanho da cédula e versão do QR em função do nº de votos (determinístico) + QR do protótipo de 2016."""

from __future__ import annotations

import base64

from comum import gravar
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from urna3g import BRANCO, crypto
from urna3g.ballot import emitir
from urna3g.manifest import Candidato, Cargo, Eleicao, Partido
from urna3g.qr import versao_qr


def eleicao_com(n_votos: int) -> Eleicao:
    cargos, resto, i = [], n_votos, 0
    while resto:
        k = min(resto, 20)
        cargos.append(Cargo(f"c{i}", f"Cargo {i}", k))
        resto -= k
        i += 1
    cands = [Candidato(10 + j, f"Cand {j}", c.id, 1) for c in cargos for j in range(c.votos_por_eleitor)]
    return Eleicao("E1", cargos=cargos, partidos=[Partido(1, "P", "P")], candidatos=cands, secoes=["001"])


def qr_versao_ecc(texto: str, ecc: str) -> int:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M

    q = qrcode.QRCode(error_correction={"L": ERROR_CORRECT_L, "M": ERROR_CORRECT_M}[ecc])
    q.add_data(texto)
    q.make(fit=True)
    return int(q.version)


def main() -> None:
    chave = crypto.gerar_chave()
    linhas = []
    for n in (1, 2, 3, 5, 10, 20, 40):
        e = eleicao_com(n)
        for secao in ("001", "SECAO-0123456789"[:16]):
            c = emitir(e, secao, [BRANCO] * n, chave)
            t = c.texto()
            linhas.append({"votos": n, "secao_bytes": len(secao.encode()), "bytes_binarios": len(c.cabecalho()) + 64,
                           "caracteres_qr": len(t), "versao_qr_M": versao_qr(t), "modulos_lado": 17 + 4 * versao_qr(t)})
    # Protótipo de 2016: texto "#v1;v2;v3;id" cifrado com RSA-1024 OAEP(SHA-1), base64 com quebras de linha (PyCrypto)
    pub1024 = rsa.generate_private_key(public_exponent=65537, key_size=1024).public_key()
    claro = b"#99;96;80;123456789"
    cif = pub1024.encrypt(claro, padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None))
    b64 = base64.encodebytes(cif).decode()  # equivalente a str.encode('base64') do Python 2 (quebra a cada 76)
    prototipo = {"bytes_cifrados": len(cif), "caracteres_qr": len(b64), "versao_qr_L": qr_versao_ecc(b64, "L"),
                 "versao_qr_M": qr_versao_ecc(b64, "M"), "observacao": "texto do QR = base64 do RSA-1024-OAEP; o protótipo usava correção L"}
    p = gravar("e1-tamanho-cedula", {"metodo": "uma medição por configuração (determinístico); votos brancos têm o mesmo tamanho que qualquer outro (int32)",
                                     "nova_versao": linhas, "prototipo_2016": prototipo})
    for ln in linhas:
        print(ln)
    print("protótipo:", prototipo, "\n->", p)


if __name__ == "__main__":
    main()
