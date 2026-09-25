const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  BackendSupervisor,
  resolveBackendLaunch,
} = require("../src/backend-supervisor");

function fixture(source) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "agent-kronig-sidecar-"));
  const script = path.join(directory, "fixture.js");
  fs.writeFileSync(script, source);
  return {directory, script};
}

function supervisorFor(script, overrides = {}) {
  return new BackendSupervisor({
    command: process.execPath,
    args: [script],
    dataDir: path.dirname(script),
    tokenFactory: () => "t".repeat(43),
    startupTimeoutMs: 750,
    healthCheck: async () => true,
    ...overrides,
  });
}

test("starts from one valid readiness line and keeps secrets out of argv", async (context) => {
  const {directory, script} = fixture(`
    const record = {protocol: 1, url: "http://127.0.0.1:43127", pid: process.pid, runtime_fingerprint: "abc123"};
    process.stdout.write(JSON.stringify(record) + "\\n");
    setInterval(() => {}, 1000);
  `);
  context.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  const supervisor = supervisorFor(script);
  const ready = await supervisor.start();

  assert.equal(ready.url, "http://127.0.0.1:43127");
  assert.equal(supervisor.spawnArguments.includes("t".repeat(43)), false);
  assert.equal(supervisor.spawnEnvironment.AGENT_KRONIG_DESKTOP_TOKEN, "t".repeat(43));
  assert.equal(supervisor.spawnEnvironment.AGENT_KRONIG_DATA_DIR, directory);
  await supervisor.stop();
  await supervisor.stop();
});

test("rejects malformed readiness and terminates the fixture", async (context) => {
  const {directory, script} = fixture(`
    process.stdout.write("not-json\\n");
    setInterval(() => {}, 1000);
  `);
  context.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  const supervisor = supervisorFor(script);
  await assert.rejects(supervisor.start(), /readiness/i);
  assert.equal(supervisor.running, false);
});

test("reports early sidecar exit with bounded sanitized diagnostics", async (context) => {
  const {directory, script} = fixture(`
    process.stderr.write("launch-token=secret\\n");
    process.exit(7);
  `);
  context.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  const supervisor = supervisorFor(script);
  await assert.rejects(supervisor.start(), /exited.*7/i);
  assert.doesNotMatch(supervisor.diagnostics, /secret/);
});

test("times out and terminates a silent fixture", async (context) => {
  const {directory, script} = fixture("setInterval(() => {}, 1000);");
  context.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  const supervisor = supervisorFor(script, {startupTimeoutMs: 80});
  await assert.rejects(supervisor.start(), /timed out/i);
  assert.equal(supervisor.running, false);
});

test("development launch imports the current source tree without installation", () => {
  const launch = resolveBackendLaunch({
    projectRoot: "/opt/agent-kronig",
    platform: "linux",
    environment: {PYTHONPATH: "/existing/python"},
  });
  assert.equal(launch.command, "/opt/agent-kronig/.venv/bin/python");
  assert.deepEqual(launch.args, ["-m", "tcad_agent.desktop.server"]);
  assert.equal(
    launch.environment.PYTHONPATH,
    `/opt/agent-kronig/src${path.delimiter}/existing/python`,
  );
});

test("stop escalates when a sidecar ignores graceful termination", async (context) => {
  const {directory, script} = fixture(`
    process.on("SIGTERM", () => {});
    const record = {protocol: 1, url: "http://127.0.0.1:43127", pid: process.pid, runtime_fingerprint: "abc123"};
    process.stdout.write(JSON.stringify(record) + "\\n");
    setInterval(() => {}, 1000);
  `);
  context.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  const supervisor = supervisorFor(script);
  await supervisor.start();
  const pid = supervisor.readiness.pid;
  await supervisor.stop();
  await new Promise((resolve) => setTimeout(resolve, 50));
  assert.throws(() => process.kill(pid, 0), /ESRCH/);
});
