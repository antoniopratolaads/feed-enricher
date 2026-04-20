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

SYSTEM_PROMPT_BASE = """Sei un esperto di e-commerce specializzato in feed Google Merchant Center e Meta Catalog.
Ricevi un prodotto con titolo, descrizione, brand, eventuali metriche (clicks, conversioni, ROAS, vendite Shopify, viste).

IL TUO COMPITO: estrarre / inferire il MASSIMO NUMERO di attributi usando i NOMI UFFICIALI Google.
L'output deve essere DIRETTAMENTE utilizzabile come feed supplementare su Google Merchant Center
(i nomi dei campi corrispondono 1:1 alla specifica ufficiale GMC 2026).

USA le metriche performance per calibrare il tono:
- zombie/no_clicks → titolo più aggressivo, attributi in evidenza, keyword search-friendly
- bestseller → mantieni il messaggio vincente
- alte viste e poche conversioni → descrizione punta su benefici e differenziatori

RESTITUISCI UN UNICO JSON valido con i seguenti NOMI UFFICIALI GMC (spec https://support.google.com/merchants/answer/7052112).
Ometti le chiavi che iniziano con "_comment_" dalla risposta — servono solo a organizzare questa spec.
Per ogni campo: popolalo se desumibile, altrimenti stringa vuota "" o array vuoto [].

{
  "_comment_A": "===== TESTI (GMC core) =====",
  "title": "Titolo GMC 70-150 char · Formula: Brand + Prodotto + Attributi chiave",
  "description": "Descrizione GMC 200-5000 char · tono descrittivo, NO promozionale",

  "_comment_B": "===== TASSONOMIA =====",
  "google_product_category": "Path COMPLETO Google Taxonomy (es. 'Electronics > Video > Televisions')",
  "product_type": "Tassonomia merchant 2-3 livelli (es. 'TV > Smart OLED > 55\"')",

  "_comment_C": "===== IDENTITÀ =====",
  "brand": "Brand produttore",
  "gtin": "EAN-13 / UPC-12 / GTIN-14 solo cifre (vuoto se assente)",
  "mpn": "Manufacturer Part Number (codice modello produttore)",
  "identifier_exists": "yes|no (no solo per prodotti custom/vintage/no-brand senza gtin+mpn)",
  "item_group_id": "ID gruppo varianti dello stesso modello (es. sku base senza taglia/colore)",

  "_comment_D": "===== ATTRIBUTI APPAREL & UNIVERSALI =====",
  "gender": "male|female|unisex|''",
  "age_group": "newborn|infant|toddler|kids|adult|''",
  "adult": "yes|no (yes SOLO per prodotti vietati ai minori)",
  "color": "Colore/i principali (max 3, separati da '/')",
  "size": "Taglia/numero/misura",
  "size_system": "EU|US|UK|IT|JP|CN|FR|DE|MEX|AU|BR|''",
  "size_type": "regular|petite|plus|maternity|big and tall|''",
  "material": "Materiale principale + percentuali (es. '95% cotone, 5% elastan')",
  "pattern": "Fantasia (tinta unita, righe, quadri, floreale, animalier)",

  "_comment_E": "===== CONDIZIONE & DISPONIBILITÀ =====",
  "condition": "new|refurbished|used",
  "availability": "in_stock|out_of_stock|preorder|backorder",
  "availability_date": "YYYY-MM-DD se preorder/backorder, altrimenti ''",
  "expiration_date": "YYYY-MM-DD per deperibili",

  "_comment_F": "===== PREZZO UNITARIO =====",
  "unit_pricing_measure": "Volume/peso prodotto (es. '50 ml', '200 g')",
  "unit_pricing_base_measure": "Base prezzo unitario (es. '100 ml', '1 kg')",

  "_comment_G": "===== BUNDLE & MULTIPACK =====",
  "is_bundle": "yes|no|''",
  "multipack": "Numero unità (es. '6') o '' se singolo",

  "_comment_H": "===== SPEDIZIONE =====",
  "shipping_weight": "Peso pacco (es. '2 kg', '500 g')",
  "shipping_length": "Lunghezza pacco (es. '30 cm')",
  "shipping_width": "Larghezza pacco",
  "shipping_height": "Altezza pacco",
  "shipping_label": "Etichetta logistica merchant (es. 'oversize', 'fragile', 'standard')",
  "ships_from_country": "Paese ISO-2 (es. 'IT', 'DE')",
  "min_handling_time": "Giorni preparazione min (es. '1')",
  "max_handling_time": "Giorni preparazione max",
  "transit_time_label": "Label tempi consegna",

  "_comment_I": "===== ENERGY LABEL (TV/monitor/elettrodomestici EU) =====",
  "energy_efficiency_class": "A|B|C|D|E|F|G o '' se non applicabile",
  "min_energy_efficiency_class": "Classe minima scala (es. 'G')",
  "max_energy_efficiency_class": "Classe massima (es. 'A')",

  "_comment_J": "===== CERTIFICATION (obbligatoria EU per energy label prodotti EPREL) =====",
  "certification": [
    {"authority": "EC", "name": "EPREL", "code": "M/2019/1783"}
  ],

  "_comment_K": "===== HIGHLIGHTS (GMC: scannable bullets) =====",
  "product_highlight": ["6-10 bullet verificabili, max 150 char ciascuno"],

  "_comment_L": "===== PRODUCT DETAIL (GMC structured: qualsiasi attributo non coperto sopra) =====",
  "product_detail": [
    {"section_name": "Specifiche tecniche", "attribute_name": "Processore", "attribute_value": "Intel Core i7-13700H"},
    {"section_name": "Specifiche tecniche", "attribute_name": "RAM", "attribute_value": "16 GB DDR5"},
    {"section_name": "Connettività", "attribute_name": "Porte", "attribute_value": "USB-C Thunderbolt 4, HDMI 2.1"},
    {"section_name": "Nella confezione", "attribute_name": "Accessori", "attribute_value": "Cavo USB-C, documentazione"},
    {"section_name": "Compatibilità", "attribute_name": "Veicoli", "attribute_value": "Volkswagen Golf VII 2012-2020"},
    {"section_name": "Composizione", "attribute_name": "Principio attivo", "attribute_value": "Paracetamolo 500 mg"},
    {"section_name": "Composizione", "attribute_name": "Ingredienti", "attribute_value": "Acqua, glicerina, acido ialuronico..."},
    {"section_name": "Composizione", "attribute_name": "Allergeni", "attribute_value": "Contiene GLUTINE, tracce di soia"},
    {"section_name": "Forma farmaceutica", "attribute_name": "Forma", "attribute_value": "Compresse rivestite"},
    {"section_name": "Posologia", "attribute_name": "Adulti", "attribute_value": "1 cp ogni 6-8h, max 3/die"},
    {"section_name": "Animale", "attribute_name": "Specie", "attribute_value": "Cane adulto piccola taglia"},
    {"section_name": "Dimensioni", "attribute_name": "LxPxA", "attribute_value": "220 x 92 x 85 cm"},
    {"section_name": "Origine", "attribute_name": "Paese", "attribute_value": "Made in Italy"}
  ],

  "_comment_M": "===== MEDIA =====",
  "video_link": "URL video demo (solo se presente nel testo)",
  "lifestyle_image_link": "URL immagine lifestyle/ambiente (solo se presente)",

  "_comment_N": "===== DESTINATION & TAX =====",
  "included_destination": ["Shopping_ads", "Free_listings", "Display_ads"],
  "excluded_destination": [],
  "tax_category": "Categoria fiscale se specificata (es. 'books', 'clothing')",

  "_comment_O": "===== CUSTOM LABELS auto-derivate =====",
  "custom_label_0": "stagione/collezione (FW25, SS26, evergreen)",
  "custom_label_1": "fascia_prezzo (entry|mid|premium|luxury)",
  "custom_label_2": "uso/occasione (daily, formale, sport, regalo)",
  "custom_label_3": "",
  "custom_label_4": "",

  "_comment_P": "===== META-ONLY (usati solo dall'export Meta Catalog) =====",
  "title_meta": "Titolo Meta max 200 char, più descrittivo",
  "description_meta_short": "Short description Meta max 200 char",
  "fb_product_category": "Categoria Facebook se diversa da Google",
  "rich_text_description": "HTML Meta (bold/italic/list) — vuoto se non desumibile"
}

REGOLE ASSOLUTE:
1. **NOMI UFFICIALI GMC**: usa ESATTAMENTE i nomi sopra. Sono i nomi-colonna del feed supplementare.
   Attributi non-standard (ingredienti, allergeni, principio_attivo, compatibilità, posologia, origine
   Made in XXX, dimensioni prodotto, etc.) vanno DENTRO `product_detail` come oggetti strutturati
   `{section_name, attribute_name, attribute_value}` — MAI come chiavi top-level inventate.
2. **NON INVENTARE**: se non desumibile, stringa vuota o array vuoto. MAI allucinare GTIN, prezzi,
   codici modello, certificazioni, paesi origine, compatibilità veicoli.
3. **identifier_exists=no** solo se mancano sia gtin che mpn per un prodotto custom/vintage/no-brand.
4. **product_highlight**: 6-10 bullet verificabili, max 150 char, ogni bullet = spec/feature misurabile.
5. **product_detail**: 8-20 oggetti strutturati. Usa section_name standardizzati:
   "Specifiche tecniche", "Connettività", "Nella confezione", "Compatibilità", "Composizione",
   "Forma farmaceutica", "Posologia", "Animale", "Dimensioni", "Origine", "Valori nutrizionali",
   "Alimentazione", "Installazione".
6. **certification**: array di oggetti `{authority, name, code}`. Authority = ente (CE, EC, FSC, OEKO-TEX,
   Bio IT-BIO-XXX, DOP, IGP). Esempio per TV: `[{"authority":"EC","name":"EPREL","code":"M/2021/123456"}]`.
   Nessuna certificazione inventata — solo se letteralmente documentata nel testo.
7. **description**: NO parole vietate (acquista, compra, offerta, sconto, migliore, gratis, imperdibile, emoji).
8. **title, title_meta** iniziano col brand.
9. **Rispondi SOLO con JSON valido, senza markdown, senza ``` di apertura/chiusura**.
10. Chiavi `_comment_*` omesse dalla risposta.
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

    # ONLY OFFICIAL GMC + META NAMES — colonne direttamente usabili in feed supplementari
    official_cols = [
        # Testi GMC
        "title", "description",
        # Tassonomia
        "google_product_category", "product_type",
        # Identità GMC
        "brand", "gtin", "mpn", "identifier_exists", "item_group_id",
        # Attributi apparel / universali
        "gender", "age_group", "adult",
        "color", "size", "size_system", "size_type",
        "material", "pattern",
        # Stato
        "condition", "availability", "availability_date", "expiration_date",
        # Prezzi unitari
        "unit_pricing_measure", "unit_pricing_base_measure",
        # Bundle
        "is_bundle", "multipack",
        # Spedizione
        "shipping_weight", "shipping_length", "shipping_width", "shipping_height",
        "shipping_label", "ships_from_country",
        "min_handling_time", "max_handling_time", "transit_time_label",
        # Energia (GMC official)
        "energy_efficiency_class", "min_energy_efficiency_class", "max_energy_efficiency_class",
        # Certification (GMC structured)
        "certification",
        # Highlights & details (contengono tutti gli attributi non top-level)
        "product_highlight", "product_detail",
        # Media
        "video_link", "lifestyle_image_link",
        # Destination & tax
        "included_destination", "excluded_destination", "tax_category",
        # Custom labels
        "custom_label_0", "custom_label_1", "custom_label_2", "custom_label_3", "custom_label_4",
        # Meta-only
        "title_meta", "description_meta_short", "fb_product_category", "rich_text_description",
        # Meta interni (non GMC)
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

    # Serializzazione speciale per campi strutturati GMC
    _STRUCT_LIST_FIELDS = {"product_detail"}       # [{section_name, attribute_name, attribute_value}]
    _CERTIFICATION_FIELD = "certification"         # [{authority, name, code}]
    _SIMPLE_LIST_FIELDS = {"included_destination", "excluded_destination"}
    _PIPE_LIST_FIELDS = {"product_highlight"}      # GMC accetta multipli separati con |
    # Campi che esistono già e NON vanno sovrascritti se pieni (a meno che overwrite=True)
    _OVERRIDE_ALWAYS = {"title", "description", "title_meta", "description_meta_short",
                         "rich_text_description"}

    def _serialize(field: str, value) -> str:
        """Serializza il valore AI nel formato stringa GMC-compatibile."""
        if value is None:
            return ""
        # product_detail: section_name:attribute_name=attribute_value | ... (multi-valore GMC)
        if field in _STRUCT_LIST_FIELDS and isinstance(value, list):
            return " | ".join(
                f"{d.get('section_name', '')}:{d.get('attribute_name', '')}={d.get('attribute_value', '')}"
                for d in value if isinstance(d, dict)
            )
        # certification: authority:name:code | ... (GMC accepts multi-value with pipe)
        if field == _CERTIFICATION_FIELD and isinstance(value, list):
            parts = []
            for d in value:
                if isinstance(d, dict):
                    a = d.get("authority", "")
                    n = d.get("name", "")
                    c = d.get("code", "")
                    parts.append(f"{a}:{n}:{c}")
                else:
                    parts.append(str(d))
            return " | ".join(p for p in parts if p.strip(":"))
        # product_highlight: pipe separator, 150 char max per bullet
        if field in _PIPE_LIST_FIELDS and isinstance(value, list):
            return " | ".join(str(b)[:150] for b in value[:10])
        # included_destination / excluded_destination: comma-separated standard GMC
        if field in _SIMPLE_LIST_FIELDS and isinstance(value, list):
            return ",".join(str(x) for x in value)
        # Fallback list/dict → JSON
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
                        # Campi identità / fonti autoritative: preserva l'originale del feed
                        if field in ("brand", "gtin", "mpn", "item_group_id",
                                     "identifier_exists", "ships_from_country",
                                     "tax_category", "min_handling_time", "max_handling_time"):
                            continue
                        df.at[idx, field] = serialized

            done += 1
            if progress_callback:
                progress_callback(done, total)

    return df
