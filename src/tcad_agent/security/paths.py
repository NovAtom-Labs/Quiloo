"""Credential-like path detection shared by policy and persistence layers."""

from pathlib import Path

CREDENTIAL_PATH_COMPONENTS = frozenset(
    {
        ".aws",
        ".env",
        ".gnupg",
        ".netrc",
        ".ssh",
        "credentials",
        "id_ed25519",
        "id_rsa",
        "secrets",
    }
)


def is_credential_path(path: Path) -> bool:
    """Return whether any path component conventionally contains credentials."""

    return bool({part.casefold() for part in path.parts} & CREDENTIAL_PATH_COMPONENTS)
