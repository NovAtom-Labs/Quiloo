const assert = require("node:assert/strict");
const crypto = require("node:crypto");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {createLinuxUpdateVerifier} = require("../src/linux-update-verifier");

test("accepts only an update signed by the pinned Ed25519 publisher", async (context) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "agent-kronig-update-"));
  context.after(() => fs.rmSync(directory, {recursive: true, force: true}));
  const artifact = path.join(directory, "Agent-Kronig.AppImage");
  fs.writeFileSync(artifact, "signed application bytes");
  const {publicKey, privateKey} = crypto.generateKeyPairSync("ed25519");
  const digest = crypto.createHash("sha256").update(fs.readFileSync(artifact)).digest();
  const signature = crypto.sign(null, digest, privateKey);
  let requestedUrl = null;
  const verify = createLinuxUpdateVerifier({
    feedUrl: "https://updates.example.test/stable/",
    publicKey: publicKey.export({type: "spki", format: "pem"}),
    fetchImpl: async (url) => {
      requestedUrl = url;
      return {ok: true, arrayBuffer: async () => signature};
    },
  });

  await verify(artifact);
  assert.equal(requestedUrl, "https://updates.example.test/stable/Agent-Kronig.AppImage.sig");
  fs.writeFileSync(artifact, "tampered application bytes");
  await assert.rejects(verify(artifact), /publisher signature/i);
});

test("fails closed when signature material is unavailable", async () => {
  assert.throws(
    () => createLinuxUpdateVerifier({feedUrl: "https://updates.example.test", publicKey: ""}),
    /public key/i,
  );
});
