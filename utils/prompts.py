"""Prompt template versioning.

Stores a library of system-prompt templates scoped by sector. Each entry is
versioned: saving a new body bumps the version, keeps history. The active
version per sector is used by enrich_product() at runtime.

Storage: ~/.feed_enricher/prompts.json
Structure:
    {
      "sectors": {
          "abbigliamento": {
              "active": 2,
              "versions": [
                  {"version": 1, "body": "...", "created_at": "...", "note": "initial"},
                  {"version": 2, "body": "...", "created_at": "...", "note": "more aggressive titles"}
              ]
          },
          ...
      }
    }
"""
from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

_LOCK = threading.Lock()
_STORE = Path.home() / ".feed_enricher" / "prompts.json"
_STORE.parent.mkdir(parents=True, exist_ok=True)


def _load() -> dict:
    if not _STORE.exists():
        return {"sectors": {}}
    try:
        with _STORE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if "sectors" not in data:
            data["sectors"] = {}
        return data
    except (OSError, json.JSONDecodeError):
        return {"sectors": {}}


def _save(data: dict) -> None:
    tmp = _STORE.with_suffix(".json.tmp")
    with _LOCK:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        tmp.replace(_STORE)


def list_sectors() -> list[str]:
    return sorted(_load().get("sectors", {}).keys())


def list_versions(sector: str) -> list[dict]:
    data = _load()
    entry = data.get("sectors", {}).get(sector)
    if not entry:
        return []
    return list(entry.get("versions", []))


def get_active(sector: str) -> dict | None:
    """Return the active version entry for a sector, or None if none stored."""
    data = _load()
    entry = data.get("sectors", {}).get(sector)
    if not entry:
        return None
    active = entry.get("active")
    for v in entry.get("versions", []):
        if v.get("version") == active:
            return v
    # fallback: last one
    if entry.get("versions"):
        return entry["versions"][-1]
    return None


def save_version(sector: str, body: str, note: str = "") -> int:
    """Create a new version for `sector` and mark it active. Returns version number."""
    data = _load()
    sectors = data.setdefault("sectors", {})
    entry = sectors.setdefault(sector, {"active": 0, "versions": []})
    versions = entry.setdefault("versions", [])
    next_ver = (max((v["version"] for v in versions), default=0) + 1)
    versions.append({
        "version": next_ver,
        "body": body,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": note,
    })
    entry["active"] = next_ver
    _save(data)
    return next_ver


def set_active(sector: str, version: int) -> bool:
    data = _load()
    entry = data.get("sectors", {}).get(sector)
    if not entry:
        return False
    if not any(v["version"] == version for v in entry.get("versions", [])):
        return False
    entry["active"] = version
    _save(data)
    return True


def delete_version(sector: str, version: int) -> bool:
    data = _load()
    entry = data.get("sectors", {}).get(sector)
    if not entry:
        return False
    before = len(entry.get("versions", []))
    entry["versions"] = [v for v in entry.get("versions", []) if v["version"] != version]
    if len(entry["versions"]) == before:
        return False
    # reset active if we deleted it
    if entry.get("active") == version:
        entry["active"] = entry["versions"][-1]["version"] if entry["versions"] else 0
    _save(data)
    return True


def get_template_body(sector: str) -> str | None:
    """Compact helper used by enrich_product() to fetch the active template body."""
    v = get_active(sector)
    return v.get("body") if v else None
