# Homelab Service Backup

A self-hosted Docker service that version-controls your homelab service
directories (Jellyfin, the *arr stack, Deluge, etc.) into a **private** GitHub
repository, so you can recover from a critical failure. It exposes a web UI for
monitoring, configuration, and one-click restore.

It uses **git itself** as the storage and versioning engine: your services
directory is the git work-tree, the `.git` directory lives in the container's
data volume, and every backup is a commit that gets pushed to GitHub. That gives
you version history, diffs, "last synced" status, and trivial restore for free —
with **no data duplication**.

## Features

- Single Docker container (FastAPI backend + React frontend).
- **Hybrid sync**: filesystem watching with a debounce, plus a periodic safety
  interval (configurable; can also be watch-only or interval-only).
- **Per-service and per-directory exclusions** — e.g. skip the multi-GB
  `audiobookshelf/data` folder while still backing up its `config`.
- **One-click restore** from any backup, with a diff preview and optional
  automatic stop/start of the affected containers via the Docker socket.
- Web dashboard: sync status, last synced, pending changes, ahead/behind remote,
  repo size, manual "Back up now" / "Push now".
- Auto-generated disaster-recovery manifest (`BACKUP_MANIFEST.md/json`) listing
  services, images and ports.
- Optional notifications (ntfy / Discord / Gotify webhook).
- Healthcheck (`/healthz`) and Prometheus metrics (`/metrics`).

## How it works

```
host:/opt  ──(mounted RW)──>  container:/services   (git work-tree)
                              container:/data/repo.git  (git dir + history)
                              container:/data/state.db  (settings/state)
```

A backup = `git add -A` -> `git commit` -> `git push` (HTTPS + PAT). Exclusions
are written to `repo.git/info/exclude`, so your real service folders stay clean.
Restore = `git checkout <commit> -- <path>`.

## Quick start

1. Edit [`docker-compose.yaml`](docker-compose.yaml):
   - Map your services base directory to `/services` (default `/opt:/services`).
   - Adjust the published port (default `8787`) and `TZ` if needed.
2. Build and run:

   ```bash
   docker compose up -d --build
   ```

   To rebuild the image after updating source files without restarting immediately:

   ```bash
   docker compose build
   ```

   Or to rebuild and restart in one step (zero-downtime swap — `/data` volume is
   preserved):

   ```bash
   docker compose up -d --build
   ```

3. Open `http://<server-ip>:8787` and go to **Settings**:
   - Set the **GitHub repository URL** (must be a **private** repo).
   - Paste a **fine-grained Personal Access Token** with `Contents: read & write`
     on that repo.
   - Choose your sync mode/interval, then click **Connect & initialise**.
4. Go to **Services** and toggle off any large data directories you don't want
   backed up.
5. Hit **Back up now** on the Dashboard for the first commit.

> The repo will contain real secrets (auth files, keys, sqlite DBs) backed up
> as-is, so it **must stay private**.

## Updating after source changes

After pulling new changes or editing source files, rebuild the image and restart
the container:

```bash
# Rebuild image only (does not restart the running container)
docker compose build

# Rebuild and restart in one step (recommended — /data volume is preserved)
docker compose up -d --build
```

The build compiles the React frontend (Node stage) and copies the Python backend
into the image. The running container's `/data` volume — which holds your git
history and settings — is never touched by a rebuild.

## Restoring after a total failure

Even with the mini PC gone, the GitHub repo is a full snapshot:

```bash
git clone https://github.com/you/homelab-backup.git /opt
cd /opt/<service> && docker compose up -d   # repeat per service
```

`BACKUP_MANIFEST.md` (committed on every backup) lists each service's images and
ports to guide recovery.

## Development

Backend:

```bash
cd backend
pip install -r requirements.txt
DATA_DIR=./data SERVICES_DIR=../example-services uvicorn app.main:app --reload
```

Frontend (proxies `/api` to `localhost:8000`):

```bash
cd frontend
npm install
npm run dev
```

## Notes

- The file watcher uses inotify. If you watch very many directories you may need
  to raise the host limit:

  ```bash
  echo 'fs.inotify.max_user_watches=524288' | sudo tee /etc/sysctl.d/99-inotify.conf
  sudo sysctl -p /etc/sysctl.d/99-inotify.conf
  ```

  Excluded directories are not watched, which keeps the count low.
- The container needs the Docker socket only for the restore stop/start feature;
  remove that mount to disable it.
