# Native GitHub Alpha Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Present Agent Kronig as a native desktop product on GitHub and publish the gated `v0.1.0-alpha.1` prerelease for Linux, Windows, Intel Mac, and Apple Silicon.

**Architecture:** A shared release-contract module validates Python, Electron, and tag versions before expensive builds. Native matrix jobs test and package on their own operating systems, a deterministic staging tool admits only reviewed installer formats, and one gated publication job generates checksums and creates the prerelease after every build succeeds. The public README and supporting community documents lead with native installation while detailed scientific and operational material remains linked documentation.

**Tech Stack:** Python 3.13, pytest, Electron 44, electron-builder, GitHub Actions, GitHub Releases, Bash and PowerShell runner shells.

**Spec:** `docs/superpowers/specs/2026-09-25-native-github-alpha-release-design.md`

## Global Constraints

- Application version is exactly `0.1.0-alpha.1` and the Git tag is exactly `v0.1.0-alpha.1`.
- Linux x86-64, Windows x86-64, Intel Mac, and Apple Silicon must build on native GitHub-hosted runners.
- The release is a GitHub prerelease and is never published partially.
- Release assets are installers, portable application archives, an optional Linux signature, and one checksum manifest only.
- Missing signing secrets produce honestly labeled unsigned alpha packages and never print credentials.
- Auto-update channel metadata is not published in this alpha.
- `ExperimentSpec` remains the simulator-neutral contract and no release work changes simulator behavior.
- Proprietary Sentaurus material and credentials never enter Git history or release artifacts.
- Documentation and release copy use Agent Kronig as the product name and contain no em dashes.

## Review Focus

- A tag whose version differs from Python or Electron metadata must fail before matrix builds start. Covered by Task 1 release-contract tests.
- A platform build missing one required installer must fail staging instead of publishing an incomplete artifact set. Covered by Task 2 staging tests.
- Two platform artifacts with the same filename must fail aggregation instead of overwriting one another. Covered by Task 2 aggregation tests.
- Empty signing secrets must permit an explicitly unsigned alpha build without expanding workflow permissions. Covered by Task 2 workflow assertions.
- One failed matrix runner must prevent release publication. Covered by Task 2 workflow dependency assertions and Task 4 live workflow inspection.

---

### Task 1: Version and Tag Contract

**Files:**
- Create: `scripts/release_contract.py`
- Create: `tests/unit/desktop/test_release_contract.py`
- Modify: `pyproject.toml`
- Modify: `desktop/package.json`
- Modify: `desktop/pnpm-lock.yaml`

**Interfaces:**
- Consumes: root `pyproject.toml`, `desktop/package.json`, and a tag string.
- Produces: `ReleaseIdentity(version: str, tag: str)`, `load_release_identity(root: Path, tag: str | None) -> ReleaseIdentity`, and a zero-or-nonzero command-line validation entrypoint.

- [ ] **Step 1: Write failing release identity tests**

```python
from pathlib import Path

import pytest

from scripts.release_contract import load_release_identity


def write_versions(root: Path, python_version: str, desktop_version: str) -> None:
    (root / "desktop").mkdir()
    (root / "pyproject.toml").write_text(
        f'[project]\nname = "agent-kronig"\nversion = "{python_version}"\n'
    )
    (root / "desktop" / "package.json").write_text(
        '{"name":"agent-kronig-desktop","version":"' + desktop_version + '"}'
    )


def test_release_identity_accepts_matching_alpha_versions(tmp_path: Path) -> None:
    write_versions(tmp_path, "0.1.0-alpha.1", "0.1.0-alpha.1")
    identity = load_release_identity(tmp_path, "v0.1.0-alpha.1")
    assert identity.version == "0.1.0-alpha.1"
    assert identity.tag == "v0.1.0-alpha.1"


@pytest.mark.parametrize(
    ("python_version", "desktop_version", "tag"),
    [
        ("0.1.0", "0.1.0-alpha.1", "v0.1.0-alpha.1"),
        ("0.1.0-alpha.1", "0.1.0", "v0.1.0-alpha.1"),
        ("0.1.0-alpha.1", "0.1.0-alpha.1", "v0.1.0"),
        ("0.1.0-alpha.1", "0.1.0-alpha.1", "desktop-v0.1.0-alpha.1"),
    ],
)
def test_release_identity_rejects_mismatched_or_nonstandard_versions(
    tmp_path: Path,
    python_version: str,
    desktop_version: str,
    tag: str,
) -> None:
    write_versions(tmp_path, python_version, desktop_version)
    with pytest.raises(ValueError):
        load_release_identity(tmp_path, tag)
```

- [ ] **Step 2: Run the release identity tests and verify RED**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q tests/unit/desktop/test_release_contract.py`

Expected: collection fails because `scripts.release_contract` does not exist.

- [ ] **Step 3: Implement strict release identity validation**

Implement a frozen `ReleaseIdentity` dataclass. Read Python metadata with `tomllib`, Electron metadata with `json`, require exact equality, require semantic prerelease format `MAJOR.MINOR.PATCH-alpha.N`, and require `tag == f"v{version}"` when a tag is provided. The CLI accepts `--root` and optional `--tag`, prints only the validated tag and version, and returns `2` with a concise error on invalid input.

- [ ] **Step 4: Set both project versions to `0.1.0-alpha.1`**

Update `pyproject.toml` and `desktop/package.json`, then run `pnpm --dir desktop install --lockfile-only` with the configured Node runtime so `desktop/pnpm-lock.yaml` carries the same importer version.

- [ ] **Step 5: Verify GREEN and repository identity**

Run:

```bash
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q tests/unit/desktop/test_release_contract.py
.venv/bin/python scripts/release_contract.py --root . --tag v0.1.0-alpha.1
```

Expected: all tests pass and the command reports version `0.1.0-alpha.1` with tag `v0.1.0-alpha.1`.

- [ ] **Step 6: Commit Task 1**

```bash
git add scripts/release_contract.py tests/unit/desktop/test_release_contract.py pyproject.toml desktop/package.json desktop/pnpm-lock.yaml
git commit -m "build(release): enforce alpha version identity"
```

### Task 2: Curated Artifacts and Gated Publication

**Files:**
- Create: `scripts/release_artifacts.py`
- Create: `tests/unit/desktop/test_release_artifacts.py`
- Create: `tests/unit/desktop/test_release_workflow.py`
- Modify: `.github/workflows/desktop-build.yml`

**Interfaces:**
- Consumes: an electron-builder `desktop/dist` directory, platform and architecture names, or a downloaded matrix-artifact tree.
- Produces: `stage_platform_artifacts(source: Path, destination: Path, platform: str, architecture: str) -> tuple[Path, ...]`, `collect_release_artifacts(source: Path, destination: Path) -> tuple[Path, ...]`, a sorted `SHA256SUMS.txt`, and a tag-triggered GitHub prerelease.

- [ ] **Step 1: Write failing artifact selection tests**

Test real temporary files for all four platform and architecture combinations. Require exactly two primary packages per build, permit one Linux `.sig`, refuse unpacked directories and update YAML, reject a missing required suffix, reject duplicate filenames during collection, and verify checksum lines are sorted and match file bytes.

- [ ] **Step 2: Write failing workflow contract tests**

Load `.github/workflows/desktop-build.yml` with `yaml.safe_load` and assert:

```python
assert workflow["on"]["push"]["tags"] == ["v*"]
assert set(workflow["jobs"]) == {"validate", "build", "release"}
assert workflow["jobs"]["build"]["needs"] == "validate"
assert workflow["jobs"]["release"]["needs"] == "build"
assert workflow["jobs"]["release"]["permissions"]["contents"] == "write"
assert workflow["jobs"]["release"]["if"] == "startsWith(github.ref, 'refs/tags/')"
```

Also assert the four expected runner and architecture rows, that ordinary workflow permissions are `contents: read`, that release creation includes `--prerelease`, and that the release job calls `scripts/release_artifacts.py collect` before `gh release create`.

- [ ] **Step 3: Run both test modules and verify RED**

Run:

```bash
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q \
  tests/unit/desktop/test_release_artifacts.py \
  tests/unit/desktop/test_release_workflow.py
```

Expected: failures because the artifact module and publication job do not exist.

- [ ] **Step 4: Implement deterministic artifact staging**

Use exact, case-sensitive suffix contracts:

- Linux x64: one `.AppImage`, one `.deb`, optional matching `.AppImage.sig`
- Windows x64: one `.exe`, one `.zip`
- mac x64: one `.dmg`, one `.zip`, each filename containing `-mac-x64`
- mac arm64: one `.dmg`, one `.zip`, each filename containing `-mac-arm64`

Copy files with `shutil.copy2`, reject destinations that exist, reject symlinks and non-files, and generate SHA-256 values by streaming 1 MiB chunks. The CLI exposes `stage` and `collect` subcommands and prints only staged relative filenames and the checksum manifest path.

- [ ] **Step 5: Redesign the workflow**

Add a `validate` job that checks the tag and versions. Make `build` depend on it. Set `CSC_IDENTITY_AUTO_DISCOVERY` to `false` when signing material is absent. After artifact inspection, invoke the staging script and upload only `desktop/release-stage/**/*` with a seven-day retention period.

Add a Linux `release` job with `contents: write`. Download the four matrix artifacts into separate directories, run deterministic collection, and execute:

```bash
gh release create "$GITHUB_REF_NAME" release-assets/* \
  --repo "$GITHUB_REPOSITORY" \
  --title "Agent Kronig 0.1.0 Alpha 1" \
  --notes-file docs/releases/v0.1.0-alpha.1.md \
  --prerelease \
  --verify-tag
```

Set `GH_TOKEN` only on the publication step from `secrets.GITHUB_TOKEN`.

- [ ] **Step 6: Verify GREEN**

Run:

```bash
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q \
  tests/unit/desktop/test_release_artifacts.py \
  tests/unit/desktop/test_release_workflow.py
```

Expected: all artifact and workflow contract tests pass.

- [ ] **Step 7: Commit Task 2**

```bash
git add scripts/release_artifacts.py tests/unit/desktop/test_release_artifacts.py tests/unit/desktop/test_release_workflow.py .github/workflows/desktop-build.yml
git commit -m "ci(release): publish gated native prereleases"
```

### Task 3: Native-First GitHub Presentation

**Files:**
- Create: `docs/releases/v0.1.0-alpha.1.md`
- Create: `CONTRIBUTING.md`
- Create: `SECURITY.md`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `.github/ISSUE_TEMPLATE/bug-report.yml`
- Create: `.github/ISSUE_TEMPLATE/config.yml`
- Modify: `README.md`
- Modify: `INSTALLATION.md`
- Modify: `tests/unit/desktop/test_desktop_documentation.py`

**Interfaces:**
- Consumes: release tag, native packages, existing operations and scientific documentation.
- Produces: a native-first GitHub landing page, alpha release notes, security reporting policy, contributor workflow, and structured issue intake.

- [ ] **Step 1: Write failing documentation contract tests**

Extend `test_desktop_documentation.py` to assert:

- README begins with Agent Kronig identity and links `v0.1.0-alpha.1` downloads for Linux, Windows, Intel Mac, and Apple Silicon before source-development instructions.
- README contains `Alpha software`, `Native desktop application`, `Sentaurus`, and `DEVSIM`.
- release notes contain `Unsigned alpha`, `Manual updates`, current capabilities, and explicit limitations.
- `CONTRIBUTING.md`, `SECURITY.md`, the pull-request template, and issue configuration exist.
- `SECURITY.md` tells reporters not to open public issues for credentials or vulnerabilities.
- none of the public-facing additions contain em dash characters.

- [ ] **Step 2: Run the documentation tests and verify RED**

Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q tests/unit/desktop/test_desktop_documentation.py`

Expected: failure because release notes and community files do not exist and README does not lead with alpha downloads.

- [ ] **Step 3: Rewrite README around the native product**

Keep the root README concise and professional. Use the tracked Agent Kronig icon, product statement, alpha warning, platform download table, workflow summary, capability table, deliberate limitations, architecture boundary, developer quick start, testing commands, and links to installation, desktop operations, architecture, security, contributing, and license documents. Remove redundant implementation detail already covered by linked documents.

- [ ] **Step 4: Add release and community documentation**

Write concrete alpha notes with install warnings and manual upgrade instructions. Define contribution setup, test gates, simulator-neutral rules, pull-request expectations, responsible vulnerability reporting, and structured bug fields for OS, architecture, package, reproduction, logs with secret redaction, and expected behavior.

- [ ] **Step 5: Verify GREEN**

Run:

```bash
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q tests/unit/desktop/test_desktop_documentation.py
git diff --check
```

Expected: documentation tests and whitespace checks pass.

- [ ] **Step 6: Commit Task 3**

```bash
git add README.md INSTALLATION.md CONTRIBUTING.md SECURITY.md docs/releases .github/PULL_REQUEST_TEMPLATE.md .github/ISSUE_TEMPLATE tests/unit/desktop/test_desktop_documentation.py
git commit -m "docs: present Agent Kronig as a native alpha"
```

### Task 4: Verify, Publish, and Audit Alpha 1

**Files:**
- Modify only if verification finds a tested defect in files from Tasks 1 through 3.

**Interfaces:**
- Consumes: clean `main`, release workflow, and `v0.1.0-alpha.1` tag.
- Produces: synchronized `origin/main`, annotated release tag, completed native workflow, GitHub prerelease URL, and audited asset inventory.

- [ ] **Step 1: Run the complete local verification gate**

Run:

```bash
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q
PATH="/Users/satyagni/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH" pnpm --dir desktop test
.venv/bin/ruff check .
OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/mypy src
.venv/bin/python scripts/sync_requirements.py --check
.venv/bin/python scripts/release_contract.py --root . --tag v0.1.0-alpha.1
git diff --check
```

Expected: every command exits zero.

- [ ] **Step 2: Review the complete release diff**

Review all commits after spec commit `381644d`, confirm no credentials or proprietary material are tracked, and confirm the release job has the only `contents: write` permission.

- [ ] **Step 3: Push verified `main`**

Fetch `origin`, require `git rev-list --left-right --count origin/main...main` to report no remote-only commits, then push `main` normally without force.

- [ ] **Step 4: Create and push the annotated alpha tag**

```bash
git tag -a v0.1.0-alpha.1 -m "Agent Kronig 0.1.0 Alpha 1"
git push origin v0.1.0-alpha.1
```

Create the tag only after the source commit is confirmed on `origin/main`. Never replace an existing tag.

- [ ] **Step 5: Monitor the GitHub Actions run**

Use the public GitHub Actions API to follow the tag-triggered workflow. Wait for all four build jobs and the release job. If a job fails, inspect the exact job and logs, add a failing regression test for any repository defect, fix it on `main`, delete the unreleased local and remote tag only if GitHub has not published a release, then create a new `v0.1.0-alpha.2` version rather than rewriting a published alpha tag.

- [ ] **Step 6: Audit the published prerelease**

Use the GitHub Releases API to require:

- prerelease is `true`
- tag is `v0.1.0-alpha.1`
- Linux AppImage and Debian package exist
- Windows installer and ZIP exist
- Intel Mac DMG and ZIP exist
- Apple Silicon DMG and ZIP exist
- `SHA256SUMS.txt` exists
- no update YAML, unpacked directory, `.env`, or credential-like asset exists

- [ ] **Step 7: Record final publication evidence**

Report the main commit SHA, tag SHA, workflow URL, release URL, exact asset list, checksum manifest, signing status, test totals, and any runner warning that remains relevant to alpha users.
