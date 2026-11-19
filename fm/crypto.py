"""Cifrado de los datos que se publican en la web (AES-256-GCM).

El repositorio y la web son públicos, pero los datos de tu liga viajan cifrados.
La clave (DIRECTOR_KEY, 32 bytes en base64url) solo está en los secretos de
GitHub y en tu enlace personal, detrás del '#', que el navegador nunca envía
al servidor. Sin la clave, data.enc es ruido.

Formato: base64( nonce[12] + AES-GCM(gzip(json)) ).

Uso:
    python -m fm.crypto nueva-clave
    python -m fm.crypto cifrar entrada salida      (usa $DIRECTOR_KEY)
    python -m fm.crypto descifrar entrada salida
"""

import base64
import gzip
import os
import sys


def _key(key_b64=None):
    k = (key_b64 or os.getenv("DIRECTOR_KEY", "")).strip()
    if not k:
        raise RuntimeError("Falta DIRECTOR_KEY")
    raw = base64.urlsafe_b64decode(k + "=" * (-len(k) % 4))
    if len(raw) != 32:
        raise RuntimeError("DIRECTOR_KEY debe ser de 32 bytes")
    return raw


def new_key():
    return base64.urlsafe_b64encode(os.urandom(32)).decode().rstrip("=")


def encrypt_bytes(data, key_b64=None, compress=True):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    payload = gzip.compress(data, mtime=0) if compress else data
    ct = AESGCM(_key(key_b64)).encrypt(nonce, payload, None)
    return base64.b64encode(nonce + ct)


def decrypt_bytes(blob, key_b64=None, compressed=True):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    raw = base64.b64decode(blob)
    out = AESGCM(_key(key_b64)).decrypt(raw[:12], raw[12:], None)
    return gzip.decompress(out) if compressed else out


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = argv[0]
    if cmd == "nueva-clave":
        print(new_key())
        return 0
    if cmd in ("cifrar", "descifrar") and len(argv) == 3:
        with open(argv[1], "rb") as f:
            data = f.read()
        out = encrypt_bytes(data) if cmd == "cifrar" else decrypt_bytes(data)
        with open(argv[2], "wb") as f:
            f.write(out)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
