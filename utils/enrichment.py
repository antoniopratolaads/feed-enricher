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

SYSTEM_PROMPT_BASE = """Sei un esperto di e-commerce, Google Merchant Center, Meta Catalog e copywriting performance-driven.
Ricevi un prodotto con: titolo, descrizione, eventuali metriche (clicks, conversioni, ROAS, vendite Shopify, viste).
IL TUO COMPITO: estrarre E INFERIRE il MASSIMO NUMERO di attributi standard possibili leggendo titolo + descrizione + metadata.
Scrivi UN SOLO JSON con TUTTI i campi qui sotto. Per ogni campo: popolalo SEMPRE se desumibile dal testo,
altrimenti lascia stringa vuota "" o array vuoto []. NON lasciare i campi fuori dal JSON.

USA le metriche performance per calibrare il tono:
- zombie/no_clicks → titolo più aggressivo, attributi in evidenza, keyword search-friendly
- bestseller → mantieni il messaggio vincente, valorizza prove sociali implicite
- alte viste e poche conversioni → descrizione punta su benefici e differenziatori

RESTITUISCI UN SINGOLO JSON valido con TUTTI questi campi (nomi UFFICIALI Google/Meta):
{
  "_comment_testi": "TESTI PRINCIPALI",
  "title": "Titolo Google Merchant (70-150 char). Formula: Brand + Prodotto + Attributi chiave",
  "title_meta": "Titolo Meta Catalog (max 200 char, più descrittivo)",
  "description": "Descrizione Google 200-5000 char, tono descrittivo, NO promozionale",
  "description_meta_short": "Short description Meta max 200 char",
  "rich_text_description": "HTML Meta (bold/italic/list). Vuoto se non desumibile struttura",

  "_comment_tassonomia": "CATEGORIZZAZIONE",
  "google_product_category": "Percorso COMPLETO Google Taxonomy (es. 'Electronics > Video > Televisions')",
  "product_type": "Tassonomia interna 2-3 livelli (es. 'TV > Smart TV OLED > 55 pollici')",
  "fb_product_category": "Categoria Facebook se diversa da Google (es. 'Electronics > TVs')",

  "_comment_identita": "IDENTITÀ PRODOTTO",
  "brand": "Brand ufficiale del produttore",
  "gtin": "Codice EAN-13 o UPC-12 (solo cifre) SE presente",
  "mpn": "Manufacturer Part Number / codice modello brand",
  "identifier_exists": "yes|no (no solo se mancano gtin+mpn per prodotti no-brand/vintage/custom)",
  "item_group_id": "ID gruppo per varianti dello stesso modello (es. sku base senza taglia/colore)",

  "_comment_attributi_apparel": "APPAREL & SCARPE & ACCESSORI",
  "gender": "male|female|unisex|''",
  "age_group": "newborn|infant|toddler|kids|adult|''",
  "color": "Colore/i principali (max 3, separati da '/')",
  "size": "Taglia/numero EU/misura (es. '42', 'M', '15.6\"')",
  "size_system": "EU|US|UK|IT|JP|CN|FR|DE|MEX|AU|''",
  "size_type": "regular|petite|plus|maternity|big and tall|''",
  "material": "Materiale principale + percentuali (es. '95% cotone, 5% elastan')",
  "pattern": "Fantasia (tinta unita, righe, quadri, floreale, animalier, ...)",

  "_comment_condizioni": "CONDIZIONE & DISPONIBILITÀ",
  "condition": "new|refurbished|used (default new)",
  "availability": "in_stock|out_of_stock|preorder|backorder",
  "availability_date": "YYYY-MM-DD se preorder/backorder, altrimenti ''",
  "expiration_date": "YYYY-MM-DD per prodotti deperibili (food/pharma)",

  "_comment_prezzo": "PREZZO & OFFERTE (compila solo se desumibili)",
  "unit_pricing_measure": "es. '50 ml' (volume/peso del prodotto)",
  "unit_pricing_base_measure": "es. '100 ml' (base calcolo prezzo unitario)",

  "_comment_spedizione": "SPEDIZIONE & DIMENSIONI",
  "shipping_weight": "es. '500 g' o '2 kg'",
  "shipping_length": "es. '30 cm' (lunghezza pacco)",
  "shipping_width": "es. '20 cm'",
  "shipping_height": "es. '10 cm'",
  "product_length": "Lunghezza prodotto (es. '160 cm' mobili, '15.6\"' laptop)",
  "product_width": "Larghezza prodotto",
  "product_height": "Altezza prodotto",
  "product_weight": "Peso prodotto (es. '1.8 kg' laptop)",

  "_comment_bundle": "BUNDLE & MULTIPACK",
  "is_bundle": "yes|no|''",
  "multipack": "Numero unità in multipack (es. '6') o '' se singolo",

  "_comment_energia": "ENERGY LABEL (TV, monitor, elettrodomestici EU)",
  "energy_efficiency_class": "A|B|C|D|E|F|G o '' se non applicabile",
  "min_energy_efficiency_class": "Classe minima nella scala (es. 'G')",
  "max_energy_efficiency_class": "Classe massima (es. 'A')",

  "_comment_highlights": "HIGHLIGHTS & DETAILS",
  "product_highlight": ["6-10 bullet verificabili, max 150 char ciascuno"],
  "product_detail": [
    {"section_name": "Specifiche tecniche", "attribute_name": "Processore", "attribute_value": "Intel Core i7-12700H"},
    {"section_name": "Connettività", "attribute_name": "Porte", "attribute_value": "2x USB-C Thunderbolt 4, HDMI 2.1"},
    {"section_name": "Nella confezione", "attribute_name": "Accessori", "attribute_value": "Cavo USB-C, documentazione"}
  ],

  "_comment_compatibilita": "COMPATIBILITÀ & RICAMBI (auto, accessori elettronica)",
  "compatible_with": "Modelli compatibili (es. 'Volkswagen Golf VII 2012-2020')",
  "oem_number": "Codice OEM originale (ricambi auto)",

  "_comment_food_pharma": "FOOD / PHARMA / INTEGRATORI (solo se applicabile)",
  "ingredients": "Lista ingredienti se food/cosmetics/integratori (stringa separata da virgole)",
  "allergens": "Allergeni in evidenza per food (glutine, lattosio, frutta a guscio, ...)",
  "active_ingredient": "Principio attivo per farmaci OTC (es. 'Paracetamolo 500mg')",
  "pharmaceutical_form": "compresse|capsule|sciroppo|gel|spray|cerotto|''",
  "dosage": "Posologia consigliata (solo OTC/integratori con claim EFSA)",

  "_comment_pet": "PET (solo se prodotto per animali)",
  "animal_species": "cane|gatto|uccelli|pesci|roditori|rettili|''",
  "life_stage": "puppy|kitten|junior|adult|senior|all|''",

  "_comment_certificazioni": "CERTIFICAZIONI / OMOLOGAZIONI",
  "certifications": ["CE", "FSC", "OEKO-TEX", "Bio IT-BIO-XXX", "DOP", "IGP", "..."],

  "_comment_origine": "ORIGINE",
  "country_of_origin": "Paese produzione (es. 'Italy', 'Germany', 'China')",
  "made_in_italy": "yes|no|'' (yes solo se è chiaramente Made in Italy)",

  "_comment_media": "MEDIA (hint per il catalogo, non inventare URL)",
  "has_video": "yes|no|'' (se video link nel testo)",

  "_comment_keyword": "KEYWORDS SEO",
  "keywords": ["array", "di", "keyword", "search-friendly"],

  "_comment_custom_labels": "CUSTOM LABELS automatiche (derivate dalla descrizione)",
  "custom_label_0": "stagione / collezione (FW25, SS26, evergreen, ...) se desumibile",
  "custom_label_1": "fascia_prezzo (entry|mid|premium|luxury) se desumibile",
  "custom_label_2": "uso/occasione (daily, formale, sport, regalo, ...)",

  "_comment_performance": "SEGNALI PERFORMANCE INFERITI",
  "target_audience": "Descrizione breve target (es. 'Professionisti creativi', 'Runner intermedi 20+ km/sett')"
}

REGOLE ASSOLUTE:
1. **NON INVENTARE**: se un campo non è desumibile dal testo, lascia stringa vuota "" o array [].
   MAI allucinare GTIN, prezzi, certificazioni, paesi origine, compatibilità.
2. **SEMPRE popolati** quando desumibili: brand, color, size, material, gender, age_group, condition, product_highlight.
3. **gtin/mpn**: popola solo se letterali nel testo. Se assenti: identifier_exists="no".
4. **title e title_meta** DEVONO iniziare col brand.
5. **product_highlight**: 6-10 bullet verificabili, max 150 char, OGNI bullet = una feature/spec misurabile.
6. **product_detail**: 5-15 oggetti strutturati raggruppati per section_name logica (Specifiche, Connettività, Nella confezione, ...).
7. **description**: NO parole vietate (acquista, compra, offerta, sconto, migliore, gratis, imperdibile, emoji).
8. **unit_pricing**: utile per cosmesi/food/drogheria (€/100ml, €/100g).
9. **Rispondi SOLO con JSON valido, senza markdown, senza ``` di apertura/chiusura**.
10. I campi "_comment_*" sono solo organizzatori — DEVI ometterli dalla risposta JSON, includi solo i campi con valori effettivi.
"""


def get_default_base_prompt() -> str:
    """Expose the current base system prompt for the prompt editor UI."""
    return SYSTEM_PROMPT_BASE


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
    """Compone il system prompt.

    Priorità:
      1. Template utente attivo (da utils/prompts.py) per questo sector → usato tale-e-quale
      2. BASE + brief settoriale YAML (default)
    """
    # 1. Override utente via prompt versioning
    try:
        from . import prompts as _prompts
        body = _prompts.get_template_body(sector_name or "_default")
        if body:
            return body
    except ImportError:
        pass

    parts = [SYSTEM_PROMPT_BASE]
    if sector_name:
        sector = load_sector(sector_name)
        if sector:
            parts.append("\n\n" + _sector_brief(sector))
            parts.append("\nApplica RIGOROSAMENTE queste regole settoriali a tutti i campi.")
    return "".join(parts)


def enrich_product(client: Anthropic, product: dict, model: str = DEFAULT_MODEL,
                   sector: str = "", max_tokens: int = 3500) -> dict:
    """Chiama Claude per un singolo prodotto.

    Args:
        max_tokens: tetto token output. 2048 default perché il JSON completo
        (20+ campi con product_highlight[] e product_detail[]) supera spesso 1500 token
        su prodotti con description lunga.
    """
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
            max_tokens=max_tokens,
            system=[{
                "type": "text",
                "text": _build_system_prompt(sector),
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": f"Prodotto:\n{input_txt}"}],
        )
        text = resp.content[0].text if resp.content else ""
        stop_reason = getattr(resp, "stop_reason", "") or ""
        data = _extract_json(text)
        if data:
            data["_enrichment_status"] = "ok"
            return data
        # Empty parse — attach debug context so the UI shows WHY
        snippet = (text or "").strip()[:180].replace("\n", " ")
        if stop_reason == "max_tokens":
            status = f"empty:max_tokens (alza max_tokens, risposta troncata)"
        elif not text:
            status = "empty:no_text (Claude non ha risposto)"
        else:
            status = f"empty:no_json ({snippet}...)"
        return {"_enrichment_status": status}
    except Exception as e:
        return {"_enrichment_status": f"error: {type(e).__name__}: {e}"}


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
    max_tokens: int = 3500,
) -> pd.DataFrame:
    """Arricchisce l'intero dataframe in parallelo.

    Args:
        sector: può essere:
            - stringa vuota: prompt generico
            - nome settore (es. 'abbigliamento'): applica best practice del settore
            - 'auto': auto-classifica ogni prodotto e applica il settore rilevato
    """
    client = Anthropic(api_key=api_key)
    df = df.copy()

    work_df = df.head(limit) if limit else df
    indices = work_df.index.tolist()
    total = len(indices)

    # Auto-detect sector per-row quando sector=='auto'
    per_row_sector: dict = {}
    if sector == "auto":
        try:
            from . import sector_classifier
            detected = sector_classifier.apply_to_enrichment(work_df)
            per_row_sector = detected.to_dict()
        except Exception:
            per_row_sector = {}

    # nomi UFFICIALI Google/Meta — elenco completo attributi estraibili dall'AI
    official_cols = [
        # Testi principali
        "title", "description", "title_meta", "description_meta_short", "rich_text_description",
        # Tassonomia
        "google_product_category", "product_type", "fb_product_category",
        # Identità
        "brand", "gtin", "mpn", "identifier_exists", "item_group_id",
        # Attributi apparel / electronics
        "gender", "age_group", "color", "size", "size_system", "size_type",
        "material", "pattern",
        # Stato
        "condition", "availability", "availability_date", "expiration_date",
        # Prezzi unitari
        "unit_pricing_measure", "unit_pricing_base_measure",
        # Spedizione / dimensioni
        "shipping_weight", "shipping_length", "shipping_width", "shipping_height",
        "product_length", "product_width", "product_height", "product_weight",
        # Bundle
        "is_bundle", "multipack",
        # Energia
        "energy_efficiency_class", "min_energy_efficiency_class", "max_energy_efficiency_class",
        # Highlights
        "product_highlight", "product_detail",
        # Compatibilità
        "compatible_with", "oem_number",
        # Food / pharma
        "ingredients", "allergens", "active_ingredient", "pharmaceutical_form", "dosage",
        # Pet
        "animal_species", "life_stage",
        # Certificazioni / origine
        "certifications", "country_of_origin", "made_in_italy",
        # Media / target
        "has_video", "target_audience",
        # Keywords / custom labels
        "keywords", "custom_label_0", "custom_label_1", "custom_label_2",
        # Meta
        "_enrichment_status", "_detected_sector",
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
        # Resolve effective sector for this row
        if sector == "auto":
            effective_sector = per_row_sector.get(idx) or ""
        else:
            effective_sector = sector
        result = enrich_product(client, row, model=model, sector=effective_sector,
                                max_tokens=max_tokens)
        if effective_sector:
            result.setdefault("_detected_sector", effective_sector)
        return idx, result

    # Campi che possono essere in formato lista/oggetto e vanno serializzati
    _LIST_FIELDS = {"keywords", "product_highlight", "certifications"}
    _STRUCT_LIST_FIELDS = {"product_detail"}  # lista di dict
    # Campi che esistono già e NON vanno sovrascritti se pieni (a meno che overwrite=True)
    _OVERRIDE_ALWAYS = {"title", "description", "title_meta", "description_meta_short",
                         "rich_text_description"}

    def _serialize(field: str, value) -> str:
        """Serializza il valore AI nel formato stringa che salviamo nella cella."""
        if value is None:
            return ""
        if field in _STRUCT_LIST_FIELDS and isinstance(value, list):
            return " | ".join(
                f"{d.get('section_name', '')}:{d.get('attribute_name', '')}={d.get('attribute_value', '')}"
                for d in value if isinstance(d, dict)
            )
        if field in _LIST_FIELDS and isinstance(value, list):
            if field == "product_highlight":
                return " | ".join(str(b)[:150] for b in value[:10])
            return ", ".join(str(x) for x in value)
        if isinstance(value, (list, dict)):
            return json.dumps(value, ensure_ascii=False)
        return str(value).strip()

    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        futures = [ex.submit(_task, idx) for idx in indices]
        for fut in as_completed(futures):
            idx, result = fut.result()

            # _enrichment_status e _detected_sector sempre
            df.at[idx, "_enrichment_status"] = result.get("_enrichment_status", "")
            if result.get("_detected_sector"):
                df.at[idx, "_detected_sector"] = result["_detected_sector"]

            # Itera TUTTI i campi ufficiali e salva quelli popolati dall'AI
            for field in official_cols:
                if field in ("_enrichment_status", "_detected_sector"):
                    continue
                ai_value = result.get(field)
                if ai_value is None or ai_value == "" or ai_value == []:
                    continue
                serialized = _serialize(field, ai_value)
                if not serialized:
                    continue
                if field in _OVERRIDE_ALWAYS:
                    if overwrite_title_description or field not in ("title", "description"):
                        df.at[idx, field] = serialized
                else:
                    # Attributi: popola se il campo è vuoto; sovrascrivi attributi derivati (size, color, ...) sempre
                    current = str(df.at[idx, field] if field in df.columns else "").strip()
                    if not current or current.lower() in ("nan", "none"):
                        df.at[idx, field] = serialized
                    else:
                        # Se c'era già un valore nel feed originale per attributi canonici, rispetta l'originale
                        # per campi identity (brand, gtin, mpn) — altrimenti sovrascrivi con AI
                        if field in ("brand", "gtin", "mpn", "item_group_id",
                                     "identifier_exists", "oem_number", "country_of_origin"):
                            continue  # mantieni valore originale
                        df.at[idx, field] = serialized

            done += 1
            if progress_callback:
                progress_callback(done, total)

    return df
