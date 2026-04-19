"""Export feed supplementari in Excel / CSV / XML GMC."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

import pandas as pd


def to_excel_bytes(dfs: dict[str, pd.DataFrame]) -> bytes:
    """Genera xlsx multi-foglio."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        for name, df in dfs.items():
            safe = name[:31]
            df.to_excel(w, sheet_name=safe, index=False)
            ws = w.sheets[safe]
            for i, col in enumerate(df.columns):
                width = min(max(len(str(col)), df[col].astype(str).map(len).max() if len(df) else 10), 50)
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
    """Converte un dataframe in RSS 2.0 GMC-compatible."""
    items = []
    for _, row in df.iterrows():
        children = []
        for col in df.columns:
            val = row[col]
            if pd.isna(val) or str(val).strip() == "":
                continue
            tag = col if col == "id" else col
            children.append(f"    <g:{tag}>{escape(str(val))}</g:{tag}>")
        items.append("  <item>\n" + "\n".join(children) + "\n  </item>")

    body = "\n".join(items)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:g="http://base.google.com/ns/1.0">
<channel>
  <title>{escape(title)}</title>
  <description>Feed supplementare generato</description>
{body}
</channel>
</rss>"""
