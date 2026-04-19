"""Pagina 4: custom_label basate su performance Google Ads."""
import streamlit as st
import pandas as pd
import plotly.express as px

from utils.state import init_state, current_df
from utils.ui import apply_theme
from utils.labels import label_performance

init_state()
apply_theme()

st.title("5. Custom Label - Performance")
st.caption("Segmenta i prodotti per ROAS, click, conversioni")

df = current_df()
if df is None:
    st.warning("Carica prima un feed.")
    st.stop()

required = ["clicks", "cost", "conversions", "conv_value"]
missing = [c for c in required if c not in df.columns]
if missing:
    st.warning(f"⚠️ Questa label richiede dati Google Ads (mancano: {', '.join(missing)}).")
    st.markdown("""
    **Cosa puoi fare invece:**
    - Salta questa pagina e usa le altre label (Margine, Stagionalità, Stock, Sell-through, View-to-buy)
    - Il **bestseller_label** in *Stagionalità* può funzionare anche con vendite Shopify
    - Carica GAds in *2. Google Ads* (è opzionale ma sblocca questa pagina)
    """)
    st.stop()

st.subheader("Soglie")
c1, c2, c3 = st.columns(3)
roas_high = c1.number_input("ROAS alto (≥)", value=4.0, step=0.5)
roas_low = c2.number_input("ROAS basso (≥)", value=1.5, step=0.1)
zombie_clicks = c3.number_input("Click minimi per 'zombie' (no conv)", value=30, step=5)

labels = label_performance(df, roas_high=roas_high, roas_low=roas_low, min_clicks_zombie=zombie_clicks)

dist = labels.value_counts().reset_index()
dist.columns = ["label", "count"]

c1, c2 = st.columns([2, 3])
with c1:
    st.dataframe(dist, use_container_width=True, hide_index=True)
with c2:
    fig = px.pie(dist, names="label", values="count", title="Distribuzione label performance", hole=0.4)
    st.plotly_chart(fig, use_container_width=True)

st.subheader("Anteprima")
preview = df.copy()
preview["performance_label"] = labels
cols = ["id", "title", "clicks", "cost", "conversions", "conv_value", "performance_label"]
cols = [c for c in cols if c in preview.columns]
st.dataframe(preview[cols].head(200), use_container_width=True, height=400)

if st.button("Salva label 'performance_label'", type="primary"):
    st.session_state["labels"]["performance_label"] = labels
    st.success("Label salvata. Vai su **Feed Supplementare** per esportare.")
