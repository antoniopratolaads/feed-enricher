"""Enrichment cache: hash(product_input) → stored AI output.

Skips re-enrichment for products unchanged since the last run. Cache is JSONL
keyed by a stable md5 of relevant input fields + model/provider/sector tag.

Typical hit rate after the first run: 70-95% on update pushes.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

_LOCK = threading.Lock()
_CACHE_DIR = Path.home() / ".feed_enricher" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


# Fields that, when unchanged, let us reuse a previous enrichment result.
# Order-insensitive but content-sensitive.
RELEVANT_INPUT_FIELDS = (
    "id", "title", "description", "brand", "product_type",
    "google_product_category", "price", "gtin", "mpn", "color", "size", "material",
)


def _hash_row(row: dict, *, model: str, sector: str, provider: str) -> str:
    """Hash stabile sul contenuto ORIGINALE quando disponibile.

    Se title_original / description_original esistono (set al primo
    enrichment come backup), usali per calcolare hash. Così re-run dello
    stesso prodotto già arricchito hitta la cache invece di pagare di nuovo.
    """
    payload = {}
    for k in RELEVANT_INPUT_FIELDS:
        if k == "title":
            v = row.get("title_original") or row.get("title", "")
        elif k == "description":
            v = row.get("description_original") or row.get("description", "")
        else:
            v = row.get(k, "")
        payload[k] = str(v or "").strip()
    payload["_meta"] = f"{provider}|{model}|{sector}"
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.md5(blob).hexdigest()


def _cache_file(namespace: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in namespace)[:64] or "default"
    return _CACHE_DIR / f"{safe}.jsonl"


def _load_cache(namespace: str) -> dict[str, dict]:
    """Load cache file → {hash: entry_dict}. Last write wins on dup keys."""
    path = _cache_file(namespace)
    if not path.exists():
        return {}
    out: dict[str, dict] = {}
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    out[e["hash"]] = e
                except (json.JSONDecodeError, KeyError):
                    continue
    except OSError:
        return {}
    return out


def _append_cache(namespace: str, entry: dict) -> None:
    path = _cache_file(namespace)
    with _LOCK:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def get_cached(rows: pd.DataFrame, *, namespace: str = "default",
               model: str = "", sector: str = "", provider: str = "") -> tuple[dict[int, dict], list[int]]:
    """Inspect which rows are already cached.

    Returns (cached_results, missing_indices):
        cached_results: {row_index: enrichment_dict}
        missing_indices: list of row indices that still need enrichment
    """
    cache = _load_cache(namespace)
    cached: dict[int, dict] = {}
    missing: list[int] = []
    for idx, row in rows.iterrows():
        h = _hash_row(row.to_dict(), model=model, sector=sector, provider=provider)
        if h in cache:
            cached[idx] = cache[h]["result"]
        else:
            missing.append(idx)
    return cached, missing


def store(rows_with_results: Iterable[tuple[dict, dict]], *, namespace: str = "default",
          model: str = "", sector: str = "", provider: str = "") -> int:
    """Persist enrichment results. Returns number of entries written.

    Args:
        rows_with_results: iterable of (input_row_dict, result_dict) tuples
    """
    count = 0
    for row, result in rows_with_results:
        if not result:
            continue
        h = _hash_row(row, model=model, sector=sector, provider=provider)
        entry = {
            "hash": h,
            "result": result,
            "model": model,
            "sector": sector,
            "provider": provider,
        }
        _append_cache(namespace, entry)
        count += 1
    return count


def clear(namespace: str = "default") -> None:
    """Delete cache file for a namespace."""
    path = _cache_file(namespace)
    with _LOCK:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def stats(namespace: str = "default") -> dict:
    """Return cache stats: entry count + file size."""
    path = _cache_file(namespace)
    if not path.exists():
        return {"entries": 0, "size_bytes": 0, "path": str(path)}
    cache = _load_cache(namespace)
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return {"entries": len(cache), "size_bytes": size, "path": str(path)}
