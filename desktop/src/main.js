"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const {BackendSupervisor} = require("./backend-supervisor");
const {DesktopSettingsStore} = require("./settings-store");
const {createLinuxUpdateVerifier} = require("./linux-update-verifier");
const {UpdateController} = require("./update-controller");

function createLaunchToken() {
  return crypto.randomBytes(32).toString("base64url");
}

function shouldAutoStart(processLike) {
  return processLike.type === "browser";
}

function attachNavigationPolicy(webContents, allowedOrigin) {
  webContents.setWindowOpenHandler(() => ({action: "deny"}));
  webContents.on("will-navigate", (event, destination) => {
    try {
      if (new URL(destination).origin !== allowedOrigin) event.preventDefault();
    } catch {
      event.preventDefault();
    }
  });
}

function installPermissionPolicy(electronSession) {
  electronSession.setPermissionRequestHandler((_webContents, _permission, callback) => {
    callback(false);
  });
  electronSession.setPermissionCheckHandler(() => false);
}

function installGracefulQuit(app, stopBackend, onBlocked = async () => {}) {
  let shutdownComplete = false;
  let shutdownStarted = false;
  app.on("before-quit", (event) => {
    if (shutdownComplete) return;
    event.preventDefault();
    if (shutdownStarted) return;
    shutdownStarted = true;
    void Promise.resolve()
      .then(stopBackend)
      .then(() => {
        shutdownComplete = true;
        app.quit();
      })
      .catch(async (error) => {
        shutdownStarted = false;
        await onBlocked(error);
      });
  });
}

function createApplication(
  electron = require("electron"),
  updater = require("electron-updater").autoUpdater,
) {
  const {app, BrowserWindow, dialog, ipcMain, safeStorage, session} = electron;
  let mainWindow = null;
  let supervisor = null;
  let settingsStore = null;
  const updateFeedUrl = process.env.AGENT_KRONIG_UPDATE_URL || "";
  let verifyDownload = async () => {};
  if (process.platform === "linux" && updateFeedUrl) {
    const publicKeyPath = path.join(__dirname, "linux-update-public-key.pem");
    verifyDownload = createLinuxUpdateVerifier({
      feedUrl: updateFeedUrl,
      publicKey: fs.readFileSync(publicKeyPath, "utf8"),
    });
  }
  const updateController = new UpdateController({
    updater,
    feedUrl: updateFeedUrl,
    channel: process.env.AGENT_KRONIG_UPDATE_CHANNEL || "stable",
    statusClient: backendActivity,
    verifyDownload,
  });

  const desktopInfo = () => Object.freeze({
    application: "Agent Kronig",
    version: app.getVersion(),
    platform: process.platform,
    architecture: process.arch,
    packaged: app.isPackaged,
  });

  function sidecarRoot() {
    return path.join(process.resourcesPath, "sidecars");
  }

  function backendOptions() {
    const projectRoot = path.resolve(__dirname, "../..");
    const resourceRoot = app.isPackaged ? process.resourcesPath : projectRoot;
    const options = {
      dataDir: app.getPath("userData"),
      tokenFactory: createLaunchToken,
      startupTimeoutMs: app.isPackaged ? 120000 : 15000,
      isPackaged: app.isPackaged,
      resourcesPath: process.resourcesPath,
      projectRoot,
      environment: {
        ...process.env,
        ...settingsStore.environment(),
        TCAD_KNOWLEDGE_INDEX: path.join(
          resourceRoot,
          "knowledge-sources",
          "index",
          "knowledge.sqlite3",
        ),
        TCAD_SKILLS_ROOT: path.join(resourceRoot, "skills"),
        OPENHANDS_SUPPRESS_BANNER: "1",
      },
    };
    if (app.isPackaged) {
      const suffix = process.platform === "win32" ? ".exe" : "";
      options.devsimRunner = path.join(
        sidecarRoot(),
        "devsim",
        `agent-kronig-devsim${suffix}`,
      );
    }
    return options;
  }

  function createWindow() {
    const window = new BrowserWindow({
      width: 1500,
      height: 940,
      minWidth: 1080,
      minHeight: 680,
      backgroundColor: "#0b0f14",
      show: false,
      title: "Agent Kronig",
      webPreferences: {
        preload: path.join(__dirname, "preload.js"),
        contextIsolation: true,
        sandbox: true,
        nodeIntegration: false,
        webSecurity: true,
        devTools: !app.isPackaged,
      },
    });
    window.once("ready-to-show", () => window.show());
    window.on("closed", () => {
      if (mainWindow === window) mainWindow = null;
    });
    return window;
  }

  async function backendActivity() {
    if (!supervisor?.readiness) return {active: true};
    const response = await fetch(`${supervisor.readiness.url}/api/desktop/status`, {
      cache: "no-store",
    });
    if (!response.ok) throw new Error("Desktop activity status is unavailable");
    return response.json();
  }

  async function assertBackendIdle() {
    const status = await backendActivity();
    if (!status || status.active !== false) {
      throw new Error("Finish or stop active work before closing or restarting Agent Kronig.");
    }
  }

  async function prepareBackendShutdown() {
    if (!supervisor?.readiness) return;
    const response = await fetch(
      `${supervisor.readiness.url}/api/desktop/prepare-shutdown`,
      {
        method: "POST",
        cache: "no-store",
        headers: {Authorization: `Bearer ${supervisor.readiness.launchToken}`},
      },
    );
    if (response.ok) return;
    let message = "Agent Kronig could not prepare the local service for shutdown.";
    try {
      const payload = await response.json();
      if (payload?.message) message = payload.message;
    } catch {
      // Keep the sanitized fallback message.
    }
    throw new Error(message);
  }

  async function launchWorkspace(previousWindow = null) {
    const candidate = new BackendSupervisor(backendOptions());
    supervisor = candidate;
    candidate.once("unexpected-exit", (event) => {
      if (supervisor !== candidate) return;
      const suffix = event.code === null ? `signal ${event.signal}` : `code ${event.code}`;
      void showStartupError(new Error(`Backend exited unexpectedly with ${suffix}`), mainWindow);
    });
    try {
      const ready = await candidate.start();
      const window = createWindow();
      attachNavigationPolicy(window.webContents, ready.url);
      await window.loadURL(
        `${ready.url}/desktop/bootstrap?token=${encodeURIComponent(ready.launchToken)}`,
      );
      mainWindow = window;
      if (previousWindow && previousWindow !== window) previousWindow.close();
    } catch (error) {
      await showStartupError(error, previousWindow);
    }
  }

  async function showStartupError(error, previousWindow = null) {
    const logDirectory = app.getPath("logs");
    fs.mkdirSync(logDirectory, {recursive: true});
    const logPath = path.join(logDirectory, "desktop-startup.log");
    const category = error && /lock/i.test(error.message)
      ? "Workspace already open"
      : "Local service could not start";
    fs.writeFileSync(
      logPath,
      `${new Date().toISOString()} ${category}\n${supervisor?.diagnostics || "No backend diagnostics were emitted."}\n`,
      {encoding: "utf8", mode: 0o600},
    );
    const window = createWindow();
    window.webContents.on("will-navigate", (event, destination) => {
      if (!destination.startsWith("agent-kronig-error://")) return;
      event.preventDefault();
      if (destination === "agent-kronig-error://retry") {
        void launchWorkspace(window);
      } else if (destination === "agent-kronig-error://quit") {
        app.quit();
      }
    });
    await window.loadFile(path.join(__dirname, "error.html"), {
      query: {category, logPath},
    });
    mainWindow = window;
    if (previousWindow && previousWindow !== window) previousWindow.close();
  }

  function registerIpc() {
    ipcMain.handle("desktop:select-directory", async () => {
      const result = await dialog.showOpenDialog(mainWindow, {
        title: "Open repository folder",
        properties: ["openDirectory"],
      });
      return Object.freeze({
        cancelled: result.canceled || result.filePaths.length === 0,
        path: result.canceled ? null : result.filePaths[0] || null,
      });
    });
    ipcMain.handle("desktop:get-info", () => desktopInfo());
    ipcMain.handle("desktop:get-settings", () => settingsStore.getPublicSettings());
    ipcMain.handle("desktop:save-settings", async (_event, payload) => {
      await assertBackendIdle();
      const state = settingsStore.save(payload);
      setTimeout(async () => {
        const previousWindow = mainWindow;
        try {
          await stopBackendWhenIdle();
          await launchWorkspace(previousWindow);
        } catch (error) {
          await dialog.showMessageBox(previousWindow, {
            type: "warning",
            message: error.message,
          });
        }
      }, 50);
      return Object.freeze({...state, restarting: true});
    });
    ipcMain.handle("desktop:get-update-state", () => updateController.getState());
    ipcMain.handle("desktop:check-for-updates", () => updateController.checkForUpdates());
    ipcMain.handle(
      "desktop:apply-update-when-safe",
      () => updateController.applyUpdateWhenSafe(),
    );
  }

  async function stopBackend() {
    await supervisor?.stop();
  }

  async function stopBackendWhenIdle() {
    await prepareBackendShutdown();
    await stopBackend();
  }

  async function run() {
    if (!app.requestSingleInstanceLock()) {
      app.quit();
      return;
    }
    app.on("second-instance", () => {
      if (mainWindow) {
        if (mainWindow.isMinimized()) mainWindow.restore();
        mainWindow.focus();
      }
    });
    installGracefulQuit(app, stopBackendWhenIdle, async (error) => {
      await dialog.showMessageBox(mainWindow, {
        type: "warning",
        message: error.message,
      });
    });
    app.on("window-all-closed", () => app.quit());
    await app.whenReady();
    installPermissionPolicy(session.defaultSession);
    settingsStore = new DesktopSettingsStore({
      dataDir: app.getPath("userData"),
      safeStorage,
      baseEnvironment: process.env,
    });
    registerIpc();
    await launchWorkspace();
  }

  return {run, stopBackend};
}

if (shouldAutoStart(process)) {
  void createApplication().run();
}

module.exports = {
  attachNavigationPolicy,
  createApplication,
  createLaunchToken,
  installGracefulQuit,
  installPermissionPolicy,
  shouldAutoStart,
};
