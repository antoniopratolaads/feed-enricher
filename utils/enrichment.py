"""Enrichment prodotti via Claude API: taxonomy Google + estrazione attributi."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import pandas as pd
from anthropic import Anthropic

DEFAULT_MODEL = "claude-sonnet-4-6"

import os, yaml
from pathlib import Path

SECTORS_DIR = Path(__file__).parent.parent / "config" / "sectors"


def list_sectors() -> list[str]:
    if not SECTORS_DIR.exists():
        return []
    return [p.stem for p in SECTORS_DIR.glob("*.yaml")]


def load_sector(name: str) -> dict:
    f = SECTORS_DIR / f"{name}.yaml"
    if not f.exists():
        return {}
    return yaml.safe_load(f.read_text()) or {}


def _sector_brief(sector: dict) -> str:
    """Estrae le regole più importanti del sector in formato compatto per il system prompt."""
    if not sector:
        return ""
    parts = [f"## SETTORE: {sector.get('display_name', sector.get('sector', 'generico'))}"]
    if t := sector.get("title"):
        parts.append(f"\nTITOLO — formula: {t.get('formula', '')}")
        if examples := t.get("formula_examples", []):
            parts.append("Esempi: " + " | ".join(examples[:3]))
        if rules := t.get("rules"):
            parts.append("Regole title:\n- " + "\n- ".join(rules))
        if forb := t.get("forbidden_words"):
            parts.append("Parole VIETATE nel title: " + ", ".join(forb))
    if d := sector.get("description"):
        if struct := d.get("structure"):
            parts.append("\nDESCRIZIONE — struttura:\n- " + "\n- ".join(struct))
        if length := d.get("length"):
            parts.append(f"Lunghezza: {length.get('min_chars', 200)}-{length.get('ideal_chars', 500)} char ideali")
        if tone := d.get("tone"):
            parts.append("Tono:\n- " + "\n- ".join(tone))
    if reqs := sector.get("required_attributes"):
        parts.append("\nATTRIBUTI:")
        for r in reqs[:6]:
            vals = r.get("values") or r.get("common_values") or []
            parts.append(f"- {r['name']}: {', '.join(map(str, vals[:8])) if vals else ''}")
    if tax := sector.get("google_taxonomy"):
        if paths := tax.get("common_paths"):
            parts.append(f"\nGoogle taxonomy frequenti:\n- " + "\n- ".join(paths[:8]))
    if voice := sector.get("ai_voice"):
        if do := voice.get("do"):
            parts.append("\nFAI:\n- " + "\n- ".join(do))
        if dont := voice.get("dont"):
            parts.append("EVITA:\n- " + "\n- ".join(dont))
    return "\n".join(parts)

SYSTEM_PROMPT_BASE = """Sei un esperto di e-commerce, Google Merchant Center e copywriting performance-driven.
Ricevi un prodotto con: titolo, descrizione, eventuali metriche (clicks, conversioni, ROAS, vendite Shopify, viste).
USA queste metriche per calibrare il tono:
- se è zombie/no_clicks → titolo più aggressivo, attributi in evidenza, parole chiave search-friendly
- se è bestseller → mantieni il messaggio vincente, valorizza prove sociali implicite (es. "amato")
- se ha alte viste ma poche conversioni → migliora descrizione spingendo su benefici e differenziatori

Restituisci SEMPRE un JSON valido con questi NOMI UFFICIALI Google/Meta:
{
  "title": "Titolo OTTIMIZZATO Google Merchant Center (70-150 char). Formula: Brand + Prodotto + Attributi chiave",
  "title_meta": "Titolo OTTIMIZZATO Meta Catalog (max 200 char, più descrittivo)",
  "description": "Descrizione completa Google (200-5000 char). Tono descrittivo, NO promozionale",
  "description_meta_short": "Short description Meta (max 200 char)",
  "google_product_category": "Percorso completo Google Taxonomy",
  "product_type": "Tassonomia interna 2-3 livelli",
  "brand": "Brand del prodotto",
  "color": "Colore/i principali (max 3, separati da '/')",
  "size": "Taglia/misura/volume (per cosmesi: '50 ml', '200 g')",
  "size_system": "EU|US|UK|IT|...",
  "material": "Materiale principale + percentuali se disponibili",
  "gender": "male|female|unisex|''",
  "age_group": "newborn|infant|toddler|kids|adult|''",
  "pattern": "Fantasia",
  "condition": "new|refurbished|used (default new)",
  "product_highlight": ["bullet 1 (max 150 char)", "bullet 2", "..." ],
  "product_detail": [
    {"section_name": "Sezione", "attribute_name": "Nome", "attribute_value": "Valore"},
    {"section_name": "...", "attribute_name": "...", "attribute_value": "..."}
  ],
  "unit_pricing_measure": "es. '50 ml' (volume del prodotto, utile per €/100ml in GMC)",
  "unit_pricing_base_measure": "es. '100 ml' (base per il calcolo del prezzo unitario)",
  "shipping_weight": "es. '500 g' (solo se desumibile)",
  "is_bundle": "yes|no|'' (yes solo se è chiaramente un bundle/kit)",
  "multipack": "es. '3' (numero unità in un multipack, vuoto se singolo)",
  "keywords": ["lista", "di", "keyword"]
}

REGOLE FONDAMENTALI:
- Non inventare dati: se non desumibile dal testo, lascia stringa vuota o array vuoto
- title e title_meta DEVONO contenere il brand all'inizio
- product_highlight: massimo 10 bullet point, ognuno verificabile dal testo
- product_detail: lista oggetti con section_name + attribute_name + attribute_value
- unit_pricing utile per cosmesi/food (€/100ml, €/100g)
- description NON deve contenere parole vietate: 'acquista', 'compra', 'offerta', 'sconto', emoji
- Rispondi SOLO con JSON, senza markdown."""


def _extract_json(text: str) -> dict:
    """Estrae JSON anche se wrappato in markdown."""
    text = text.strip()
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return {}


def _build_system_prompt(sector_name: str = "") -> str:
    """Compone il system prompt: base + brief settoriale dal YAML."""
    parts = [SYSTEM_PROMPT_BASE]
    if sector_name:
        sector = load_sector(sector_name)
        if sector:
            parts.append("\n\n" + _sector_brief(sector))
            parts.append("\nApplica RIGOROSAMENTE queste regole settoriali a tutti i campi.")
    return "".join(parts)


def enrich_product(client: Anthropic, product: dict, model: str = DEFAULT_MODEL,
                   sector: str = "") -> dict:
    """Chiama Claude per un singolo prodotto."""
    payload = {
        "title": product.get("title", ""),
        "description": str(product.get("description", ""))[:1500],
        "brand": product.get("brand", ""),
        "existing_category": product.get("product_type", "") or product.get("google_product_category", ""),
        "link": product.get("link", ""),
    }
    # signals da GAds / Shopify (se presenti)
    for key in ("clicks", "conversions", "conv_value", "cost",
                "shopify_units_sold", "shopify_revenue", "shopify_views"):
        v = product.get(key)
        if v not in (None, "", 0, 0.0):
            payload[key] = v
    input_txt = json.dumps(payload, ensure_ascii=False, default=str)

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            system=[{
                "type": "text",
                "text": _build_system_prompt(sector),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": f"Prodotto:\n{input_txt}"}],
        )
        text = resp.content[0].text if resp.content else ""
        data = _extract_json(text)
        data["_enrichment_status"] = "ok" if data else "empty"
        return data
    except Exception as e:
        return {"_enrichment_status": f"error: {e}"}


REFINE_SYSTEM = """Sei un copywriter e-commerce. Ricevi un prodotto già arricchito (titolo ottimizzato, descrizione, attributi) e un'istruzione dell'utente.
Riscrivi titolo e/o descrizione SECONDO l'ISTRUZIONE.
Restituisci SEMPRE solo questo JSON:
{"title": "...", "description": "...", "title_meta": "...", "description_meta_short": "...", "notes": "una frase su cosa hai cambiato"}
Mantieni inalterato qualsiasi attributo non menzionato. Non inventare informazioni."""


def refine_product(client: Anthropic, product: dict, instruction: str, model: str = DEFAULT_MODEL) -> dict:
    payload = {
        "current_title": product.get("title", ""),
        "current_description": product.get("description", ""),
        "brand": product.get("brand", ""),
        "category": product.get("google_product_category", ""),
        "color": product.get("color", ""),
        "size": product.get("size", ""),
    }
    user_msg = f"Istruzione: {instruction}\n\nProdotto:\n{json.dumps(payload, ensure_ascii=False)}"
    try:
        resp = client.messages.create(
            model=model, max_tokens=800,
            system=[{"type": "text", "text": REFINE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user_msg}],
        )
        text = resp.content[0].text if resp.content else ""
        return _extract_json(text) or {}
    except Exception as e:
        return {"_error": str(e)}


def chat_about_data(client: Anthropic, history: list, df_context: str, model: str = DEFAULT_MODEL) -> str:
    """Chat libera con Claude usando un riassunto del catalogo come contesto."""
    system = (
        "Sei l'assistente AI di Feed Enricher Pro. Aiuti l'utente a migliorare il suo feed prodotto. "
        "Hai accesso a un riassunto del catalogo arricchito. Quando l'utente chiede modifiche concrete, "
        "suggerisci un'ISTRUZIONE precisa che potrà applicare con il pulsante 'Applica refinement'. "
        "Sii conciso, max 5 frasi.\n\n"
        f"CONTESTO CATALOGO:\n{df_context}"
    )
    try:
        resp = client.messages.create(
            model=model, max_tokens=600,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=history,
        )
        return resp.content[0].text if resp.content else ""
    except Exception as e:
        return f"Errore: {e}"


def enrich_dataframe(
    df: pd.DataFrame,
    api_key: str,
    model: str = DEFAULT_MODEL,
    max_workers: int = 5,
    limit: Optional[int] = None,
    progress_callback=None,
    sector: str = "",
    overwrite_title_description: bool = True,
) -> pd.DataFrame:
    """Arricchisce l'intero dataframe in parallelo."""
    client = Anthropic(api_key=api_key)
    df = df.copy()

    work_df = df.head(limit) if limit else df
    indices = work_df.index.tolist()
    total = len(indices)

    # nomi UFFICIALI Google/Meta (no più suffisso _ai)
    official_cols = [
        "title", "description", "title_meta", "description_meta_short",
        "google_product_category", "product_type", "brand", "color", "size",
        "size_system", "material", "gender", "age_group", "pattern", "condition",
        "product_highlight", "product_detail",
        "unit_pricing_measure", "unit_pricing_base_measure",
        "shipping_weight", "is_bundle", "multipack",
        "keywords", "_enrichment_status",
    ]
    for c in official_cols:
        if c not in df.columns:
            df[c] = ""

    # backup originali
    if overwrite_title_description:
        if "title" in df.columns and "title_original" not in df.columns:
            df["title_original"] = df["title"]
        if "description" in df.columns and "description_original" not in df.columns:
            df["description_original"] = df["description"]

    def _task(idx):
        row = df.loc[idx].to_dict()
        result = enrich_product(client, row, model=model, sector=sector)
        return idx, result

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_task, idx) for idx in indices]
        for fut in as_completed(futures):
            idx, result = fut.result()
            # campi specifici Meta (sempre nuovi, non esistono prima)
            df.at[idx, "title_meta"] = result.get("title_meta", "")
            df.at[idx, "description_meta_short"] = result.get("description_meta_short", "")
            kw = result.get("keywords", [])
            df.at[idx, "keywords"] = ", ".join(kw) if isinstance(kw, list) else str(kw)
            df.at[idx, "_enrichment_status"] = result.get("_enrichment_status", "")

            # NUOVI CAMPI GMC (solo se desumibili)
            ph = result.get("product_highlight", [])
            if isinstance(ph, list) and ph:
                # GMC accetta multipli product_highlight separati - li uniamo con pipe per il CSV
                df.at[idx, "product_highlight"] = " | ".join(str(b)[:150] for b in ph[:10])

            pd_list = result.get("product_detail", [])
            if isinstance(pd_list, list) and pd_list:
                # serializza come "section:name=value | section:name=value"
                serialized = " | ".join(
                    f"{d.get('section_name', '')}:{d.get('attribute_name', '')}={d.get('attribute_value', '')}"
                    for d in pd_list if isinstance(d, dict)
                )
                df.at[idx, "product_detail"] = serialized

            for f in ("unit_pricing_measure", "unit_pricing_base_measure",
                      "shipping_weight", "is_bundle", "multipack"):
                v = result.get(f, "")
                if v:
                    df.at[idx, f] = v

            # OVERRIDE / POPOLAMENTO con nomi UFFICIALI
            for field in ("title", "description", "google_product_category", "product_type",
                          "brand", "color", "size", "size_system", "material",
                          "gender", "age_group", "pattern", "condition"):
                ai_value = result.get(field, "")
                if not ai_value:
                    continue
                # title/description: sovrascrivi sempre se overwrite=True
                if field in ("title", "description"):
                    if overwrite_title_description:
                        df.at[idx, field] = ai_value
                else:
                    # attributi: popola se vuoto, sempre
                    current = str(df.at[idx, field] if field in df.columns else "").strip()
                    if not current:
                        df.at[idx, field] = ai_value
            done += 1
            if progress_callback:
                progress_callback(done, total)

    return df
