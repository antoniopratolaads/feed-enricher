"""Export feed supplementari in Excel / CSV / XML GMC."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

import pandas as pd


def _safe_max_len(series: pd.Series) -> int:
    """Return max string length in series, robust to NA/None/float NaN.

    Handles pandas nullable string dtype which preserves pd.NA after astype(str)."""
    try:
        # Fill NA then cast via pure Python str() which always returns a string
        return int(series.fillna("").apply(lambda x: len(str(x))).max())
    except (ValueError, TypeError):
        return 10


def to_excel_bytes(dfs: dict[str, pd.DataFrame]) -> bytes:
    """Genera xlsx multi-foglio."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        for name, df in dfs.items():
            safe = name[:31]
            df.to_excel(w, sheet_name=safe, index=False)
            ws = w.sheets[safe]
            for i, col in enumerate(df.columns):
                if len(df) == 0:
                    content_width = 10
                else:
                    content_width = _safe_max_len(df[col])
                width = min(max(len(str(col)), content_width), 50)
                ws.set_column(i, i, width)
    return buf.getvalue()


def supplemental_feed(
    df: pd.DataFrame,
    id_col: str = "id",
    label_mapping: dict | None = None,
    extra_cols: list | None = None,
) -> pd.DataFrame:
    """
    label_mapping: {'custom_label_0': 'performance_label', ...}
    Crea un feed supplementare con solo id + campi override.
    """
    out = pd.DataFrame()
    out["id"] = df[id_col]
    if label_mapping:
        for target, source in label_mapping.items():
            if source in df.columns:
                out[target] = df[source]
    if extra_cols:
        for c in extra_cols:
            if c in df.columns:
                out[c] = df[c]
    return out


def to_gmc_xml(df: pd.DataFrame, title: str = "Supplemental Feed") -> str:
    """Converte un dataframe in RSS 2.0 GMC-compatible (vettorizzato)."""
    if len(df) == 0:
        body = ""
    else:
        # Pre-stringify colonna per colonna (vectorizzato) + pre-escape.
        col_frames: dict[str, pd.Series] = {}
        for col in df.columns:
            s = df[col]
            s_str = s.where(s.notna(), "").astype(str).str.strip()
            s_str = s_str.mask(s_str.str.lower().isin(["nan", "none", "null"]), "")
            col_frames[col] = s_str

        # Costruzione per-riga con join (evita apply di pd.isna / escape riga per riga)
        items = []
        append = items.append
        cols = list(df.columns)
        col_values = {c: col_frames[c].tolist() for c in cols}
        n = len(df)
        for i in range(n):
            parts = []
            p_append = parts.append
            for c in cols:
                v = col_values[c][i]
                if not v:
                    continue
                p_append(f"    <g:{c}>{escape(v)}</g:{c}>")
            append("  <item>\n" + "\n".join(parts) + "\n  </item>")
        body = "\n".join(items)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
<channel>
  <title>{escape(title)}</title>
  <description>Feed supplementare generato</description>
{body}
</channel>
</rss>"""
