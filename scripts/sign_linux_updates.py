#!/usr/bin/env python3
"""Create detached Ed25519 signatures for Linux update artifacts."""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey


def sign_linux_updates(root: Path, private_key_pem: str) -> tuple[Path, ...]:
    key = serialization.load_pem_private_key(
        private_key_pem.encode("utf-8"), password=None
    )
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("Linux update signing key must be Ed25519")
    artifacts = tuple(sorted(root.glob("*.AppImage")))
    if not artifacts:
        raise FileNotFoundError("no Linux AppImage update artifact was found")
    signatures: list[Path] = []
    for artifact in artifacts:
        digest_builder = hashlib.sha256()
        with artifact.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest_builder.update(chunk)
        digest = digest_builder.digest()
        signature_path = artifact.with_name(f"{artifact.name}.sig")
        signature_path.write_bytes(key.sign(digest))
        signatures.append(signature_path)
    return tuple(signatures)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    private_key = os.getenv("DESKTOP_LINUX_SIGNING_PRIVATE_KEY", "")
    if not private_key:
        print("Linux update signing key is not configured; development artifacts remain unsigned.")
        return 0
    for signature in sign_linux_updates(arguments.root, private_key):
        print(signature)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
