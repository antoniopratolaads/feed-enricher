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
import re

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


def _normalize_availability(v: str) -> str:
    s = str(v).lower().strip()
    if not s or s in ("nan", "none"):
        return "out of stock"
    if "in stock" in s or "in_stock" in s or s in ("yes", "available", "disponibile"):
        return "in stock"
    if "preorder" in s or "pre-order" in s or "pre_order" in s:
        return "preorder"
    if "backorder" in s:
        return "backorder"
    return "out of stock"


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
    """Return first non-empty value from cols. Handles list/dict/NA safely."""
    for c in cols:
        if c not in row.index:
            continue
        v = row[c]
        # Liste / array / dict: vuoti → skip, pieni → serializza JSON
        if isinstance(v, (list, tuple)):
            if len(v) == 0:
                continue
            import json as _json
            return _json.dumps(v, ensure_ascii=False)
        if isinstance(v, dict):
            if not v:
                continue
            import json as _json
            return _json.dumps(v, ensure_ascii=False)
        # Scalare: check NA
        try:
            if pd.isna(v):
                continue
        except (TypeError, ValueError):
            pass
        s = str(v).strip()
        if s and s.lower() not in ("nan", "none", "null"):
            return s
    return ""


def build_google_feed(df: pd.DataFrame, currency: str = "EUR") -> pd.DataFrame:
    """Genera DataFrame conforme a Google Merchant Center con normalizzazioni."""
    out = pd.DataFrame(index=df.index)
    for target, sources, _, _ in GOOGLE_FIELDS:
        if target == "identifier_exists":
            continue
        out[target] = df.apply(lambda r: _coalesce(r, sources), axis=1) if sources else ""

    # normalizzazioni
    out["availability"] = out["availability"].map(_normalize_availability)
    out["condition"] = out["condition"].map(_normalize_condition)
    out["price"] = out["price"].map(lambda v: _normalize_price(v, currency))
    out["sale_price"] = out["sale_price"].map(lambda v: _normalize_price(v, currency) if v else "")
    # title 70-150
    out["title"] = out["title"].map(lambda v: _truncate(v, 150))
    # description 500-5000
    out["description"] = out["description"].map(lambda v: _truncate(v, 5000))
    # identifier_exists
    out["identifier_exists"] = out.apply(
        lambda r: "no" if not r["gtin"] and not r["mpn"] else "yes", axis=1
    )
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
        out[target] = df.apply(lambda r: _coalesce(r, srcs), axis=1)

    # Normalizzazioni (stessa logica di Google dove applicabile)
    out["availability"] = out["availability"].map(_normalize_availability)
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
