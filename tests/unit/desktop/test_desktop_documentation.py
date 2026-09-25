from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_desktop_launcher_is_executable_and_uses_the_supported_entrypoint() -> None:
    launcher = ROOT / "scripts" / "run_desktop_dev.sh"

    assert launcher.exists()
    assert os.access(launcher, os.X_OK)
    source = launcher.read_text()
    assert "desktop/node_modules/.bin/electron" in source
    assert "TCAD_WORKSPACE" in source
    assert "pnpm --dir" in source
    assert "source \"$REPOSITORY_ROOT/.env\"" in source


def test_desktop_operations_guide_covers_supported_distribution_contract() -> None:
    guide = (ROOT / "docs" / "operations" / "desktop-application.md").read_text()

    required_phrases = (
        "Linux AppImage",
        "Debian or Ubuntu",
        "Windows installer",
        "Intel Mac",
        "Apple Silicon",
        "No browser is required",
        "AGENT_KRONIG_UPDATE_URL",
        "AGENT_KRONIG_UPDATE_CHANNEL",
        "operating system's protected credential storage",
        "does not delete a selected repository",
        "Sentaurus",
        "scripts/run_desktop_dev.sh",
    )
    for phrase in required_phrases:
        assert phrase in guide


def test_primary_docs_route_users_to_the_native_installation_guide() -> None:
    readme = (ROOT / "README.md").read_text()
    installation = (ROOT / "INSTALLATION.md").read_text()

    assert "Native desktop application" in readme
    assert "docs/operations/desktop-application.md" in readme
    assert "Self-contained native installation" in installation
    assert "docs/operations/desktop-application.md" in installation


def test_desktop_interface_exposes_update_controls() -> None:
    template = (ROOT / "src" / "tcad_agent" / "web" / "templates" / "ide.html").read_text()
    script = (ROOT / "src" / "tcad_agent" / "web" / "static" / "ide.js").read_text()

    assert 'id="desktop-check-updates"' in template
    assert 'id="desktop-apply-update"' in template
    assert "checkForUpdates" in script
    assert "applyUpdateWhenSafe" in script
