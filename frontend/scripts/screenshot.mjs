/**
 * Capture the documentation screenshots used in the README.
 *
 * What it does:
 *   1. Boots a `vite preview` server serving the production build in `dist/`.
 *   2. Opens each page in headless Chromium with the `/api/**` calls mocked
 *      (see MOCK_DATA below), so the UI renders a realistic, populated state
 *      without needing a real backend / GitHub repo.
 *   3. Writes PNGs to `../docs/` for both the dark and light themes.
 *
 * Usage:
 *   npm run build && node scripts/screenshot.mjs      # from the frontend/ dir
 *   npm run screenshot                                # shortcut (builds first)
 *
 * Requirements (one-time):
 *   npm install                          # installs the `playwright` dev dep
 *   npx playwright install chromium      # downloads the headless browser
 *   sudo npx playwright install-deps chromium   # Linux: OS libraries for Chromium
 *
 * To add a screenshot, add an entry to SHOTS. To change what the UI shows,
 * edit MOCK_DATA.
 */
import { chromium } from "playwright";
import { spawn } from "node:child_process";
import { mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_DIR = resolve(__dirname, "..");
const OUT_DIR = resolve(FRONTEND_DIR, "..", "docs");
const PORT = Number(process.env.PORT ?? 4317);
const BASE = `http://localhost:${PORT}`;

// ---- Pages to capture (one PNG per entry) ----------------------------------
const SHOTS = [
  { path: "/dashboard", theme: "dark", file: "dashboard-dark.png" },
  { path: "/dashboard", theme: "light", file: "dashboard-light.png" },
];

const VIEWPORT = { width: 1360, height: 600 };

// ---- Mocked API responses --------------------------------------------------
// Edit these to change what the screenshots depict.
const now = Date.now();
const iso = (msAgo) => new Date(now - msAgo).toISOString();

const lastCommit = {
  sha: "a1b9f4c0d2e3f4a5b6c7d8e9f0a1b2c3d4e5f6a7",
  short_sha: "a1b9f4c",
  author: "Homelab Keeper",
  date: iso(5 * 60 * 1000),
  subject: "Backup 2026-06-14 19:42 UTC (5 files changed)",
};

const MOCK_DATA = {
  status: {
    initialized: true,
    branch: "main",
    has_remote: true,
    pending_changes: 0,
    ahead: 0,
    behind: 0,
    last_commit: lastCommit,
    repo_size_bytes: 48234496,
    clean: true,
    activity: "idle",
    last_error: null,
    docker_available: true,
    configured: true,
  },
  services: [
    {
      name: "jellyfin", rel_path: "jellyfin", compose_file: "docker-compose.yml",
      size_bytes: 1287654, enabled: true,
      subdirs: [
        { name: "config", rel_path: "jellyfin/config", size_bytes: 985432, excluded: false },
        { name: "cache", rel_path: "jellyfin/cache", size_bytes: 4503599627, excluded: true },
      ],
    },
    {
      name: "radarr", rel_path: "radarr", compose_file: "docker-compose.yml",
      size_bytes: 542112, enabled: true,
      subdirs: [{ name: "config", rel_path: "radarr/config", size_bytes: 542112, excluded: false }],
    },
    {
      name: "audiobookshelf", rel_path: "audiobookshelf", compose_file: "docker-compose.yml",
      size_bytes: 18452, enabled: false, subdirs: [],
    },
  ],
  history: [
    { ...lastCommit },
    { sha: "b2", short_sha: "f73c1aa", author: "Homelab Keeper", date: iso(3.6e6), subject: "Backup 2026-06-14 18:42 UTC (2 files changed)" },
    { sha: "c3", short_sha: "9d40e21", author: "Homelab Keeper", date: iso(9e6), subject: "Backup 2026-06-14 17:12 UTC (11 files changed)" },
    { sha: "d4", short_sha: "31aa9f8", author: "Homelab Keeper", date: iso(8.64e7), subject: "Backup 2026-06-13 19:42 UTC (1 file changed)" },
  ],
  settings: {
    services_dir: "/services", repo_url: "https://github.com/you/homelab-backup.git",
    branch: "main", has_token: true, git_author_name: "Homelab Keeper",
    git_author_email: "keeper@homelab.local", sync_mode: "hybrid",
    interval_seconds: 3600, debounce_seconds: 15, auto_push: true,
    stop_containers_on_restore: true, notify_webhook_url: "https://ntfy.sh/my-homelab",
    notify_on_success: false, notify_on_failure: true, initialized: true,
  },
  logs: [],
};

function mockBody(url) {
  if (url.includes("/api/status")) return MOCK_DATA.status;
  if (url.includes("/api/services")) return MOCK_DATA.services;
  if (url.includes("/api/history")) return MOCK_DATA.history;
  if (url.includes("/api/settings")) return MOCK_DATA.settings;
  if (url.includes("/api/logs")) return MOCK_DATA.logs;
  return {};
}

// ---- Preview server lifecycle ----------------------------------------------
function startPreview() {
  const bin = resolve(FRONTEND_DIR, "node_modules/.bin/vite");
  const proc = spawn(bin, ["preview", "--port", String(PORT)], {
    cwd: FRONTEND_DIR,
    stdio: ["ignore", "pipe", "pipe"],
  });
  proc.stderr.on("data", (d) => process.stderr.write(d));
  return proc;
}

async function waitForServer(timeoutMs = 20000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(BASE + "/");
      if (res.ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(
    `Preview server did not start on ${BASE}. Did you run \`npm run build\` first?`,
  );
}

// ---- Main ------------------------------------------------------------------
async function main() {
  mkdirSync(OUT_DIR, { recursive: true });

  const server = startPreview();
  let browser;
  try {
    await waitForServer();
    browser = await chromium.launch();

    for (const shot of SHOTS) {
      const ctx = await browser.newContext({
        viewport: VIEWPORT,
        deviceScaleFactor: 2,
      });
      await ctx.addInitScript((theme) => {
        localStorage.setItem("hlb-theme", theme);
      }, shot.theme);
      await ctx.route("**/api/**", (route) =>
        route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(mockBody(route.request().url())),
        }),
      );
      const page = await ctx.newPage();
      await page.goto(BASE + shot.path, { waitUntil: "networkidle" });
      await page.waitForTimeout(600); // let entrance animation settle
      await page.screenshot({ path: resolve(OUT_DIR, shot.file) });
      console.log(`captured docs/${shot.file}`);
      await ctx.close();
    }
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
  console.log("done");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
