"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

const {BackendSupervisor} = require("./backend-supervisor");

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

function installGracefulQuit(app, stopBackend) {
  let shutdownComplete = false;
  let shutdownStarted = false;
  app.on("before-quit", (event) => {
    if (shutdownComplete) return;
    event.preventDefault();
    if (shutdownStarted) return;
    shutdownStarted = true;
    void Promise.resolve(stopBackend()).finally(() => {
      shutdownComplete = true;
      app.quit();
    });
  });
}

function createApplication(electron = require("electron")) {
  const {app, BrowserWindow, dialog, ipcMain} = electron;
  let mainWindow = null;
  let supervisor = null;

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
    const options = {
      dataDir: app.getPath("userData"),
      tokenFactory: createLaunchToken,
      isPackaged: app.isPackaged,
      resourcesPath: process.resourcesPath,
      projectRoot: path.resolve(__dirname, "../.."),
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
      },
    });
    window.once("ready-to-show", () => window.show());
    window.on("closed", () => {
      if (mainWindow === window) mainWindow = null;
    });
    return window;
  }

  async function launchWorkspace() {
    supervisor = new BackendSupervisor(backendOptions());
    try {
      const ready = await supervisor.start();
      const window = createWindow();
      attachNavigationPolicy(window.webContents, ready.url);
      await window.loadURL(
        `${ready.url}/desktop/bootstrap?token=${encodeURIComponent(ready.launchToken)}`,
      );
      mainWindow = window;
    } catch (error) {
      await showStartupError(error);
    }
  }

  async function showStartupError(error) {
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
        window.close();
        void launchWorkspace();
      } else if (destination === "agent-kronig-error://quit") {
        app.quit();
      }
    });
    await window.loadFile(path.join(__dirname, "error.html"), {
      query: {category, logPath},
    });
    mainWindow = window;
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
    ipcMain.handle("desktop:get-update-state", () => ({state: "not-configured"}));
    ipcMain.handle("desktop:check-for-updates", () => ({state: "not-configured"}));
    ipcMain.handle("desktop:apply-update-when-safe", () => ({state: "not-configured"}));
  }

  async function stopBackend() {
    await supervisor?.stop();
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
    installGracefulQuit(app, stopBackend);
    app.on("window-all-closed", () => app.quit());
    await app.whenReady();
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
  shouldAutoStart,
};
