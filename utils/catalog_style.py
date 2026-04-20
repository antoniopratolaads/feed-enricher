"""Catalog-wide style coherence.

Analizza un campione di prodotti con Claude Haiku (cheap, 1 call per catalogo)
e produce uno STYLE GUIDE che viene iniettato nel system prompt di ogni call
successiva. Risultato: tutti i prodotti enrichati seguono la stessa formula
titoli, stesso tono descrizione, stessa tassonomia, stesso vocabolario.

Costo: ~€0.005-0.02 Haiku per catalogo (runtime 5-10s).
Il guide rimane parte del system prompt → cached → zero overhead per prodotto.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pandas as pd
from anthropic import Anthropic


_STORE_DIR = Path.home() / ".feed_enricher" / "style_guides"
_STORE_DIR.mkdir(parents=True, exist_ok=True)


_ANALYZER_PROMPT = """Sei un esperto di catalogo e-commerce. Ricevi un CAMPIONE di prodotti grezzi.
Tuo compito: produrre uno STYLE GUIDE conciso che verrà usato come anchor di stile
per arricchire TUTTO il catalogo in modo coerente.

Output: SOLO JSON valido con questi campi (max 500 token totale):

{
  "catalog_summary": "1-2 frasi: tipologia catalogo + brand dominanti + settore",
  "voice": "Tecnico|Descrittivo|Premium|Lifestyle|Emozionale (scegli 1, quello prevalente)",
  "title_formula": "Pattern titolo da usare per TUTTI (es. 'Brand + Modello + Tipo + Attributi chiave separati da |')",
  "title_examples": ["Esempio 1 già conforme", "Esempio 2", "Esempio 3"],
  "description_style": "2 frasi: struttura fissa + cose da evitare (es. 'Apri con cos'è e per chi. No aggettivi vuoti tipo elegante/raffinato')",
  "taxonomy_pattern": "Pattern google_product_category (es. 'Sempre 3 livelli: Apparel > Clothing > SPECIFICO')",
  "forbidden_terms": ["lista", "parole", "vietate", "nel", "catalogo"],
  "preferred_terms": {"elegante": "dal design pulito", "di qualità": "costruito in X", "offerta": "[eliminare]"},
  "product_highlight_style": "Come scrivere i bullet (es. '1 feature misurabile per riga, inizia con specifica tecnica, no claim marketing')",
  "attribute_conventions": "Convenzioni attributi (es. 'color = nome italiano standard, material = % e composizione, size = EU per scarpe')"
}

Analizza titoli, descrizioni, brand, categorie esistenti per inferire stile coerente.
Output SOLO JSON, niente markdown, niente ```."""


def _sample_products(df: pd.DataFrame, n: int = 12) -> list[dict]:
    """Sample N products stratified by brand when possible."""
    n = min(n, len(df))
    if "brand" in df.columns and df["brand"].notna().any():
        brands = df["brand"].dropna().astype(str).unique().tolist()
        if len(brands) > 1:
            per_brand = max(1, n // min(len(brands), 6))
            picked = []
            for b in brands[:6]:
                sub = df[df["brand"].astype(str) == b].head(per_brand)
                picked.append(sub)
            sampled = pd.concat(picked) if picked else df.head(n)
            if len(sampled) < n:
                rest = df.drop(sampled.index, errors="ignore").head(n - len(sampled))
                sampled = pd.concat([sampled, rest])
            sampled = sampled.head(n)
        else:
            sampled = df.sample(min(n, len(df)), random_state=42)
    else:
        sampled = df.sample(min(n, len(df)), random_state=42)

    rows = []
    for _, row in sampled.iterrows():
        compact = {}
        for k in ("id", "title", "description", "brand", "product_type",
                  "google_product_category", "price", "gtin", "color", "size", "material"):
            v = row.get(k, "")
            if v is None or pd.isna(v):
                continue
            s = str(v).strip()
            if s and s.lower() not in ("nan", "none"):
                compact[k] = s[:300]  # trunc description
        if compact:
            rows.append(compact)
    return rows


def analyze_catalog(df: pd.DataFrame, api_key: str, *,
                    sample_size: int = 12,
                    model: str = "claude-haiku-4-5-20251001") -> dict:
    """Analyze catalog sample and return structured style guide.

    Returns dict with keys: catalog_summary, voice, title_formula, title_examples,
    description_style, taxonomy_pattern, forbidden_terms, preferred_terms,
    product_highlight_style, attribute_conventions.
    """
    sample = _sample_products(df, n=sample_size)
    if not sample:
        return {}

    payload = json.dumps(sample, ensure_ascii=False, default=str)
    client = Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=800,
            system=_ANALYZER_PROMPT,
            messages=[{"role": "user", "content": f"Campione catalogo:\n{payload}"}],
        )
        text = resp.content[0].text if resp.content else ""
    except Exception as e:  # noqa
        return {"_error": str(e)}

    # Extract JSON
    import re
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"_error": "no_json", "_raw": text[:200]}
    try:
        guide = json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"_error": f"json_parse: {e}", "_raw": text[:200]}

    return guide


def format_for_prompt(guide: dict) -> str:
    """Render style guide as compact text block for system prompt injection.

    Kept under ~600 tokens to stay cache-friendly.
    """
    if not guide or "_error" in guide:
        return ""
    lines = ["\n=== STYLE GUIDE DEL CATALOGO (applica a TUTTI i prodotti per coerenza) ==="]
    if v := guide.get("catalog_summary"):
        lines.append(f"Catalogo: {v}")
    if v := guide.get("voice"):
        lines.append(f"Tono voce: {v}")
    if v := guide.get("title_formula"):
        lines.append(f"Formula titolo (usare SEMPRE): {v}")
    if exs := guide.get("title_examples"):
        exs_str = " | ".join(str(e)[:120] for e in exs[:3] if e)
        if exs_str:
            lines.append(f"Esempi titoli conformi: {exs_str}")
    if v := guide.get("description_style"):
        lines.append(f"Stile description: {v}")
    if v := guide.get("taxonomy_pattern"):
        lines.append(f"Pattern google_product_category: {v}")
    if lst := guide.get("forbidden_terms"):
        lines.append(f"Parole vietate nel catalogo: {', '.join(str(x) for x in lst[:15])}")
    if pref := guide.get("preferred_terms"):
        if isinstance(pref, dict) and pref:
            pairs = [f"{k}→{v}" for k, v in list(pref.items())[:8]]
            lines.append(f"Sostituzioni: {', '.join(pairs)}")
    if v := guide.get("product_highlight_style"):
        lines.append(f"Stile product_highlight: {v}")
    if v := guide.get("attribute_conventions"):
        lines.append(f"Convenzioni attributi: {v}")
    lines.append("=== FINE STYLE GUIDE ===\n")
    return "\n".join(lines)


# ============================================================
# PERSISTENCE per feed/cliente
# ============================================================
def _guide_path(namespace: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in namespace)[:80] or "default"
    return _STORE_DIR / f"{safe}.json"


def save_guide(namespace: str, guide: dict) -> Path:
    path = _guide_path(namespace)
    path.write_text(json.dumps(guide, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_guide(namespace: str) -> dict | None:
    path = _guide_path(namespace)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def delete_guide(namespace: str) -> bool:
    path = _guide_path(namespace)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False
