"""
polymarket_us_auth.py — Ed25519 request signing for the Polymarket US retail API.

Shared by the execution client (`polymarket_exec_client`) and the read-only
market-data client (`polymarket_us_data`) so the signing contract lives in one
place. Verified live 2026-07-20 — see docs/setup/polymarket-us-setup.md:

  - Headers: X-PM-Access-Key (key_id), X-PM-Timestamp (ms), X-PM-Signature
    = base64(Ed25519 sign of "{ts}{METHOD}{path}")
  - The signed message covers the **bare path only** — query strings and the
    request body are NOT signed (signing the query returns 401).
  - The base64 secret decodes to 64 bytes; the first 32 are the Ed25519 seed.
"""

import base64
import time


def load_signer(secret_key: str):
    """Build an Ed25519 private key from the base64-encoded secret."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(secret_key)[:32])


def signed_headers(key_id: str, signer, method: str, path: str) -> dict:
    """Return the signed request headers. `path` must be the bare request path
    (no query string) — that is what the signature covers."""
    ts = str(int(time.time() * 1000))
    sig = base64.b64encode(signer.sign(f"{ts}{method}{path}".encode())).decode()
    return {
        "X-PM-Access-Key": key_id,
        "X-PM-Timestamp": ts,
        "X-PM-Signature": sig,
        "Content-Type": "application/json",
    }
