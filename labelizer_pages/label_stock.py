"""Pagina 7: custom_label basate su stock."""
import streamlit as st
import plotly.express as px

from utils.state import init_state, current_df
from utils.ui import apply_theme
from utils.labels import label_stock

init_state()
apply_theme()

st.title("8. Custom Label - Stock")

df = current_df()
if df is None:
    st.warning("Carica prima un feed.")
    st.stop()

if "availability" not in df.columns:
    st.error("Il feed non contiene la colonna 'availability'.")
    st.stop()

st.info("Se è presente la colonna 'quantity' verrà creata anche la granularità low/mid/high stock.")

labels = label_stock(df)
dist = labels.value_counts().reset_index()
dist.columns = ["label", "count"]

c1, c2 = st.columns(2)
c1.dataframe(dist, use_container_width=True, hide_index=True)
c2.plotly_chart(px.pie(dist, names="label", values="count", hole=0.4,
                       title="Distribuzione stock"), use_container_width=True)

preview = df.copy()
preview["stock_label"] = labels
cols = [c for c in ["id", "title", "availability", "quantity", "stock_label"] if c in preview.columns]
st.dataframe(preview[cols].head(200), use_container_width=True, height=400)

if st.button("Salva 'stock_label'", type="primary"):
    st.session_state["labels"]["stock_label"] = labels
    st.success("Salvata")
