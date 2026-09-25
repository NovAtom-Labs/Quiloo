"use strict";

const CHANNELS = Object.freeze({
  selectDirectory: "desktop:select-directory",
  getDesktopInfo: "desktop:get-info",
  getUpdateState: "desktop:get-update-state",
  checkForUpdates: "desktop:check-for-updates",
  applyUpdateWhenSafe: "desktop:apply-update-when-safe",
  getSettings: "desktop:get-settings",
  saveSettings: "desktop:save-settings",
});

function createDesktopApi(ipcRenderer) {
  return Object.freeze(
    Object.fromEntries(
      Object.entries(CHANNELS).map(([name, channel]) => [
        name,
        (...args) => ipcRenderer.invoke(channel, ...args),
      ]),
    ),
  );
}

function installPreload({contextBridge, ipcRenderer}) {
  contextBridge.exposeInMainWorld("agentKronigDesktop", createDesktopApi(ipcRenderer));
}

if (process.type === "renderer") {
  installPreload(require("electron"));
}

module.exports = {CHANNELS, createDesktopApi, installPreload};
