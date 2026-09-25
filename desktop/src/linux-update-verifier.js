"use strict";

const crypto = require("node:crypto");
const fs = require("node:fs");
const path = require("node:path");

function sha256File(filePath) {
  return new Promise((resolve, reject) => {
    const digest = crypto.createHash("sha256");
    const stream = fs.createReadStream(filePath);
    stream.on("data", (chunk) => digest.update(chunk));
    stream.once("error", reject);
    stream.once("end", () => resolve(digest.digest()));
  });
}

function createLinuxUpdateVerifier({feedUrl, publicKey, fetchImpl = fetch}) {
  if (typeof publicKey !== "string" || !publicKey.includes("PUBLIC KEY")) {
    throw new Error("A pinned Linux update public key is required");
  }
  const feed = new URL(feedUrl);
  if (feed.protocol !== "https:") throw new Error("Linux update signatures require HTTPS");
  const key = crypto.createPublicKey(publicKey);

  return async (downloadedFile) => {
    if (typeof downloadedFile !== "string" || !path.isAbsolute(downloadedFile)) {
      throw new Error("Downloaded update path is unavailable");
    }
    const artifact = path.resolve(downloadedFile);
    const signatureUrl = new URL(`${encodeURIComponent(path.basename(artifact))}.sig`, feed);
    const response = await fetchImpl(signatureUrl.href, {cache: "no-store"});
    if (!response.ok) throw new Error("Linux publisher signature is unavailable");
    const signature = Buffer.from(await response.arrayBuffer());
    if (signature.length !== 64) throw new Error("Linux publisher signature is malformed");
    const digest = await sha256File(artifact);
    if (!crypto.verify(null, digest, key, signature)) {
      throw new Error("Linux publisher signature is invalid");
    }
  };
}

module.exports = {createLinuxUpdateVerifier, sha256File};
