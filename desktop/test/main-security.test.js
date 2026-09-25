const assert = require("node:assert/strict");
const test = require("node:test");

const {
  attachNavigationPolicy,
  configureApplicationIdentity,
  createLaunchToken,
  developmentIconPath,
  shouldAutoStart,
  installGracefulQuit,
  installPermissionPolicy,
} = require("../src/main");

test("denies every renderer permission request and check", () => {
  let requestHandler;
  let checkHandler;
  installPermissionPolicy({
    setPermissionRequestHandler(handler) { requestHandler = handler; },
    setPermissionCheckHandler(handler) { checkHandler = handler; },
  });

  let decision = true;
  requestHandler({}, "media", (allowed) => { decision = allowed; });
  assert.equal(decision, false);
  assert.equal(checkHandler({}, "clipboard-read"), false);
});

test("navigation policy allows only the authenticated loopback origin", () => {
  let openHandler;
  let navigateHandler;
  const webContents = {
    setWindowOpenHandler(handler) {
      openHandler = handler;
    },
    on(event, handler) {
      if (event === "will-navigate") navigateHandler = handler;
    },
  };
  attachNavigationPolicy(webContents, "http://127.0.0.1:43127");

  assert.deepEqual(openHandler(), {action: "deny"});
  let prevented = false;
  navigateHandler({preventDefault: () => { prevented = true; }}, "http://127.0.0.1:43127/workspaces/1");
  assert.equal(prevented, false);
  navigateHandler({preventDefault: () => { prevented = true; }}, "https://example.com/");
  assert.equal(prevented, true);
});

test("launch token contains at least 32 random bytes", () => {
  const first = createLaunchToken();
  const second = createLaunchToken();
  assert.notEqual(first, second);
  assert.ok(Buffer.from(first, "base64url").length >= 32);
});

test("desktop entrypoint auto-starts only in Electron's browser process", () => {
  assert.equal(shouldAutoStart({type: "browser"}), true);
  assert.equal(shouldAutoStart({type: "renderer"}), false);
  assert.equal(shouldAutoStart({}), false);
});

test("development windows use the tracked Agent Kronig icon", () => {
  const path = require("node:path");
  const icon = developmentIconPath(false, path.resolve(__dirname, ".."));

  assert.equal(icon, path.resolve(__dirname, "../assets/icon.png"));
  assert.equal(developmentIconPath(true, path.resolve(__dirname, "..")), undefined);
});

test("development runtime identifies itself as Agent Kronig", () => {
  const names = [];

  configureApplicationIdentity({setName(name) { names.push(name); }});

  assert.deepEqual(names, ["Agent Kronig"]);
});

test("application quit waits for backend shutdown", async () => {
  let handler;
  let quitCalls = 0;
  let releaseStop;
  const stopped = new Promise((resolve) => { releaseStop = resolve; });
  installGracefulQuit(
    {
      on(event, callback) {
        if (event === "before-quit") handler = callback;
      },
      quit() {
        quitCalls += 1;
      },
    },
    () => stopped,
  );
  let prevented = false;
  handler({preventDefault: () => { prevented = true; }});
  assert.equal(prevented, true);
  assert.equal(quitCalls, 0);
  releaseStop();
  await stopped;
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(quitCalls, 1);
});

test("application quit remains open when backend work is active", async () => {
  let handler;
  let quitCalls = 0;
  let blockedCalls = 0;
  installGracefulQuit(
    {
      on(_event, callback) { handler = callback; },
      quit() { quitCalls += 1; },
    },
    async () => { throw new Error("active work"); },
    async () => { blockedCalls += 1; },
  );
  handler({preventDefault() {}});
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(quitCalls, 0);
  assert.equal(blockedCalls, 1);
});
