"""Validation helpers: GTIN checksum, duplicate detection, image dimension checks.

Used by the Catalog Optimizer to surface data-quality warnings before export.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd
import requests


# ============================================================
# GTIN (EAN-13 / UPC-A / GTIN-14) validation
# ============================================================
def is_valid_gtin(value: str | int | float | None) -> bool:
    """Validate GTIN-8/12/13/14 via mod-10 check digit."""
    if value is None:
        return False
    s = str(value).strip()
    if not s or not s.isdigit():
        return False
    if len(s) not in (8, 12, 13, 14):
        return False
    digits = [int(c) for c in s]
    check = digits.pop()
    # Weights alternate 3,1 from rightmost remaining digit
    total = 0
    for i, d in enumerate(reversed(digits)):
        total += d * (3 if i % 2 == 0 else 1)
    expected = (10 - (total % 10)) % 10
    return expected == check


def validate_gtins(df: pd.DataFrame, col: str = "gtin") -> dict:
    """Return summary of GTIN validation.

    Keys: total, with_gtin, valid, invalid, missing
    """
    if col not in df.columns:
        return {"total": len(df), "with_gtin": 0, "valid": 0, "invalid": 0, "missing": len(df)}
    series = df[col].astype(str).str.strip().replace({"nan": "", "None": ""})
    with_gtin = series.ne("").sum()
    missing = int(len(series) - with_gtin)
    valid = int(series[series.ne("")].apply(is_valid_gtin).sum())
    invalid = int(with_gtin - valid)
    return {
        "total": int(len(df)),
        "with_gtin": int(with_gtin),
        "valid": valid,
        "invalid": invalid,
        "missing": missing,
    }


# ============================================================
# Duplicate detection
# ============================================================
def find_duplicates(df: pd.DataFrame, cols: Iterable[str] = ("title", "description")) -> pd.DataFrame:
    """Return rows whose `cols` values collide with another row in the dataframe.

    Adds a `_dup_group` column (hash of combined values) to make grouping obvious.
    """
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return df.iloc[0:0]
    work = df[cols].fillna("").astype(str).agg(" ".join, axis=1).str.strip().str.lower()
    mask = work.duplicated(keep=False) & work.ne("")
    out = df.loc[mask].copy()
    if not out.empty:
        out["_dup_group"] = work.loc[mask].map(lambda s: hashlib.md5(s.encode()).hexdigest()[:8])
    return out


# ============================================================
# Image dimension check (HEAD request — fast, no download)
# ============================================================
MIN_IMAGE_SIZE = 800  # Google Merchant Center recommends 800x800+


@dataclass
class ImageIssue:
    url: str
    reason: str
    width: int | None = None
    height: int | None = None


def _check_one_image(url: str, timeout: float = 3.0) -> ImageIssue | None:
    """HEAD-request + small GET to read image dimensions. Returns issue or None."""
    if not url or not isinstance(url, str) or not url.startswith(("http://", "https://")):
        return ImageIssue(url=url or "", reason="missing_or_invalid_url")
    try:
        # Quick HEAD for status + content-length
        h = requests.head(url, timeout=timeout, allow_redirects=True)
        if h.status_code >= 400:
            return ImageIssue(url=url, reason=f"http_{h.status_code}")
        ctype = (h.headers.get("content-type") or "").lower()
        if "image" not in ctype and "octet" not in ctype:
            return ImageIssue(url=url, reason=f"not_image_{ctype or 'unknown'}")
        # Fetch first 32KB to parse dimensions (most image headers fit in <32KB)
        r = requests.get(url, timeout=timeout, stream=True)
        chunk = r.raw.read(32 * 1024)
        r.close()
        try:
            from PIL import Image
            import io
            img = Image.open(io.BytesIO(chunk))
            w, hgt = img.size
            if w < MIN_IMAGE_SIZE or hgt < MIN_IMAGE_SIZE:
                return ImageIssue(url=url, reason="too_small", width=w, height=hgt)
        except Exception:
            # PIL not available or unparseable header — skip dimension check
            return None
        return None
    except requests.RequestException as e:
        return ImageIssue(url=url, reason=f"request_error:{type(e).__name__}")


def validate_images(urls: Iterable[str], max_workers: int = 20, limit: int | None = 200) -> list[ImageIssue]:
    """Parallel image checks. `limit` caps how many we actually hit (to avoid slowdowns).

    Returns list of ImageIssue instances (only problematic URLs).
    """
    urls_list = [u for u in urls if isinstance(u, str)]
    if limit:
        urls_list = urls_list[:limit]
    issues: list[ImageIssue] = []
    if not urls_list:
        return issues
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
        for res in ex.map(_check_one_image, urls_list):
            if res is not None:
                issues.append(res)
    return issues


# ============================================================
# Aggregate quality summary — cheap, no network
# ============================================================
@dataclass
class QualitySummary:
    total_rows: int = 0
    gtin: dict = field(default_factory=dict)
    duplicates: int = 0
    missing_images: int = 0
    short_titles: int = 0
    short_descriptions: int = 0


def quality_summary(df: pd.DataFrame) -> QualitySummary:
    s = QualitySummary(total_rows=int(len(df)))
    s.gtin = validate_gtins(df, "gtin")
    try:
        s.duplicates = int(len(find_duplicates(df, ("title", "description"))))
    except Exception:
        s.duplicates = 0
    if "image_link" in df.columns:
        s.missing_images = int(df["image_link"].isna().sum() + df["image_link"].astype(str).str.strip().eq("").sum())
    if "title" in df.columns:
        s.short_titles = int((df["title"].astype(str).str.len() < 30).sum())
    if "description" in df.columns:
        s.short_descriptions = int((df["description"].astype(str).str.len() < 80).sum())
    return s
