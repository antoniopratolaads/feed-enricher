"""Match Shopify ↔ feed quando gli ID non combaciano:
- fuzzy match su titolo (rapidfuzz)
- composite match su brand+price+category quando i titoli divergono troppo
"""
from __future__ import annotations
import pandas as pd
import re
from rapidfuzz import fuzz, process


def _norm(s: str) -> str:
    s = str(s or "").lower().strip()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s


def _to_price(v) -> float | None:
    s = re.sub(r"[^\d.,-]", "", str(v)).replace(",", ".")
    try:
        return float(s)
    except (ValueError, TypeError):
        return None


def fuzzy_match_titles(
    feed_df: pd.DataFrame,
    shop_df: pd.DataFrame,
    feed_title_col: str = "title",
    shop_title_col: str = "title",
    threshold: int = 80,
) -> pd.DataFrame:
    """Per ogni riga del feed cerca il match migliore in shop_df.
    Ritorna DataFrame: feed_idx | shop_idx | score | feed_title | shop_title"""
    shop_titles = shop_df[shop_title_col].astype(str).map(_norm).tolist()
    out_rows = []
    for fi, ft in feed_df[feed_title_col].astype(str).items():
        norm = _norm(ft)
        if not norm:
            continue
        match = process.extractOne(norm, shop_titles, scorer=fuzz.token_set_ratio,
                                    score_cutoff=threshold)
        if match:
            matched_str, score, shop_pos = match
            out_rows.append({
                "feed_idx": fi,
                "shop_idx": shop_df.index[shop_pos],
                "score": int(score),
                "feed_title": ft,
                "shop_title": shop_df.iloc[shop_pos][shop_title_col],
            })
    return pd.DataFrame(out_rows)


def composite_match(
    feed_df: pd.DataFrame,
    shop_df: pd.DataFrame,
    feed_cols: dict,
    shop_cols: dict,
    price_tolerance_pct: float = 0.10,
    title_threshold: int = 60,
) -> pd.DataFrame:
    """Match basato su brand + price + (opz.) category. Più tollerante del fuzzy puro.
    feed_cols/shop_cols = {'title': '...', 'brand': '...', 'price': '...', 'category': '...'}"""
    out = []
    # raggruppa shop per brand normalizzato per accelerare
    shop_df = shop_df.copy()
    shop_df["_brand_norm"] = shop_df[shop_cols.get("brand", "brand")].astype(str).map(_norm) \
        if shop_cols.get("brand") in shop_df.columns else ""
    shop_df["_price_num"] = shop_df[shop_cols.get("price", "price")].map(_to_price) \
        if shop_cols.get("price") in shop_df.columns else None
    shop_df["_title_norm"] = shop_df[shop_cols.get("title", "title")].astype(str).map(_norm) \
        if shop_cols.get("title") in shop_df.columns else ""

    for fi, frow in feed_df.iterrows():
        fbrand = _norm(frow.get(feed_cols.get("brand", "brand"), ""))
        fprice = _to_price(frow.get(feed_cols.get("price", "price"), ""))
        ftitle = _norm(frow.get(feed_cols.get("title", "title"), ""))
        if not ftitle:
            continue

        candidates = shop_df
        if fbrand:
            candidates = candidates[candidates["_brand_norm"] == fbrand]
        if fprice and len(candidates):
            tol = fprice * price_tolerance_pct
            candidates = candidates[
                (candidates["_price_num"] >= fprice - tol) &
                (candidates["_price_num"] <= fprice + tol)
            ]
        if not len(candidates):
            continue

        # tra i candidati, fuzzy sul titolo
        scores = candidates["_title_norm"].apply(lambda t: fuzz.token_set_ratio(ftitle, t))
        best_score = scores.max()
        if best_score >= title_threshold:
            best_idx = scores.idxmax()
            out.append({
                "feed_idx": fi,
                "shop_idx": best_idx,
                "score": int(best_score),
                "feed_title": frow.get(feed_cols.get("title"), ""),
                "shop_title": shop_df.at[best_idx, shop_cols.get("title", "title")],
            })
    return pd.DataFrame(out)


def merge_via_match(
    feed_df: pd.DataFrame,
    shop_df: pd.DataFrame,
    matches: pd.DataFrame,
    cols_to_pull: dict,
) -> pd.DataFrame:
    """Applica i match a feed_df portando le colonne dello shop.
    cols_to_pull = {'shop_col_source': 'feed_col_target'}"""
    feed = feed_df.copy()
    for _, target in cols_to_pull.items():
        if target not in feed.columns:
            feed[target] = pd.NA

    if not len(matches):
        return feed

    lookup = matches.set_index("feed_idx")["shop_idx"].to_dict()
    for fi, si in lookup.items():
        for src, tgt in cols_to_pull.items():
            if src in shop_df.columns:
                feed.at[fi, tgt] = shop_df.at[si, src]
    return feed
