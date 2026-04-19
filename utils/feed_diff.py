"""Compute delta between two feed snapshots.

Product identity follows a hierarchical fallback:
    1. `id` (SKU) if non-empty
    2. `gtin` (EAN-13/UPC) if valid
    3. `mpn` if non-empty
    4. hash(title + brand + price) as last resort

Returned buckets:
    added     — new product keys (need enrichment)
    removed   — disappeared keys (flag to user, possibly delete enriched)
    modified  — same key, different content hash (consider re-enrichment)
    unchanged — same key, same content
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd


# Fields that define a product's identity content.
_CONTENT_FIELDS = (
    "title", "description", "brand", "price", "sale_price",
    "product_type", "google_product_category",
    "color", "size", "material", "gender", "age_group",
    "availability", "condition", "gtin", "mpn", "link", "image_link",
)


@dataclass
class FeedDelta:
    added: list[str] = field(default_factory=list)          # product keys new to this run
    removed: list[str] = field(default_factory=list)         # product keys missing in new
    modified: list[str] = field(default_factory=list)        # product keys with changed content
    unchanged: list[str] = field(default_factory=list)
    new_rows: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    modified_rows: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    removed_rows: pd.DataFrame = field(default_factory=lambda: pd.DataFrame())
    key_map_new: dict[str, int] = field(default_factory=dict)  # key -> index in new df
    key_map_old: dict[str, int] = field(default_factory=dict)  # key -> index in old df


# ============================================================
# PRODUCT KEY (hierarchical fallback)
# ============================================================
def _clean(v) -> str:
    if v is None:
        return ""
    s = str(v).strip()
    if s.lower() in ("nan", "none", "null"):
        return ""
    return s


def product_key(row, strategy: str = "hierarchical") -> str:
    """Return a stable key for the row according to the chosen strategy.

    Strategies:
        'hierarchical' — id → gtin → mpn → hash(title+brand+price)
        'id'           — always the id field (empty if missing)
        'gtin'         — always the gtin field (empty if missing)
        'mpn'          — always the mpn field (empty if missing)
        'hash'         — always hash(title+brand+price)
    """
    get = (lambda k: _clean(row.get(k))) if isinstance(row, dict) else (lambda k: _clean(row.get(k) if hasattr(row, "get") else ""))

    if strategy == "id":
        return get("id")
    if strategy == "gtin":
        return get("gtin")
    if strategy == "mpn":
        return get("mpn")
    if strategy == "hash":
        blob = f"{get('title')}|{get('brand')}|{get('price')}".lower()
        return "h:" + hashlib.md5(blob.encode()).hexdigest()[:16]

    # hierarchical (default)
    rid = get("id")
    if rid:
        return f"id:{rid}"
    gtin = get("gtin")
    if gtin and gtin.isdigit() and len(gtin) in (8, 12, 13, 14):
        return f"gtin:{gtin}"
    mpn = get("mpn")
    if mpn:
        return f"mpn:{mpn}"
    blob = f"{get('title')}|{get('brand')}|{get('price')}".lower()
    return "h:" + hashlib.md5(blob.encode()).hexdigest()[:16]


def _content_hash(row) -> str:
    get = (lambda k: _clean(row.get(k))) if isinstance(row, dict) else (lambda k: _clean(row.get(k) if hasattr(row, "get") else ""))
    payload = "|".join(get(k) for k in _CONTENT_FIELDS)
    return hashlib.md5(payload.encode()).hexdigest()[:16]


# ============================================================
# DELTA COMPUTATION
# ============================================================
def compute_delta(
    old_df: pd.DataFrame | None,
    new_df: pd.DataFrame,
    strategy: str = "hierarchical",
) -> FeedDelta:
    """Compute the diff new_df vs old_df.

    If old_df is None → everything is 'added'.
    """
    d = FeedDelta()

    # Index new_df
    new_keys: dict[str, tuple[int, str]] = {}  # key -> (row_idx, content_hash)
    for idx, row in new_df.iterrows():
        key = product_key(row.to_dict(), strategy=strategy)
        if not key or key == "h:":
            continue
        new_keys[key] = (idx, _content_hash(row.to_dict()))
        d.key_map_new[key] = idx

    # Empty old → everything added
    if old_df is None or old_df.empty:
        d.added = list(new_keys.keys())
        d.new_rows = new_df.loc[[new_keys[k][0] for k in d.added if new_keys[k][0] in new_df.index]].copy()
        return d

    # Index old_df
    old_keys: dict[str, tuple[int, str]] = {}
    for idx, row in old_df.iterrows():
        key = product_key(row.to_dict(), strategy=strategy)
        if not key or key == "h:":
            continue
        old_keys[key] = (idx, _content_hash(row.to_dict()))
        d.key_map_old[key] = idx

    new_key_set = set(new_keys.keys())
    old_key_set = set(old_keys.keys())

    d.added = sorted(new_key_set - old_key_set)
    d.removed = sorted(old_key_set - new_key_set)

    for k in new_key_set & old_key_set:
        if new_keys[k][1] != old_keys[k][1]:
            d.modified.append(k)
        else:
            d.unchanged.append(k)
    d.modified.sort()
    d.unchanged.sort()

    # Subset dataframes for UI display
    if d.added:
        added_idx = [new_keys[k][0] for k in d.added if new_keys[k][0] in new_df.index]
        d.new_rows = new_df.loc[added_idx].copy()
        d.new_rows["_product_key"] = [k for k in d.added if new_keys[k][0] in new_df.index]

    if d.modified:
        mod_idx = [new_keys[k][0] for k in d.modified if new_keys[k][0] in new_df.index]
        d.modified_rows = new_df.loc[mod_idx].copy()
        d.modified_rows["_product_key"] = [k for k in d.modified if new_keys[k][0] in new_df.index]

    if d.removed:
        rem_idx = [old_keys[k][0] for k in d.removed if old_keys[k][0] in old_df.index]
        d.removed_rows = old_df.loc[rem_idx].copy()
        d.removed_rows["_product_key"] = [k for k in d.removed if old_keys[k][0] in old_df.index]

    return d


def delta_summary(delta: FeedDelta) -> dict:
    return {
        "added": len(delta.added),
        "removed": len(delta.removed),
        "modified": len(delta.modified),
        "unchanged": len(delta.unchanged),
    }
