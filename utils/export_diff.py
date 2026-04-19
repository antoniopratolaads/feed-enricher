"""Export diff: snapshot last export + compute delta vs current.

Purpose: on update pushes to Google Merchant / Meta Catalog, upload only the
products that actually changed since the last export. Reduces upload size
and avoids unnecessary re-indexing.

Snapshots are stored per session in ~/.feed_enricher/sessions/<id>/exports/.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Iterable

import pandas as pd

_BASE = Path.home() / ".feed_enricher" / "sessions"


def _snapshot_dir(session_id: str) -> Path:
    p = _BASE / session_id / "exports"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _row_hash(row: pd.Series, cols: Iterable[str]) -> str:
    payload = {c: str(row.get(c, "")).strip() for c in cols}
    return hashlib.md5(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def save_snapshot(session_id: str, target: str, df: pd.DataFrame,
                  id_col: str = "id") -> Path:
    """Persist a hash-per-row snapshot for the given target (google|meta)."""
    d = _snapshot_dir(session_id)
    path = d / f"{target}_last.jsonl"
    cols = [c for c in df.columns if c != id_col]
    tmp = path.with_suffix(".jsonl.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for _, row in df.iterrows():
            rid = str(row.get(id_col, "")).strip()
            if not rid:
                continue
            f.write(json.dumps({
                "id": rid,
                "hash": _row_hash(row, cols),
            }, ensure_ascii=False) + "\n")
    tmp.replace(path)
    return path


def load_snapshot(session_id: str, target: str) -> dict[str, str]:
    """Return {id: hash} from the last snapshot, or {} if none."""
    path = _snapshot_dir(session_id) / f"{target}_last.jsonl"
    if not path.exists():
        return {}
    out: dict[str, str] = {}
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    out[str(e["id"])] = e["hash"]
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        return {}
    return out


def compute_diff(session_id: str, target: str, df: pd.DataFrame,
                 id_col: str = "id") -> dict:
    """Diff `df` against the last snapshot for `target`.

    Returns:
        {
          "has_snapshot": bool,
          "added": [ids of products new since last export],
          "modified": [ids of products with differing hash],
          "removed": [ids present last time but gone now],
          "unchanged": [ids unchanged],
          "added_df": DataFrame,
          "modified_df": DataFrame,
          "delta_df": DataFrame (added + modified, ready to upload)
        }
    """
    previous = load_snapshot(session_id, target)
    cols = [c for c in df.columns if c != id_col]

    current_ids: set[str] = set()
    current_hashes: dict[str, str] = {}
    for _, row in df.iterrows():
        rid = str(row.get(id_col, "")).strip()
        if not rid:
            continue
        current_ids.add(rid)
        current_hashes[rid] = _row_hash(row, cols)

    added = sorted(current_ids - set(previous.keys()))
    removed = sorted(set(previous.keys()) - current_ids)
    modified = sorted(
        rid for rid in current_ids & set(previous.keys())
        if current_hashes[rid] != previous[rid]
    )
    unchanged = sorted(current_ids - set(added) - set(modified))

    df_ids = df[df[id_col].astype(str).isin(added)] if id_col in df.columns else df.iloc[0:0]
    df_mod = df[df[id_col].astype(str).isin(modified)] if id_col in df.columns else df.iloc[0:0]
    df_delta = pd.concat([df_ids, df_mod]) if not (df_ids.empty and df_mod.empty) else df.iloc[0:0]

    return {
        "has_snapshot": bool(previous),
        "added": added,
        "modified": modified,
        "removed": removed,
        "unchanged": unchanged,
        "added_df": df_ids,
        "modified_df": df_mod,
        "delta_df": df_delta,
    }
