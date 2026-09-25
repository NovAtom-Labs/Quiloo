# Agent Kronig Native Desktop Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the existing Agent Kronig workspace as a self-contained, browserless desktop application with a packaged Python backend, native folder selection, safe lifecycle management, cross-platform installers, and update readiness.

**Architecture:** A thin Electron shell starts a loopback-only Python sidecar, exchanges a one-use launch token for an HTTP-only desktop session, and loads the existing FastAPI workspace unchanged. The shell exposes a narrow preload bridge for folder selection and application lifecycle while scientific, agentic, repository, and permission behavior remains in Python. Target-native CI builds Electron installers and PyInstaller sidecars for Linux, Windows, and macOS.

**Tech Stack:** Python 3.13, FastAPI, Uvicorn, PyInstaller, Electron 44.4.5, electron-builder 26.15.3, electron-updater 6.8.9, Node built-in test runner, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-09-25-native-desktop-distribution-design.md`

## Global Constraints

- Treat `ExperimentSpec` as the simulator-neutral product contract.
- Never branch product behavior on a named device.
- Keep simulator syntax inside adapter packages and refuse unsupported physics.
- Preserve source, version, hash, compiler, simulator, and validation provenance.
- Never place credentials or proprietary Sentaurus material in the repository.
- Keep `tcad-agent serve` operational and behaviorally compatible.
- Bind every desktop backend to `127.0.0.1` on an operating-system-selected port.
- Keep Electron renderer sandboxing and context isolation enabled with Node integration disabled.
- Never apply an update while an agent or simulation run is active.
- Build each distributable on its target operating system.

## Review Focus

- A stolen, reused, empty, or malformed bootstrap token must not create a desktop session. Task 1 tests all four cases.
- A stale or competing data lock must fail clearly without corrupting the SQLite store. Task 1 tests live contention and clean release.
- Backend stdout noise or a malformed readiness record must not open a privileged window. Task 3 tests bounded parsing and rejection.
- Native folder selection cancellation and unexpected paths must not create a workspace. Task 2 tests bridge cancellation and server-side canonicalization.
- Update actions during active work must remain blocked even if the renderer requests installation directly. Task 4 tests main-process gating against backend status.

---

### Task 1: Desktop backend mode and private session

**Files:**
- Create: `src/tcad_agent/desktop/__init__.py`
- Create: `src/tcad_agent/desktop/config.py`
- Create: `src/tcad_agent/desktop/lock.py`
- Create: `src/tcad_agent/desktop/auth.py`
- Create: `src/tcad_agent/desktop/server.py`
- Modify: `src/tcad_agent/web/app.py`
- Modify: `src/tcad_agent/web/ide_routes.py`
- Modify: `pyproject.toml`
- Test: `tests/unit/desktop/test_config.py`
- Test: `tests/unit/desktop/test_lock.py`
- Test: `tests/unit/desktop/test_auth.py`
- Test: `tests/unit/desktop/test_server.py`

**Interfaces:**
- Produces: `DesktopLaunchConfig.from_environment()`, `DataDirectoryLock`, `DesktopAuth`, `create_desktop_app(config)`, `serve_desktop(config)`, and the `agent-kronig-desktop-backend` script.
- Produces: `GET /api/desktop/status -> {active: bool}` for lifecycle and updater gating.
- Consumes: existing `create_app`, `build_default_ide_services`, `AgentSupervisor`, and `runtime_fingerprint`.

- [ ] **Step 1: Write failing data-path and configuration tests**

  Test literal Linux, Windows, and macOS paths through `default_data_dir(system, home, environment)`. Test that `DesktopLaunchConfig.from_environment()` rejects a non-loopback host, a missing token, and tokens shorter than 32 bytes.

- [ ] **Step 2: Run the configuration tests and verify RED**

  Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q tests/unit/desktop/test_config.py`
  Expected: import failure because `tcad_agent.desktop.config` does not exist.

- [ ] **Step 3: Implement immutable desktop configuration**

  Add `default_data_dir()` and a frozen `DesktopLaunchConfig` with `host`, `port`, `launch_token`, `data_dir`, `protocol_version`, and `devsim_runner`. Derive platform directories from explicit arguments in tests and from `platform.system()`, `Path.home()`, and `os.environ` in production.

- [ ] **Step 4: Write and run failing lock tests**

  Test that one `DataDirectoryLock` acquires the data directory, a second instance raises `DesktopDataLockError`, and closing the first allows the second to acquire. Run the test and verify failure because the lock does not exist.

- [ ] **Step 5: Implement cross-platform advisory locking**

  Keep one open lock file handle. Use `fcntl.flock(..., LOCK_EX | LOCK_NB)` on POSIX and `msvcrt.locking(..., LK_NBLCK, 1)` on Windows. Store the current PID for diagnostics and release the operating-system lock in `close()` and context-manager exit.

- [ ] **Step 6: Write and run failing authentication tests**

  Create a real FastAPI `TestClient` around `create_app(desktop_auth=DesktopAuth(token))`. Assert `/health` remains public, `/` returns 401 before bootstrap, an invalid or short token returns 403, a valid token redirects and sets an HTTP-only SameSite strict cookie, the same token cannot be exchanged twice, and the cookie opens `/`.

- [ ] **Step 7: Implement desktop authentication middleware and bootstrap**

  Add `DesktopAuth` with constant-time token comparison and one-use consumption. Add middleware that allows only `/health` and `/desktop/bootstrap` before authentication. Add a bootstrap route that sets the cookie and redirects to `/`. Leave browser mode unchanged when `desktop_auth` is absent.

- [ ] **Step 8: Write and run failing readiness and activity tests**

  Test `readiness_record()` against literal expected JSON fields. Build an IDE store with one running record and assert `GET /api/desktop/status` reports active; transition it to completed and assert false. Verify the server binds a supplied socket on port zero and prints one readiness record before serving.

- [ ] **Step 9: Implement the backend entrypoint**

  Build the IDE services before `create_app`, acquire `DataDirectoryLock`, create the desktop app, bind a socket to `127.0.0.1:0`, emit one compact JSON readiness line, and run `uvicorn.Server` with the bound socket. Add `agent-kronig-desktop-backend = "tcad_agent.desktop.server:main"`.

- [ ] **Step 10: Verify and commit Task 1**

  Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q tests/unit/desktop tests/unit/web`
  Expected: all selected tests pass.

  Commit: `feat(desktop): add private managed backend mode`

### Task 2: Desktop-aware frontend bridge

**Files:**
- Create: `src/tcad_agent/web/static/desktop-bridge.js`
- Modify: `src/tcad_agent/web/templates/ide.html`
- Modify: `src/tcad_agent/web/static/ide.js`
- Test: `tests/js/desktop_bridge.test.js`
- Modify: `tests/unit/web/test_api.py`
- Modify: `tests/unit/web/test_ide_javascript.py`

**Interfaces:**
- Consumes: preload API `window.agentKronigDesktop.selectDirectory()` returning `{cancelled: boolean, path: string | null}`.
- Produces: `AgentKronigDesktopBridge.selectDirectory(fetchImpl, desktopApi)` with native-first, browser-fallback behavior.

- [ ] **Step 1: Write the failing bridge behavior test**

  Test three literal cases with real promises: native bridge returns `/home/research/project`; native cancellation returns `null` without calling fetch; absent bridge calls `POST /api/system/directories/select` and returns its path.

- [ ] **Step 2: Run the bridge test and verify RED**

  Run: `pnpm exec node tests/js/desktop_bridge.test.js`
  Expected: failure because `desktop-bridge.js` does not exist.

- [ ] **Step 3: Implement the bridge and wire Open Folder**

  Export a small browser module and call it from the existing Open Folder handler. Preserve server-side canonicalization by submitting the returned path through the existing workspace form flow. Load the bridge script before `ide.js` with a cache-busting version.

- [ ] **Step 4: Verify and commit Task 2**

  Run: `OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q tests/unit/web && pnpm exec node tests/js/desktop_bridge.test.js`
  Expected: all selected tests pass.

  Commit: `feat(desktop): connect native folder selection bridge`

### Task 3: Secure Electron shell and backend supervisor

**Files:**
- Create: `desktop/package.json`
- Create: `desktop/pnpm-lock.yaml`
- Create: `desktop/src/readiness.js`
- Create: `desktop/src/backend-supervisor.js`
- Create: `desktop/src/preload.js`
- Create: `desktop/src/main.js`
- Create: `desktop/src/error.html`
- Create: `desktop/test/readiness.test.js`
- Create: `desktop/test/backend-supervisor.test.js`
- Create: `desktop/test/preload-contract.test.js`
- Create: `desktop/assets/icon.svg`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Task 1 readiness JSON and bootstrap URL.
- Produces: `parseReadinessLine(line)`, `BackendSupervisor`, and the allowlisted `agentKronigDesktop` preload API.
- Produces: `pnpm --dir desktop start` and `pnpm --dir desktop test`.

- [ ] **Step 1: Create package metadata and install pinned dependencies**

  Use Electron `44.4.5`, electron-builder `26.15.3`, and electron-updater `6.8.9`. Define `start`, `test`, `pack`, and `dist` scripts. Generate the lockfile with `pnpm --dir desktop install --lockfile-only`.

- [ ] **Step 2: Write and run failing readiness parser tests**

  Assert that one literal record with protocol `1`, loopback URL, PID, and fingerprint parses. Reject non-JSON, arrays, non-loopback URLs, wrong protocols, missing fields, and lines over 16 KiB.

  Run: `pnpm --dir desktop test`
  Expected: failure because the readiness parser does not exist.

- [ ] **Step 3: Implement readiness parsing**

  Parse one bounded line, require exact field types, require `http://127.0.0.1:<port>`, and return a frozen object. Do not accept `localhost`, IPv6, HTTPS, paths, credentials, or query strings in the readiness URL.

- [ ] **Step 4: Write and run failing supervisor tests**

  Use a temporary executable Node fixture that emits readiness or malformed output. Assert successful readiness, timeout termination, malformed-record rejection, early-exit reporting, and idempotent graceful stop. Assert environment carries the token and data path while command arguments do not.

- [ ] **Step 5: Implement `BackendSupervisor`**

  Spawn the configured sidecar asynchronously, read one bounded stdout line, collect bounded sanitized stderr, expose `start()` and `stop()`, poll `/health`, and terminate the process tree on timeout or application exit. In development, launch `.venv/bin/python -m tcad_agent.desktop.server`; in a packaged app, launch the resource sidecar.

- [ ] **Step 6: Write and run the preload contract test**

  Load the preload module through an injected `contextBridge` and `ipcRenderer`. Assert the exposed object contains exactly `selectDirectory`, `getDesktopInfo`, `getUpdateState`, `checkForUpdates`, and `applyUpdateWhenSafe` and no raw IPC function.

- [ ] **Step 7: Implement the secure window and IPC handlers**

  Acquire the single-instance lock, start the backend, create the window only after health succeeds, and load `/desktop/bootstrap?token=<encoded token>`. Configure `contextIsolation: true`, `sandbox: true`, and `nodeIntegration: false`. Deny navigation outside the launch origin, deny window creation, and handle native directory selection through `dialog.showOpenDialog`.

- [ ] **Step 8: Add deterministic diagnostics**

  Show the local `error.html` page for startup failures. Include a sanitized category, log path, Retry, and Quit. Never render child stdout, credentials, tokens, prompts, or arbitrary HTML.

- [ ] **Step 9: Verify and commit Task 3**

  Run: `pnpm --dir desktop test && OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q tests/unit/desktop tests/unit/web`
  Expected: all selected tests pass.

  Commit: `feat(desktop): add secure Electron application shell`

### Task 4: Safe update state and release packaging

**Files:**
- Create: `desktop/src/update-controller.js`
- Create: `desktop/test/update-controller.test.js`
- Create: `desktop/electron-builder.yml`
- Create: `packaging/pyinstaller/backend.spec`
- Create: `packaging/pyinstaller/devsim_runner.spec`
- Create: `src/tcad_agent/desktop/devsim_runner.py`
- Create: `scripts/build_desktop_sidecars.py`
- Create: `.github/workflows/desktop-build.yml`
- Modify: `desktop/src/main.js`
- Modify: `desktop/package.json`
- Modify: `pyproject.toml`
- Test: `tests/unit/desktop/test_devsim_runner.py`
- Test: `tests/unit/desktop/test_build_sidecars.py`

**Interfaces:**
- Consumes: Task 1 `/api/desktop/status` and Task 3 IPC surface.
- Produces: `UpdateController` state machine and target-native AppImage, DEB, NSIS, DMG, and ZIP configurations.
- Produces: fixed DEVSIM runner command `agent-kronig-devsim <compiled-job-json>`.

- [ ] **Step 1: Write and run failing updater tests**

  Inject an updater adapter and backend-status client. Assert stable initial state, update check transitions, download progress, verification error, active-work rejection, idle installation, and pilot or stable channel selection. Assert direct renderer requests cannot bypass the backend status check.

- [ ] **Step 2: Implement the updater state machine**

  Wrap `electron-updater` behind `UpdateController`. Keep automatic installation disabled. Require the backend to report `active: false` immediately before `quitAndInstall`. Expose sanitized state through IPC. Disable network update checks when no HTTPS feed is configured.

- [ ] **Step 3: Write and run failing DEVSIM sidecar tests**

  Test that the runner accepts one compiled-job manifest, invokes the existing fixed DEVSIM runtime contract, rejects paths outside the job root, and returns a nonzero exit code with sanitized stderr for malformed jobs.

- [ ] **Step 4: Implement the DEVSIM sidecar entrypoint**

  Reuse the deterministic compiled job and local-runner boundary. Do not accept arbitrary shell commands or simulator source from standard input.

- [ ] **Step 5: Write and run failing sidecar build-script tests**

  Inject a command runner and assert exact PyInstaller calls, immutable output directories, target-specific executable names, and failure when expected output is absent.

- [ ] **Step 6: Implement PyInstaller specifications and build orchestration**

  Collect package templates, static assets, fonts, manifests, skills, curated knowledge, OpenHands data, and native libraries. Produce one-folder backend and DEVSIM distributions and copy them into `desktop/resources/<platform>-<arch>/` for electron-builder.

- [ ] **Step 7: Configure target-native installers and CI**

  Configure Linux AppImage and DEB, Windows NSIS and portable ZIP, and macOS DMG and ZIP. Add a GitHub Actions matrix using Ubuntu, Windows, Intel macOS, and Apple Silicon macOS runners. Each job installs Python 3.13 and pnpm, runs tests, builds sidecars, packages Electron, inventories artifacts, scans for `.env` and secret patterns, and uploads unsigned development artifacts. Release signing runs only when the corresponding protected secrets are present.

- [ ] **Step 8: Verify and commit Task 4**

  Run: `pnpm --dir desktop test && OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q tests/unit/desktop`
  Expected: all selected tests pass.

  Commit: `build(desktop): package sidecars installers and updates`

### Task 5: Installation documentation and local macOS proof

**Files:**
- Modify: `README.md`
- Modify: `INSTALLATION.md`
- Create: `docs/operations/desktop-application.md`
- Create: `scripts/run_desktop_dev.sh`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: Tasks 1 through 4 commands and artifact paths.
- Produces: one supported developer launch command, platform installation instructions, update policy, diagnostics, and uninstall behavior.

- [ ] **Step 1: Add the supported development launcher**

  The script resolves the repository root, loads `.env` without printing it, sets a desktop-specific `TCAD_WORKSPACE`, and runs `pnpm --dir desktop start`. It refuses a missing virtual environment or missing desktop dependencies with one actionable message.

- [ ] **Step 2: Document installation and operation**

  Document AppImage, DEB, NSIS, Intel DMG, and Apple Silicon DMG installation. Explain data locations, browser-mode preservation, native folder selection, update channels, safe restart, logs, crash recovery, Sentaurus separation, and uninstallation without deleting repositories.

- [ ] **Step 3: Build and run the macOS development application**

  Install desktop dependencies, launch the Electron application against the source backend, open the fixture repository with the native folder dialog, inspect a file, and close the application. Then run `pnpm --dir desktop run pack:app` and launch the generated `.app` bundle against its packaged backend sidecar.

- [ ] **Step 4: Run final verification**

  Run:

  ```bash
  OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/pytest -q
  .venv/bin/ruff check .
  OPENHANDS_SUPPRESS_BANNER=1 .venv/bin/mypy src
  .venv/bin/python scripts/sync_requirements.py --check
  pnpm --dir desktop test
  git diff --check
  ```

  Expected: all commands exit zero.

- [ ] **Step 5: Commit Task 5**

  Commit: `docs(desktop): document native installation and operations`
