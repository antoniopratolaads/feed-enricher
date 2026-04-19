"""Parser multi-formato per feed prodotto (Google Merchant XML, CSV, TSV, JSON)."""
from __future__ import annotations

import io
import json
from typing import Optional

import pandas as pd
import requests
from lxml import etree

GMC_NS = {
    "g": "http://base.google.com/ns/1.0",
    "atom": "http://www.w3.org/2005/Atom",
}

# Campi canonici Google Merchant Center di uso comune
CANONICAL_FIELDS = [
    "id", "title", "description", "link", "image_link", "additional_image_link",
    "availability", "price", "sale_price", "brand", "gtin", "mpn", "condition",
    "google_product_category", "product_type", "color", "size", "material",
    "gender", "age_group", "pattern", "item_group_id", "shipping", "tax",
    "custom_label_0", "custom_label_1", "custom_label_2", "custom_label_3", "custom_label_4",
]


def _download(url: str, timeout: int = 60) -> bytes:
    headers = {"User-Agent": "Mozilla/5.0 FeedEnricher/1.0"}
    r = requests.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return r.content


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse_xml_feed(content: bytes) -> pd.DataFrame:
    """Parse Google Merchant XML (RSS 2.0 o Atom)."""
    parser = etree.XMLParser(recover=True, huge_tree=True)
    root = etree.fromstring(content, parser=parser)

    # RSS: channel/item, Atom: entry
    items = root.findall(".//item") or root.findall(".//atom:entry", GMC_NS) or root.findall(".//entry")

    rows = []
    for it in items:
        row = {}
        for child in it.iter():
            tag = _strip_ns(child.tag)
            if tag in ("item", "entry"):
                continue
            text = (child.text or "").strip()
            if not text:
                continue
            # se duplicato, accumula separato da " | "
            if tag in row and row[tag] != text:
                row[tag] = f"{row[tag]} | {text}"
            else:
                row[tag] = text
        if row:
            rows.append(row)

    df = pd.DataFrame(rows)
    return df


def parse_csv_feed(content: bytes, sep: Optional[str] = None) -> pd.DataFrame:
    buf = io.BytesIO(content)
    if sep:
        return pd.read_csv(buf, sep=sep, dtype=str).fillna("")
    # autodetect
    for s in ["\t", ",", ";", "|"]:
        try:
            buf.seek(0)
            df = pd.read_csv(buf, sep=s, dtype=str, engine="python")
            if df.shape[1] > 1:
                return df.fillna("")
        except Exception:
            continue
    buf.seek(0)
    return pd.read_csv(buf, dtype=str).fillna("")


def parse_excel_feed(content: bytes, sheet_name=0) -> pd.DataFrame:
    """Parse .xlsx / .xls feed. Sheet 0 di default, oppure nome/indice specifico."""
    return pd.read_excel(io.BytesIO(content), sheet_name=sheet_name, dtype=str).fillna("")


def list_excel_sheets(content: bytes) -> list[str]:
    """Ritorna i nomi dei fogli in un file Excel (per scegliere)."""
    xl = pd.ExcelFile(io.BytesIO(content))
    return xl.sheet_names


def parse_json_feed(content: bytes) -> pd.DataFrame:
    data = json.loads(content)
    if isinstance(data, dict):
        for key in ("items", "products", "data", "entries"):
            if key in data and isinstance(data[key], list):
                data = data[key]
                break
    return pd.DataFrame(data).fillna("")


def load_feed(source: str | bytes, filename: str = "") -> pd.DataFrame:
    """Carica feed da URL o bytes. Rileva il formato."""
    if isinstance(source, str) and source.startswith(("http://", "https://")):
        content = _download(source)
        filename = source.lower()
    else:
        content = source if isinstance(source, bytes) else source.read()
        filename = filename.lower()

    head = content[:512].lstrip().lower() if isinstance(content, bytes) else b""

    if filename.endswith((".xlsx", ".xls", ".xlsm")):
        return parse_excel_feed(content)
    if head.startswith(b"<") or filename.endswith(".xml") or b"<rss" in head or b"<feed" in head:
        return parse_xml_feed(content)
    if head.startswith(b"{") or head.startswith(b"[") or filename.endswith(".json"):
        return parse_json_feed(content)
    return parse_csv_feed(content)


# Alias comuni → nome standard GMC.
# Coprono export Shopify, WooCommerce, Magento, PrestaShop, italiano/inglese.
COLUMN_ALIASES = {
    # ID
    "id": ["product_id", "sku", "variant_sku", "handle", "item_id", "shopify_variant_id",
           "id_prodotto", "codice", "codice_articolo", "reference", "ref"],
    # Title
    "title": ["name", "product_name", "product_title", "nome", "nome_prodotto",
              "titolo", "titolo_del_prodotto"],
    # Description
    "description": ["body_html", "body", "long_description", "descrizione",
                    "description_html", "short_description", "summary", "descrizione_lunga"],
    # Link
    "link": ["url", "product_url", "permalink", "page_url", "shop_url"],
    # Image
    "image_link": ["image", "image_src", "image_url", "main_image", "immagine",
                   "immagine_principale", "photo", "foto", "img"],
    "additional_image_link": ["additional_images", "image_2", "image_3",
                              "immagini_aggiuntive", "gallery"],
    # Availability
    "availability": ["stock_status", "in_stock", "disponibilita", "disponibilità",
                     "availability_status"],
    # Price
    "price": ["variant_price", "regular_price", "prezzo", "prezzo_listino",
              "list_price", "msrp"],
    "sale_price": ["variant_sale_price", "discounted_price", "promo_price",
                   "prezzo_scontato", "prezzo_promo"],
    # Identifiers
    "gtin": ["ean", "ean13", "barcode", "variant_barcode", "upc", "isbn"],
    "mpn": ["model", "manufacturer_part_number", "sku_produttore", "codice_produttore",
            "ref_produttore"],
    # Brand
    "brand": ["vendor", "manufacturer", "marchio", "marca", "produttore"],
    # Category
    "google_product_category": ["google_category", "gmc_category", "category_google"],
    "product_type": ["category", "categoria", "tipo_prodotto", "type", "categories"],
    # Attributes
    "color": ["colore", "colour", "variant_color", "option1_color"],
    "size": ["taglia", "misura", "variant_size", "option2_size", "volume", "weight",
             "peso", "capacita", "capacità"],
    "material": ["materiale", "fabric", "tessuto", "composition", "composizione"],
    "pattern": ["fantasia", "design", "print", "stampa"],
    "gender": ["genere", "sesso", "for_gender"],
    "age_group": ["age_range", "fascia_eta", "fascia_età", "target_age"],
    # Inventory
    "quantity": ["variant_inventory_qty", "stock", "stock_quantity", "qty",
                 "scorta", "giacenza", "magazzino"],
    "cost_of_goods": ["variant_cost", "cost", "costo", "costo_acquisto", "cogs"],
    # Condition
    "condition": ["condizione", "stato", "product_condition"],
}


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Normalizza i nomi colonna al formato canonical GMC + applica alias intelligenti."""
    # 1. lowercase + remove namespace + spaces/dashes → underscore
    rename = {}
    for c in df.columns:
        low = c.lower().strip()
        low = low.replace("g:", "").replace(" ", "_").replace("-", "_")
        rename[c] = low
    df = df.rename(columns=rename)

    # 2. inverti il mapping per lookup rapido (alias → standard)
    alias_to_std = {}
    for std, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            alias_to_std[alias] = std

    # 3. applica aliases SOLO se la colonna standard non esiste già
    final_rename = {}
    existing = set(df.columns)
    for col in df.columns:
        if col in alias_to_std:
            std = alias_to_std[col]
            if std not in existing:
                final_rename[col] = std
                existing.add(std)
                existing.discard(col)
    if final_rename:
        df = df.rename(columns=final_rename)

    return df


def get_alias_report(df: pd.DataFrame) -> list[dict]:
    """Genera un report di quali alias sono stati riconosciuti, per UI feedback."""
    alias_to_std = {}
    for std, aliases in COLUMN_ALIASES.items():
        for alias in aliases:
            alias_to_std[alias] = std
    report = []
    for col in df.columns:
        std = alias_to_std.get(col)
        if std and std != col:
            report.append({"originale": col, "mappato_a": std})
    return report
