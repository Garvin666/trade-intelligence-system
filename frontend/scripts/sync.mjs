import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = path.resolve(frontendRoot, "..");
const appOut = path.join(projectRoot, "output", "app");
const offlineOut = path.join(projectRoot, "output", "app-offline.html");
const onlineDist = path.join(frontendRoot, "dist");
const offlineDist = path.join(frontendRoot, "dist-offline");

if (!fs.existsSync(onlineDist)) {
  throw new Error("online build missing, run: pnpm build:online");
}
if (!fs.existsSync(path.join(offlineDist, "index.html"))) {
  throw new Error("offline build missing, run: pnpm build:offline");
}

fs.rmSync(appOut, { recursive: true, force: true });
fs.cpSync(onlineDist, appOut, { recursive: true });
fs.copyFileSync(path.join(offlineDist, "index.html"), offlineOut);

console.log(`SYNC OK\n  online -> ${appOut}\n  offline -> ${offlineOut}`);
