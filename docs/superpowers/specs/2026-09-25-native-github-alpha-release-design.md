# Native GitHub Alpha Release Design

## 1. Objective

The Quiloo repository will present Agent Kronig as a native desktop TCAD research workspace and
publish a reproducible `0.1.0-alpha.1` prerelease for Linux, Windows, Intel Mac, and Apple Silicon.
The public repository must lead with installation and product capability, while preserving the
scientific contracts, security boundaries, simulator neutrality, and contributor detail already
implemented in the codebase.

The release is an alpha. It is suitable for controlled evaluation, not production laboratory
control or fabrication-calibrated prediction.

## 2. Public Repository Structure

The root README will use this order:

1. Agent Kronig identity and one-sentence product description.
2. Alpha status and direct platform download table.
3. A concise explanation of the native repository-agent workflow.
4. Current TCAD and repository capabilities.
5. Explicit scientific and operational limitations.
6. Architecture and simulator-boundary summary.
7. Source-development quick start.
8. Testing, security, documentation, and contribution links.

Detailed installation, operations, architecture, acceptance, and product material will remain in
dedicated documents. The README will link to them instead of duplicating their full contents.
Generated installers, application bundles, sidecars, local workspaces, secrets, and proprietary
Sentaurus material will remain outside Git history.

## 3. Release Identity

- Application version: `0.1.0-alpha.1`
- Git tag: `v0.1.0-alpha.1`
- GitHub release title: `Agent Kronig 0.1.0 Alpha 1`
- GitHub release state: prerelease
- Release notes source: `docs/releases/v0.1.0-alpha.1.md`

The Python project version and Electron package version must match. A deterministic verification
script will reject a mismatched tag or malformed prerelease version before platform builds start.

## 4. Native Build Matrix

One tag-triggered GitHub Actions workflow will run four independent native builds:

| Platform | Runner | Architecture | Published packages |
| --- | --- | --- | --- |
| Linux | Ubuntu latest | x86-64 | AppImage and Debian package |
| Windows | Windows latest | x86-64 | NSIS installer and portable ZIP |
| macOS | Intel macOS runner | x86-64 | DMG and application ZIP |
| macOS | Apple Silicon macOS runner | arm64 | DMG and application ZIP |

Each runner will install locked dependencies, build the reviewed knowledge index, run the Python
and desktop suites, create target-native Python sidecars, scan sidecars and packages for credential
material, and upload only the curated distributable files.

A release job will run only after all four builds succeed. It will download the four artifact sets,
reject duplicate filenames, generate one sorted `SHA256SUMS.txt`, and create the GitHub prerelease.
No partial release will be published when one platform fails.

## 5. Signing and Alpha Trust

Signing remains optional for this first alpha because the repository does not yet expose evidence
that macOS, Windows, and Linux signing secrets are configured. When a platform signing secret is
present, the native builder will use it. When it is absent, the build will remain unsigned and the
release notes will say so plainly.

The workflow must never print signing keys or credentials. Linux detached signatures are published
only when the configured Ed25519 signing key produces them. The pinned public key remains the
authority for later in-app Linux update verification.

This alpha will not publish auto-update channel metadata. Manual download and reinstall is the
supported update path until per-platform signing and update feeds are operational.

## 6. GitHub Release Content

The release will contain only:

- Linux AppImage and Debian installer
- Windows NSIS installer and portable ZIP
- Intel Mac DMG and application ZIP
- Apple Silicon DMG and application ZIP
- optional Linux detached signature
- `SHA256SUMS.txt`

Unpacked application directories, build logs, PyInstaller work products, source maps, temporary
archives, credentials, and proprietary simulator files must never be release assets.

## 7. Release Notes

The alpha notes will summarize:

- native repository workbench and local file operation
- agentic editing, terminal execution, task tracking, and bounded subagents
- approval-gated actions outside the selected repository
- DEVSIM execution and deterministic evidence bundles
- simulator-neutral `ExperimentSpec` and Sentaurus adapter boundary
- current scientific and operational limitations
- unsigned-build installation warnings
- supported manual upgrade path

The notes will not imply that licensed Sentaurus execution, production signing, automatic updates,
hardware control, or fabrication calibration is complete.

## 8. GitHub Metadata

The public repository title in source content is Agent Kronig. The existing GitHub repository URL
remains `NovAtom-Labs/Quiloo` for this alpha so cloning and existing links stay stable. The desired
repository description is:

> Native simulator-neutral TCAD research agent for repository workflows, DEVSIM execution, and
> validated Sentaurus-ready evidence.

The desired topics are `tcad`, `electron`, `scientific-computing`, `semiconductor`, `devsim`,
`sentaurus`, `openhands`, and `agentic-ai`. Updating repository metadata requires authenticated
GitHub API or settings access and is separate from Git transport.

## 9. Failure and Security Behavior

- A version mismatch stops the workflow before expensive platform builds.
- A Python, desktop, packaging, or credential-scan failure blocks that platform and the release.
- A missing expected installer fails artifact staging.
- Duplicate release filenames fail aggregation instead of overwriting an asset.
- A tag that already has a release is updated idempotently only by the same workflow and tag.
- Release publication uses the workflow-scoped `GITHUB_TOKEN` with `contents: write` only in the
  release job.
- Pull requests and ordinary branch pushes retain read-only workflow permissions.

## 10. Acceptance Criteria

The work is accepted when:

1. Local `main` and `origin/main` contain the native application implementation.
2. README and installation entrypoints describe a native-only product.
3. Python and Electron versions both report `0.1.0-alpha.1`.
4. Release metadata validation passes for `v0.1.0-alpha.1` and rejects mismatches.
5. The complete Python and desktop test suites pass.
6. The release workflow validates syntactically and exposes four native build jobs plus one gated
   publication job.
7. Tag `v0.1.0-alpha.1` is pushed only after the source commit reaches `origin/main`.
8. GitHub publishes one prerelease containing every expected platform package and
   `SHA256SUMS.txt`, or the exact failing runner and reason are reported without publishing a
   partial release.
