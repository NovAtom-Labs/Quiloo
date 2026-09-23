"""Canonical Ed25519 signing for remote job submissions."""

from __future__ import annotations

import base64
import binascii
import json

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from tcad_agent.remote_protocol.models import SubmitJobPayload, SubmitJobRequest


class SignatureVerificationError(ValueError):
    pass


def encode_private_key(key: Ed25519PrivateKey) -> str:
    raw = key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return base64.b64encode(raw).decode()


def encode_public_key(key: Ed25519PublicKey) -> str:
    raw = key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode()


def _decode(value: str, *, expected_length: int) -> bytes:
    try:
        decoded = base64.b64decode(value, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise SignatureVerificationError("invalid base64 key or signature") from exc
    if len(decoded) != expected_length:
        raise SignatureVerificationError("invalid key or signature length")
    return decoded


def canonical_submit_bytes(value: SubmitJobPayload | SubmitJobRequest) -> bytes:
    fields = value.model_dump(mode="json", exclude={"signature_b64", "bundle_b64"})
    return json.dumps(fields, sort_keys=True, separators=(",", ":")).encode()


def sign_submit_request(payload: SubmitJobPayload, private_key_b64: str) -> SubmitJobRequest:
    key = Ed25519PrivateKey.from_private_bytes(_decode(private_key_b64, expected_length=32))
    signature = key.sign(canonical_submit_bytes(payload))
    values = payload.model_dump(mode="python")
    values["signature_b64"] = base64.b64encode(signature).decode()
    return SubmitJobRequest.model_validate(values)


def verify_submit_request(request: SubmitJobRequest, public_key_b64: str) -> None:
    signature = _decode(request.signature_b64, expected_length=64)
    try:
        Ed25519PublicKey.from_public_bytes(_decode(public_key_b64, expected_length=32)).verify(
            signature, canonical_submit_bytes(request)
        )
    except InvalidSignature as exc:
        raise SignatureVerificationError("submission signature is not trusted") from exc
