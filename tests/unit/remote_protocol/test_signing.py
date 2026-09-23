from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tcad_agent.remote_protocol.models import SubmitJobPayload
from tcad_agent.remote_protocol.signing import (
    SignatureVerificationError,
    encode_private_key,
    encode_public_key,
    sign_submit_request,
    verify_submit_request,
)


def payload() -> SubmitJobPayload:
    now = datetime.now(UTC)
    return SubmitJobPayload(
        job_id=uuid4(),
        required_simulator_version="S-2024.03",
        manifest_sha256="a" * 64,
        bundle_b64="Ynl0ZXM=",
        issued_at=now,
        expires_at=now + timedelta(minutes=5),
    )


def test_valid_ed25519_signature_verifies() -> None:
    private = Ed25519PrivateKey.generate()
    request = sign_submit_request(payload(), encode_private_key(private))
    verify_submit_request(request, encode_public_key(private.public_key()))


def test_altered_signed_field_is_rejected() -> None:
    private = Ed25519PrivateKey.generate()
    request = sign_submit_request(payload(), encode_private_key(private))
    altered = request.model_copy(update={"manifest_sha256": "b" * 64})
    with pytest.raises(SignatureVerificationError):
        verify_submit_request(altered, encode_public_key(private.public_key()))


def test_untrusted_public_key_is_rejected() -> None:
    private = Ed25519PrivateKey.generate()
    untrusted = Ed25519PrivateKey.generate()
    request = sign_submit_request(payload(), encode_private_key(private))
    with pytest.raises(SignatureVerificationError):
        verify_submit_request(request, encode_public_key(untrusted.public_key()))
