"""Logiche di calcolo per custom_label (performance, margine, stagionalità, stock)."""
from __future__ import annotations

import pandas as pd
import numpy as np


# ---------- PERFORMANCE (da dati Google Ads) ----------

def label_performance(
    df: pd.DataFrame,
    roas_high: float = 4.0,
    roas_low: float = 1.5,
    min_clicks_zombie: int = 30,
) -> pd.Series:
    """Richiede colonne: clicks, cost, conversions, conv_value (da GAds)."""
    clicks = pd.to_numeric(df.get("clicks", 0), errors="coerce").fillna(0)
    cost = pd.to_numeric(df.get("cost", 0), errors="coerce").fillna(0)
    conv = pd.to_numeric(df.get("conversions", 0), errors="coerce").fillna(0)
    val = pd.to_numeric(df.get("conv_value", 0), errors="coerce").fillna(0)

    roas = np.where(cost > 0, val / cost, 0)

    labels = np.where(clicks == 0, "no_clicks",
             np.where((clicks >= min_clicks_zombie) & (conv == 0), "zombie",
             np.where(roas >= roas_high, "high_roas",
             np.where(roas >= roas_low, "mid_roas",
             np.where(roas > 0, "low_roas", "no_conv")))))
    return pd.Series(labels, index=df.index)


# ---------- MARGINE / PREZZO ----------

def _to_price(s):
    """Converte '19.99 EUR' → 19.99."""
    return pd.to_numeric(
        s.astype(str).str.extract(r"([\d]+[.,]?[\d]*)")[0].str.replace(",", "."),
        errors="coerce",
    )


def label_price_bucket(df: pd.DataFrame, price_col: str = "price", n_buckets: int = 5) -> pd.Series:
    p = _to_price(df[price_col])
    try:
        cuts = pd.qcut(p, q=n_buckets, labels=[f"price_q{i+1}" for i in range(n_buckets)], duplicates="drop")
        return cuts.astype(str).fillna("price_na")
    except Exception:
        return pd.Series(["price_na"] * len(df), index=df.index)


def label_margin(
    df: pd.DataFrame,
    cost_col: str = "cost_of_goods",
    price_col: str = "price",
    high_margin: float = 0.50,
    low_margin: float = 0.20,
) -> pd.Series:
    if cost_col not in df.columns:
        return pd.Series(["margin_na"] * len(df), index=df.index)
    price = _to_price(df[price_col])
    cost = pd.to_numeric(df[cost_col], errors="coerce")
    margin = (price - cost) / price.replace(0, np.nan)
    labels = np.where(margin.isna(), "margin_na",
             np.where(margin >= high_margin, "margin_high",
             np.where(margin >= low_margin, "margin_mid", "margin_low")))
    return pd.Series(labels, index=df.index)


# ---------- STAGIONALITÀ / FRESHNESS ----------

def label_freshness(
    df: pd.DataFrame,
    date_col: str = "date_added",
    new_days: int = 30,
) -> pd.Series:
    if date_col not in df.columns:
        return pd.Series(["freshness_na"] * len(df), index=df.index)
    d = pd.to_datetime(df[date_col], errors="coerce")
    days = (pd.Timestamp.now() - d).dt.days
    labels = np.where(d.isna(), "freshness_na",
             np.where(days <= new_days, "new_arrival",
             np.where(days <= 180, "recent", "evergreen")))
    return pd.Series(labels, index=df.index)


def label_bestseller(df: pd.DataFrame, conv_col: str = "conversions", top_pct: float = 0.20) -> pd.Series:
    if conv_col not in df.columns:
        return pd.Series(["bs_na"] * len(df), index=df.index)
    conv = pd.to_numeric(df[conv_col], errors="coerce").fillna(0)
    if conv.sum() == 0:
        return pd.Series(["no_sales"] * len(df), index=df.index)
    threshold = conv.quantile(1 - top_pct)
    labels = np.where(conv >= threshold, "bestseller",
             np.where(conv > 0, "seller", "no_sales"))
    return pd.Series(labels, index=df.index)


def label_clearance(df: pd.DataFrame) -> pd.Series:
    if "sale_price" in df.columns and "price" in df.columns:
        p = _to_price(df["price"])
        sp = _to_price(df["sale_price"])
        discount = (p - sp) / p.replace(0, np.nan)
        labels = np.where(discount.isna() | (discount <= 0), "full_price",
                 np.where(discount >= 0.30, "clearance",
                 np.where(discount >= 0.10, "on_sale", "full_price")))
        return pd.Series(labels, index=df.index)
    return pd.Series(["full_price"] * len(df), index=df.index)


# ---------- SHOPIFY-DRIVEN ----------

def label_sell_through(df: pd.DataFrame) -> pd.Series:
    """Sell-through = vendite / (vendite + giacenza). Richiede shopify_units_sold + quantity."""
    if "shopify_units_sold" not in df.columns or "quantity" not in df.columns:
        return pd.Series(["sellthrough_na"] * len(df), index=df.index)
    sold = pd.to_numeric(df["shopify_units_sold"], errors="coerce").fillna(0)
    stock = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
    denom = (sold + stock).replace(0, np.nan)
    st_rate = sold / denom
    labels = np.where(st_rate.isna(), "sellthrough_na",
             np.where(st_rate >= 0.50, "fast_mover",
             np.where(st_rate >= 0.20, "steady_mover",
             np.where(st_rate > 0, "slow_mover", "stale_stock"))))
    return pd.Series(labels, index=df.index)


def label_view_to_buy(df: pd.DataFrame) -> pd.Series:
    """Tasso di conversione Shopify (vendite / viste). Identifica zombie organici."""
    if "shopify_views" not in df.columns or "shopify_units_sold" not in df.columns:
        return pd.Series(["v2b_na"] * len(df), index=df.index)
    views = pd.to_numeric(df["shopify_views"], errors="coerce").fillna(0)
    sold = pd.to_numeric(df["shopify_units_sold"], errors="coerce").fillna(0)
    rate = np.where(views > 0, sold / views, 0)
    labels = np.where(views < 20, "low_traffic",
             np.where(rate >= 0.05, "high_converter",
             np.where(rate >= 0.01, "mid_converter", "organic_zombie")))
    return pd.Series(labels, index=df.index)


# ---------- STOCK ----------

def label_stock(df: pd.DataFrame) -> pd.Series:
    if "availability" in df.columns:
        av = df["availability"].astype(str).str.lower()
        # se c'è anche quantity usiamo granularità maggiore
        if "quantity" in df.columns:
            q = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)
            labels = np.where(~av.str.contains("in stock|in_stock", na=False), "out_of_stock",
                     np.where(q <= 3, "low_stock",
                     np.where(q <= 10, "mid_stock", "high_stock")))
            return pd.Series(labels, index=df.index)
        labels = np.where(av.str.contains("in stock|in_stock", na=False), "in_stock", "out_of_stock")
        return pd.Series(labels, index=df.index)
    return pd.Series(["stock_na"] * len(df), index=df.index)
