const assert = require("node:assert/strict");
const {EventEmitter} = require("node:events");
const test = require("node:test");

const {UpdateController} = require("../src/update-controller");

class FakeUpdater extends EventEmitter {
  constructor() {
    super();
    this.feedCalls = [];
    this.checkCalls = 0;
    this.downloadCalls = 0;
    this.installCalls = 0;
  }

  setFeedURL(value) {
    this.feedCalls.push(value);
  }

  async checkForUpdates() {
    this.checkCalls += 1;
  }

  async downloadUpdate() {
    this.downloadCalls += 1;
  }

  quitAndInstall() {
    this.installCalls += 1;
  }
}

function configured(overrides = {}) {
  const updater = new FakeUpdater();
  const controller = new UpdateController({
    updater,
    feedUrl: "https://updates.example.test/agent-kronig",
    channel: "stable",
    statusClient: async () => ({active: false}),
    ...overrides,
  });
  return {controller, updater};
}

test("remains offline when no HTTPS feed is configured", async () => {
  const updater = new FakeUpdater();
  const controller = new UpdateController({
    updater,
    feedUrl: "",
    statusClient: async () => ({active: false}),
  });
  assert.equal(controller.getState().state, "disabled");
  await controller.checkForUpdates();
  assert.equal(updater.checkCalls, 0);
});

test("rejects non-HTTPS update feeds and unknown channels", () => {
  assert.throws(() => configured({feedUrl: "http://updates.example.test"}), /HTTPS/);
  assert.throws(() => configured({channel: "nightly"}), /channel/);
});

test("tracks checks, availability, progress, and verified download readiness", async () => {
  const {controller, updater} = configured({channel: "pilot"});
  assert.equal(controller.getState().state, "idle");
  assert.equal(updater.channel, "pilot");
  await controller.checkForUpdates();
  assert.equal(controller.getState().state, "checking");
  updater.emit("update-available", {version: "0.2.0"});
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(updater.downloadCalls, 1);
  assert.equal(controller.getState().state, "downloading");
  updater.emit("download-progress", {percent: 42.25});
  assert.equal(controller.getState().progressPercent, 42.25);
  updater.emit("update-downloaded", {version: "0.2.0"});
  assert.equal(controller.getState().state, "ready");
  assert.equal(controller.getState().version, "0.2.0");
});

test("sanitizes updater verification and download errors", () => {
  const {controller, updater} = configured();
  updater.emit("error", new Error("signature failed for /Users/person/private"));
  assert.deepEqual(controller.getState(), {
    state: "error",
    channel: "stable",
    enabled: true,
    progressPercent: null,
    version: null,
    message: "Update verification or download failed.",
  });
});

test("blocks installation while backend work is active", async () => {
  const {controller, updater} = configured({
    statusClient: async () => ({active: true}),
  });
  updater.emit("update-downloaded", {version: "0.2.0"});
  await assert.rejects(controller.applyUpdateWhenSafe(), /active/i);
  assert.equal(controller.getState().state, "blocked");
  assert.equal(updater.installCalls, 0);
});

test("rechecks backend status immediately before installation", async () => {
  let statusCalls = 0;
  const {controller, updater} = configured({
    statusClient: async () => {
      statusCalls += 1;
      return {active: false};
    },
  });
  updater.emit("update-downloaded", {version: "0.2.0"});
  const state = await controller.applyUpdateWhenSafe();
  assert.equal(statusCalls, 1);
  assert.equal(updater.installCalls, 1);
  assert.equal(state.state, "installing");
});
