"""Sessioni: cartella per sessione + cronologia eventi su disco."""
from __future__ import annotations
import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path.home() / ".feed_enricher" / "sessions"
PROJECTS_META = Path.home() / ".feed_enricher" / "projects.json"


def _load_projects_meta() -> dict:
    if PROJECTS_META.exists():
        try:
            return json.loads(PROJECTS_META.read_text())
        except Exception:
            pass
    return {}


def _save_projects_meta(data: dict):
    PROJECTS_META.parent.mkdir(parents=True, exist_ok=True)
    PROJECTS_META.write_text(json.dumps(data, indent=2, default=str))


def set_project_name(session_id: str, name: str, description: str = ""):
    data = _load_projects_meta()
    data[session_id] = {
        "name": name.strip() or session_id,
        "description": description.strip(),
        "created": data.get(session_id, {}).get("created", datetime.now().isoformat(timespec="seconds")),
        "last_opened": datetime.now().isoformat(timespec="seconds"),
    }
    _save_projects_meta(data)

    # Mirror to SQLite index
    try:
        from . import sqlite_store
        sqlite_store.upsert_session(session_id, project_name=name.strip())
    except Exception:
        pass


def get_project_name(session_id: str) -> str:
    data = _load_projects_meta()
    return data.get(session_id, {}).get("name", session_id)


def get_project_info(session_id: str) -> dict:
    return _load_projects_meta().get(session_id, {})


def touch_project(session_id: str):
    """Aggiorna last_opened."""
    data = _load_projects_meta()
    if session_id in data:
        data[session_id]["last_opened"] = datetime.now().isoformat(timespec="seconds")
        _save_projects_meta(data)


def remove_project_meta(session_id: str):
    data = _load_projects_meta()
    if session_id in data:
        del data[session_id]
        _save_projects_meta(data)


def _session_id() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def session_dir(session_id: str) -> Path:
    p = BASE_DIR / session_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def init_session(state) -> str:
    """Crea sessione se non esiste, ritorna l'ID."""
    if "session_id" not in state or not state["session_id"]:
        sid = _session_id()
        state["session_id"] = sid
        d = session_dir(sid)
        # crea history vuota
        (d / "history.jsonl").touch()
        (d / "outputs").mkdir(exist_ok=True)
        log_event(sid, "session_started", {})
    return state["session_id"]


def log_event(session_id: str, event: str, payload: Optional[dict] = None):
    d = session_dir(session_id)
    line = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "event": event,
        "payload": payload or {},
    }
    with (d / "history.jsonl").open("a") as f:
        f.write(json.dumps(line, default=str) + "\n")

    # Mirror to SQLite index (best-effort; never blocks JSONL write)
    try:
        from . import sqlite_store
        sqlite_store.log_event(session_id, event, payload)
    except Exception:
        pass


def read_history(session_id: str) -> list[dict]:
    f = session_dir(session_id) / "history.jsonl"
    if not f.exists():
        return []
    out = []
    for line in f.read_text().splitlines():
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def list_sessions() -> list[dict]:
    if not BASE_DIR.exists():
        return []
    rows = []
    for d in sorted(BASE_DIR.iterdir(), reverse=True):
        if not d.is_dir():
            continue
        outputs = list((d / "outputs").glob("*")) if (d / "outputs").exists() else []
        history = read_history(d.name)
        rows.append({
            "id": d.name,
            "path": str(d),
            "events": len(history),
            "files": len(outputs),
            "size_kb": round(sum(f.stat().st_size for f in outputs) / 1024, 1),
            "started": history[0]["ts"] if history else "—",
            "last": history[-1]["ts"] if history else "—",
        })
    return rows


def save_output(session_id: str, filename: str, content: bytes, kind: str = "file") -> Path:
    """Salva un file generato nella cartella outputs della sessione."""
    d = session_dir(session_id) / "outputs"
    d.mkdir(exist_ok=True)
    out = d / filename
    out.write_bytes(content)
    log_event(session_id, "file_saved", {"filename": filename, "size": len(content), "kind": kind})
    return out


def list_outputs(session_id: str) -> list[Path]:
    d = session_dir(session_id) / "outputs"
    if not d.exists():
        return []
    return sorted(d.glob("*"))


def save_snapshot(session_id: str, state) -> Path:
    """Salva uno snapshot dello state (dataframe + labels) nella cartella sessione.
    Usa parquet per i df (veloce, preserva dtype)."""
    import pandas as pd
    d = session_dir(session_id) / "snapshot"
    d.mkdir(exist_ok=True)

    for key in ("feed_df", "merged_df", "enriched_df", "gads_df", "raw_df"):
        df = state.get(key)
        if df is not None and hasattr(df, "to_parquet"):
            try:
                df.to_parquet(d / f"{key}.parquet", index=False)
            except Exception:
                # fallback CSV se parquet fallisce (tipi complessi)
                df.to_csv(d / f"{key}.csv", index=False)

    # labels → JSON serializzabile
    labels = state.get("labels", {})
    if labels:
        serial = {k: v.tolist() if hasattr(v, "tolist") else list(v) for k, v in labels.items()}
        (d / "labels.json").write_text(json.dumps(serial))

    # meta info
    meta = {
        "feed_source": state.get("feed_source", ""),
        "api_key_present": bool(state.get("api_key")),
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    (d / "meta.json").write_text(json.dumps(meta, indent=2))
    log_event(session_id, "snapshot_saved", {
        "dataframes": [k for k in ("feed_df", "merged_df", "enriched_df", "gads_df")
                        if state.get(k) is not None],
        "labels_count": len(labels),
    })
    return d


def restore_snapshot(session_id: str, state) -> bool:
    """Ricarica i dataframe salvati in una sessione nello state corrente."""
    import pandas as pd
    d = session_dir(session_id) / "snapshot"
    if not d.exists():
        return False

    restored = []
    for key in ("feed_df", "merged_df", "enriched_df", "gads_df", "raw_df"):
        pq = d / f"{key}.parquet"
        csv = d / f"{key}.csv"
        if pq.exists():
            state[key] = pd.read_parquet(pq)
            restored.append(key)
        elif csv.exists():
            state[key] = pd.read_csv(csv)
            restored.append(key)

    # labels
    lbl_file = d / "labels.json"
    if lbl_file.exists():
        data = json.loads(lbl_file.read_text())
        state["labels"] = {k: pd.Series(v) for k, v in data.items()}

    # meta
    meta_file = d / "meta.json"
    if meta_file.exists():
        meta = json.loads(meta_file.read_text())
        state["feed_source"] = meta.get("feed_source", "")

    state["session_id"] = session_id
    log_event(session_id, "snapshot_restored", {"dataframes": restored})
    return len(restored) > 0


def delete_session(session_id: str) -> bool:
    d = BASE_DIR / session_id
    if d.exists():
        shutil.rmtree(d)
        remove_project_meta(session_id)
        return True
    return False


def clone_project(src_session_id: str, new_name: str) -> str:
    """Duplica un progetto (inclusi snapshot + outputs + history) con un nuovo id."""
    src = BASE_DIR / src_session_id
    if not src.exists():
        raise FileNotFoundError(src_session_id)
    new_id = _session_id()
    dst = BASE_DIR / new_id
    shutil.copytree(src, dst)
    set_project_name(new_id, new_name)
    log_event(new_id, "project_cloned", {"from": src_session_id})
    return new_id


def list_projects() -> list[dict]:
    """Lista arricchita: session data + project metadata."""
    meta = _load_projects_meta()
    sessions = list_sessions()
    for s in sessions:
        sid = s["id"]
        m = meta.get(sid, {})
        s["name"] = m.get("name", sid)
        s["description"] = m.get("description", "")
        s["created"] = m.get("created", s.get("started", ""))
        s["last_opened"] = m.get("last_opened", s.get("last", ""))
        s["is_named"] = sid in meta
    # ordina per last_opened desc
    sessions.sort(key=lambda x: x.get("last_opened", ""), reverse=True)
    return sessions


def open_in_finder(path: Path):
    """Apre la cartella nel Finder/Explorer (best-effort)."""
    import subprocess, sys
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", str(path)])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", str(path)])
    except Exception:
        pass
