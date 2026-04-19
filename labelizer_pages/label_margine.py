"""Pagina 5: custom_label basate su prezzo e margine."""
import streamlit as st
import pandas as pd
import plotly.express as px

from utils.state import init_state, current_df
from utils.ui import apply_theme
from utils.labels import label_price_bucket, label_margin, _to_price

init_state()
apply_theme()

st.title("6. Custom Label - Prezzo e Margine")

df = current_df()
if df is None:
    st.warning("Carica prima un feed.")
    st.stop()

tab1, tab2 = st.tabs(["Bucket di prezzo", "Margine"])

with tab1:
    if "price" not in df.columns:
        st.error("Campo 'price' non trovato nel feed.")
    else:
        n = st.slider("Numero bucket (quantili)", 3, 10, 5)
        labels = label_price_bucket(df, "price", n_buckets=n)
        dist = labels.value_counts().reset_index()
        dist.columns = ["label", "count"]

        c1, c2 = st.columns([2, 3])
        with c1:
            st.dataframe(dist, use_container_width=True, hide_index=True)
            p = _to_price(df["price"]).dropna()
            st.metric("Prezzo mediano", f"{p.median():.2f}")
            st.metric("Min / Max", f"{p.min():.2f} / {p.max():.2f}")
        with c2:
            fig = px.histogram(p, nbins=40, title="Distribuzione prezzi")
            st.plotly_chart(fig, use_container_width=True)

        if st.button("Salva 'price_bucket_label'", type="primary", key="save_price"):
            st.session_state["labels"]["price_bucket_label"] = labels
            st.success("Salvata")

with tab2:
    st.caption("Richiede una colonna costo (costo del venduto / COGS). Puoi caricarla qui o deve essere già nel feed.")

    cost_col = st.text_input("Nome colonna costo nel feed", value="cost_of_goods")

    up = st.file_uploader("Oppure carica CSV con id + costo", type=["csv"], key="cost_upload")
    if up is not None:
        cost_df = pd.read_csv(up)
        cost_df.columns = [c.lower().strip() for c in cost_df.columns]
        st.dataframe(cost_df.head(), use_container_width=True)

        id_col = st.selectbox("Colonna id", cost_df.columns, key="costid")
        cc = st.selectbox("Colonna costo", cost_df.columns, key="costcost")
        if st.button("Unisci costi al catalogo"):
            base = current_df().copy()
            base = base.merge(
                cost_df[[id_col, cc]].rename(columns={id_col: "id", cc: cost_col}),
                on="id", how="left",
            )
            # aggiorna merged_df
            st.session_state["merged_df"] = base
            st.success(f"Uniti costi per {base[cost_col].notna().sum()} prodotti")

    df = current_df()
    c1, c2 = st.columns(2)
    high = c1.number_input("Margine alto (≥)", value=0.50, step=0.05)
    low = c2.number_input("Margine basso (≥)", value=0.20, step=0.05)

    labels = label_margin(df, cost_col=cost_col, high_margin=high, low_margin=low)
    dist = labels.value_counts().reset_index()
    dist.columns = ["label", "count"]
    st.dataframe(dist, use_container_width=True, hide_index=True)
    fig = px.pie(dist, names="label", values="count", hole=0.4, title="Margine")
    st.plotly_chart(fig, use_container_width=True)

    if st.button("Salva 'margin_label'", type="primary", key="save_margin"):
        st.session_state["labels"]["margin_label"] = labels
        st.success("Salvata")
