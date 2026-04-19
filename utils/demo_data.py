"""Generatore di dataset demo realistici: catalogo + Google Ads + Shopify."""
from __future__ import annotations
import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

random.seed(42)
np.random.seed(42)

BRANDS = [
    ("Nike", "Apparel & Accessories > Shoes"),
    ("Adidas", "Apparel & Accessories > Shoes"),
    ("Puma", "Apparel & Accessories > Clothing"),
    ("Levi's", "Apparel & Accessories > Clothing > Pants"),
    ("Ray-Ban", "Apparel & Accessories > Sunglasses"),
    ("Apple", "Electronics > Phones"),
    ("Samsung", "Electronics > Phones"),
    ("Sony", "Electronics > Audio > Headphones"),
    ("Bose", "Electronics > Audio > Headphones"),
    ("Dyson", "Home & Garden > Household Appliances"),
    ("KitchenAid", "Home & Garden > Kitchen"),
    ("Lego", "Toys & Games"),
    ("Fjallraven", "Apparel & Accessories > Bags"),
    ("Patagonia", "Apparel & Accessories > Outerwear"),
    ("North Face", "Apparel & Accessories > Outerwear"),
]

PRODUCT_TEMPLATES = {
    "Shoes": [("Sneaker {model}", ["Air Max", "Ultraboost", "Suede", "RS-X", "Cortez", "Gel-Lyte"]),
              ("Scarpa running {model}", ["Pegasus", "Vaporfly", "Solar Glide", "Velocity"])],
    "Clothing": [("T-shirt {model}", ["Classic", "Vintage", "Oversize", "Slim Fit", "Boxy"]),
                 ("Felpa {model}", ["Hoodie", "Crewneck", "Zip", "Tech Fleece"])],
    "Pants": [("Jeans {model}", ["501", "511", "Skinny", "Mom Fit", "Bootcut", "Cargo"])],
    "Sunglasses": [("Occhiali {model}", ["Aviator", "Wayfarer", "Clubmaster", "Round", "Hexagonal"])],
    "Phones": [("Smartphone {model}", ["Pro 15", "Galaxy S24", "Pixel 8", "Edge 50"])],
    "Headphones": [("Cuffie {model}", ["WH-1000XM5", "QC45", "Buds Pro", "AirPods"])],
    "Appliances": [("Aspirapolvere {model}", ["V15", "V12", "Outsize", "Omni"])],
    "Kitchen": [("Impastatrice {model}", ["Artisan", "Pro 600", "Mini", "Classic"])],
    "Toys & Games": [("Set {model}", ["City", "Star Wars", "Technic", "Friends", "Architecture"])],
    "Bags": [("Zaino {model}", ["Kanken", "Greenland", "Raven", "Tote"])],
    "Outerwear": [("Giacca {model}", ["Down", "Nano Puff", "Torrentshell", "Denali", "Apex"])],
}

COLORS = ["nero", "bianco", "blu navy", "grigio", "rosso", "verde militare", "beige", "rosa", "giallo", ""]
SIZES_CLOTHING = ["XS", "S", "M", "L", "XL", "XXL"]
SIZES_SHOES = ["38", "39", "40", "41", "42", "43", "44", "45"]
MATERIALS = ["cotone", "poliestere", "pelle", "nylon", "lana", "alluminio", "vetro", ""]


def _category_key(cat: str) -> str:
    last = cat.split(">")[-1].strip()
    return last if last in PRODUCT_TEMPLATES else cat.split(">")[1].strip() if ">" in cat else "Clothing"


def generate_feed(n: int = 500) -> pd.DataFrame:
    rows = []
    for i in range(n):
        brand, cat = random.choice(BRANDS)
        catkey = _category_key(cat)
        templates = PRODUCT_TEMPLATES.get(catkey, PRODUCT_TEMPLATES["Clothing"])
        template, models = random.choice(templates)
        model = random.choice(models)
        title = f"{brand} {template.format(model=model)}"

        # ~30% titoli "poveri" per dimostrare l'enrichment
        if random.random() < 0.30:
            title = brand + " " + model

        color = random.choice(COLORS)
        size = random.choice(SIZES_SHOES if "Shoe" in cat else SIZES_CLOTHING) if random.random() > 0.2 else ""
        material = random.choice(MATERIALS)

        price = round(np.random.lognormal(mean=4.0, sigma=0.7), 2)
        price = max(9.99, min(price, 1500))
        on_sale = random.random() < 0.25
        sale_price = round(price * random.uniform(0.5, 0.85), 2) if on_sale else ""

        in_stock = random.random() > 0.12
        qty = random.randint(0, 80) if in_stock else 0

        # ~20% senza descrizione, ~10% senza categoria GMC, ~5% senza immagine
        desc = ""
        if random.random() > 0.20:
            desc = f"{title} - {color} - {material if material else 'qualità premium'}. " \
                   f"Disponibile in varie taglie. Spedizione rapida e reso gratuito."
        gmc_cat = cat if random.random() > 0.10 else ""
        img = f"https://cdn.example.com/p/{i:05d}.jpg" if random.random() > 0.05 else ""

        added_days_ago = int(np.random.exponential(scale=120))
        date_added = (datetime.now() - timedelta(days=added_days_ago)).strftime("%Y-%m-%d")

        rows.append({
            "id": f"SKU-{i:05d}",
            "title": title,
            "description": desc,
            "link": f"https://shop.example.com/p/{i:05d}",
            "image_link": img,
            "availability": "in stock" if in_stock else "out of stock",
            "price": f"{price} EUR",
            "sale_price": f"{sale_price} EUR" if sale_price else "",
            "brand": brand,
            "gtin": f"{random.randint(10**12, 10**13-1)}" if random.random() > 0.3 else "",
            "mpn": f"MPN-{random.randint(1000,99999)}",
            "condition": "new",
            "google_product_category": gmc_cat,
            "product_type": cat,
            "color": color if random.random() > 0.4 else "",
            "size": size,
            "material": material if random.random() > 0.5 else "",
            "date_added": date_added,
            "quantity": qty,
        })
    return pd.DataFrame(rows)


def generate_gads(feed_df: pd.DataFrame, coverage: float = 0.65) -> pd.DataFrame:
    """Genera performance Google Ads per ~65% dei prodotti."""
    rows = []
    sample = feed_df.sample(frac=coverage, random_state=42)
    for _, p in sample.iterrows():
        # impressions distribuite log-normal, click ~CTR 1-4%, conv ~CVR 0.5-3%
        impressions = int(np.random.lognormal(6.5, 1.2))
        ctr = np.random.uniform(0.005, 0.06)
        clicks = int(impressions * ctr)
        # ~15% sono "zombie" (alti click, 0 conv)
        is_zombie = random.random() < 0.15 and clicks > 30
        cvr = 0 if is_zombie else np.random.uniform(0, 0.04)
        conv = round(clicks * cvr, 2)
        # CPC log-normal
        cpc = round(np.random.lognormal(-0.5, 0.4), 2)
        cost = round(clicks * cpc, 2)
        # AOV ~50€ + variazione, ~25% chance high-value
        aov = np.random.uniform(20, 200) * (3 if random.random() < 0.1 else 1)
        conv_value = round(conv * aov, 2)

        rows.append({
            "product_id": p["id"],
            "title": p["title"],
            "brand": p["brand"],
            "impressions": impressions,
            "clicks": clicks,
            "cost": cost,
            "conversions": conv,
            "conv_value": conv_value,
            "ctr": round(ctr, 4),
            "cpc": cpc,
            "cvr": round(cvr, 4),
            "roas": round(conv_value / cost, 2) if cost else 0,
        })
    return pd.DataFrame(rows)


def generate_shopify_sales(feed_df: pd.DataFrame, coverage: float = 0.70) -> pd.DataFrame:
    sample = feed_df.sample(frac=coverage, random_state=24)
    rows = []
    for _, p in sample.iterrows():
        # Pareto: pochi prodotti vendono molto
        units = int(np.random.pareto(1.5) * 3)
        if random.random() < 0.25:  # 25% bestseller boost
            units = int(units * np.random.uniform(3, 10))
        units = max(0, min(units, 500))
        price_num = float(str(p["price"]).split()[0])
        revenue = round(units * price_num * np.random.uniform(0.85, 1.0), 2)
        rows.append({
            "id": p["id"],
            "title": p["title"],
            "units_sold": units,
            "revenue": revenue,
        })
    return pd.DataFrame(rows)


def generate_shopify_inventory(feed_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, p in feed_df.iterrows():
        price_num = float(str(p["price"]).split()[0])
        # COGS ~ 30-65% del prezzo
        margin_pct = np.random.uniform(0.30, 0.65)
        cogs = round(price_num * (1 - margin_pct), 2)
        rows.append({
            "id": p["id"],
            "variant_cost": cogs,
            "variant_inventory_qty": p["quantity"],
        })
    return pd.DataFrame(rows)


def generate_shopify_views(feed_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, p in feed_df.iterrows():
        views = int(np.random.lognormal(4.5, 1.5))
        rows.append({"id": p["id"], "views": views})
    return pd.DataFrame(rows)


def generate_full_demo(n_products: int = 500) -> dict:
    """Genera tutti i dataset e li ritorna come dict."""
    feed = generate_feed(n_products)
    gads = generate_gads(feed)
    sales = generate_shopify_sales(feed)
    inv = generate_shopify_inventory(feed)
    views = generate_shopify_views(feed)
    return {
        "feed": feed,
        "gads": gads,
        "shopify_sales": sales,
        "shopify_inventory": inv,
        "shopify_views": views,
    }


def load_demo_into_session(st_session, n: int = 500):
    """Carica dati demo direttamente in session_state e fa già il merge."""
    data = generate_full_demo(n)
    feed = data["feed"]
    gads = data["gads"]

    metric_cols = ["impressions", "clicks", "cost", "conversions", "conv_value", "ctr", "cpc", "cvr", "roas"]
    merged = feed.merge(
        gads[["product_id"] + metric_cols].rename(columns={"product_id": "id"}),
        on="id", how="left"
    )
    for c in metric_cols:
        merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0)

    # shopify sales
    s = data["shopify_sales"].rename(columns={"units_sold": "shopify_units_sold", "revenue": "shopify_revenue"})
    merged = merged.merge(s[["id", "shopify_units_sold", "shopify_revenue"]], on="id", how="left")
    merged["shopify_units_sold"] = merged["shopify_units_sold"].fillna(0)
    merged["shopify_revenue"] = merged["shopify_revenue"].fillna(0)

    # shopify inventory
    inv = data["shopify_inventory"].rename(columns={"variant_cost": "cost_of_goods"})
    merged = merged.merge(inv[["id", "cost_of_goods"]], on="id", how="left")

    # shopify views
    v = data["shopify_views"].rename(columns={"views": "shopify_views"})
    merged = merged.merge(v[["id", "shopify_views"]], on="id", how="left")
    merged["shopify_views"] = merged["shopify_views"].fillna(0)

    st_session["raw_df"] = feed.copy()
    st_session["feed_df"] = feed.copy()
    st_session["gads_df"] = gads.copy()
    st_session["merged_df"] = merged
    st_session["feed_source"] = f"demo_data_{n}_products"
    return data, merged
