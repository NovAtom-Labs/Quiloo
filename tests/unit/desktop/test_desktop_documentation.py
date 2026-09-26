from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_desktop_launchers_delegate_to_the_shared_native_entrypoint() -> None:
    launcher = ROOT / "scripts" / "run_desktop_dev.sh"
    windows_launcher = ROOT / "scripts" / "run_desktop_dev.ps1"

    assert launcher.exists()
    assert os.access(launcher, os.X_OK)
    source = launcher.read_text()
    assert '"$REPOSITORY_ROOT/.venv/bin/python"' in source
    assert '"$REPOSITORY_ROOT/scripts/run_desktop_dev.py"' in source
    assert windows_launcher.exists()
    windows_source = windows_launcher.read_text()
    assert ".venv\\Scripts\\python.exe" in windows_source
    assert "scripts\\run_desktop_dev.py" in windows_source


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


def test_repository_exposes_no_standalone_browser_launcher() -> None:
    readme = (ROOT / "README.md").read_text()
    installation = (ROOT / "INSTALLATION.md").read_text()
    operations = (ROOT / "docs" / "operations" / "desktop-application.md").read_text()
    project = (ROOT / "pyproject.toml").read_text()

    assert not (ROOT / "src" / "tcad_agent" / "web" / "launcher.py").exists()
    assert not (ROOT / "launch_tcad_agent.command").exists()
    assert not (ROOT / "docs" / "operations" / "local-web-app.md").exists()
    for source in (readme, installation, operations, project):
        assert "tcad-agent serve" not in source
        assert "tcad-agent-web" not in source
        assert "--no-browser" not in source


def test_desktop_interface_exposes_update_controls() -> None:
    template = (ROOT / "src" / "tcad_agent" / "web" / "templates" / "ide.html").read_text()
    script = (ROOT / "src" / "tcad_agent" / "web" / "static" / "ide.js").read_text()

    assert 'id="desktop-check-updates"' in template
    assert 'id="desktop-apply-update"' in template
    assert "checkForUpdates" in script
    assert "applyUpdateWhenSafe" in script


def test_readme_leads_with_native_alpha_downloads() -> None:
    readme = (ROOT / "README.md").read_text()
    source_setup = readme.index("Develop from source")

    assert readme.lstrip().startswith("<p align=\"center\">")
    for phrase in (
        "Agent Kronig",
        "Alpha software",
        "Native desktop application",
        "DEVSIM",
        "Sentaurus",
        "v0.1.0-alpha.12/Agent-Kronig-0.1.0-alpha.12-linux-x64.AppImage",
        "v0.1.0-alpha.12/Agent-Kronig-0.1.0-alpha.12-win-x64.exe",
        "v0.1.0-alpha.12/Agent-Kronig-0.1.0-alpha.12-mac-x64.dmg",
        "v0.1.0-alpha.12/Agent-Kronig-0.1.0-alpha.12-mac-arm64.dmg",
    ):
        assert phrase in readme
        if "v0.1.0-alpha.12/" in phrase:
            assert readme.index(phrase) < source_setup


def test_readme_reports_the_repository_license() -> None:
    readme = (ROOT / "README.md").read_text()
    license_text = (ROOT / "LICENSE").read_text()

    assert "Apache License 2.0" in readme
    assert "Apache License" in license_text


def test_alpha_release_and_community_documents_are_complete() -> None:
    release_notes = (ROOT / "docs" / "releases" / "v0.1.0-alpha.12.md").read_text()
    security = (ROOT / "SECURITY.md").read_text()
    required_files = (
        ROOT / "CONTRIBUTING.md",
        ROOT / "SECURITY.md",
        ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "bug-report.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml",
    )

    for path in required_files:
        assert path.exists()
    for phrase in (
        "Unsigned alpha",
        "Manual updates",
        "Current capabilities",
        "Known limitations",
    ):
        assert phrase in release_notes
    assert "Do not open a public issue" in security
    assert "credentials" in security
    assert "vulnerabilities" in security


def test_new_public_documents_do_not_use_em_dashes() -> None:
    paths = (
        ROOT / "README.md",
        ROOT / "INSTALLATION.md",
        ROOT / "CONTRIBUTING.md",
        ROOT / "SECURITY.md",
        ROOT / "docs" / "releases" / "v0.1.0-alpha.12.md",
        ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "bug-report.yml",
        ROOT / ".github" / "ISSUE_TEMPLATE" / "config.yml",
    )
    for path in paths:
        assert "—" not in path.read_text()
