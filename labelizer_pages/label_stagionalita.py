"""Pagina 7: custom_label stagionalità + Shopify-driven (sell-through, view-to-buy)."""
import streamlit as st
import pandas as pd
import plotly.express as px

from utils.state import init_state, current_df
from utils.ui import apply_theme
from utils.labels import (
    label_freshness, label_bestseller, label_clearance,
    label_sell_through, label_view_to_buy,
)

init_state()
apply_theme()

st.title("7. Custom Label - Stagionalità & Shopify signals")

df = current_df()
if df is None:
    st.warning("Carica prima un feed.")
    st.stop()

tabs = st.tabs(["Freshness (nuovi)", "Bestseller", "Clearance / Sconti",
                "Sell-through (Shopify)", "View-to-buy (Shopify)"])


def _render(labels, save_name, title=""):
    dist = labels.value_counts().reset_index()
    dist.columns = ["label", "count"]
    c1, c2 = st.columns(2)
    c1.dataframe(dist, use_container_width=True, hide_index=True)
    c2.plotly_chart(px.pie(dist, names="label", values="count", hole=0.4, title=title),
                    use_container_width=True)
    if st.button(f"Salva '{save_name}'", type="primary", key=f"save_{save_name}"):
        st.session_state["labels"][save_name] = labels
        st.success("Salvata")


with tabs[0]:
    st.caption("Basato su data aggiunta prodotto.")
    date_cols = [c for c in df.columns if any(k in c.lower() for k in ["date", "created", "added"])]
    if not date_cols:
        st.warning("Nessuna colonna data trovata.")
    else:
        date_col = st.selectbox("Colonna data", date_cols)
        days = st.slider("Giorni per 'new_arrival'", 7, 90, 30)
        _render(label_freshness(df, date_col=date_col, new_days=days), "freshness_label")

with tabs[1]:
    st.caption("Top venditori. Usa conversioni GAds o vendite Shopify.")
    use_shopify = st.toggle("Usa vendite Shopify invece di conversioni GAds",
                            value="shopify_units_sold" in df.columns)
    col = "shopify_units_sold" if use_shopify else "conversions"
    if col not in df.columns:
        st.warning(f"Manca la colonna '{col}'.")
    else:
        top_pct = st.slider("Top % = bestseller", 5, 50, 20) / 100
        _render(label_bestseller(df, conv_col=col, top_pct=top_pct), "bestseller_label")

with tabs[2]:
    _render(label_clearance(df), "clearance_label", "Sconto (sale_price vs price)")

with tabs[3]:
    st.caption("Sell-through = vendite / (vendite + giacenza). Identifica fast/slow movers e stale stock.")
    if "shopify_units_sold" not in df.columns or "quantity" not in df.columns:
        st.warning("Servono `shopify_units_sold` (Shopify Sales) e `quantity` (Shopify Inventory).")
    else:
        _render(label_sell_through(df), "sellthrough_label", "Sell-through")

with tabs[4]:
    st.caption("Tasso di conversione organico Shopify. Identifica zombie organici (visti ma non comprati).")
    if "shopify_views" not in df.columns or "shopify_units_sold" not in df.columns:
        st.warning("Servono `shopify_views` e `shopify_units_sold`.")
    else:
        _render(label_view_to_buy(df), "view_to_buy_label", "View → Buy")
