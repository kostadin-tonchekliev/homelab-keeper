from __future__ import annotations

import json
import subprocess

from .logbus import log_bus


def _docker(*args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def available() -> bool:
    try:
        return _docker("version", "--format", "{{.Server.Version}}").returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def list_compose_projects() -> list[dict]:
    """List running compose projects keyed by working dir, when docker is reachable."""
    if not available():
        return []
    proc = _docker("ps", "--format", "{{json .}}")
    projects: dict[str, dict] = {}
    for line in proc.stdout.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        labels = row.get("Labels", "")
        project = ""
        workdir = ""
        for kv in labels.split(","):
            if kv.startswith("com.docker.compose.project="):
                project = kv.split("=", 1)[1]
            elif kv.startswith("com.docker.compose.project.working_dir="):
                workdir = kv.split("=", 1)[1]
        if project:
            projects.setdefault(
                project, {"project": project, "working_dir": workdir, "containers": []}
            )
            projects[project]["containers"].append(row.get("Names", ""))
    return list(projects.values())


def compose_down(working_dir: str) -> bool:
    if not available():
        return False
    proc = _docker("compose", "--project-directory", working_dir, "stop", timeout=300)
    if proc.returncode != 0:
        log_bus.warning(f"compose stop failed for {working_dir}: {proc.stderr.strip()}")
        return False
    log_bus.info(f"Stopped containers in {working_dir}.")
    return True


def compose_up(working_dir: str) -> bool:
    if not available():
        return False
    proc = _docker(
        "compose", "--project-directory", working_dir, "up", "-d", timeout=300
    )
    if proc.returncode != 0:
        log_bus.warning(f"compose up failed for {working_dir}: {proc.stderr.strip()}")
        return False
    log_bus.info(f"Started containers in {working_dir}.")
    return True
