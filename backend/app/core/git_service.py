from __future__ import annotations

import shutil
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from urllib.parse import quote, urlparse, urlunparse

from ..config import get_config
from ..models import Settings
from .logbus import log_bus


class GitError(RuntimeError):
    pass


@dataclass
class Commit:
    sha: str
    short_sha: str
    author: str
    date: str
    subject: str


@dataclass
class BackupResult:
    commit: Commit | None
    skipped_large_files: list[str]


@dataclass
class RepoStatus:
    initialized: bool
    branch: str
    has_remote: bool
    pending_changes: int
    ahead: int
    behind: int
    last_commit: Commit | None
    repo_size_bytes: int
    clean: bool


class GitService:
    """Drives a single git repo whose work-tree is the services directory and
    whose git-dir lives in the persistent data volume."""

    def __init__(self) -> None:
        self._config = get_config()
        self._lock = RLock()

    # ----- low level ---------------------------------------------------------
    def _env(self, settings: Settings) -> dict[str, str]:
        import os

        env = os.environ.copy()
        env["GIT_DIR"] = str(self._config.git_dir)
        env["GIT_WORK_TREE"] = settings.services_dir
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_AUTHOR_NAME"] = settings.git_author_name
        env["GIT_AUTHOR_EMAIL"] = settings.git_author_email
        env["GIT_COMMITTER_NAME"] = settings.git_author_name
        env["GIT_COMMITTER_EMAIL"] = settings.git_author_email
        return env

    # Lock files git creates while an operation is in progress.
    _GIT_LOCK_FILES = ("index.lock", "HEAD.lock", "MERGE_HEAD.lock", "COMMIT_EDITMSG.lock")
    # A lock older than this many seconds is considered stale (no live process holds it).
    _STALE_LOCK_AGE = 60

    def _clear_stale_locks(self) -> None:
        """Remove git lock files that are older than _STALE_LOCK_AGE seconds.

        Git writes the PID of the locking process into these files on some
        platforms, but not reliably across versions, so we use file age as a
        conservative proxy: if the file has not been touched in 60 s there is no
        live git process holding it.
        """
        git_dir = self._config.git_dir
        for name in self._GIT_LOCK_FILES:
            lock = git_dir / name
            try:
                age = time.time() - lock.stat().st_mtime
                if age > self._STALE_LOCK_AGE:
                    lock.unlink(missing_ok=True)
                    log_bus.warning(
                        f"Removed stale git lock {name} (age {age:.0f}s). "
                        "The previous git process was likely interrupted."
                    )
            except FileNotFoundError:
                pass
            except OSError as exc:
                log_bus.warning(f"Could not remove git lock {name}: {exc}")

    def _run(
        self,
        settings: Settings,
        *args: str,
        check: bool = True,
        timeout: int = 600,
    ) -> subprocess.CompletedProcess:
        with self._lock:
            self._clear_stale_locks()
            proc = subprocess.run(
                ["git", *args],
                env=self._env(settings),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        if check and proc.returncode != 0:
            err_text = proc.stderr.strip() or proc.stdout.strip()
            # If we still hit a lock error despite our cleanup (another real
            # process holds it), report clearly rather than showing a raw git
            # message.
            if "index.lock" in err_text or ".lock': File exists" in err_text:
                raise GitError(
                    "Git is locked by another process. If no other backup is "
                    "running, the lock file is stale — it will be removed "
                    f"automatically after {self._STALE_LOCK_AGE}s: {err_text}"
                )
            raise GitError(
                f"git {' '.join(args)} failed ({proc.returncode}): {err_text}"
            )
        return proc

    def _token(self, settings: Settings) -> str | None:
        return settings.github_token or self._config.github_token

    @staticmethod
    def _is_ssh_url(url: str) -> bool:
        return url.startswith("git@") or url.startswith("ssh://")

    def _authed_url(self, settings: Settings) -> str:
        """Inject the token into the HTTPS remote URL for network operations.

        The token is never written to git config or committed; it is only passed
        on the command line for the duration of a push/fetch.
        """
        url = settings.repo_url.strip()
        if not url:
            raise GitError("Repository URL is not configured.")
        if self._is_ssh_url(url):
            raise GitError(
                "SSH URLs (git@github.com:…) are not supported. "
                "This service authenticates over HTTPS using a Personal Access Token. "
                "Change the repository URL to the HTTPS form: "
                "https://github.com/<user>/<repo>.git"
            )
        token = self._token(settings)
        if not token or not url.startswith("https://"):
            return url
        parsed = urlparse(url)
        netloc = f"x-access-token:{quote(token, safe='')}@{parsed.hostname}"
        if parsed.port:
            netloc += f":{parsed.port}"
        return urlunparse(parsed._replace(netloc=netloc))

    @staticmethod
    def _redact(text: str, settings: Settings) -> str:
        token = settings.github_token
        if token:
            text = text.replace(token, "***")
        return text

    # ----- excludes ----------------------------------------------------------
    def write_excludes(self, lines: list[str]) -> None:
        info_dir = self._config.git_dir / "info"
        info_dir.mkdir(parents=True, exist_ok=True)
        header = [
            "# Generated by Homelab Service Backup. Do not edit by hand;",
            "# manage exclusions from the web UI (Services tab).",
            "",
        ]
        content = "\n".join(header + lines) + "\n"
        (info_dir / "exclude").write_text(content)

    # ----- lifecycle ---------------------------------------------------------
    def is_initialized(self) -> bool:
        return (self._config.git_dir / "HEAD").exists()

    def init_repo(self, settings: Settings) -> None:
        """Initialise the local repo and attach it to the remote.

        Live files in the work-tree are treated as the source of truth: if the
        remote already has history we layer the current files on top of it as a
        new commit rather than overwriting the working tree.
        """
        with self._lock:
            url = settings.repo_url.strip()
            if url and self._is_ssh_url(url):
                raise GitError(
                    "SSH URLs (git@github.com:…) are not supported. "
                    "Use the HTTPS URL instead: https://github.com/<user>/<repo>.git"
                )

            git_dir = self._config.git_dir
            git_dir.mkdir(parents=True, exist_ok=True)
            if not self.is_initialized():
                self._run(settings, "init", "-b", settings.branch)
                log_bus.info("Initialised local git repository.")

            self._run(settings, "config", "core.fileMode", "false")
            self._run(settings, "config", "gc.auto", "0")
            # Large service directories can exceed git's 1 MB default post
            # buffer, causing GitHub to return HTTP 408 mid-push.  500 MB is
            # enough for typical homelab repos.
            self._run(settings, "config", "http.postBuffer", "524288000")

            # (Re)point origin at the configured URL (without the token).
            self._run(settings, "remote", "remove", "origin", check=False)
            if url:
                self._run(settings, "remote", "add", "origin", url)

            if settings.repo_url.strip():
                authed = self._authed_url(settings)
                fetch = self._run(settings, "fetch", authed, settings.branch, check=False)
                remote_has_branch = fetch.returncode == 0
                if remote_has_branch:
                    # Mark remote files as tracked without touching the work-tree.
                    self._run(settings, "reset", "--mixed", "FETCH_HEAD", check=False)
                    log_bus.info(
                        f"Attached to existing remote history on '{settings.branch}'."
                    )

    # ----- status ------------------------------------------------------------
    def _dir_size(self, path: Path) -> int:
        total = 0
        for p in path.rglob("*"):
            try:
                if p.is_file():
                    total += p.stat().st_size
            except OSError:
                continue
        return total

    def last_commit(self, settings: Settings) -> Commit | None:
        proc = self._run(
            settings,
            "log",
            "-1",
            "--pretty=format:%H%x1f%h%x1f%an%x1f%cI%x1f%s",
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            return None
        parts = proc.stdout.strip().split("\x1f")
        if len(parts) != 5:
            return None
        return Commit(*parts)

    def status(self, settings: Settings) -> RepoStatus:
        if not self.is_initialized():
            return RepoStatus(
                initialized=False,
                branch=settings.branch,
                has_remote=False,
                pending_changes=0,
                ahead=0,
                behind=0,
                last_commit=None,
                repo_size_bytes=0,
                clean=True,
            )

        porcelain = self._run(settings, "status", "--porcelain", check=False)
        pending = len([ln for ln in porcelain.stdout.splitlines() if ln.strip()])

        ahead = behind = 0
        rl = self._run(
            settings,
            "rev-list",
            "--left-right",
            "--count",
            f"origin/{settings.branch}...HEAD",
            check=False,
        )
        if rl.returncode == 0 and rl.stdout.strip():
            try:
                behind_s, ahead_s = rl.stdout.strip().split()
                behind, ahead = int(behind_s), int(ahead_s)
            except ValueError:
                pass

        remotes = self._run(settings, "remote", check=False)
        return RepoStatus(
            initialized=True,
            branch=settings.branch,
            has_remote="origin" in remotes.stdout.split(),
            pending_changes=pending,
            ahead=ahead,
            behind=behind,
            last_commit=self.last_commit(settings),
            repo_size_bytes=self._dir_size(self._config.git_dir),
            clean=pending == 0,
        )

    # ----- large-file helpers ------------------------------------------------
    # GitHub rejects any single blob that exceeds this size.
    _GITHUB_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100 MB

    def _unstage_oversized_files(self, settings: Settings) -> list[str]:
        """Remove files that exceed GitHub's 100 MB hard limit from the index.

        Called after ``git add -A`` so that oversized files are never included
        in a commit.  Returns the list of relative paths that were dropped.
        """
        proc = self._run(settings, "diff", "--cached", "--name-only", check=False)
        if not proc.stdout.strip():
            return []

        services_dir = Path(settings.services_dir)
        oversized: list[str] = []
        for rel in proc.stdout.splitlines():
            rel = rel.strip()
            if not rel:
                continue
            try:
                if (services_dir / rel).stat().st_size > self._GITHUB_MAX_FILE_SIZE:
                    oversized.append(rel)
            except OSError:
                pass

        if not oversized:
            return []

        for path in oversized:
            self._run(settings, "rm", "--cached", "--", path, check=False)

        log_bus.warning(
            f"Skipped {len(oversized)} file(s) that exceed GitHub's 100 MB limit. "
            "Add them to the Services exclusions list to suppress this warning:"
        )
        for path in oversized:
            log_bus.warning(f"  \u2022 {path}")
        return oversized

    @staticmethod
    def _parse_github_large_file_paths(err: str) -> list[str]:
        """Extract file paths from a GitHub GH001 large-file rejection message."""
        import re

        return re.findall(r"remote: error: File (.+?) is [\d.]+ MB;", err)

    def _strip_large_files_from_unpushed_history(
        self, settings: Settings, paths: list[str]
    ) -> None:
        """Rewrite all unpushed local commits into one commit without *paths*.

        Strategy:
        - If the remote branch already exists: soft-reset HEAD to
          ``origin/<branch>``, collapsing all local-only commits back into the
          staging area, remove the large files, and re-commit.
        - If there is no remote branch yet (first push ever): soft-squash all
          commits after the root into the root via ``reset --soft HEAD~(n-1)``,
          then amend the root commit without the large files.
        """
        has_remote = (
            self._run(
                settings,
                "rev-parse",
                "--verify",
                f"origin/{settings.branch}",
                check=False,
            ).returncode
            == 0
        )

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        if has_remote:
            self._run(settings, "reset", "--soft", f"origin/{settings.branch}")
            for p in paths:
                self._run(settings, "rm", "--cached", "--", p, check=False)
            self._run(
                settings,
                "commit",
                "-m",
                f"Backup {now} (large files auto-excluded)",
            )
        else:
            n = int(
                self._run(
                    settings, "rev-list", "--count", "HEAD", check=False
                ).stdout.strip()
                or "1"
            )
            if n > 1:
                # Collapse commits 2…n back onto root so the index holds the
                # full current state; then amend root to drop the large files.
                self._run(settings, "reset", "--soft", f"HEAD~{n - 1}")
            for p in paths:
                self._run(settings, "rm", "--cached", "--", p, check=False)
            self._run(
                settings,
                "commit",
                "--amend",
                "-m",
                f"Backup {now} (large files auto-excluded)",
            )

        log_bus.warning(
            f"Rewrote local commit history to remove {len(paths)} large file(s). "
            "Add them to the Services exclusions to prevent this on future backups."
        )

    # ----- backup / push -----------------------------------------------------

    # When a file is actively written by a running container (e.g. a live
    # SQLite database) git can detect a hash mismatch mid-index and bail with
    # "confused by unstable object source data".  A short wait and retry is
    # enough in practice because the write burst settles quickly.
    _ADD_RETRIES = 3
    _ADD_RETRY_DELAY = 3  # seconds between attempts

    def backup(self, settings: Settings, message: str | None = None) -> BackupResult:
        with self._lock:
            if not self.is_initialized():
                self.init_repo(settings)

            log_bus.info("Staging: running git add -A (may take a moment for large trees)…")
            for attempt in range(1, self._ADD_RETRIES + 1):
                proc = self._run(settings, "add", "-A", check=False)
                if proc.returncode == 0:
                    break
                err_text = proc.stderr.strip() or proc.stdout.strip()
                if "confused by unstable object source data" in err_text:
                    if attempt < self._ADD_RETRIES:
                        log_bus.warning(
                            f"Staging: a file changed mid-index (attempt {attempt}/{self._ADD_RETRIES}), "
                            f"retrying in {self._ADD_RETRY_DELAY}s… "
                            "(a running container is writing to the file — consider excluding it)"
                        )
                        time.sleep(self._ADD_RETRY_DELAY)
                    else:
                        raise GitError(
                            f"git add -A failed after {self._ADD_RETRIES} attempts — "
                            "a file is being actively written by a running container. "
                            f"Exclude it on the Services page to prevent this. Details: {err_text}"
                        )
                else:
                    raise GitError(f"git add -A failed ({proc.returncode}): {err_text}")

            # Drop oversized files before we even look at the staged count so
            # that GitHub's 100 MB per-file limit is never hit at push time.
            skipped = self._unstage_oversized_files(settings)

            staged = self._run(settings, "diff", "--cached", "--name-only", check=False)
            if not staged.stdout.strip():
                log_bus.info("Staging complete: no changes to commit.")
                return BackupResult(commit=None, skipped_large_files=skipped)

            count = len([ln for ln in staged.stdout.splitlines() if ln.strip()])
            log_bus.info(f"Staging complete: {count} file(s) changed. Creating commit…")

            now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            msg = message or f"Backup {now} ({count} file(s) changed)"
            self._run(settings, "commit", "-m", msg)
            commit = self.last_commit(settings)
            log_bus.success(f"Committed backup: {msg}")

            if settings.auto_push and settings.repo_url.strip():
                self.push(settings)
            return BackupResult(commit=commit, skipped_large_files=skipped)

    def push(self, settings: Settings) -> None:
        with self._lock:
            log_bus.info("Pushing commits to remote…")
            authed = self._authed_url(settings)
            proc = self._run(
                settings, "push", authed, f"HEAD:{settings.branch}", check=False
            )
            if proc.returncode != 0:
                err = self._redact(proc.stderr.strip(), settings)
                large_files = self._parse_github_large_file_paths(err)
                if large_files:
                    log_bus.warning(
                        f"Push rejected: {len(large_files)} file(s) exceed GitHub's "
                        "100 MB limit. Rewriting local history to remove them…"
                    )
                    self._strip_large_files_from_unpushed_history(settings, large_files)
                    # Retry with cleaned history.
                    proc = self._run(
                        settings,
                        "push",
                        authed,
                        f"HEAD:{settings.branch}",
                        check=False,
                    )
                    if proc.returncode != 0:
                        err = self._redact(proc.stderr.strip(), settings)
                        log_bus.error(f"Push failed: {err}")
                        raise GitError(f"Push failed: {err}")
                    log_bus.success(f"Pushed to origin/{settings.branch}.")
                    return
                log_bus.error(f"Push failed: {err}")
                raise GitError(f"Push failed: {err}")
            log_bus.success(f"Pushed to origin/{settings.branch}.")

    def fetch(self, settings: Settings) -> None:
        with self._lock:
            authed = self._authed_url(settings)
            self._run(settings, "fetch", authed, settings.branch, check=False)

    # ----- history / diff ----------------------------------------------------
    def log(self, settings: Settings, limit: int = 100) -> list[Commit]:
        if not self.is_initialized():
            return []
        proc = self._run(
            settings,
            "log",
            f"-{limit}",
            "--pretty=format:%H%x1f%h%x1f%an%x1f%cI%x1f%s",
            check=False,
        )
        commits: list[Commit] = []
        for line in proc.stdout.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 5:
                commits.append(Commit(*parts))
        return commits

    def commit_files(self, settings: Settings, sha: str) -> list[dict]:
        proc = self._run(
            settings, "show", "--numstat", "--format=", sha, check=False
        )
        files: list[dict] = []
        for line in proc.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) == 3:
                added, removed, path = parts
                files.append({"added": added, "removed": removed, "path": path})
        return files

    def diff(self, settings: Settings, sha: str, path: str | None = None) -> str:
        args = ["show", sha]
        if path:
            args += ["--", path]
        proc = self._run(settings, *args, check=False)
        return proc.stdout

    # ----- restore -----------------------------------------------------------
    def restore_preview(self, settings: Settings, sha: str, paths: list[str]) -> str:
        # Diff of what restoring would change: target commit vs current work-tree.
        proc = self._run(settings, "diff", sha, "--", *(paths or ["."]), check=False)
        return proc.stdout

    def restore(self, settings: Settings, sha: str, paths: list[str]) -> None:
        with self._lock:
            targets = paths if paths else ["."]
            self._run(settings, "checkout", sha, "--", *targets)
            log_bus.success(
                f"Restored {', '.join(targets)} from {sha[:8]}."
            )

    # ----- maintenance -------------------------------------------------------
    def gc(self, settings: Settings) -> None:
        if self.is_initialized():
            self._run(settings, "gc", "--auto", check=False)

    def reset_repo(self) -> None:
        """Remove the local git dir (does not touch the work-tree)."""
        with self._lock:
            if self._config.git_dir.exists():
                shutil.rmtree(self._config.git_dir)


git_service = GitService()
