"""Enrichment prodotti via AI (Claude / OpenAI / Gemini): taxonomy Google + estrazione attributi."""
from __future__ import annotations

import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Union

import pandas as pd
from anthropic import Anthropic

DEFAULT_MODEL = "claude-sonnet-4-6"


# ============================================================
# PROVIDER ABSTRACTION — Claude / OpenAI / Gemini
# ============================================================
def detect_provider(model: str) -> str:
    """Resolve provider name from model id."""
    m = (model or "").lower()
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith("gemini"):
        return "gemini"
    if m.startswith(("gpt", "o3", "o4")):
        return "openai"
    return "anthropic"


def _resolve_key(api_key: Union[str, dict, None], provider: str) -> str:
    """Accept str|dict|None. If dict, pick by provider. If None, load config."""
    if isinstance(api_key, dict):
        mapping = {
            "anthropic": ("anthropic_api_key", "api_key"),
            "openai":    ("openai_api_key",),
            "gemini":    ("gemini_api_key",),
        }
        for k in mapping.get(provider, ()):
            if v := api_key.get(k):
                return v
        return ""
    if api_key:
        return api_key
    try:
        from .config import load_config
        cfg = load_config()
        return cfg.get(f"{provider}_api_key", "") or ""
    except Exception:
        return ""


def make_client(provider: str, api_key: str):
    """Create provider-specific client."""
    if provider == "anthropic":
        return Anthropic(api_key=api_key)
    if provider == "openai":
        from openai import OpenAI
        return OpenAI(api_key=api_key)
    if provider == "gemini":
        from google import genai
        return genai.Client(api_key=api_key)
    raise ValueError(f"Unknown provider: {provider}")


def _generate(client, provider: str, model: str, system: str, user: str,
              max_tokens: int = 3500, temperature: float = 0.3,
              json_mode: bool = False) -> tuple[str, str]:
    """Unified generation. Returns (text, stop_reason)."""
    if provider == "anthropic":
        resp = client.messages.create(
            model=model, max_tokens=max_tokens, temperature=temperature,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            messages=[{"role": "user", "content": user}],
        )
        text = resp.content[0].text if resp.content else ""
        return text, getattr(resp, "stop_reason", "") or ""

    if provider == "openai":
        kwargs = dict(
            model=model, max_tokens=max_tokens, temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        choice = resp.choices[0]
        text = choice.message.content or ""
        return text, choice.finish_reason or ""

    if provider == "gemini":
        cfg = {
            "system_instruction": system,
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }
        if json_mode:
            cfg["response_mime_type"] = "application/json"
        resp = client.models.generate_content(
            model=model, contents=user, config=cfg,
        )
        text = resp.text or ""
        stop = ""
        try:
            stop = resp.candidates[0].finish_reason.name if resp.candidates else ""
        except Exception:
            pass
        # Gemini signals output-cap as "MAX_TOKENS"
        if stop == "MAX_TOKENS":
            stop = "max_tokens"
        return text, stop

    raise ValueError(f"Unknown provider: {provider}")

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

SYSTEM_PROMPT_BASE = """Esperto feed Google Merchant + Meta Catalog. Estrai/inferisci il massimo di attributi GMC ufficiali dal prodotto dato. Output = JSON diretto per feed supplementare GMC (nomi 1:1 spec GMC 2026).

Se arrivano metriche: zombie/no_clicks → titolo aggressivo + keyword search-friendly; bestseller → messaggio vincente; alte viste poche conv → benefici/differenziatori.

Output UN SOLO JSON valido, senza markdown, senza ```. Ometti chiavi con valori vuoti. Non inventare dati: se non desumibile, escludi la chiave.

Campi GMC (usa questi nomi esatti, ometti quelli vuoti):
- title (70-150ch, Brand+Prodotto+Attributi chiave) · description (200-5000ch, descrittivo no promo)
- google_product_category (path completo) · product_type (merchant 2-3 livelli)
- brand · gtin (solo cifre 8/12/13/14) · mpn · identifier_exists (no se mancano gtin+mpn) · item_group_id
- gender (male|female|unisex) · age_group (newborn|infant|toddler|kids|adult) · adult (yes|no)
- color (max 3, '/') · size · size_system (EU|US|UK|IT|JP|CN|FR|DE|MEX|AU|BR — default EU per cataloghi italiani con taglie numeriche 35-50 scarpe o 34-62 abbigliamento) · size_type (regular|petite|plus|maternity|big and tall)
- material (con %) · pattern (tinta unita|righe|quadri|floreale|animalier|...)
- condition (new|refurbished|used) · availability (in_stock|out_of_stock|preorder|backorder)
- availability_date · expiration_date (YYYY-MM-DD)
- unit_pricing_measure (es. '50 ml') · unit_pricing_base_measure (es. '100 ml')
- is_bundle (yes|no) · multipack (numero)
- shipping_weight · shipping_length/width/height · shipping_label · ships_from_country (ISO-2)
- min_handling_time · max_handling_time · transit_time_label
- energy_efficiency_class (A-G) · min_energy_efficiency_class · max_energy_efficiency_class
- certification (array [{authority,name,code}] es. [{"authority":"EC","name":"EPREL","code":"M/2021/1234"}])
- product_highlight (array 6-10 bullet max 150ch, feature/spec misurabili)
- product_detail (array [{section_name,attribute_name,attribute_value}] 8-20 entries per INFO NON COPERTE SOPRA: Specifiche tecniche, Connettività, Nella confezione, Compatibilità, Composizione [ingredienti/allergeni/principio attivo], Forma farmaceutica, Posologia, Animale [specie, età], Dimensioni, Origine, Valori nutrizionali, Alimentazione, Installazione)
- video_link · lifestyle_image_link
- included_destination · excluded_destination (array) · tax_category

NB: NON popolare i campi `custom_label_0..4` né `custom_number_0..4` — sono gestiti dal merchant via Labelizer basato su performance reali, non AI-inferable.

Campi META Catalog (nomi ufficiali Meta Commerce):
- title_meta (Meta title fino 200ch, più descrittivo)
- short_description (Meta max 200ch)
- rich_text_description (HTML Meta: <b><i><u><br><ul><li>)
- fb_product_category · origin_country (ISO-2)
- manufacturer_info (nome+indirizzo produttore, EU GPSR reg 2023/988)
- importer_name · importer_address (extra-EU GPSR)
- commerce_tax_category (STANDARD|FOOD|BOOKS|...)
- status (active|archived|staging)
- video (array [{tag,url}])

Regole:
1. Usa ESATTI nomi GMC sopra (colonne feed supplementare). Info non-coperte da campi top-level → dentro product_detail.
2. Non inventare gtin, mpn, certificazioni, origine, compatibilità. Solo quando letteralmente desumibile.
3. title/title_meta iniziano col brand.
4. description: NO acquista|compra|offerta|sconto|migliore|gratis|imperdibile|emoji.
5. Output: SOLO JSON valido, senza markdown. Ometti chiavi con valori vuoti per risparmiare token.
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


def _build_system_prompt(sector_name: str = "", style_guide_text: str = "",
                          target: str = "both") -> str:
    """Compone il system prompt.

    Priorità:
      1. Template utente attivo (da utils/prompts.py) per questo sector → usato tale-e-quale
      2. BASE + brief settoriale YAML (default)
    style_guide_text: testo style guide del catalogo, appeso per coerenza cross-prodotto.
    target: 'google' | 'meta' | 'both' — filtra blocco Meta dal prompt quando 'google'
            per risparmiare token output ~15%.
    """
    # 1. Override utente via prompt versioning
    try:
        from . import prompts as _prompts
        body = _prompts.get_template_body(sector_name or "_default")
        if body:
            if style_guide_text:
                body = body + "\n" + style_guide_text
            return body
    except ImportError:
        pass

    prompt = SYSTEM_PROMPT_BASE
    # Filtra il blocco META se target è solo Google
    if target == "google":
        # Rimuove da "Campi META Catalog" fino a "Regole:" (esclusivo)
        import re as _re
        prompt = _re.sub(
            r"Campi META Catalog.*?(?=Regole:)",
            "",
            prompt,
            count=1,
            flags=_re.DOTALL,
        )
        prompt += "\nTarget: SOLO Google Merchant Center. NON popolare campi META (title_meta, short_description, rich_text_description, fb_product_category, origin_country, manufacturer_info, importer_*, commerce_tax_category, status, video).\n"
    elif target == "meta":
        prompt += "\nTarget: SOLO Meta Catalog. Popola titoli/description con limiti Meta (title ≤200, description ≤9999, short_description ≤200). Puoi skippare campi GMC-only come certification, transit_time_label, shipping_label, tax_category, included_destination, excluded_destination, promotion_id.\n"

    parts = [prompt]
    if sector_name:
        sector = load_sector(sector_name)
        if sector:
            parts.append("\n\n" + _sector_brief(sector))
            parts.append("\nApplica RIGOROSAMENTE queste regole settoriali a tutti i campi.")
    if style_guide_text:
        parts.append(style_guide_text)
    return "".join(parts)


def enrich_product(client, product: dict, model: str = DEFAULT_MODEL,
                   sector: str = "", max_tokens: int = 3500,
                   style_guide_text: str = "",
                   target: str = "both",
                   provider: Optional[str] = None) -> dict:
    """Chiama il provider AI per un singolo prodotto.

    Args:
        max_tokens: tetto token output. 2048 default perché il JSON completo
        (20+ campi con product_highlight[] e product_detail[]) supera spesso 1500 token
        su prodotti con description lunga.
    """
    # Usa title/description ORIGINALI quando disponibili (set su primo enrichment).
    # Questo rende hash cache stabile e evita re-enrichment ricorsivo del già-enrichato.
    title_src = (
        product.get("title_original")
        if product.get("title_original")
        and str(product.get("title_original", "")).strip().lower() not in ("", "nan", "none")
        else product.get("title", "")
    )
    desc_src = (
        product.get("description_original")
        if product.get("description_original")
        and str(product.get("description_original", "")).strip().lower() not in ("", "nan", "none")
        else product.get("description", "")
    )
    payload = {
        "title": title_src,
        "description": str(desc_src)[:1500],
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

    prov = provider or detect_provider(model)
    try:
        system_txt = _build_system_prompt(sector, style_guide_text, target)
        text, stop_reason = _generate(
            client, prov, model, system_txt,
            f"Prodotto:\n{input_txt}",
            max_tokens=max_tokens, temperature=0.3,
            json_mode=(prov in ("openai", "gemini")),
        )
        data = _extract_json(text)
        if data:
            # Custom labels/numbers non devono essere popolate dall'AI —
            # sono gestite dal merchant via Labelizer/performance data.
            for k in ("custom_label_0", "custom_label_1", "custom_label_2",
                     "custom_label_3", "custom_label_4",
                     "custom_number_0", "custom_number_1", "custom_number_2",
                     "custom_number_3", "custom_number_4"):
                data.pop(k, None)
            data["_enrichment_status"] = "ok"
            return data
        # Empty parse — attach debug context so the UI shows WHY
        snippet = (text or "").strip()[:180].replace("\n", " ")
        if str(stop_reason).lower() in ("max_tokens", "length"):
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


def refine_product(client, product: dict, instruction: str,
                   model: str = DEFAULT_MODEL,
                   provider: Optional[str] = None) -> dict:
    payload = {
        "current_title": product.get("title", ""),
        "current_description": product.get("description", ""),
        "brand": product.get("brand", ""),
        "category": product.get("google_product_category", ""),
        "color": product.get("color", ""),
        "size": product.get("size", ""),
    }
    user_msg = f"Istruzione: {instruction}\n\nProdotto:\n{json.dumps(payload, ensure_ascii=False)}"
    prov = provider or detect_provider(model)
    try:
        text, _ = _generate(
            client, prov, model, REFINE_SYSTEM, user_msg,
            max_tokens=800, temperature=0.4,
            json_mode=(prov in ("openai", "gemini")),
        )
        return _extract_json(text) or {}
    except Exception as e:
        return {"_error": str(e)}


def chat_about_data(client, history: list, df_context: str,
                    model: str = DEFAULT_MODEL,
                    provider: Optional[str] = None) -> str:
    """Chat libera con AI usando un riassunto del catalogo come contesto."""
    system = (
        "Sei l'assistente AI di Feed Enricher Pro. Aiuti l'utente a migliorare il suo feed prodotto. "
        "Hai accesso a un riassunto del catalogo arricchito. Quando l'utente chiede modifiche concrete, "
        "suggerisci un'ISTRUZIONE precisa che potrà applicare con il pulsante 'Applica refinement'. "
        "Sii conciso, max 5 frasi.\n\n"
        f"CONTESTO CATALOGO:\n{df_context}"
    )
    prov = provider or detect_provider(model)
    try:
        if prov == "anthropic":
            resp = client.messages.create(
                model=model, max_tokens=600,
                system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
                messages=history,
            )
            return resp.content[0].text if resp.content else ""
        if prov == "openai":
            msgs = [{"role": "system", "content": system}] + history
            resp = client.chat.completions.create(
                model=model, max_tokens=600, temperature=0.5, messages=msgs,
            )
            return resp.choices[0].message.content or ""
        if prov == "gemini":
            # Flatten history → single user turn preserving roles as plain text
            lines = []
            for m in history:
                role = "Utente" if m.get("role") == "user" else "Assistente"
                content = m.get("content", "")
                if isinstance(content, list):
                    content = " ".join(str(c.get("text", c)) if isinstance(c, dict) else str(c) for c in content)
                lines.append(f"{role}: {content}")
            user_blob = "\n\n".join(lines)
            resp = client.models.generate_content(
                model=model, contents=user_blob,
                config={"system_instruction": system, "max_output_tokens": 600, "temperature": 0.5},
            )
            return resp.text or ""
        return f"Provider non supportato: {prov}"
    except Exception as e:
        return f"Errore: {e}"


def enrich_dataframe(
    df: pd.DataFrame,
    api_key: Union[str, dict, None] = None,
    model: str = DEFAULT_MODEL,
    max_workers: int = 5,
    limit: Optional[int] = None,
    progress_callback=None,
    sector: str = "",
    overwrite_title_description: bool = True,
    max_tokens: int = 3500,
    style_guide_text: str = "",
    skip_already_enriched: bool = True,
    target: str = "both",
    provider: Optional[str] = None,
) -> pd.DataFrame:
    """Arricchisce l'intero dataframe in parallelo.

    Args:
        sector: può essere:
            - stringa vuota: prompt generico
            - nome settore (es. 'abbigliamento'): applica best practice del settore
            - 'auto': auto-classifica ogni prodotto e applica il settore rilevato
    """
    prov = provider or detect_provider(model)
    key = _resolve_key(api_key, prov)
    if not key:
        raise ValueError(f"API key mancante per provider '{prov}'. Configura in Settings.")
    client = make_client(prov, key)
    df = df.copy()

    # Filtra fuori i prodotti già arricchiti quando skip_already_enriched=True.
    # Un prodotto è considerato già arricchito se _enrichment_status in ('ok', 'cached').
    base_df = df
    if skip_already_enriched and "_enrichment_status" in df.columns:
        status = df["_enrichment_status"].astype(str).str.strip().str.lower()
        unenriched_mask = ~status.isin(["ok", "cached"])
        base_df = df[unenriched_mask]
    work_df = base_df.head(limit) if limit else base_df
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
        # Meta-only (nomi UFFICIALI Meta Catalog)
        "title_meta", "short_description", "rich_text_description", "fb_product_category",
        "origin_country", "manufacturer_info", "importer_name", "importer_address",
        "commerce_tax_category", "status",
        "custom_number_0", "custom_number_1", "custom_number_2", "custom_number_3", "custom_number_4",
        "video",
        # Meta interni (non esportati in feed)
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
                                max_tokens=max_tokens, style_guide_text=style_guide_text,
                                target=target, provider=prov)
        if effective_sector:
            result.setdefault("_detected_sector", effective_sector)
        return idx, result

    # Serializzazione speciale per campi strutturati GMC / Meta
    _STRUCT_LIST_FIELDS = {"product_detail"}       # [{section_name, attribute_name, attribute_value}]
    _CERTIFICATION_FIELD = "certification"         # [{authority, name, code}]
    _VIDEO_FIELD = "video"                         # [{tag, url}] Meta-only
    _SIMPLE_LIST_FIELDS = {"included_destination", "excluded_destination"}
    _PIPE_LIST_FIELDS = {"product_highlight"}      # GMC accetta multipli separati con |
    # Campi che esistono già e NON vanno sovrascritti se pieni (a meno che overwrite=True)
    _OVERRIDE_ALWAYS = {"title", "description", "title_meta", "short_description",
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
        # video (Meta): tag:url | ... for multiple videos
        if field == _VIDEO_FIELD and isinstance(value, list):
            parts = []
            for d in value:
                if isinstance(d, dict):
                    tag = d.get("tag", "")
                    url = d.get("url", "")
                    if url:
                        parts.append(f"{tag}:{url}" if tag else url)
                elif d:
                    parts.append(str(d))
            return " | ".join(parts)
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
                                     "identifier_exists", "ships_from_country", "origin_country",
                                     "tax_category", "commerce_tax_category",
                                     "min_handling_time", "max_handling_time",
                                     "manufacturer_info", "importer_name", "importer_address"):
                            continue
                        df.at[idx, field] = serialized

            done += 1
            if progress_callback:
                progress_callback(done, total)

    return df
