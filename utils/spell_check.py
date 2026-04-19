"""Italian spell-check for enriched titles/descriptions.

Uses pyspellchecker (pure-Python, ~1MB IT dictionary). Lightweight, no
external services. Flags words not found in the dictionary so the operator
can audit likely AI-hallucinated terms before exporting to GMC/Meta.

Import is deferred so missing dictionaries don't break the app.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

import pandas as pd


@dataclass
class SpellIssue:
    row_idx: int
    column: str
    word: str
    suggestion: str | None = None


# Words we never flag — brand names, common units, SKUs, e-commerce jargon
_SAFE_TOKENS = {
    "pro", "plus", "max", "mini", "ultra", "eco", "premium", "light",
    "gb", "mb", "tb", "kb", "ml", "cl", "kg", "mg", "ah", "mah", "w", "v",
    "cm", "mm", "lcd", "led", "oled", "hd", "fhd", "usb", "hdmi", "ssd", "hdd",
    "ios", "xl", "xxl", "xs", "s", "m", "l",
    "streetwear", "unisex", "vintage", "outdoor", "waterproof",
}


def _get_checker():
    """Lazy-init pyspellchecker (Italian). Returns None if unavailable."""
    try:
        from spellchecker import SpellChecker
    except ImportError:
        return None
    try:
        return SpellChecker(language="it")
    except Exception:
        # Try EN as a fallback — better than nothing
        try:
            return SpellChecker(language="en")
        except Exception:
            return None


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-ZàèéìòùÀÈÉÌÒÙ]{3,}", text or "")


def check_text(text: str, checker=None) -> list[tuple[str, str | None]]:
    """Return list of (misspelled_word, suggestion)."""
    if not text:
        return []
    sp = checker or _get_checker()
    if sp is None:
        return []
    words = _tokenize(text)
    candidates = [w for w in words if w.lower() not in _SAFE_TOKENS]
    unknown = sp.unknown(candidates)
    out: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for w in candidates:
        wl = w.lower()
        if wl not in unknown or wl in seen:
            continue
        seen.add(wl)
        sug = sp.correction(wl)
        if sug == wl:  # no better suggestion found
            sug = None
        out.append((w, sug))
    return out


def check_dataframe(
    df: pd.DataFrame,
    cols: Iterable[str] = ("title", "description"),
    limit: int | None = 500,
) -> list[SpellIssue]:
    """Spell-check up to `limit` rows across the given columns."""
    sp = _get_checker()
    if sp is None:
        return []
    cols = [c for c in cols if c in df.columns]
    if not cols:
        return []
    issues: list[SpellIssue] = []
    view = df.head(limit) if limit else df
    for idx, row in view.iterrows():
        for c in cols:
            for word, sug in check_text(str(row[c]), sp):
                issues.append(SpellIssue(row_idx=int(idx), column=c, word=word, suggestion=sug))
    return issues
