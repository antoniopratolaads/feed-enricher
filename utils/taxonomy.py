"""Google Product Taxonomy autocomplete.

Loads the official Google taxonomy (~6000 categories) and provides fuzzy
matching from a free-text title. Used to seed `google_product_category`
suggestions before or in place of AI classification.

The taxonomy file is downloaded on first use to `~/.feed_enricher/cache/`
so we don't ship 500KB of text in the repo.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable

import requests

try:
    from rapidfuzz import fuzz, process
except ImportError:  # pragma: no cover
    fuzz = None
    process = None


TAXONOMY_URL_IT = "https://www.google.com/basepages/producttype/taxonomy-with-ids.it-IT.txt"
TAXONOMY_URL_EN = "https://www.google.com/basepages/producttype/taxonomy-with-ids.en-US.txt"

_CACHE_DIR = Path.home() / ".feed_enricher" / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

_TAXONOMY_CACHE: list[tuple[int, str]] | None = None


def _cache_path(lang: str) -> Path:
    return _CACHE_DIR / f"google_taxonomy.{lang}.txt"


def _download_taxonomy(lang: str = "it-IT") -> Path:
    """Fetch the taxonomy file once; subsequent calls read from cache."""
    url = TAXONOMY_URL_IT if lang.startswith("it") else TAXONOMY_URL_EN
    dst = _cache_path(lang)
    if dst.exists() and dst.stat().st_size > 0:
        return dst
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        dst.write_text(r.text, encoding="utf-8")
    except requests.RequestException:
        # If network fails, write a stub so we don't retry on every call.
        dst.write_text("", encoding="utf-8")
    return dst


def load_taxonomy(lang: str = "it-IT") -> list[tuple[int, str]]:
    """Return the cached taxonomy as [(id, path), ...]. First line is header."""
    global _TAXONOMY_CACHE
    if _TAXONOMY_CACHE is not None:
        return _TAXONOMY_CACHE
    path = _download_taxonomy(lang)
    entries: list[tuple[int, str]] = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(" - ", 1)
                if len(parts) != 2:
                    continue
                try:
                    cat_id = int(parts[0].strip())
                except ValueError:
                    continue
                entries.append((cat_id, parts[1].strip()))
    except OSError:
        pass
    _TAXONOMY_CACHE = entries
    return entries


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-ZàèéìòùÀÈÉÌÒÙ]+", (text or "").lower()))


def suggest_category(title: str, brand: str = "", limit: int = 5,
                     lang: str = "it-IT") -> list[dict]:
    """Return top-`limit` candidate taxonomy matches for the given title.

    Uses rapidfuzz token_set_ratio if available, otherwise falls back to
    a simple token-overlap score.

    Returns: [{id, path, score}, ...]
    """
    entries = load_taxonomy(lang)
    if not entries:
        return []
    query = f"{title} {brand}".strip().lower()
    if not query:
        return []

    if process is not None:
        # rapidfuzz processes in C, very fast even on 6000 entries
        paths = [p for _, p in entries]
        matches = process.extract(
            query, paths,
            scorer=fuzz.token_set_ratio,
            limit=limit,
        )
        id_by_path = {p: cid for cid, p in entries}
        return [
            {"id": id_by_path.get(m[0]), "path": m[0], "score": int(m[1])}
            for m in matches
            if m[1] >= 40
        ]

    # Fallback — basic token overlap
    q_tokens = _tokenize(query)
    scored: list[tuple[int, int, str]] = []
    for cat_id, path in entries:
        p_tokens = _tokenize(path)
        if not p_tokens:
            continue
        overlap = len(q_tokens & p_tokens)
        if overlap == 0:
            continue
        score = int(100 * overlap / max(len(q_tokens | p_tokens), 1))
        scored.append((score, cat_id, path))
    scored.sort(reverse=True)
    return [
        {"id": cid, "path": p, "score": s}
        for s, cid, p in scored[:limit]
    ]


def suggest_bulk(titles: Iterable[str], brands: Iterable[str] | None = None,
                 lang: str = "it-IT") -> list[dict | None]:
    """Suggest the top match for each (title, brand) pair. None = no match."""
    brands = list(brands) if brands else [""] * len(list(titles))
    out: list[dict | None] = []
    for i, t in enumerate(titles):
        b = brands[i] if i < len(brands) else ""
        matches = suggest_category(t, brand=b, limit=1, lang=lang)
        out.append(matches[0] if matches else None)
    return out
