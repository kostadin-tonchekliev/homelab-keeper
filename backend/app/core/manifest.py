from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .discovery import discover_services
from .logbus import log_bus

MANIFEST_JSON = "BACKUP_MANIFEST.json"
MANIFEST_MD = "BACKUP_MANIFEST.md"


def _parse_compose(path: Path) -> list[dict]:
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except (yaml.YAMLError, OSError):
        return []
    services = data.get("services", {}) or {}
    result = []
    for name, spec in services.items():
        if not isinstance(spec, dict):
            continue
        result.append(
            {
                "name": name,
                "image": spec.get("image", ""),
                "container_name": spec.get("container_name", ""),
                "ports": spec.get("ports", []) or [],
                "restart": spec.get("restart", ""),
            }
        )
    return result


def build_manifest(services_dir: str) -> dict:
    base = Path(services_dir)
    services = discover_services(services_dir)
    entries = []
    for svc in services:
        compose_path = base / svc.rel_path / (svc.compose_file or "")
        entries.append(
            {
                "service": svc.name,
                "compose_file": svc.compose_file,
                "containers": _parse_compose(compose_path) if svc.compose_file else [],
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "services_dir": services_dir,
        "services": entries,
    }


def _render_md(manifest: dict) -> str:
    lines = [
        "# Backup Manifest",
        "",
        f"Generated: {manifest['generated_at']}",
        "",
        "This file is auto-generated on every backup. To recover on a fresh machine:",
        "",
        "1. Clone this repository into your services directory.",
        "2. For each service folder, run `docker compose up -d`.",
        "",
        "## Services",
        "",
    ]
    for entry in manifest["services"]:
        lines.append(f"### {entry['service']}")
        lines.append("")
        for c in entry["containers"]:
            ports = ", ".join(str(p) for p in c.get("ports", []))
            lines.append(
                f"- **{c['name']}** — image `{c['image'] or 'n/a'}`"
                + (f", ports: {ports}" if ports else "")
            )
        if not entry["containers"]:
            lines.append("- (no parsed containers)")
        lines.append("")
    return "\n".join(lines)


def _content_hash(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


def write_manifest(services_dir: str) -> None:
    """Write the manifest only when the service content has changed.

    The `generated_at` timestamp is deliberately excluded from the
    change-detection hash so that a backup with no real service changes does
    not produce a new manifest file (which would otherwise make every backup
    commit have at least one "changed" file and trigger an infinite watcher
    loop).
    """
    base = Path(services_dir)
    if not base.is_dir():
        return
    try:
        manifest = build_manifest(services_dir)

        # Build a stable fingerprint of the service content (no timestamp).
        stable = {k: v for k, v in manifest.items() if k != "generated_at"}
        new_hash = _content_hash(json.dumps(stable, sort_keys=True))

        json_path = base / MANIFEST_JSON
        # Only rewrite if service content changed since last write.
        if json_path.exists():
            try:
                old = json.loads(json_path.read_text())
                old_stable = {k: v for k, v in old.items() if k != "generated_at"}
                old_hash = _content_hash(json.dumps(old_stable, sort_keys=True))
                if old_hash == new_hash:
                    return
            except (json.JSONDecodeError, OSError):
                pass  # can't read old file → overwrite

        json_path.write_text(json.dumps(manifest, indent=2) + "\n")
        (base / MANIFEST_MD).write_text(_render_md(manifest))
    except OSError as exc:
        log_bus.warning(f"Could not write manifest: {exc}")
