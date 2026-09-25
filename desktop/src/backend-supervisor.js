"use strict";

const {spawn} = require("node:child_process");
const path = require("node:path");

const {MAX_READINESS_BYTES, parseReadinessLine} = require("./readiness");

const MAX_DIAGNOSTIC_BYTES = 8 * 1024;

function delay(milliseconds) {
  return new Promise((resolve) => setTimeout(resolve, milliseconds));
}

function sanitizeDiagnostics(value) {
  return value
    .replace(/(token|password|secret|api[-_]?key)\s*[:=]\s*[^\s]+/gi, "$1=[REDACTED]")
    .replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, "")
    .slice(-MAX_DIAGNOSTIC_BYTES);
}

function developmentPython(projectRoot, platform = process.platform) {
  const relative = platform === "win32"
    ? [".venv", "Scripts", "python.exe"]
    : [".venv", "bin", "python"];
  return path.join(projectRoot, ...relative);
}

function resolveBackendLaunch({
  isPackaged = false,
  resourcesPath = process.resourcesPath,
  projectRoot = path.resolve(__dirname, "../.."),
  platform = process.platform,
  environment = process.env,
} = {}) {
  if (isPackaged) {
    const executable = platform === "win32" ? "agent-kronig-backend.exe" : "agent-kronig-backend";
    return {
      command: path.join(resourcesPath, "sidecars", "backend", executable),
      args: [],
    };
  }
  return {
    command: environment.AGENT_KRONIG_PYTHON || developmentPython(projectRoot, platform),
    args: ["-m", "tcad_agent.desktop.server"],
    environment: {
      PYTHONPATH: [path.join(projectRoot, "src"), environment.PYTHONPATH]
        .filter(Boolean)
        .join(path.delimiter),
    },
  };
}

async function defaultHealthCheck(origin, deadline) {
  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${origin}/health`, {cache: "no-store"});
      if (response.ok) return true;
    } catch {
      // Uvicorn can still be entering its serve loop after emitting readiness.
    }
    await delay(50);
  }
  return false;
}

class BackendSupervisor {
  constructor(options = {}) {
    const launch = options.command
      ? {command: options.command, args: options.args || []}
      : resolveBackendLaunch(options);
    this.command = launch.command;
    this.args = [...launch.args];
    this.dataDir = path.resolve(options.dataDir);
    this.devsimRunner = options.devsimRunner ? path.resolve(options.devsimRunner) : null;
    this.tokenFactory = options.tokenFactory;
    this.startupTimeoutMs = options.startupTimeoutMs || 15000;
    this.healthCheck = options.healthCheck || defaultHealthCheck;
    this.spawnImpl = options.spawnImpl || spawn;
    this.environment = {
      ...(options.environment || process.env),
      ...(launch.environment || {}),
    };
    this.child = null;
    this.readiness = null;
    this.diagnostics = "";
    this.spawnArguments = [];
    this.spawnEnvironment = {};
  }

  get running() {
    return Boolean(this.child && this.child.exitCode === null && !this.child.killed);
  }

  async start() {
    if (this.child) throw new Error("Backend supervisor has already been started");
    const token = this.tokenFactory();
    const environment = {
      ...this.environment,
      AGENT_KRONIG_DESKTOP_HOST: "127.0.0.1",
      AGENT_KRONIG_DESKTOP_PORT: "0",
      AGENT_KRONIG_DESKTOP_TOKEN: token,
      AGENT_KRONIG_DATA_DIR: this.dataDir,
      PYTHONUNBUFFERED: "1",
    };
    if (this.devsimRunner) environment.AGENT_KRONIG_DEVSIM_RUNNER = this.devsimRunner;
    this.spawnArguments = [...this.args];
    this.spawnEnvironment = {...environment};

    const child = this.spawnImpl(this.command, this.args, {
      env: environment,
      stdio: ["ignore", "pipe", "pipe"],
      windowsHide: true,
    });
    this.child = child;

    try {
      const readiness = await this.#waitForReadiness(child);
      const healthy = await this.healthCheck(readiness.url, Date.now() + this.startupTimeoutMs);
      if (!healthy) throw new Error("Backend health check timed out");
      this.readiness = readiness;
      return Object.freeze({...readiness, launchToken: token});
    } catch (error) {
      await this.stop();
      throw error;
    }
  }

  #waitForReadiness(child) {
    return new Promise((resolve, reject) => {
      let stdout = Buffer.alloc(0);
      let settled = false;
      const finish = (callback, value) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        callback(value);
      };
      const timer = setTimeout(
        () => finish(reject, new Error("Backend readiness timed out")),
        this.startupTimeoutMs,
      );

      child.stderr.on("data", (chunk) => {
        this.diagnostics = sanitizeDiagnostics(this.diagnostics + chunk.toString("utf8"));
      });
      child.stdout.on("data", (chunk) => {
        if (settled) return;
        stdout = Buffer.concat([stdout, chunk]);
        if (stdout.length > MAX_READINESS_BYTES) {
          finish(reject, new Error("Backend readiness output exceeded the size limit"));
          return;
        }
        const newline = stdout.indexOf(0x0a);
        if (newline === -1) return;
        try {
          finish(resolve, parseReadinessLine(stdout.subarray(0, newline).toString("utf8")));
        } catch (error) {
          finish(reject, error);
        }
      });
      child.once("error", (error) => {
        finish(reject, new Error(`Backend could not be started: ${error.message}`));
      });
      child.once("exit", (code, signal) => {
        if (settled) return;
        const suffix = code === null ? `signal ${signal}` : `code ${code}`;
        finish(reject, new Error(`Backend exited before readiness with ${suffix}`));
      });
    });
  }

  async stop() {
    const child = this.child;
    this.child = null;
    this.readiness = null;
    if (!child || child.exitCode !== null || child.killed) return;

    child.kill("SIGTERM");
    await Promise.race([
      new Promise((resolve) => child.once("exit", resolve)),
      delay(750),
    ]);
    if (child.exitCode === null) child.kill("SIGKILL");
  }
}

module.exports = {
  BackendSupervisor,
  defaultHealthCheck,
  developmentPython,
  resolveBackendLaunch,
  sanitizeDiagnostics,
};
