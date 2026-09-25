"use strict";

function normalizedVersion(value) {
  const version = typeof value === "string" ? value : "";
  return /^[0-9A-Za-z.+-]{1,64}$/.test(version) ? version : null;
}

class UpdateController {
  constructor({updater, statusClient, feedUrl = "", channel = "stable"}) {
    if (!["stable", "pilot"].includes(channel)) {
      throw new Error("Update channel must be stable or pilot");
    }
    this.updater = updater;
    this.statusClient = statusClient;
    this.channel = channel;
    this.enabled = Boolean(feedUrl);
    this.state = this.enabled ? "idle" : "disabled";
    this.progressPercent = null;
    this.version = null;
    this.message = null;

    if (!this.enabled) return;
    const parsed = new URL(feedUrl);
    if (parsed.protocol !== "https:" || parsed.username || parsed.password) {
      throw new Error("Update feed must use HTTPS without embedded credentials");
    }
    updater.autoDownload = false;
    updater.autoInstallOnAppQuit = false;
    updater.channel = channel;
    updater.setFeedURL({provider: "generic", url: parsed.href, channel});
    this.#attachEvents();
  }

  #attachEvents() {
    this.updater.on("update-available", (info) => {
      this.state = "available";
      this.version = normalizedVersion(info?.version);
      void this.#download();
    });
    this.updater.on("update-not-available", () => {
      this.state = "up-to-date";
      this.progressPercent = null;
    });
    this.updater.on("download-progress", (progress) => {
      const value = Number(progress?.percent);
      this.progressPercent = Number.isFinite(value)
        ? Math.max(0, Math.min(100, value))
        : null;
    });
    this.updater.on("update-downloaded", (info) => {
      this.state = "ready";
      this.version = normalizedVersion(info?.version) || this.version;
      this.progressPercent = 100;
    });
    this.updater.on("error", () => {
      this.state = "error";
      this.progressPercent = null;
      this.version = null;
      this.message = "Update verification or download failed.";
    });
  }

  async #download() {
    this.state = "downloading";
    this.progressPercent = 0;
    try {
      await this.updater.downloadUpdate();
    } catch {
      this.state = "error";
      this.progressPercent = null;
      this.version = null;
      this.message = "Update verification or download failed.";
    }
  }

  getState() {
    return Object.freeze({
      state: this.state,
      channel: this.channel,
      enabled: this.enabled,
      progressPercent: this.progressPercent,
      version: this.version,
      message: this.message,
    });
  }

  async checkForUpdates() {
    if (!this.enabled) return this.getState();
    this.state = "checking";
    this.message = null;
    try {
      await this.updater.checkForUpdates();
    } catch {
      this.state = "error";
      this.message = "Update verification or download failed.";
    }
    return this.getState();
  }

  async applyUpdateWhenSafe() {
    if (!this.enabled) return this.getState();
    if (this.state !== "ready") {
      throw new Error("No verified update is ready to install");
    }
    const status = await this.statusClient();
    if (!status || status.active !== false) {
      this.state = "blocked";
      this.message = "Finish or stop active work before installing the update.";
      throw new Error("An agent or simulation run is active");
    }
    this.state = "installing";
    this.message = null;
    this.updater.quitAndInstall(false, true);
    return this.getState();
  }
}

module.exports = {UpdateController, normalizedVersion};
