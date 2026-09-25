const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {DesktopSettingsStore} = require("../src/settings-store");

function temporaryDirectory() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "agent-kronig-settings-"));
}

function protectedStorage() {
  return {
    isEncryptionAvailable: () => true,
    getSelectedStorageBackend: () => "keychain",
    encryptString: (value) => Buffer.from([...value].reverse().join(""), "utf8"),
    decryptString: (value) => [...value.toString("utf8")].reverse().join(""),
  };
}

test("stores non-secret settings and protects the Bedrock credential", () => {
  const dataDir = temporaryDirectory();
  const store = new DesktopSettingsStore({
    dataDir,
    safeStorage: protectedStorage(),
    platform: "darwin",
  });

  const state = store.save({
    region: "ap-south-1",
    model: "bedrock/global.anthropic.claude-sonnet-4-6",
    reasoningEffort: "medium",
    bedrockApiKey: "test-secret-value",
  });

  assert.equal(state.hasBedrockCredential, true);
  assert.equal(state.credentialStorage, "protected");
  assert.equal(JSON.stringify(state).includes("test-secret-value"), false);
  assert.equal(fs.readFileSync(path.join(dataDir, "settings.json"), "utf8").includes("test-secret-value"), false);
  assert.equal(fs.readFileSync(path.join(dataDir, "secrets.bin"), "utf8").includes("test-secret-value"), false);

  const environment = store.environment();
  assert.equal(environment.AWS_BEARER_TOKEN_BEDROCK, "test-secret-value");
  assert.equal(environment.AWS_REGION_NAME, "ap-south-1");
  assert.equal(environment.LLM_MODEL, "bedrock/global.anthropic.claude-sonnet-4-6");
  assert.equal(environment.TCAD_REASONING_EFFORT, "medium");
});

test("keeps a credential in memory when Linux protected storage is unavailable", () => {
  const dataDir = temporaryDirectory();
  const store = new DesktopSettingsStore({
    dataDir,
    safeStorage: {
      isEncryptionAvailable: () => true,
      getSelectedStorageBackend: () => "basic_text",
      encryptString: () => { throw new Error("must not persist"); },
      decryptString: () => { throw new Error("must not persist"); },
    },
    platform: "linux",
  });

  const state = store.save({
    region: "us-east-1",
    model: "bedrock/example",
    reasoningEffort: "low",
    bedrockApiKey: "session-only",
  });

  assert.equal(state.credentialStorage, "session");
  assert.equal(store.environment().AWS_BEARER_TOKEN_BEDROCK, "session-only");
  assert.equal(fs.existsSync(path.join(dataDir, "secrets.bin")), false);
});

test("never returns secrets and validates every setting", () => {
  const store = new DesktopSettingsStore({
    dataDir: temporaryDirectory(),
    safeStorage: protectedStorage(),
    platform: "win32",
  });

  assert.throws(() => store.save({region: "", model: "bedrock/example", reasoningEffort: "low"}), /region/i);
  assert.throws(() => store.save({region: "us-east-1", model: "invalid", reasoningEffort: "low"}), /model/i);
  assert.throws(() => store.save({region: "us-east-1", model: "bedrock/example", reasoningEffort: "extreme"}), /reasoning/i);

  const state = store.save({
    region: "us-east-1",
    model: "bedrock/example",
    reasoningEffort: "high",
    bedrockApiKey: "hidden",
  });
  assert.equal("bedrockApiKey" in state, false);
  const cleared = store.save({
    region: "us-east-1",
    model: "bedrock/example",
    reasoningEffort: "high",
    clearCredential: true,
  });
  assert.equal(cleared.hasBedrockCredential, false);
  assert.equal("AWS_BEARER_TOKEN_BEDROCK" in store.environment(), false);
});

test("uses managed launch configuration until the researcher saves overrides", () => {
  const store = new DesktopSettingsStore({
    dataDir: temporaryDirectory(),
    safeStorage: protectedStorage(),
    platform: "linux",
    baseEnvironment: {
      AWS_REGION_NAME: "eu-west-1",
      LLM_MODEL: "bedrock/managed-profile",
      TCAD_REASONING_EFFORT: "high",
      AWS_BEARER_TOKEN_BEDROCK: "managed-secret",
    },
  });

  assert.deepEqual(store.environment(), {
    AWS_REGION_NAME: "eu-west-1",
    LLM_MODEL: "bedrock/managed-profile",
    TCAD_REASONING_EFFORT: "high",
    AWS_BEARER_TOKEN_BEDROCK: "managed-secret",
  });
  assert.equal(store.getPublicSettings().hasBedrockCredential, true);
});
