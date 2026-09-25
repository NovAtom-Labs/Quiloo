# Agent Kronig Native Desktop Distribution Design

## 1. Objective

Agent Kronig will ship as a self-contained desktop application for Linux, Windows, and macOS.
Researchers will install one application, open an existing repository, and use the current Agent
Kronig workspace without installing a browser, Python, Node.js, or a source checkout.

Linux x86-64 is the primary customer target. Windows x86-64 is the secondary customer target.
macOS Intel and Apple Silicon builds support development, demonstrations, and customers using
macOS workstations.

The desktop application must preserve the existing simulator-neutral product boundaries. It must
not branch behavior on a named device, silently approximate unsupported physics, place simulator
syntax outside its adapter, or weaken result and provenance validation.

## 2. Success Criteria

The first complete desktop release must:

1. Open the existing Agent Kronig interface in a native application window without launching an
   external browser.
2. Start and stop a packaged Agent Kronig backend automatically.
3. Package the Python runtime and application dependencies so customers do not install Python.
4. Package an isolated DEVSIM runner so the pilot simulator works without a separate installation.
5. Keep Sentaurus external and connect through the existing licensed-runner boundary.
6. Select repositories through the operating system's native directory dialog.
7. Preserve the browser launcher for development, headless operation, debugging, and recovery.
8. Store application data in the operating system's standard per-user data directory.
9. Prevent simultaneous desktop and browser backends from mutating the same application-data
   directory.
10. Check for signed pilot or stable updates and install them only when no agent, simulation, or
    future hardware run is active.
11. Produce installable Linux, Windows, and macOS artifacts from native continuous-integration
    runners.
12. Keep timing-sensitive or safety-sensitive hardware control outside Electron and outside the
    LLM process.

## 3. Product Experience

The researcher installs and opens Agent Kronig like any other desktop application. The desktop
window starts a private local backend, waits for a verified readiness response, and then loads the
same HTML, CSS, JavaScript, and FastAPI application used by the browser workflow.

The repository remains in its original location. Agent Kronig stores conversations, run metadata,
logs, configuration, and caches below the normal per-user application-data directory. Files are
copied into the repository only when the researcher or an approved agent action explicitly creates
them.

The desktop and browser modes share one interface and one backend. Desktop-only actions are
enabled through a narrow native bridge. When that bridge is absent, the existing browser fallbacks
remain available.

## 4. Runtime Architecture

```text
Agent Kronig desktop package
  |
  +-- Electron main process
  |     +-- application lifecycle
  |     +-- backend supervisor
  |     +-- native directory dialog
  |     +-- encrypted secret storage
  |     +-- signed update client
  |     +-- diagnostic logging
  |
  +-- Chromium renderer
  |     +-- existing Agent Kronig workspace
  |     +-- isolated preload bridge
  |
  +-- packaged Python backend
  |     +-- FastAPI
  |     +-- OpenHands runtime
  |     +-- workspace and permission services
  |     +-- TCAD knowledge and validation
  |
  +-- packaged DEVSIM runner
        +-- isolated Python runtime
        +-- DEVSIM native dependencies
```

Electron is a presentation and lifecycle shell. It does not execute scientific logic, agent logic,
or hardware timing loops. The Python backend remains authoritative for repository operations,
permissions, TCAD orchestration, canonical results, validation, and evidence.

## 5. Desktop Shell

Desktop code lives under `desktop/`. The shell uses Electron with a minimal main process and no
frontend framework migration. It loads the current loopback application after the backend becomes
ready.

The production `BrowserWindow` configuration must:

- enable `contextIsolation`;
- disable `nodeIntegration`;
- enable renderer sandboxing;
- expose only an allowlisted preload API;
- deny unexpected navigation and new-window requests;
- deny arbitrary permission requests;
- load only the private loopback origin established for the current launch;
- keep development tools disabled in packaged stable builds.

The preload bridge exposes only:

- `selectDirectory()`;
- `getDesktopInfo()`;
- `getUpdateState()`;
- `checkForUpdates()`;
- `applyUpdateWhenSafe()`;
- `openArtifact(path)` after backend path authorization;
- settings operations for encrypted secrets.

The renderer must never receive Node.js, filesystem, process, or unrestricted IPC access.

## 6. Backend Startup and Authentication

The desktop shell launches a packaged backend executable with:

- loopback host `127.0.0.1`;
- port `0`, allowing the operating system to choose an available port;
- a cryptographically random launch token;
- the resolved application-data directory;
- desktop mode enabled;
- the packaged DEVSIM runner path.

The backend binds its socket before reporting readiness. It writes exactly one machine-readable
readiness record to standard output containing the selected URL, runtime fingerprint, process ID,
and protocol version. Human-readable diagnostics go to standard error and the desktop log file.

Electron opens a bootstrap URL carrying the launch token once. The backend exchanges it for an
HTTP-only, same-site session cookie and redirects to a token-free URL. All application and event
stream endpoints require that session in desktop mode. A token is valid only for its launch and is
never written to logs or persistent storage.

Browser mode continues to bind to loopback and operate without the desktop bootstrap exchange.
Desktop mode and browser mode are separate explicit startup modes.

## 7. Process Lifecycle

Electron owns all packaged child processes. Startup proceeds in this order:

1. Acquire Electron's single-instance lock.
2. Resolve and create the platform application-data directory.
3. Acquire an exclusive backend data lock.
4. Start the Python backend.
5. Parse and validate the readiness record.
6. Verify `/health` and the expected runtime fingerprint.
7. Create the application window and complete the token exchange.

Shutdown proceeds in this order:

1. Ask the backend whether work is active.
2. Block update installation and ordinary shutdown until the user stops the active operation or
   explicitly chooses the supported safe stop path.
3. Request graceful backend shutdown.
4. Wait for a bounded grace period.
5. Terminate remaining owned child processes if graceful shutdown fails.
6. Release the data lock and exit.

Unexpected backend exit leaves the desktop shell alive. The shell shows a diagnostic screen with
the exit category, sanitized log location, Retry, and Quit. It does not silently start a new writer
while repository state may be uncertain.

## 8. Self-Contained Python and DEVSIM Packaging

Each operating-system build produces two one-folder sidecars:

1. `agent-kronig-backend`, containing CPython 3.13, Agent Kronig, OpenHands, scientific
   dependencies, templates, skills, curated knowledge, and static assets.
2. `agent-kronig-devsim`, containing a separate CPython 3.13 runtime, DEVSIM 2.9.1, NumPy, and a
   fixed runner entrypoint.

One-folder packaging is preferred over one-file extraction because startup is faster, native
libraries remain inspectable, and update replacement is more reliable. The sidecars are built on
their target operating system and included as immutable Electron resources.

The existing `ExperimentSpec` contract, capability checking, deterministic DEVSIM compiler,
bounded execution, canonical normalization, validation, and evidence bundle remain unchanged.
The desktop package changes deployment, not scientific behavior.

Sentaurus is never bundled. A configured Sentaurus installation or licensed remote runner remains
an external capability exposed through the existing Sentaurus adapter and runner protocol.

## 9. Application Data and Secrets

Default data locations are:

- Linux: `${XDG_DATA_HOME:-~/.local/share}/Agent Kronig` and
  `${XDG_CONFIG_HOME:-~/.config}/Agent Kronig`;
- Windows: `%APPDATA%\Agent Kronig` for mutable data and configuration;
- macOS: `~/Library/Application Support/Agent Kronig`.

The application stores SQLite databases, conversations, run records, logs, cached knowledge,
compiled jobs, and result bundles under the data directory. It stores non-secret preferences in a
versioned JSON settings file.

Electron encrypts Bedrock and integration credentials with the operating system's protected
storage. On Linux, persistent credential storage is enabled only when an OS secret service is
available. Otherwise the application keeps the credential in memory for the current session and
asks again after restart. The application must not fall back to plaintext storage.

The backend receives configured secrets through inherited process input that is excluded from
logs and diagnostics. Credentials are never placed in command-line arguments, repository files,
update metadata, or generated evidence.

## 10. Native Directory Selection

In desktop mode, the existing Open Folder action calls the preload bridge. Electron opens the
operating system's directory dialog and returns one selected absolute path. The renderer submits
that path through the existing workspace API, where canonicalization, repository inspection, and
permission rules remain authoritative.

In browser mode, the current server-side picker and absolute-path entry remain available. The
frontend selects the native bridge only through feature detection.

## 11. Updates and Release Channels

The desktop package supports `pilot` and `stable` channels. A generic HTTPS release endpoint hosts
platform-specific update metadata and complete signed artifacts. Customer installations never
store a GitHub access token.

The release pipeline builds on native Linux, Windows, Intel macOS, and Apple Silicon macOS runners.
It signs Windows and macOS artifacts with NovAtom release credentials. Linux AppImage artifacts
carry a separately verified release signature. Update metadata identifies the application version,
channel, operating system, architecture, minimum supported OS, cryptographic hash, size, and
release notes.

The update client may check and download in the background, but it must not apply an update while
an agent, terminal command, simulation, validation process, or future hardware run is active. The
user chooses Restart and update after the backend reports a safe idle state. Updates replace the
Electron shell and both sidecars as one release.

Before a version that changes persistent storage starts, the backend creates a consistent database
backup and records the schema version. A failed migration leaves the previous database and
application release usable. Update failures never delete the installed version.

Rollouts progress through internal, pilot, and stable channels. Pilot releases support percentage
rollouts. A broken release is superseded by a higher patched version rather than mutating already
published artifacts.

## 12. Platform Packages

The supported first-release matrix is:

| Platform | Architecture | Primary package | Secondary package |
| --- | --- | --- | --- |
| Linux | x86-64 | AppImage | DEB |
| Windows 10/11 | x86-64 | NSIS installer | portable test bundle |
| macOS | Intel x86-64 | signed DMG | application ZIP |
| macOS | Apple Silicon arm64 | signed DMG | application ZIP |

AppImage is the primary Linux package because it runs without root installation and includes the
Chromium runtime. DEB supports managed Ubuntu and Debian workstations. RPM packaging may be added
after a supported customer distribution is identified.

## 13. Browser Workflow Preservation

`tcad-agent serve` and `tcad-agent serve --no-browser` remain supported. They continue to use the
current loopback web application and are covered by the existing test suite. Desktop work must not
move core behavior into Electron.

The source-development desktop command starts Electron against the source Python backend. Browser
and desktop development commands use distinct default data directories so they can be tested
without corrupting or sharing mutable state.

## 14. Autonomous Hardware Boundary

Electron and the LLM agent are supervisory components. They may request a validated experimental
recipe and display bounded telemetry, but they must not own timing-sensitive control, safety
interlocks, watchdogs, emergency stops, or direct actuator loops.

A future laboratory integration uses a separate deterministic hardware-control service:

```text
Agent Kronig agent
  -> typed and policy-checked experiment request
  -> deterministic hardware-control service
  -> device drivers, interlocks, watchdogs, and real-time loops
```

Raw high-rate telemetry flows from the controller to durable storage. The UI receives a throttled
summary suitable for human observation. A frozen or terminated desktop UI cannot disable an
interlock or change the controller's safe state.

Hardware execution is not part of the first desktop implementation. The first release establishes
the process and interface boundary required to add it safely later.

## 15. Error Handling

The application distinguishes:

- backend startup failure;
- backend protocol mismatch;
- unexpected backend exit;
- DEVSIM runner failure;
- data-directory lock conflict;
- database migration failure;
- update check failure;
- update verification failure;
- update installation blocked by active work;
- unavailable protected credential storage;
- unavailable external Sentaurus capability.

Each failure presents a concise explanation and a bounded recovery action. Detailed diagnostics
are written to a local log with credentials, tokens, prompts, and proprietary simulator content
redacted. Sentaurus unavailability does not disable repository work or DEVSIM.

## 16. Testing and Verification

Python unit and integration tests cover desktop-mode authentication, readiness records,
application-data resolution, data locking, safe shutdown state, DEVSIM sidecar invocation, and
database migration behavior.

Electron unit tests cover backend supervision, readiness parsing, retry behavior, bridge
allowlisting, navigation denial, directory selection, update state transitions, and active-work
installation blocking.

Desktop end-to-end tests launch the source backend and Electron shell, open a fixture repository,
create a conversation, open and edit a file, inspect activity and changes, and close the app while
idle. Crash tests terminate the backend and verify the recovery screen. Security tests confirm
that the renderer has no Node.js access and that desktop API requests without the session fail.

Continuous integration runs:

- the complete existing Python and JavaScript suite;
- linting, type checking, and dependency synchronization checks;
- Electron tests on Linux, Windows, and macOS;
- backend and DEVSIM sidecar smoke tests on every supported architecture;
- installer build and clean-machine launch smoke tests on native runners;
- artifact inventory and secret scans;
- signature verification before a release may be published.

## 17. Delivery Sequence

1. Add desktop backend mode, readiness protocol, session authentication, data paths, and locks.
2. Add the Electron shell, secure preload bridge, backend supervisor, and native directory dialog.
3. Add source-development launch and end-to-end desktop tests.
4. Package the Agent Kronig and DEVSIM sidecars.
5. Produce macOS development artifacts on the current machine.
6. Add the native CI build matrix for Linux, Windows, Intel macOS, and Apple Silicon macOS.
7. Add signed update state management and a test release channel.
8. Document installation, administration, diagnostics, updates, and uninstall behavior.

Every step must leave browser mode working and must preserve the existing scientific and agentic
test suites.

## 18. Explicit Non-Goals

The first desktop release does not include:

- direct real-time hardware control;
- bundling or redistributing Sentaurus;
- bypassing `ExperimentSpec` for supported production simulations;
- remote desktop access;
- cloud multi-tenancy;
- automatic installation during active work;
- plaintext credential storage;
- arbitrary Electron renderer access to Node.js or the local filesystem;
- simultaneous write-capable desktop and browser backends using one data directory;
- automatic Git commits or pushes.
