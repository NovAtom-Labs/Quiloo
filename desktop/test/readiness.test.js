const assert = require("node:assert/strict");
const test = require("node:test");

const {MAX_READINESS_BYTES, parseReadinessLine} = require("../src/readiness");

const validRecord = {
  protocol: 1,
  url: "http://127.0.0.1:43127",
  pid: 4242,
  runtime_fingerprint: "a1b2c3d4e5f60708",
};

test("parses and freezes a valid desktop readiness record", () => {
  const parsed = parseReadinessLine(JSON.stringify(validRecord));
  assert.deepEqual(parsed, validRecord);
  assert.equal(Object.isFrozen(parsed), true);
});

for (const [name, input] of [
  ["non JSON", "ready"],
  ["array", "[]"],
  ["non-loopback hostname", JSON.stringify({...validRecord, url: "http://localhost:43127"})],
  ["wrong protocol", JSON.stringify({...validRecord, protocol: 2})],
  ["missing PID", JSON.stringify({...validRecord, pid: undefined})],
  ["URL path", JSON.stringify({...validRecord, url: "http://127.0.0.1:43127/admin"})],
  ["URL credentials", JSON.stringify({...validRecord, url: "http://user@127.0.0.1:43127"})],
  ["URL query", JSON.stringify({...validRecord, url: "http://127.0.0.1:43127/?token=x"})],
]) {
  test(`rejects ${name}`, () => {
    assert.throws(() => parseReadinessLine(input), /readiness/i);
  });
}

test("rejects readiness output larger than 16 KiB", () => {
  assert.throws(() => parseReadinessLine("x".repeat(MAX_READINESS_BYTES + 1)), /size/i);
});
