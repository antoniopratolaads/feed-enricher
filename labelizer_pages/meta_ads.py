"""Pagina 2b: Meta Ads performance — opzionale, parallelo a Google Ads."""
import streamlit as st
import pandas as pd

from utils.state import init_state, current_df
from utils.ui import apply_theme
from utils.match import fuzzy_match_titles, composite_match, merge_via_match

init_state()
apply_theme()

st.title("2b. Meta Ads · Performance")
st.caption("OPZIONALE — Importa report Meta Ads Manager (Facebook + Instagram) per arricchire le label e analytics. "
            "Si combina con Google Ads se entrambi presenti.")

st.info("**Step opzionale.** Se non hai dati Meta Ads, salta pure. "
        "Le metriche caricate vengono mergeate al catalogo e usate per le label performance e per l'analytics.")

st.markdown("""
### Come esportare da Meta Ads Manager
1. **Ads Manager → Reports → Custom report**
2. Breakdown per **Product ID** (richiede catalogo connesso) o **Product set**
3. Metriche consigliate: **Impressions, Reach, Clicks, Spend, Purchase ROAS, Purchases, Purchase value**
4. Esporta in CSV/Excel
""")

up = st.file_uploader("Carica CSV/Excel Meta Ads", type=["csv", "xlsx", "tsv"], key="meta_up")
if not up:
    st.stop()

if up.name.endswith(".xlsx"):
    meta = pd.read_excel(up)
else:
    meta = pd.read_csv(up, sep=None, engine="python")
meta.columns = [c.lower().strip().replace(" ", "_") for c in meta.columns]

st.markdown("**Anteprima**")
st.dataframe(meta.head(20), use_container_width=True)

base = current_df()
if base is None:
    st.warning("Carica prima un feed.")
    st.stop()

feed_id_col = "id" if "id" in base.columns else base.columns[0]
feed_ids = set(base[feed_id_col].astype(str))

# auto-detect ID
best_idx = 0; best_match = -1
for i, c in enumerate(meta.columns):
    m = meta[c].astype(str).isin(feed_ids).sum()
    if m > best_match: best_match, best_idx = m, i

st.divider()
st.subheader("Mappatura colonne")

c1, c2, c3 = st.columns(3)
id_col = c1.selectbox(f"ID prodotto (match `{feed_id_col}`)", meta.columns, index=best_idx,
                      help=f"Esempio feed: `{base[feed_id_col].iloc[0]}`")
impr_col = c2.selectbox("Impressions", ["—"] + list(meta.columns),
                         index=next((i+1 for i, c in enumerate(meta.columns)
                                    if "impress" in c), 0))
clicks_col = c3.selectbox("Clicks", ["—"] + list(meta.columns),
                           index=next((i+1 for i, c in enumerate(meta.columns)
                                      if "click" in c), 0))

c1, c2, c3 = st.columns(3)
spend_col = c1.selectbox("Spend / Cost", ["—"] + list(meta.columns),
                          index=next((i+1 for i, c in enumerate(meta.columns)
                                     if "spend" in c or "cost" in c or "amount_spent" in c), 0))
purch_col = c2.selectbox("Purchases (conversions)", ["—"] + list(meta.columns),
                          index=next((i+1 for i, c in enumerate(meta.columns)
                                     if "purchase" in c and "value" not in c or "conversion" in c), 0))
val_col = c3.selectbox("Purchase value (revenue)", ["—"] + list(meta.columns),
                        index=next((i+1 for i, c in enumerate(meta.columns)
                                   if "purchase_value" in c or "conversion_value" in c
                                   or "revenue" in c), 0))

# match preview
matched = len(feed_ids & set(meta[id_col].astype(str)))
pct = matched / len(feed_ids) * 100 if feed_ids else 0
mc1, mc2 = st.columns(2)
mc1.metric("ID feed", f"{len(feed_ids):,}")
mc2.metric("Match Meta", f"{matched:,}", f"{pct:.0f}%",
           delta_color="normal" if pct >= 30 else "inverse")
(st.error if pct < 10 else st.warning if pct < 50 else st.success)(
    f"Match per ID: {pct:.0f}%"
)

# fuzzy fallback
with st.expander("🤖 Match avanzato se ID non combaciano", expanded=pct < 30):
    title_col_meta = st.selectbox("Colonna titolo Meta (per fuzzy)", meta.columns,
                                   index=next((i for i, c in enumerate(meta.columns)
                                              if "title" in c or "name" in c or "product" in c), 0),
                                   key="meta_fuzzy_t")
    threshold = st.slider("Soglia fuzzy", 50, 95, 80, key="meta_fuzzy_thr")
    if st.button("Calcola fuzzy match", key="meta_run_fuzzy"):
        matches = fuzzy_match_titles(base, meta, "title", title_col_meta, threshold=threshold)
        st.session_state["meta_matches"] = matches
        st.success(f"Trovati {len(matches)} match")

    matches = st.session_state.get("meta_matches")
    if matches is not None and len(matches):
        st.dataframe(matches.head(20)[["score", "feed_title", "shop_title"]],
                      use_container_width=True, height=250)

st.divider()

if st.button("Unisci dati Meta al catalogo", type="primary"):
    cols_map = {}
    if impr_col != "—": cols_map[impr_col] = "meta_impressions"
    if clicks_col != "—": cols_map[clicks_col] = "meta_clicks"
    if spend_col != "—": cols_map[spend_col] = "meta_spend"
    if purch_col != "—": cols_map[purch_col] = "meta_purchases"
    if val_col != "—": cols_map[val_col] = "meta_purchase_value"

    if not cols_map:
        st.error("Mappa almeno una colonna metrica.")
        st.stop()

    # preferisci match diretto, fallback fuzzy
    matches = st.session_state.get("meta_matches")
    if matches is not None and len(matches) > 0 and pct < 30:
        # usa fuzzy
        for src in cols_map:
            meta[src] = pd.to_numeric(
                meta[src].astype(str).str.replace(r"[^\d.,-]", "", regex=True).str.replace(",", "."),
                errors="coerce").fillna(0)
        merged = merge_via_match(base, meta, matches, cols_to_pull=cols_map)
    else:
        # match diretto su ID
        clean = meta[[id_col] + list(cols_map.keys())].rename(columns={id_col: feed_id_col, **cols_map}).copy()
        for tgt in cols_map.values():
            clean[tgt] = pd.to_numeric(
                clean[tgt].astype(str).str.replace(r"[^\d.,-]", "", regex=True).str.replace(",", "."),
                errors="coerce").fillna(0)
        clean[feed_id_col] = clean[feed_id_col].astype(str)
        clean = clean.groupby(feed_id_col, as_index=False).agg({c: "sum" for c in cols_map.values()})
        base[feed_id_col] = base[feed_id_col].astype(str)
        merged = base.merge(clean, on=feed_id_col, how="left")

    for tgt in cols_map.values():
        merged[tgt] = pd.to_numeric(merged[tgt], errors="coerce").fillna(0)

    # ROAS Meta calcolato
    if "meta_spend" in merged.columns and "meta_purchase_value" in merged.columns:
        merged["meta_roas"] = (merged["meta_purchase_value"] /
                                merged["meta_spend"].replace(0, pd.NA)).fillna(0).round(2)

    st.session_state["merged_df"] = merged
    with_data = (merged.get("meta_clicks", merged.get("meta_impressions", 0)) > 0).sum()
    st.success(f"Meta Ads mergeato. {with_data} prodotti hanno dati Meta.")
    st.dataframe(merged[[feed_id_col] + list(cols_map.values()) +
                         (["meta_roas"] if "meta_roas" in merged.columns else [])].head(50),
                  use_container_width=True)
