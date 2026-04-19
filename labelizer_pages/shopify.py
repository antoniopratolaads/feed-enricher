"""Pagina 3: import dati Shopify (vendite, inventario, viste, margine)."""
import streamlit as st
import pandas as pd
import io

from utils.state import init_state, current_df
from utils.ui import apply_theme
from utils.match import fuzzy_match_titles, composite_match, merge_via_match

init_state()
apply_theme()

st.title("3. Shopify · Dati e-commerce")
st.caption("OPZIONALE — Migliora le label e l'enrichment AI. Salta se non hai dati Shopify.")
st.info("**Step opzionale.** I tre tab sono **indipendenti**: puoi caricare solo Vendite, solo Inventario, o solo Viste. Anche uno solo aggiunge valore.")

st.markdown("""
### Cosa esportare da Shopify
Da **Shopify Admin → Analytics → Reports** puoi esportare:

| Report Shopify | Cosa ti dà | Usato per |
|---|---|---|
| **Sales by product** | unità vendute, ricavo per SKU | bestseller, freshness, AI context |
| **Inventory** (Apps → Stocky o export Products) | quantity, COGS | margine, low_stock, sell-through |
| **Sessions by landing page** o GA4 | viste prodotto | rilevare zombie organici (visti ma non comprati) |
| **Returns** (se attivo) | tasso di reso | label "high_returns" da escludere |

In alternativa, **Shopify Admin → Products → Export** ti dà CSV con `Variant Inventory Qty`, `Variant Cost`, `Variant Price`, `Handle`.
""")

st.divider()

tab1, tab2, tab3 = st.tabs(["Vendite per prodotto", "Inventario / Costi", "Viste prodotto (opzionale)"])

# --- VENDITE ---
with tab1:
    st.markdown("**CSV richiesto**: deve contenere id prodotto + quantità venduta + ricavo (in qualsiasi periodo).")
    up = st.file_uploader("Upload Sales by product CSV", type=["csv", "xlsx"], key="sales_up")
    if up:
        sales = pd.read_excel(up) if up.name.endswith(".xlsx") else pd.read_csv(up, sep=None, engine="python")
        sales.columns = [c.lower().strip().replace(" ", "_") for c in sales.columns]
        st.dataframe(sales.head(20), use_container_width=True)

        # auto-detect ID column scegliendo quella che matcha più id del feed
        base_preview = current_df()
        feed_id_col = "id" if base_preview is not None and "id" in base_preview.columns else (base_preview.columns[0] if base_preview is not None else None)
        feed_ids = set(base_preview[feed_id_col].astype(str)) if base_preview is not None else set()

        best_idx = 0
        best_match = -1
        if feed_ids:
            for i, c in enumerate(sales.columns):
                m = sales[c].astype(str).isin(feed_ids).sum()
                if m > best_match:
                    best_match, best_idx = m, i

        c1, c2, c3 = st.columns(3)
        id_col = c1.selectbox(
            f"Colonna ID prodotto (deve matchare `{feed_id_col}` del feed)",
            sales.columns, index=best_idx, key="sid",
            help=f"Esempio ID nel feed: `{base_preview[feed_id_col].iloc[0] if base_preview is not None else ''}`"
        )
        qty_col = c2.selectbox("Colonna unità vendute", sales.columns,
                               index=next((i for i, c in enumerate(sales.columns) if "qty" in c or "sold" in c or "units" in c or "articoli" in c or "venduti" in c), 0),
                               key="sqty")
        rev_col = c3.selectbox("Colonna ricavo", sales.columns,
                               index=next((i for i, c in enumerate(sales.columns) if "revenue" in c or "sales" in c or "total" in c or "ricav" in c), 0),
                               key="srev")

        # preview match in tempo reale
        if feed_ids:
            shopify_ids = set(sales[id_col].astype(str))
            matched = len(feed_ids & shopify_ids)
            match_pct = matched / len(feed_ids) * 100 if feed_ids else 0
            mc1, mc2 = st.columns(2)
            mc1.metric("ID nel feed", f"{len(feed_ids):,}")
            mc2.metric("Match con Shopify", f"{matched:,}", f"{match_pct:.0f}%",
                       delta_color="normal" if match_pct >= 30 else "inverse")
            if match_pct < 10:
                st.error(f"⚠️ Solo {match_pct:.0f}% di match! Probabilmente hai scelto la colonna sbagliata. "
                         f"Confronta: feed = `{base_preview[feed_id_col].iloc[0]}`, Shopify = `{sales[id_col].iloc[0]}`")
            elif match_pct < 50:
                st.warning(f"Match basso ({match_pct:.0f}%). Verifica che la colonna sia quella giusta.")
            else:
                st.success(f"Match elevato ({match_pct:.0f}%) — pronto a unire.")

            # ============= FALLBACK: FUZZY / COMPOSITE =============
            with st.expander("🤖 Match avanzato (se gli ID non combaciano)", expanded=match_pct < 30):
                st.caption("Quando il match per ID è basso, prova fuzzy match sui titoli o composite (brand+prezzo+titolo).")
                strategy = st.radio("Strategia",
                                     ["Fuzzy titolo (rapidfuzz)", "Composite (brand+price+title)"],
                                     key="match_strategy", horizontal=True)
                fuzzy_threshold = st.slider("Soglia similarità", 50, 95, 80, key="fuzzy_thr")

                if strategy == "Fuzzy titolo (rapidfuzz)":
                    title_col_shop = st.selectbox("Colonna titolo Shopify", sales.columns,
                                                   index=next((i for i, c in enumerate(sales.columns)
                                                              if "title" in c or "titol" in c or "nome" in c
                                                              or "product" in c or "prodotto" in c), 0),
                                                   key="fuzzy_tcol")
                    if st.button("Calcola fuzzy match", key="run_fuzzy"):
                        with st.spinner("Calcolo..."):
                            matches = fuzzy_match_titles(base_preview, sales, "title",
                                                          title_col_shop, threshold=fuzzy_threshold)
                        st.session_state["sales_matches"] = matches
                        st.session_state["sales_raw"] = sales
                        st.session_state["sales_qty_col"] = qty_col
                        st.session_state["sales_rev_col"] = rev_col
                        st.success(f"Trovati **{len(matches)}** match su {len(base_preview)}")
                else:
                    cc1, cc2 = st.columns(2)
                    brand_col_shop = cc1.selectbox("Brand Shopify", ["—"] + list(sales.columns), key="comp_brand")
                    price_col_shop = cc2.selectbox("Prezzo Shopify", ["—"] + list(sales.columns), key="comp_price")
                    title_col_shop = st.selectbox("Titolo Shopify", sales.columns, key="comp_title")
                    price_tol = st.slider("Tolleranza prezzo (%)", 0, 30, 10, key="comp_tol") / 100
                    if st.button("Calcola composite match", key="run_comp"):
                        with st.spinner("Calcolo..."):
                            matches = composite_match(
                                base_preview, sales,
                                feed_cols={"title": "title", "brand": "brand", "price": "price"},
                                shop_cols={"title": title_col_shop,
                                           "brand": brand_col_shop if brand_col_shop != "—" else "",
                                           "price": price_col_shop if price_col_shop != "—" else ""},
                                price_tolerance_pct=price_tol,
                                title_threshold=fuzzy_threshold - 20,
                            )
                        st.session_state["sales_matches"] = matches
                        st.session_state["sales_raw"] = sales
                        st.session_state["sales_qty_col"] = qty_col
                        st.session_state["sales_rev_col"] = rev_col
                        st.success(f"Trovati **{len(matches)}** match")

                matches = st.session_state.get("sales_matches")
                if matches is not None and len(matches):
                    st.dataframe(matches.head(20)[["score", "feed_title", "shop_title"]],
                                  use_container_width=True, height=250)
                    if st.button("✅ Applica match al catalogo", type="primary", key="apply_match"):
                        sraw = st.session_state["sales_raw"]
                        qty = st.session_state["sales_qty_col"]; rev = st.session_state["sales_rev_col"]
                        for c in (qty, rev):
                            sraw[c] = pd.to_numeric(
                                sraw[c].astype(str).str.replace(r"[^\d.,-]", "", regex=True).str.replace(",", "."),
                                errors="coerce").fillna(0)
                        merged = merge_via_match(base_preview, sraw, matches,
                                                  cols_to_pull={qty: "shopify_units_sold", rev: "shopify_revenue"})
                        merged["shopify_units_sold"] = pd.to_numeric(merged["shopify_units_sold"], errors="coerce").fillna(0)
                        merged["shopify_revenue"] = pd.to_numeric(merged["shopify_revenue"], errors="coerce").fillna(0)
                        st.session_state["merged_df"] = merged
                        ws = (merged["shopify_units_sold"] > 0).sum()
                        st.success(f"Applicato! {ws} prodotti hanno vendite.")

        if st.button("Unisci vendite al catalogo", type="primary", key="merge_sales"):
            base = current_df()
            if base is None:
                st.warning("Carica prima un feed.")
            else:
                feed_id = "id" if "id" in base.columns else base.columns[0]
                clean = sales[[id_col, qty_col, rev_col]].rename(columns={
                    id_col: feed_id, qty_col: "shopify_units_sold", rev_col: "shopify_revenue"
                }).copy()
                # forza numerico PRIMA del groupby (toglie € $ , spazi)
                for c in ("shopify_units_sold", "shopify_revenue"):
                    clean[c] = pd.to_numeric(
                        clean[c].astype(str).str.replace(r"[^\d.,-]", "", regex=True).str.replace(",", "."),
                        errors="coerce",
                    )
                clean[feed_id] = clean[feed_id].astype(str)
                clean = clean.groupby(feed_id, as_index=False).agg({
                    "shopify_units_sold": "sum", "shopify_revenue": "sum"
                })
                base[feed_id] = base[feed_id].astype(str)
                merged = base.merge(clean, on=feed_id, how="left")
                merged["shopify_units_sold"] = merged["shopify_units_sold"].fillna(0)
                merged["shopify_revenue"] = merged["shopify_revenue"].fillna(0)
                st.session_state["merged_df"] = merged
                with_sales = (merged["shopify_units_sold"] > 0).sum()
                st.success(f"Vendite aggiunte. {with_sales} prodotti hanno vendite, {len(merged)-with_sales} sono no_sales.")

# --- INVENTARIO / COSTI ---
with tab2:
    st.markdown("**CSV richiesto**: ID + Variant Cost (COGS) + opzionale Quantity. Da Products Export di Shopify.")
    up = st.file_uploader("Upload Inventory/Products CSV", type=["csv", "xlsx"], key="inv_up")
    if up:
        inv = pd.read_excel(up) if up.name.endswith(".xlsx") else pd.read_csv(up, sep=None, engine="python")
        inv.columns = [c.lower().strip().replace(" ", "_") for c in inv.columns]
        st.dataframe(inv.head(20), use_container_width=True)

        base_preview = current_df()
        feed_id_col = "id" if base_preview is not None and "id" in base_preview.columns else (base_preview.columns[0] if base_preview is not None else None)
        feed_ids = set(base_preview[feed_id_col].astype(str)) if base_preview is not None else set()
        best_idx = 0; best_match = -1
        if feed_ids:
            for i, c in enumerate(inv.columns):
                m = inv[c].astype(str).isin(feed_ids).sum()
                if m > best_match: best_match, best_idx = m, i

        c1, c2, c3 = st.columns(3)
        id_col = c1.selectbox(f"Colonna ID (deve matchare `{feed_id_col}`)", inv.columns,
                              index=best_idx, key="iid",
                              help=f"Esempio ID feed: `{base_preview[feed_id_col].iloc[0] if base_preview is not None else ''}`")
        cost_col = c2.selectbox("Colonna costo (COGS)", inv.columns,
                                index=next((i for i, c in enumerate(inv.columns) if "cost" in c or "costo" in c), 0), key="icost")
        qty_col = c3.selectbox("Colonna quantità (opz.)", ["—"] + list(inv.columns), key="iqty")

        if feed_ids:
            matched = len(feed_ids & set(inv[id_col].astype(str)))
            pct = matched / len(feed_ids) * 100
            (st.error if pct < 10 else st.warning if pct < 50 else st.success)(
                f"Match: {matched}/{len(feed_ids)} ({pct:.0f}%)")

        if st.button("Unisci inventario", type="primary", key="merge_inv"):
            base = current_df()
            if base is None:
                st.warning("Carica prima un feed.")
            else:
                feed_id = "id" if "id" in base.columns else base.columns[0]
                cols = [id_col, cost_col]
                rename = {id_col: feed_id, cost_col: "cost_of_goods"}
                if qty_col != "—":
                    cols.append(qty_col)
                    rename[qty_col] = "quantity"
                clean = inv[cols].rename(columns=rename).copy()
                clean["cost_of_goods"] = pd.to_numeric(
                    clean["cost_of_goods"].astype(str).str.replace(r"[^\d.,-]", "", regex=True).str.replace(",", "."),
                    errors="coerce",
                )
                clean[feed_id] = clean[feed_id].astype(str)
                clean = clean.groupby(feed_id, as_index=False).first()
                base[feed_id] = base[feed_id].astype(str)
                merged = base.merge(clean, on=feed_id, how="left")
                merged["cost_of_goods"] = pd.to_numeric(merged["cost_of_goods"], errors="coerce")
                if "quantity" in merged.columns:
                    merged["quantity"] = pd.to_numeric(merged["quantity"], errors="coerce").fillna(0)
                st.session_state["merged_df"] = merged
                st.success(f"Costi caricati per {merged['cost_of_goods'].notna().sum()} prodotti")

# --- VIEWS ---
with tab3:
    st.markdown("**CSV richiesto**: ID prodotto + numero di viste (da Shopify Online Store sessions o GA4).")
    up = st.file_uploader("Upload Views CSV", type=["csv", "xlsx"], key="views_up")
    if up:
        views = pd.read_excel(up) if up.name.endswith(".xlsx") else pd.read_csv(up, sep=None, engine="python")
        views.columns = [c.lower().strip().replace(" ", "_") for c in views.columns]
        st.dataframe(views.head(20), use_container_width=True)

        base_preview = current_df()
        feed_id_col = "id" if base_preview is not None and "id" in base_preview.columns else (base_preview.columns[0] if base_preview is not None else None)
        feed_ids = set(base_preview[feed_id_col].astype(str)) if base_preview is not None else set()
        best_idx = 0; best_match = -1
        if feed_ids:
            for i, c in enumerate(views.columns):
                m = views[c].astype(str).isin(feed_ids).sum()
                if m > best_match: best_match, best_idx = m, i

        c1, c2 = st.columns(2)
        id_col = c1.selectbox(f"Colonna ID (deve matchare `{feed_id_col}`)", views.columns,
                              index=best_idx, key="vid",
                              help=f"Esempio ID feed: `{base_preview[feed_id_col].iloc[0] if base_preview is not None else ''}`")
        v_col = c2.selectbox("Colonna viste", views.columns,
                             index=next((i for i, c in enumerate(views.columns) if "view" in c or "session" in c or "visualizz" in c), 0), key="vc")

        if feed_ids:
            matched = len(feed_ids & set(views[id_col].astype(str)))
            pct = matched / len(feed_ids) * 100
            (st.error if pct < 10 else st.warning if pct < 50 else st.success)(
                f"Match: {matched}/{len(feed_ids)} ({pct:.0f}%)")

        if st.button("Unisci viste", type="primary", key="merge_views"):
            base = current_df()
            if base is not None:
                feed_id = "id" if "id" in base.columns else base.columns[0]
                clean = views[[id_col, v_col]].rename(columns={id_col: feed_id, v_col: "shopify_views"}).copy()
                clean["shopify_views"] = pd.to_numeric(clean["shopify_views"], errors="coerce").fillna(0)
                clean[feed_id] = clean[feed_id].astype(str)
                clean = clean.groupby(feed_id, as_index=False).agg({"shopify_views": "sum"})
                base[feed_id] = base[feed_id].astype(str)
                merged = base.merge(clean, on=feed_id, how="left")
                merged["shopify_views"] = pd.to_numeric(merged["shopify_views"], errors="coerce").fillna(0)
                st.session_state["merged_df"] = merged
                st.success(f"Viste caricate")

st.divider()

df = current_df()
if df is not None:
    shopify_cols = [c for c in df.columns if c.startswith("shopify_") or c in ("cost_of_goods", "quantity")]
    if shopify_cols:
        st.subheader("Dati Shopify nel catalogo")
        st.dataframe(df[["id"] + shopify_cols].head(50) if "id" in df.columns else df[shopify_cols].head(50),
                     use_container_width=True)
