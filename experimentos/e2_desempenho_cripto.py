"""E2 — Desempenho das operações criptográficas da cédula (n = 10 000 por operação, após aquecimento de 500)."""

from __future__ import annotations

import time

from comum import gravar, resumo
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from urna3g import crypto
from urna3g.ballot import emitir, ler
from urna3g.manifest import Eleicao
from comum import RAIZ

N, AQUECE = 10_000, 500


def medir(fn, n: int = N) -> dict:  # noqa: ANN001
    for _ in range(AQUECE):
        fn()
    t = []
    for _ in range(n):
        a = time.perf_counter_ns()
        fn()
        t.append((time.perf_counter_ns() - a) / 1e6)  # ms
    r = resumo(t, 5)
    r["ops_por_s"] = round(1000 / r["media"], 1)
    return r


def main() -> None:
    e = Eleicao.carregar(RAIZ / "exemplos" / "eleicao-demo" / "eleicao.json")
    k = crypto.gerar_chave()
    pub = k.public_key()
    cedula = emitir(e, "001", [99, 96, 80], k)
    msg, sig, texto = cedula.mensagem(), cedula.assinatura, cedula.texto()
    rsa1024 = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    rsa2048 = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    oaep = padding.OAEP(mgf=padding.MGF1(hashes.SHA1()), algorithm=hashes.SHA1(), label=None)
    claro = b"#99;96;80;123456789"
    cif = rsa1024.public_key().encrypt(claro, oaep)
    pss = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)
    sig2048 = rsa2048.sign(msg, pss, hashes.SHA256())
    ops = {
        "ed25519_assinar_106B": lambda: k.sign(msg),
        "ed25519_verificar_106B": lambda: pub.verify(sig, msg),
        "emitir_cedula_completa": lambda: emitir(e, "001", [99, 96, 80], k),
        "ler_cedula_decodificar_e_verificar": lambda: ler(texto, e, pub, "001"),
        "prototipo_rsa1024_oaep_cifrar": lambda: rsa1024.public_key().encrypt(claro, oaep),
        "prototipo_rsa1024_oaep_decifrar": lambda: rsa1024.decrypt(cif, oaep),
        "referencia_rsa2048_pss_assinar": lambda: rsa2048.sign(msg, pss, hashes.SHA256()),
        "referencia_rsa2048_pss_verificar": lambda: rsa2048.public_key().verify(sig2048, msg, pss, hashes.SHA256()),
    }
    res = {}
    for nome, fn in ops.items():
        res[nome] = medir(fn)
        print(f"{nome:40s} média {res[nome]['media']:.4f} ms  p99 {res[nome]['p99']:.4f}  {res[nome]['ops_por_s']} op/s")
    print("->", gravar("e2-desempenho-cripto", {"metodo": f"n={N} por operação, aquecimento {AQUECE}, perf_counter_ns, um núcleo",
                                                 "unidade": "ms", "operacoes": res}))


if __name__ == "__main__":
    main()
