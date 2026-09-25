const assert = require("node:assert/strict");

require("../../src/tcad_agent/web/static/desktop-bridge.js");

const bridge = globalThis.AgentKronigDesktopBridge;

async function testNativeSelection() {
  let fetchCalls = 0;
  const result = await bridge.selectDirectory(
    async () => {
      fetchCalls += 1;
      throw new Error("browser fallback should not run");
    },
    {
      selectDirectory: async () => ({cancelled: false, path: "/home/research/project"}),
    },
  );

  assert.equal(result, "/home/research/project");
  assert.equal(fetchCalls, 0);
}

async function testNativeCancellation() {
  let fetchCalls = 0;
  const result = await bridge.selectDirectory(
    async () => {
      fetchCalls += 1;
      throw new Error("browser fallback should not run");
    },
    {
      selectDirectory: async () => ({cancelled: true, path: null}),
    },
  );

  assert.equal(result, null);
  assert.equal(fetchCalls, 0);
}

async function testBrowserFallback() {
  const calls = [];
  const result = await bridge.selectDirectory(async (url, options) => {
    calls.push({url, options});
    return {
      ok: true,
      json: async () => ({path: "/tmp/project"}),
    };
  });

  assert.equal(result, "/tmp/project");
  assert.deepEqual(calls, [
    {
      url: "/api/system/directories/select",
      options: {method: "POST"},
    },
  ]);
}

async function main() {
  await testNativeSelection();
  await testNativeCancellation();
  await testBrowserFallback();
  console.log("desktop bridge tests passed");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
