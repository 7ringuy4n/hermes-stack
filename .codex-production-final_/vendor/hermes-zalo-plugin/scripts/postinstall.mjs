#!/usr/bin/env node
// scripts/postinstall.mjs
//
// Make `hermes-zalo-plugin` runnable right after `npm i -g`, even when npm's
// global bin dir isn't on PATH.
//
// Why this is needed: if you install with the Node that Hermes bundles
// (~/.hermes/node), npm's global prefix is ~/.hermes/node, so the bin symlink
// lands in ~/.hermes/node/bin — which is NOT on PATH. Hermes only exposes
// node/npm/npx via ~/.local/bin. So we mirror our bin into the SAME directory
// the active `node` is reachable from (which is on PATH by definition).
//
// Safe by design:
//   • only runs on a GLOBAL install; local installs (incl. CI `npm ci`) no-op;
//   • if the global bin dir is already on PATH (the normal case) it does nothing;
//   • never throws — a failing postinstall must not break `npm install`;
//   • only creates/replaces a symlink that points into THIS package; it never
//     clobbers an unrelated file already sitting at that name.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const NAME = "hermes-zalo-plugin";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PKG_ROOT = path.resolve(__dirname, "..");
const CLI = path.join(PKG_ROOT, "bin", "cli.mjs");

const log = (m) => console.log(`[${NAME}] ${m}`);

const isGlobal = () =>
  process.env.npm_config_global === "true" ||
  String(process.env.npm_config_location || "").toLowerCase() === "global";

const pathDirs = () => (process.env.PATH || "").split(path.delimiter).filter(Boolean);
// Canonicalize so symlinked dirs compare equal (e.g. macOS /var -> /private/var,
// or a PATH entry that is itself a symlink). Falls back to resolve if missing.
const canon = (p) => { try { return fs.realpathSync(p); } catch { return path.resolve(p); } };
const isOnPath = (dir) => { const c = canon(dir); return pathDirs().some((d) => canon(d) === c); };
const isWritable = (dir) => {
  try { fs.accessSync(dir, fs.constants.W_OK); return true; } catch { return false; }
};

// The directory the active `node` is reached through on PATH (e.g. ~/.local/bin).
function nodeBinDirOnPath() {
  for (const d of pathDirs()) {
    try { if (fs.existsSync(path.join(d, "node"))) return path.resolve(d); } catch { /* ignore */ }
  }
  return null;
}

// First writable, on-PATH directory to drop the symlink in (never the prefix bin
// itself). Prefer where `node` already lives, then ~/.local/bin, then any other.
function pickTarget(prefixBin) {
  const seen = new Set();
  const candidates = [nodeBinDirOnPath(), path.join(os.homedir(), ".local", "bin"), ...pathDirs()];
  for (const c of candidates) {
    if (!c) continue;
    const dir = path.resolve(c);
    if (seen.has(dir)) continue;
    seen.add(dir);
    if (canon(dir) === canon(prefixBin)) continue; // pointless
    if (isOnPath(dir) && fs.existsSync(dir) && isWritable(dir)) return dir;
  }
  return null;
}

try {
  if (!isGlobal()) process.exit(0);              // local installs: nothing to do
  if (process.platform === "win32") process.exit(0); // npm shims + PATH differ; skip

  try { fs.chmodSync(CLI, 0o755); } catch { /* ignore */ } // entry carries the shebang

  // npm created <prefix>/bin/<name>. <prefix> is three levels up from PKG_ROOT
  // (<prefix>/lib/node_modules/<name>).
  const prefixBin = path.resolve(PKG_ROOT, "..", "..", "..", "bin");

  // Healthy case: the global bin dir is already on PATH → npm's own link works.
  if (isOnPath(prefixBin)) process.exit(0);

  const target = pickTarget(prefixBin);
  if (!target) {
    log(`installed, but its bin dir isn't on your PATH (${prefixBin}).`);
    log(`Run it with:  npx ${NAME} <cmd>`);
    log(`or add to PATH:  export PATH="${prefixBin}:$PATH"`);
    process.exit(0);
  }

  const link = path.join(target, NAME);
  try {
    const st = fs.lstatSync(link); // throws if it doesn't exist
    const ours =
      st.isSymbolicLink() &&
      (path.resolve(target, fs.readlinkSync(link)) === CLI ||
        fs.readlinkSync(link).includes(`${path.sep}${NAME}${path.sep}`));
    if (!ours) {
      log(`a different '${NAME}' already exists in ${target}; leaving it. Use: npx ${NAME}`);
      process.exit(0);
    }
    fs.rmSync(link); // replace our own stale link
  } catch { /* doesn't exist yet — good */ }

  fs.symlinkSync(CLI, link);

  // Record the link so `hermes-zalo-plugin uninstall` can remove it later
  // (npm no longer runs uninstall lifecycle scripts).
  try {
    const stateDir = process.env.ZALO_DATA_DIR
      ? path.resolve(process.env.ZALO_DATA_DIR)
      : path.join(os.homedir(), ".hermes-zalo");
    fs.mkdirSync(stateDir, { recursive: true });
    fs.writeFileSync(path.join(stateDir, ".binlink"), link + "\n");
  } catch { /* non-fatal */ }

  log(`linked '${NAME}' into ${target} (on your PATH).`);
  log(`If the command isn't found yet in THIS shell, run 'rehash' (zsh) / 'hash -r' (bash) or open a new terminal.`);
} catch (e) {
  try { log(`postinstall note (non-fatal): ${e && e.message ? e.message : e}`); } catch { /* ignore */ }
  process.exit(0);
}
