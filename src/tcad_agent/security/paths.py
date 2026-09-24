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
_CREDENTIAL_FILENAMES = frozenset(
    {
        ".dockerconfigjson",
        ".envrc",
        ".git-credentials",
        ".npmrc",
        ".pypirc",
        "auth.json",
    }
)


def is_credential_path(path: Path) -> bool:
    """Return whether any path component conventionally contains credentials."""

    components = {part.casefold() for part in path.parts}
    return bool(
        components & CREDENTIAL_PATH_COMPONENTS
        or components & _CREDENTIAL_FILENAMES
        or any(part.startswith(".env.") for part in components)
    )
