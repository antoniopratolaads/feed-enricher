"""Builder cataloghi ottimizzati per Google Merchant Center e Meta Catalog.

Riferimenti:
- Google: https://support.google.com/merchants/answer/7052112 (specifica feed)
- Meta:   https://www.facebook.com/business/help/120325381656392 (catalog reference)

Best practice titoli/descrizioni adottate (sintesi GMC + Meta + community):
- Title Google: 70-150 char, formato `Brand + Tipo prodotto + Attributi chiave`
- Title Meta: max 200 char, idem
- Description: 500-5000 char Google · 200 short / 9999 long Meta
- Availability values normalizzati: in_stock | out_of_stock | preorder | backorder
- Condition: new | refurbished | used
- Identifier_exists = no se mancano sia gtin sia mpn (Google)
"""
from __future__ import annotations
import pandas as pd
import numpy as np
import re
import json as _json

# ---------- Specifiche campi ----------

# (target_col, [source_cols in priority order], required_for_gmc, required_for_meta)
GOOGLE_FIELDS = [
    # Identificativi base (obbligatori)
    ("id",                            ["id"],                           True,  True),
    ("title",                         ["title"],                        True,  True),
    ("description",                   ["description"],                  True,  True),
    ("link",                          ["link"],                         True,  True),
    ("mobile_link",                   ["mobile_link"],                  False, False),

    # Immagini
    ("image_link",                    ["image_link"],                   True,  True),
    ("additional_image_link",         ["additional_image_link"],        False, False),
    ("lifestyle_image_link",          ["lifestyle_image_link"],         False, False),
    ("video_link",                    ["video_link"],                   False, False),

    # Stato e disponibilità
    ("availability",                  ["availability"],                 True,  True),
    ("availability_date",             ["availability_date"],            False, False),
    ("expiration_date",               ["expiration_date"],              False, False),
    ("condition",                     ["condition"],                    True,  True),
    ("adult",                         ["adult"],                        False, False),

    # Prezzi
    ("price",                         ["price"],                        True,  True),
    ("sale_price",                    ["sale_price"],                   False, False),
    ("sale_price_effective_date",     ["sale_price_effective_date"],    False, False),
    ("unit_pricing_measure",          ["unit_pricing_measure"],         False, False),
    ("unit_pricing_base_measure",     ["unit_pricing_base_measure"],    False, False),
    ("installment",                   ["installment"],                  False, False),
    ("subscription_cost",             ["subscription_cost"],            False, False),
    ("loyalty_points",                ["loyalty_points"],               False, False),

    # Tassonomia & identità
    ("google_product_category",       ["google_product_category"],      True,  True),
    ("product_type",                  ["product_type"],                 False, False),
    ("brand",                         ["brand"],                        True,  True),
    ("gtin",                          ["gtin"],                         False, False),
    ("mpn",                           ["mpn"],                          False, False),
    ("identifier_exists",             [],                               False, False),  # calcolato

    # Attributi prodotto
    ("color",                         ["color"],                        False, False),
    ("size",                          ["size"],                         False, False),
    ("size_type",                     ["size_type"],                    False, False),
    ("size_system",                   ["size_system"],                  False, False),
    ("material",                      ["material"],                     False, False),
    ("pattern",                       ["pattern"],                      False, False),
    ("gender",                        ["gender"],                       False, False),
    ("age_group",                     ["age_group"],                    False, False),

    # Bundle & multipack
    ("is_bundle",                     ["is_bundle"],                    False, False),
    ("multipack",                     ["multipack"],                    False, False),

    # Varianti
    ("item_group_id",                 ["item_group_id"],                False, False),

    # Energia (EU)
    ("energy_efficiency_class",       ["energy_efficiency_class"],      False, False),
    ("min_energy_efficiency_class",   ["min_energy_efficiency_class"],  False, False),
    ("max_energy_efficiency_class",   ["max_energy_efficiency_class"],  False, False),

    # Certification (EU EPREL, FSC, Bio ecc.)
    ("certification",                 ["certification"],                False, False),

    # Highlights & details (structured, contengono attributi non top-level)
    ("product_highlight",             ["product_highlight"],            False, False),
    ("product_detail",                ["product_detail"],               False, False),

    # Spedizione
    ("shipping",                      ["shipping"],                     False, False),
    ("shipping_label",                ["shipping_label"],               False, False),
    ("shipping_weight",               ["shipping_weight"],              False, False),
    ("shipping_length",               ["shipping_length"],              False, False),
    ("shipping_width",                ["shipping_width"],               False, False),
    ("shipping_height",               ["shipping_height"],              False, False),
    ("ships_from_country",            ["ships_from_country"],           False, False),
    ("min_handling_time",             ["min_handling_time"],            False, False),
    ("max_handling_time",             ["max_handling_time"],            False, False),
    ("transit_time_label",            ["transit_time_label"],           False, False),

    # Tax & destinations
    ("tax",                           ["tax"],                          False, False),
    ("tax_category",                  ["tax_category"],                 False, False),
    ("included_destination",          ["included_destination"],         False, False),
    ("excluded_destination",          ["excluded_destination"],         False, False),
    ("shopping_ads_excluded_country", ["shopping_ads_excluded_country"], False, False),

    # Promozioni
    ("promotion_id",                  ["promotion_id"],                 False, False),

    # Custom labels
    ("custom_label_0",                ["custom_label_0"],               False, False),
    ("custom_label_1",                ["custom_label_1"],               False, False),
    ("custom_label_2",                ["custom_label_2"],               False, False),
    ("custom_label_3",                ["custom_label_3"],               False, False),
    ("custom_label_4",                ["custom_label_4"],               False, False),
]

# ============================================================
# META CATALOG — specifica campi ufficiali
# ============================================================
# (target_col, [source_cols priority order], required_for_meta)
# I nomi sono ESATTAMENTE quelli della spec Meta Commerce Manager.
# Riferimento: facebook.com/business/help/120325381656392
META_FIELDS = [
    # Identificativi & richiesti
    ("id",                        ["id"],                                True),
    ("title",                     ["title_meta", "title"],               True),
    ("description",               ["description"],                       True),
    ("availability",              ["availability"],                      True),
    ("condition",                 ["condition"],                         True),
    ("price",                     ["price"],                             True),
    ("link",                      ["link"],                              True),
    ("image_link",                ["image_link"],                        True),
    ("brand",                     ["brand"],                             True),

    # Immagini & media
    ("additional_image_link",     ["additional_image_link"],             False),
    ("video",                     ["video"],                             False),

    # Varianti & grouping
    ("item_group_id",             ["item_group_id"],                     False),

    # Prezzi
    ("sale_price",                ["sale_price"],                        False),
    ("sale_price_effective_date", ["sale_price_effective_date"],         False),
    ("unit_price",                ["unit_pricing_measure", "unit_pricing_base_measure"], False),

    # Descriptions aggiuntive (Meta-specific)
    ("short_description",         ["short_description",
                                    "description_meta_short"],           False),
    ("rich_text_description",     ["rich_text_description"],             False),

    # Tassonomia
    ("fb_product_category",       ["fb_product_category",
                                    "google_product_category"],          False),
    ("google_product_category",   ["google_product_category"],           False),
    ("product_type",              ["product_type"],                      False),

    # Identità
    ("gtin",                      ["gtin"],                              False),
    ("mpn",                       ["mpn"],                               False),

    # Attributi prodotto
    ("color",                     ["color"],                             False),
    ("size",                      ["size"],                              False),
    ("material",                  ["material"],                          False),
    ("pattern",                   ["pattern"],                           False),
    ("gender",                    ["gender"],                            False),
    ("age_group",                 ["age_group"],                         False),

    # Inventario
    ("inventory",                 ["quantity", "inventory"],             False),
    ("quantity_to_sell_on_facebook", ["quantity"],                       False),

    # Disponibilità temporale
    ("availability_date",         ["availability_date"],                 False),
    ("expiration_date",           ["expiration_date"],                   False),

    # Spedizione & origine
    ("shipping_weight",           ["shipping_weight"],                   False),
    ("origin_country",            ["origin_country", "ships_from_country"], False),

    # Compliance EU GPSR (produttore & importatore)
    ("manufacturer_info",         ["manufacturer_info"],                 False),
    ("manufacturer_part_number",  ["mpn"],                               False),
    ("importer_name",             ["importer_name"],                     False),
    ("importer_address",          ["importer_address"],                  False),

    # Tasse Meta Commerce
    ("commerce_tax_category",     ["commerce_tax_category"],             False),

    # Custom labels & numbers
    ("custom_label_0",            ["custom_label_0"],                    False),
    ("custom_label_1",            ["custom_label_1"],                    False),
    ("custom_label_2",            ["custom_label_2"],                    False),
    ("custom_label_3",            ["custom_label_3"],                    False),
    ("custom_label_4",            ["custom_label_4"],                    False),
    ("custom_number_0",           ["custom_number_0"],                   False),
    ("custom_number_1",           ["custom_number_1"],                   False),
    ("custom_number_2",           ["custom_number_2"],                   False),
    ("custom_number_3",           ["custom_number_3"],                   False),
    ("custom_number_4",           ["custom_number_4"],                   False),

    # Status (Meta-specific: active / archived / staging)
    ("status",                    ["status"],                            False),
]

# Alias legacy per retrocompat: manteniamo META_EXTRA come subset
META_EXTRA = [
    ("rich_text_description",   ["rich_text_description", "description"]),
    ("short_description",       ["short_description", "description_meta_short", "description"]),
    ("inventory",               ["quantity"]),
    ("fb_product_category",     ["fb_product_category", "google_product_category"]),
]


# Token canonici interni = enum Google valido (underscore).
_GMC_AVAIL = {"in_stock", "out_of_stock", "preorder", "backorder"}


def _canon_availability(v) -> str:
    """Riduce qualsiasi input a un token canonico interno (underscore).

    Output ∈ {in_stock, out_of_stock, preorder, backorder}. Ambiguo/vuoto →
    out_of_stock (default conservativo: meglio non vendere che vendere sold-out).
    """
    s = str(v).lower().strip()
    if not s or s in ("nan", "none", "null"):
        return "out_of_stock"
    norm = s.replace("-", "_").replace(" ", "_")
    while "__" in norm:
        norm = norm.replace("__", "_")
    if norm in _GMC_AVAIL:
        return norm
    if "in_stock" in norm or norm in ("instock", "yes", "y", "si", "sì", "available",
                                       "disponibile", "disp", "true", "1"):
        return "in_stock"
    if ("preorder" in norm or "pre_order" in norm or "prevendita" in norm
            or "preordine" in norm):
        return "preorder"
    if ("available_for_order" in norm or "backorder" in norm or "back_order" in norm
            or "ordinazione" in norm or "riassort" in norm):
        return "backorder"
    if "discontinued" in norm or "fuori_produzione" in norm or "cessato" in norm:
        return "discontinued"  # token interno: Google→out_of_stock, Meta→discontinued
    return "out_of_stock"


def _normalize_availability_google(v) -> str:
    """Enum Google (underscore): in_stock/out_of_stock/preorder/backorder."""
    c = _canon_availability(v)
    # Google non ha 'discontinued' → degrada a out_of_stock.
    return c if c in _GMC_AVAIL else "out_of_stock"


# Token canonico → enum Meta (con spazio). Meta non ha 'backorder'.
_CANON_TO_META = {
    "in_stock":     "in stock",
    "out_of_stock": "out of stock",
    "preorder":     "preorder",
    "backorder":    "available for order",
    "discontinued": "discontinued",
}


def _normalize_availability_meta(v) -> str:
    """Enum Meta (spazio): 'in stock'/'out of stock'/'available for order'/'preorder'."""
    return _CANON_TO_META[_canon_availability(v)]


# Retrocompat: alcuni moduli/test importano ancora il vecchio nome.
_normalize_availability = _normalize_availability_google


def _normalize_condition(v: str) -> str:
    s = str(v).lower().strip()
    if "refurb" in s or "ricondizionato" in s:
        return "refurbished"
    if "used" in s or "usato" in s or "second" in s:
        return "used"
    return "new"


def _normalize_price(v: str, currency: str = "EUR") -> str:
    """Normalizza un prezzo nel formato GMC 'NNN.NN EUR'.

    Gestisce:
      - Valore vuoto / NA → ''
      - Multi-valore pipe/slash (es. '23.9 EUR | 5.90 EUR') → prende PRIMO
      - Stringhe con valuta (es. '23.90 EUR', '€23.90', 'EUR 23.90') → normalizza
      - Numeri puri (es. '23,90', '23.90') → formatta con valuta default
      - Migliaia con separatore (es. '1.234,56' IT o '1,234.56' US) → parse robusto
    """
    s = str(v).strip()
    if not s or s.lower() in ("nan", "none"):
        return ""

    # Multi-valore: pipe / slash / virgola-spazio — prendi SOLO il primo
    for sep in (" | ", "|", " / ", " // ", " - "):
        if sep in s:
            s = s.split(sep)[0].strip()
            break

    # Estrai la prima occorrenza numerica (gestisce '€23,90', 'EUR 23.90', '23.90 EUR')
    m = re.search(r"(-?\d[\d.,]*)", s)
    if not m:
        return ""
    raw = m.group(1)

    # Determina separatori decimali/migliaia
    if "," in raw and "." in raw:
        # Decidi quale è decimale (ultimo separatore)
        if raw.rfind(",") > raw.rfind("."):
            num = raw.replace(".", "").replace(",", ".")  # formato IT 1.234,56
        else:
            num = raw.replace(",", "")                     # formato US 1,234.56
    elif "," in raw:
        # "23,90" IT → 23.90; oppure "1,234" US (ma ambiguo — preferiamo IT)
        # Se ha 3 cifre dopo la virgola senza altro separatore, trattiamo come migliaia US
        frac = raw.rsplit(",", 1)[-1]
        if len(frac) == 3 and raw.count(",") == 1 and not raw.startswith("0"):
            num = raw.replace(",", "")
        else:
            num = raw.replace(",", ".")
    else:
        num = raw

    try:
        return f"{float(num):.2f} {currency}"
    except ValueError:
        return ""


def _truncate(text: str, max_len: int) -> str:
    text = str(text or "").strip()
    if len(text) <= max_len:
        return text
    return text[:max_len - 1].rsplit(" ", 1)[0] + "…"


def _coalesce(row: pd.Series, cols: list[str]) -> str:
    """Return first non-empty value from cols. Handles list/dict/NA safely.

    Kept for backward-compat. Vectorized fast path: use _coalesce_vec.
    """
    for c in cols:
        if c not in row.index:
            continue
        v = row[c]
        if isinstance(v, (list, tuple)):
            if len(v) == 0:
                continue
            return _json.dumps(list(v), ensure_ascii=False)
        if isinstance(v, dict):
            if not v:
                continue
            return _json.dumps(v, ensure_ascii=False)
        try:
            if pd.isna(v):
                continue
        except (TypeError, ValueError):
            pass
        s = str(v).strip()
        if s and s.lower() not in ("nan", "none", "null"):
            return s
    return ""


_INVALID_TOKENS = {"", "nan", "none", "null", "<na>"}


def _series_to_clean_str(s: pd.Series) -> pd.Series:
    """Vectorized: Series → stripped string, empty for NA/placeholder values.

    Handles object columns with occasional list/dict entries by JSON-encoding them.
    """
    # Detect object dtype with container entries — fall back to apply only for those
    if s.dtype == object:
        has_container = False
        for v in s.values[:min(len(s), 64)]:  # sample check
            if isinstance(v, (list, tuple, dict)):
                has_container = True
                break
        if has_container:
            def _one(v):
                if isinstance(v, (list, tuple)):
                    return _json.dumps(list(v), ensure_ascii=False) if len(v) else ""
                if isinstance(v, dict):
                    return _json.dumps(v, ensure_ascii=False) if v else ""
                if v is None:
                    return ""
                try:
                    if pd.isna(v):
                        return ""
                except (TypeError, ValueError):
                    pass
                return str(v).strip()
            out = s.map(_one).astype(object)
        else:
            out = s.where(s.notna(), "").astype(str).str.strip()
    else:
        out = s.where(s.notna(), "").astype(str).str.strip()

    # Mask placeholders
    lower = out.str.lower()
    out = out.mask(lower.isin(_INVALID_TOKENS), "")
    return out


def _coalesce_vec(df: pd.DataFrame, cols: list[str]) -> pd.Series:
    """Vectorized coalesce across priority columns. Returns Series of stripped strings."""
    out = pd.Series("", index=df.index, dtype=object)
    if not cols:
        return out
    empty_mask = out.eq("")
    for c in cols:
        if c not in df.columns:
            continue
        if not empty_mask.any():
            break
        cand = _series_to_clean_str(df[c])
        fill = empty_mask & cand.ne("")
        if fill.any():
            out = out.mask(fill, cand)
            empty_mask = out.eq("")
    return out


def build_google_feed(df: pd.DataFrame, currency: str = "EUR") -> pd.DataFrame:
    """Genera DataFrame conforme a Google Merchant Center con normalizzazioni."""
    out = pd.DataFrame(index=df.index)
    for target, sources, _, _ in GOOGLE_FIELDS:
        if target == "identifier_exists":
            continue
        out[target] = _coalesce_vec(df, sources) if sources else ""

    # normalizzazioni
    out["availability"] = out["availability"].map(_normalize_availability_google)
    out["condition"] = out["condition"].map(_normalize_condition)
    out["price"] = out["price"].map(lambda v: _normalize_price(v, currency))
    out["sale_price"] = out["sale_price"].map(lambda v: _normalize_price(v, currency) if v else "")
    # title 70-150
    out["title"] = out["title"].map(lambda v: _truncate(v, 150))
    # description 500-5000
    out["description"] = out["description"].map(lambda v: _truncate(v, 5000))
    # identifier_exists — vectorizzato
    has_id = out["gtin"].astype(str).str.strip().ne("") | out["mpn"].astype(str).str.strip().ne("")
    out["identifier_exists"] = np.where(has_id, "yes", "no")
    # column order
    cols = [t for t, _, _, _ in GOOGLE_FIELDS]
    out = out[cols]
    return out


def build_meta_feed(df: pd.DataFrame, currency: str = "EUR") -> pd.DataFrame:
    """Genera DataFrame conforme a Meta Catalog usando i nomi ufficiali Meta Commerce.

    Le colonne seguono la spec Meta: title (fino 200 char), description (fino 9999),
    short_description (fino 200), rich_text_description (HTML), fb_product_category,
    origin_country, manufacturer_info, importer_name/address (EU GPSR),
    commerce_tax_category, custom_number_0..4, status, video.
    """
    out = pd.DataFrame(index=df.index)

    # Popola tutti i campi Meta nell'ordine della spec
    for target, srcs, _req in META_FIELDS:
        if not srcs:
            out[target] = ""
            continue
        out[target] = _coalesce_vec(df, srcs)

    # Normalizzazioni (stessa logica di Google dove applicabile)
    out["availability"] = out["availability"].map(_normalize_availability_meta)
    out["condition"] = out["condition"].map(_normalize_condition)
    out["price"] = out["price"].map(lambda v: _normalize_price(v, currency))
    if "sale_price" in out.columns:
        out["sale_price"] = out["sale_price"].map(
            lambda v: _normalize_price(v, currency) if v else ""
        )

    # Troncamenti Meta-specifici (limiti ufficiali Meta Commerce Manager)
    out["title"] = out["title"].map(lambda v: _truncate(v, 200))
    out["description"] = out["description"].map(lambda v: _truncate(v, 9999))
    if "short_description" in out.columns:
        out["short_description"] = out["short_description"].map(lambda v: _truncate(v, 200))

    # Status: default 'active' se assente
    if "status" in out.columns:
        out["status"] = out["status"].apply(
            lambda v: str(v).strip().lower() if str(v).strip() else "active"
        )
        out["status"] = out["status"].where(
            out["status"].isin(["active", "archived", "staging"]), "active"
        )

    # manufacturer_part_number = mpn se vuoto (EU GPSR richiede)
    if "manufacturer_part_number" in out.columns and "mpn" in out.columns:
        mask = out["manufacturer_part_number"].astype(str).str.strip().eq("")
        out.loc[mask, "manufacturer_part_number"] = out.loc[mask, "mpn"]

    return out


def validate_feed(df: pd.DataFrame, target: str = "google") -> pd.DataFrame:
    """Ritorna un DataFrame con righe = campo, colonne = errori/warning."""
    # Meta usa META_FIELDS (nomi ufficiali Meta), Google usa GOOGLE_FIELDS
    if target == "meta":
        # normalizza META_FIELDS al formato (target, srcs, gmc_req, meta_req)
        spec = [(t, s, False, req) for t, s, req in META_FIELDS]
    else:
        spec = GOOGLE_FIELDS
    rows = []
    n = len(df)
    for t, _, gmc_req, meta_req in spec:
        if t not in df.columns:
            rows.append({"campo": t, "richiesto": gmc_req if target == "google" else meta_req,
                         "stato": "MISSING_COLUMN", "compilazione_%": 0})
            continue
        filled = df[t].astype(str).str.strip().ne("").sum()
        pct = round(filled / n * 100, 1) if n else 0
        req = gmc_req if target == "google" else meta_req
        if req and pct < 100:
            stato = "ERROR" if pct < 90 else "WARN"
        else:
            stato = "OK"
        rows.append({"campo": t, "richiesto": req, "stato": stato, "compilazione_%": pct})
    return pd.DataFrame(rows)


def title_quality_check(df: pd.DataFrame, title_col: str = "title") -> pd.DataFrame:
    """Analizza la qualità dei titoli con metriche tipo GMC."""
    titles = df[title_col].astype(str)
    return pd.DataFrame({
        "title_len_avg": [titles.str.len().mean()],
        "title_len_min": [titles.str.len().min()],
        "title_len_max": [titles.str.len().max()],
        "too_short_<40": [(titles.str.len() < 40).sum()],
        "ideal_70_150": [titles.str.len().between(70, 150).sum()],
        "too_long_>150": [(titles.str.len() > 150).sum()],
        "all_caps": [titles.apply(lambda t: t.isupper() and len(t) > 5).sum()],
        "duplicates": [titles.duplicated().sum()],
    })


# ============================================================
# STATUS EXPORT PER-PRODOTTO (3 livelli: grezzo/arricchito/pronto_export)
# ============================================================
# Asse ORTOGONALE a `_enrichment_status` (esito chiamata AI). Qui calcoliamo
# se un prodotto è "pronto per l'export GMC" verificando i required §3 spec.
# La fonte di verità per gli enum availability/condition resta build_*_feed:
# qui ri-normalizziamo on-the-fly così lo status è coerente anche su df grezzi.

# Regex prezzo GMC valido: 'NNN.NN EUR' (valore + valuta ISO).
_PRICE_RE = re.compile(r"^\d+(\.\d{1,2})?\s[A-Z]{3}$")
_COND_ENUM = {"new", "refurbished", "used"}
# Attributi AI: almeno uno popolato per considerare il prodotto "arricchito".
_AI_ATTRS = [
    "brand", "color", "size", "material", "pattern", "gender", "age_group",
    "product_highlight", "product_detail", "product_type",
]


def _status_g(row, col: str) -> str:
    """Safe-get da una riga (Series/dict): NaN/placeholder → '' senza crash."""
    try:
        if col not in row:
            return ""
    except TypeError:
        return ""
    v = row[col]
    try:
        if pd.isna(v):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(v).strip()
    return "" if s.lower() in ("nan", "none", "null", "<na>") else s


def _status_is_url(s: str, schemes: tuple[str, ...] = ("http://", "https://")) -> bool:
    return s.startswith(schemes)


def _category_valid(s: str) -> tuple[bool, bool]:
    """(valida, sospetta) per google_product_category.

    Valida se path con '>' o ID numerico; sospetta se single-token testuale.
    """
    if not s:
        return (False, False)
    if ">" in s or s.isdigit():
        return (True, False)
    return (True, True)


def compute_export_status(row) -> tuple[str, bool, list[str]]:
    """Calcola (level, export_ready, missing) per una riga prodotto.

    - level ∈ {grezzo, arricchito, pronto_export}
    - export_ready: True se nessun campo BLOCCA manca/è invalido
    - missing: lista leggibile dei problemi (BLOCCA + AVVISA)

    L'asse errore/da-rivedere resta su `_enrichment_status` (badge §5).
    Tollera colonne assenti e NaN senza sollevare eccezioni.
    """
    from utils.validation import is_valid_gtin

    missing: list[str] = []
    status = _status_g(row, "_enrichment_status").lower()
    title = _status_g(row, "title")
    desc = _status_g(row, "description")
    cat = _status_g(row, "google_product_category")
    title_o = _status_g(row, "title_original")
    desc_o = _status_g(row, "description_original")
    cat_ok, cat_suspect = _category_valid(cat)

    # Testo riscritto: title/desc presenti e diversi dagli originali (se noti).
    text_rewritten = (
        bool(title) and bool(desc)
        and not (title == title_o and desc == desc_o and title_o != "")
    )
    is_arricchito = (
        status in ("ok", "cached") and title and desc and cat_ok and cat
        and any(_status_g(row, a) for a in _AI_ATTRS) and text_rewritten
    )
    if not is_arricchito:
        return ("grezzo", False, [])

    # --- da qui: prodotto ARRICCHITO, verifica required GMC §3 ---
    blocking = 0
    _id = _status_g(row, "id")
    if not _id:
        missing.append("id assente"); blocking += 1
    elif len(_id) > 50:
        missing.append("id troppo lungo (>50)"); blocking += 1
    if not title:
        missing.append("title assente"); blocking += 1
    elif len(title) > 150:
        missing.append("title >150 char"); blocking += 1
    elif len(title) < 30:
        missing.append("title troppo corto (<30)")  # AVVISA
    if not desc:
        missing.append("description assente"); blocking += 1
    link = _status_g(row, "link")
    if not link:
        missing.append("link assente"); blocking += 1
    elif not _status_is_url(link):
        missing.append("link non valido (no http/https)"); blocking += 1
    img = _status_g(row, "image_link")
    if not img:
        missing.append("image_link assente"); blocking += 1
    elif not _status_is_url(img, ("https://",)):
        missing.append("image_link non https"); blocking += 1
    # availability: BLOCCA se assente (la normalizzazione per-target avviene
    # comunque a valle, ma un valore mancante non deve passare per "pronto").
    if not _status_g(row, "availability"):
        missing.append("availability assente"); blocking += 1
    # condition: _normalize_condition ritorna sempre un enum valido (default new),
    # quindi BLOCCA solo se la colonna è del tutto assente.
    if not _status_g(row, "condition"):
        missing.append("condition assente"); blocking += 1
    price = _status_g(row, "price")
    if not price:
        missing.append("price assente"); blocking += 1
    elif not _PRICE_RE.match(price):
        missing.append("price formato non valido"); blocking += 1
    else:
        try:
            if float(price.split()[0]) <= 0:
                missing.append("price = 0"); blocking += 1
        except ValueError:
            missing.append("price formato non valido"); blocking += 1
    if not cat:
        missing.append("google_product_category assente"); blocking += 1
    elif cat_suspect:
        missing.append("google_product_category path sospetto")  # AVVISA
    if not _status_g(row, "brand"):
        missing.append("brand assente"); blocking += 1
    gtin = _status_g(row, "gtin")
    mpn = _status_g(row, "mpn")
    if not gtin and not mpn:
        missing.append("identificatori assenti (gtin/mpn) — identifier_exists=no")  # AVVISA
    elif gtin and not is_valid_gtin(gtin):
        missing.append("gtin checksum non valido")  # AVVISA

    export_ready = (blocking == 0)
    return ("pronto_export" if export_ready else "arricchito", export_ready, missing)


def add_export_status_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge `_export_level`, `_export_ready` (bool) e `_missing_fields` (list).

    Applica `compute_export_status` per riga. Non crasha su df vuoto o con
    colonne mancanti: ritorna una copia con le colonne valorizzate.
    """
    out = df.copy()
    if out.empty:
        out["_export_level"] = pd.Series(dtype=object)
        out["_export_ready"] = pd.Series(dtype=bool)
        out["_missing_fields"] = pd.Series(dtype=object)
        return out

    levels: list[str] = []
    ready: list[bool] = []
    missing: list[list[str]] = []
    for _, row in out.iterrows():
        lvl, rdy, miss = compute_export_status(row)
        levels.append(lvl)
        ready.append(rdy)
        missing.append(miss)
    out["_export_level"] = levels
    out["_export_ready"] = ready
    out["_missing_fields"] = missing
    return out
