from __future__ import annotations

from scripts.build_native_installers import sanitized_builder_environment


def test_unsigned_build_removes_empty_signing_variables() -> None:
    environment = sanitized_builder_environment(
        {
            "PATH": "/usr/bin",
            "CSC_LINK": "",
            "CSC_KEY_PASSWORD": "",
            "CSC_IDENTITY_AUTO_DISCOVERY": "false",
        }
    )

    assert environment == {
        "PATH": "/usr/bin",
        "CSC_IDENTITY_AUTO_DISCOVERY": "false",
    }


def test_signed_build_preserves_nonempty_signing_variables() -> None:
    environment = sanitized_builder_environment(
        {
            "CSC_LINK": "certificate-data",
            "CSC_KEY_PASSWORD": "password",
            "CSC_IDENTITY_AUTO_DISCOVERY": "true",
        }
    )

    assert environment["CSC_LINK"] == "certificate-data"
    assert environment["CSC_KEY_PASSWORD"] == "password"
    assert environment["CSC_IDENTITY_AUTO_DISCOVERY"] == "true"
