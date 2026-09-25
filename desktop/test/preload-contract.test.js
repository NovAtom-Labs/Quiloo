const assert = require("node:assert/strict");
const test = require("node:test");

const {installPreload} = require("../src/preload");

test("preload exposes only the allowlisted desktop contract", () => {
  let exposedName;
  let exposedApi;
  const calls = [];
  installPreload({
    contextBridge: {
      exposeInMainWorld(name, api) {
        exposedName = name;
        exposedApi = api;
      },
    },
    ipcRenderer: {
      invoke(channel) {
        calls.push(channel);
        return Promise.resolve({channel});
      },
    },
  });

  assert.equal(exposedName, "agentKronigDesktop");
  assert.deepEqual(Object.keys(exposedApi).sort(), [
    "applyUpdateWhenSafe",
    "checkForUpdates",
    "getDesktopInfo",
    "getUpdateState",
    "selectDirectory",
  ]);
  assert.equal(Object.isFrozen(exposedApi), true);
  assert.equal("invoke" in exposedApi, false);

  return Promise.all(Object.values(exposedApi).map((fn) => fn())).then(() => {
    assert.deepEqual(calls.sort(), [
      "desktop:apply-update-when-safe",
      "desktop:check-for-updates",
      "desktop:get-info",
      "desktop:get-update-state",
      "desktop:select-directory",
    ]);
  });
});
