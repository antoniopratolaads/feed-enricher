"""Client & feed management — multi-tenant storage.

Data model:
    Cliente (nome libero) → N Feed (ognuno col suo storico snapshot)

Storage layout (~/.feed_enricher/clients/):
    <client_slug>/
        client.json                 # {name, created_at, notes}
        feeds/
            <feed_slug>/
                feed.json           # {name, source_url, source_type, last_sync, id_strategy}
                snapshots/
                    <YYYY-MM-DD_HHMMSS>.parquet
                pending.jsonl       # queue of product-keys awaiting enrichment
                history.jsonl       # events: sync, diff, enrichment
                enriched.parquet    # cumulative enriched dataframe (grows over time)
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd

_LOCK = threading.Lock()
BASE_DIR = Path.home() / ".feed_enricher" / "clients"
BASE_DIR.mkdir(parents=True, exist_ok=True)

# Colonna chiave di prodotto usata per merge/upsert per identità (non per
# indice pandas, che non è stabile dopo reload parquet).
_PRODUCT_KEY_COL = "_product_key"


# ============================================================
# UTILITIES
# ============================================================
def _slugify(text: str) -> str:
    s = re.sub(r"[^\w\s-]", "", text.strip().lower())
    s = re.sub(r"[\s_-]+", "-", s)
    return s.strip("-")[:60] or "client"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def _client_dir(client_slug: str) -> Path:
    d = BASE_DIR / client_slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def _feed_dir(client_slug: str, feed_slug: str) -> Path:
    d = _client_dir(client_slug) / "feeds" / feed_slug
    d.mkdir(parents=True, exist_ok=True)
    (d / "snapshots").mkdir(exist_ok=True)
    return d


# ============================================================
# CLIENTS — CRUD
# ============================================================
def list_clients() -> list[dict]:
    """Return all client metadata sorted by last-used."""
    out: list[dict] = []
    if not BASE_DIR.exists():
        return out
    for child in BASE_DIR.iterdir():
        if not child.is_dir():
            continue
        meta_path = child / "client.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        meta["slug"] = child.name
        meta["n_feeds"] = len(list((child / "feeds").glob("*"))) if (child / "feeds").exists() else 0
        out.append(meta)
    out.sort(key=lambda m: m.get("last_used_at") or m.get("created_at") or "", reverse=True)
    return out


def get_client(client_slug: str) -> dict | None:
    meta_path = _client_dir(client_slug) / "client.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["slug"] = client_slug
        return meta
    except (OSError, json.JSONDecodeError):
        return None


def create_client(name: str, notes: str = "") -> str:
    slug = _slugify(name)
    if not slug:
        raise ValueError("Nome cliente non valido")
    with _LOCK:
        d = _client_dir(slug)
        meta = {
            "name": name.strip(),
            "notes": notes.strip(),
            "created_at": _now(),
            "last_used_at": _now(),
        }
        # Se esiste già: errore (non sovrascrivere)
        if (d / "client.json").exists():
            raise FileExistsError(f"Cliente '{slug}' esiste già")
        (d / "client.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    return slug


def update_client(client_slug: str, **fields) -> None:
    path = _client_dir(client_slug) / "client.json"
    if not path.exists():
        raise FileNotFoundError(client_slug)
    with _LOCK:
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta.update(fields)
        meta["last_used_at"] = _now()
        path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def delete_client(client_slug: str) -> None:
    d = _client_dir(client_slug)
    with _LOCK:
        if d.exists():
            shutil.rmtree(d)


def touch_client(client_slug: str) -> None:
    try:
        update_client(client_slug, last_used_at=_now())
    except FileNotFoundError:
        pass


# ============================================================
# FEEDS — CRUD
# ============================================================
def list_feeds(client_slug: str) -> list[dict]:
    feeds_dir = _client_dir(client_slug) / "feeds"
    if not feeds_dir.exists():
        return []
    out: list[dict] = []
    for child in feeds_dir.iterdir():
        if not child.is_dir():
            continue
        meta_path = child / "feed.json"
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            meta["slug"] = child.name
            # Enrichment stats
            meta["n_snapshots"] = len(list((child / "snapshots").glob("*.parquet")))
            meta["n_pending"] = _count_pending(client_slug, child.name)
            out.append(meta)
        except (OSError, json.JSONDecodeError):
            continue
    out.sort(key=lambda m: m.get("last_sync_at") or "", reverse=True)
    return out


def get_feed(client_slug: str, feed_slug: str) -> dict | None:
    path = _feed_dir(client_slug, feed_slug) / "feed.json"
    if not path.exists():
        return None
    try:
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta["slug"] = feed_slug
        return meta
    except (OSError, json.JSONDecodeError):
        return None


def create_feed(
    client_slug: str,
    name: str,
    source_url: str = "",
    source_type: str = "url",
    id_strategy: str = "hierarchical",
    notes: str = "",
    sector: str = "",
) -> str:
    """Create a new feed under a client.

    Args:
        source_type: 'url' | 'upload' | 'shopify' | 'custom'
        id_strategy: 'hierarchical' (id → gtin → mpn → hash) | 'id' | 'gtin' | 'mpn'
        sector: settore best-practice ereditato in enrichment ("" = generico,
            "auto" = detect per-prodotto, oppure uno slug di list_sectors()).
    """
    if not get_client(client_slug):
        raise FileNotFoundError(f"Cliente '{client_slug}' non esiste")
    feed_slug = _slugify(name)
    if not feed_slug:
        raise ValueError("Nome feed non valido")
    with _LOCK:
        d = _feed_dir(client_slug, feed_slug)
        path = d / "feed.json"
        if path.exists():
            raise FileExistsError(f"Feed '{feed_slug}' esiste già per {client_slug}")
        meta = {
            "name": name.strip(),
            "source_url": source_url.strip(),
            "source_type": source_type,
            "id_strategy": id_strategy,
            "sector": (sector or "").strip(),
            "notes": notes.strip(),
            "created_at": _now(),
            "last_sync_at": None,
            "last_snapshot": None,
            "total_products_ever": 0,
        }
        path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    touch_client(client_slug)
    return feed_slug


def update_feed(client_slug: str, feed_slug: str, **fields) -> None:
    """Aggiorna i campi del feed.json (es. source_url, sector, id_strategy)."""
    path = _feed_dir(client_slug, feed_slug) / "feed.json"
    if not path.exists():
        raise FileNotFoundError(feed_slug)
    with _LOCK:
        meta = json.loads(path.read_text(encoding="utf-8"))
        meta.update(fields)
        path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")


def delete_feed(client_slug: str, feed_slug: str) -> None:
    d = _feed_dir(client_slug, feed_slug)
    with _LOCK:
        if d.exists():
            shutil.rmtree(d)


# ============================================================
# SNAPSHOTS — store full feed dataframe per sync
# ============================================================
def save_snapshot(client_slug: str, feed_slug: str, df: pd.DataFrame) -> Path:
    """Persist the current feed as a parquet snapshot. Returns path."""
    d = _feed_dir(client_slug, feed_slug)
    stamp = _stamp()
    path = d / "snapshots" / f"{stamp}.parquet"
    # Normalize: everything as string to avoid serialization issues
    save_df = df.copy()
    for c in save_df.columns:
        try:
            save_df[c] = save_df[c].astype("string")
        except (ValueError, TypeError):
            save_df[c] = save_df[c].astype(str)
    with _LOCK:
        save_df.to_parquet(path, index=False)
    update_feed(
        client_slug, feed_slug,
        last_sync_at=_now(),
        last_snapshot=path.name,
    )
    log_event(client_slug, feed_slug, "snapshot_saved",
              {"path": path.name, "n_rows": int(len(df))})
    touch_client(client_slug)
    return path


def list_snapshots(client_slug: str, feed_slug: str) -> list[Path]:
    d = _feed_dir(client_slug, feed_slug) / "snapshots"
    if not d.exists():
        return []
    return sorted(d.glob("*.parquet"), reverse=True)


def load_snapshot(path: Path) -> pd.DataFrame:
    return pd.read_parquet(path)


def get_latest_snapshot(client_slug: str, feed_slug: str) -> pd.DataFrame | None:
    snaps = list_snapshots(client_slug, feed_slug)
    if not snaps:
        return None
    return load_snapshot(snaps[0])


def get_previous_snapshot(client_slug: str, feed_slug: str) -> pd.DataFrame | None:
    """Return the second-most-recent snapshot (for diff)."""
    snaps = list_snapshots(client_slug, feed_slug)
    if len(snaps) < 2:
        return None
    return load_snapshot(snaps[1])


def prune_snapshots(client_slug: str, feed_slug: str, keep_last_n: int = 20) -> int:
    """Keep only the `keep_last_n` most recent snapshots. Returns count deleted."""
    snaps = list_snapshots(client_slug, feed_slug)
    if len(snaps) <= keep_last_n:
        return 0
    to_delete = snaps[keep_last_n:]
    with _LOCK:
        for p in to_delete:
            try:
                p.unlink()
            except OSError:
                pass
    return len(to_delete)


# ============================================================
# PENDING ENRICHMENT QUEUE
# ============================================================
def add_pending(client_slug: str, feed_slug: str, product_keys: Iterable[str],
                reason: str = "new") -> int:
    """Append product keys that await enrichment.

    `reason`: 'new' | 'modified' | 'manual'
    Returns number appended.
    """
    d = _feed_dir(client_slug, feed_slug)
    path = d / "pending.jsonl"
    count = 0
    with _LOCK:
        with path.open("a", encoding="utf-8") as f:
            for key in product_keys:
                if not key:
                    continue
                f.write(json.dumps({
                    "key": key,
                    "reason": reason,
                    "added_at": _now(),
                }, ensure_ascii=False) + "\n")
                count += 1
    return count


def get_pending(client_slug: str, feed_slug: str) -> list[dict]:
    """Return dedup pending entries (last occurrence wins per key)."""
    d = _feed_dir(client_slug, feed_slug)
    path = d / "pending.jsonl"
    if not path.exists():
        return []
    by_key: dict[str, dict] = {}
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    by_key[e["key"]] = e
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        return []
    return list(by_key.values())


def remove_pending(client_slug: str, feed_slug: str, product_keys: Iterable[str]) -> int:
    """Remove given keys from pending queue (rewrites file)."""
    d = _feed_dir(client_slug, feed_slug)
    path = d / "pending.jsonl"
    if not path.exists():
        return 0
    remove_set = set(product_keys)
    entries = get_pending(client_slug, feed_slug)
    kept = [e for e in entries if e["key"] not in remove_set]
    removed = len(entries) - len(kept)
    with _LOCK:
        with path.open("w", encoding="utf-8") as f:
            for e in kept:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return removed


def _count_pending(client_slug: str, feed_slug: str) -> int:
    return len(get_pending(client_slug, feed_slug))


# ============================================================
# ENRICHED PERSISTENCE (cumulative)
# ============================================================
def save_enriched(client_slug: str, feed_slug: str, df: pd.DataFrame) -> Path:
    """Persist the cumulative enriched dataframe (overwrites).

    Scrittura ATOMICA (P2.2): to_parquet su file .tmp poi rename, così un
    crash a metà scrittura non lascia un enriched.parquet corrotto.
    """
    d = _feed_dir(client_slug, feed_slug)
    path = d / "enriched.parquet"
    tmp = d / "enriched.parquet.tmp"
    save_df = df.copy()
    for c in save_df.columns:
        try:
            save_df[c] = save_df[c].astype("string")
        except (ValueError, TypeError):
            save_df[c] = save_df[c].astype(str)
    with _LOCK:
        save_df.to_parquet(tmp, index=False)
        tmp.replace(path)  # rename atomico (sovrascrive il vecchio)
    return path


def load_enriched(client_slug: str, feed_slug: str) -> pd.DataFrame | None:
    path = _feed_dir(client_slug, feed_slug) / "enriched.parquet"
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except OSError:
        return None


# ============================================================
# MERGE / OVERLAY PER PRODUCT-KEY (verità: snapshot ↔ enriched)
# ============================================================
def _ensure_product_key(df: pd.DataFrame, strategy: str = "hierarchical") -> pd.DataFrame:
    """Garantisce la colonna _product_key calcolata con feed_diff.product_key.

    Scarta (key vuota) righe con identità non determinabile (key vuota o "h:"
    puro): sopravvivono nel df ma con key vuota, e i caller le filtrano prima
    dell'upsert. Funziona anche su parquet legacy senza _product_key.
    """
    from utils import feed_diff as _fd
    out = df.copy()
    keys = []
    for _, row in out.iterrows():
        k = _fd.product_key(row.to_dict(), strategy=strategy)
        if not k or k == "h:":
            k = ""
        keys.append(k)
    out[_PRODUCT_KEY_COL] = keys
    return out


def merge_enriched(client_slug: str, feed_slug: str, enriched_subset: pd.DataFrame,
                   strategy: str = "hierarchical") -> pd.DataFrame:
    """UPSERT del subset arricchito sulla base cumulativa, per _product_key.

    Risolve P0.1 + P0.3: non sovrascrive enriched.parquet col solo subset
    (perdendo gli altri prodotti) e non fa il merge per indice pandas (che si
    rompe al reload parquet). Usa _product_key come identità stabile.

    Flusso:
        1. base = enriched.parquet esistente, altrimenti latest snapshot.
        2. _product_key garantita su base e subset (strategy del feed).
        3. UPSERT per key: aggiorna colonne esistenti, aggiunge colonne nuove,
           inserisce righe di subset non presenti nella base.
        4. salva con save_enriched (atomico) e ritorna il df mergeato completo.
    """
    with _LOCK:
        base = load_enriched(client_slug, feed_slug)
        if base is None or base.empty:
            base = get_latest_snapshot(client_slug, feed_slug)
        if base is None:
            base = pd.DataFrame()

    if not base.empty:
        base = _ensure_product_key(base, strategy)
    else:
        base = pd.DataFrame(columns=[_PRODUCT_KEY_COL])

    sub = _ensure_product_key(enriched_subset, strategy)
    # scarta righe del subset senza identità: niente upsert sicuro
    sub = sub[sub[_PRODUCT_KEY_COL].astype(str).str.len() > 0]

    base = base.reset_index(drop=True)
    key_to_pos: dict[str, int] = {}
    base_keys = base[_PRODUCT_KEY_COL].astype(str).tolist() if _PRODUCT_KEY_COL in base.columns else []
    for pos, k in enumerate(base_keys):
        if k:
            key_to_pos[k] = pos  # ultima occorrenza vince (robusto a dup legacy)

    new_rows = []
    for _, srow in sub.iterrows():
        key = str(srow[_PRODUCT_KEY_COL])
        pos = key_to_pos.get(key)
        if pos is None:
            new_rows.append(srow)  # prodotto non in base → riga nuova (append)
            continue
        for col, val in srow.items():  # upsert: aggiorna/aggiungi colonne
            if col not in base.columns:
                base[col] = ""
            base.iat[pos, base.columns.get_loc(col)] = val

    if new_rows:
        new_df = pd.DataFrame(new_rows)
        for col in new_df.columns:
            if col not in base.columns:
                base[col] = ""
        base = pd.concat([base, new_df], ignore_index=True)

    base = base.reset_index(drop=True)
    save_enriched(client_slug, feed_slug, base)
    return base


def load_feed_merged(client_slug: str, feed_slug: str,
                     strategy: str = "hierarchical") -> tuple[pd.DataFrame | None, str]:
    """Carica il feed con overlay enriched→snapshot per _product_key (P0.2).

    base = latest snapshot (verità corrente dei prodotti). Se esiste
    enriched.parquet, sovrascrive sulla base — SOLO per le righe che matchano
    per _product_key — le colonne arricchite + _enrichment_status.

        * prodotti nello snapshot ma non in enriched → restano con
          _enrichment_status vuoto (sono i "nuovi").
        * prodotti in enriched ma non nello snapshot → NON inclusi (rimossi).

    Se non c'è snapshot, fallback all'enriched puro. Ritorna (df, source).
    """
    snap = get_latest_snapshot(client_slug, feed_slug)
    enr = load_enriched(client_slug, feed_slug)

    if snap is None or snap.empty:
        if enr is not None and not enr.empty:
            return enr, "enriched"
        return None, ""

    base = _ensure_product_key(snap, strategy)
    if "_enrichment_status" not in base.columns:
        base["_enrichment_status"] = ""

    if enr is None or enr.empty:
        return base.reset_index(drop=True), "snapshot"

    enr = _ensure_product_key(enr, strategy)
    # colonne arricchite = quelle in enriched non presenti nella base snapshot
    # PIÙ title/description (riscritte) e _enrichment_status.
    base_cols = set(base.columns) - {_PRODUCT_KEY_COL}
    overlay_cols = [c for c in enr.columns
                    if c != _PRODUCT_KEY_COL and (c not in base_cols
                       or c in ("title", "description", "_enrichment_status"))]

    base = base.reset_index(drop=True)
    enr_by_key: dict[str, pd.Series] = {}
    for _, erow in enr.iterrows():
        k = str(erow[_PRODUCT_KEY_COL])
        if k:
            enr_by_key[k] = erow

    base_keys = base[_PRODUCT_KEY_COL].astype(str).tolist()
    for pos, key in enumerate(base_keys):
        erow = enr_by_key.get(key)
        if erow is None:
            continue
        for col in overlay_cols:
            if col not in base.columns:
                base[col] = ""
            val = erow.get(col)
            if val is not None and str(val).strip().lower() not in ("", "nan", "none"):
                base.iat[pos, base.columns.get_loc(col)] = val

    return base.reset_index(drop=True), "merged"


# ============================================================
# EVENT LOG
# ============================================================
def log_event(client_slug: str, feed_slug: str, kind: str, payload: dict | None = None) -> None:
    d = _feed_dir(client_slug, feed_slug)
    entry = {"ts": _now(), "kind": kind, "payload": payload or {}}
    with _LOCK:
        with (d / "history.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_events(client_slug: str, feed_slug: str, limit: int = 100) -> list[dict]:
    d = _feed_dir(client_slug, feed_slug)
    path = d / "history.jsonl"
    if not path.exists():
        return []
    out: list[dict] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return list(reversed(out))[:limit]
