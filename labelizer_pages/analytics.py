"""Pagina 9: analytics performance incrociate feed + Google Ads."""
import streamlit as st
import pandas as pd
import plotly.express as px

from utils.state import init_state, current_df
from utils.ui import apply_theme

init_state()
apply_theme()

st.title("10. Performance Analytics")
st.caption("Analisi incrociata catalogo + Google Ads")

df = current_df()
if df is None or "clicks" not in df.columns:
    st.warning("Servono dati Google Ads mergeati (pagina Google Ads).")
    st.stop()

# KPI
total_cost = df["cost"].sum()
total_val = df["conv_value"].sum()
total_conv = df["conversions"].sum()
total_clicks = df["clicks"].sum()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Spesa totale", f"€{total_cost:,.2f}")
c2.metric("Conv. value", f"€{total_val:,.2f}")
c3.metric("ROAS", f"{(total_val/total_cost if total_cost else 0):.2f}x")
c4.metric("Click totali", f"{int(total_clicks):,}")
c5.metric("Conversioni", f"{total_conv:.1f}")

st.divider()

# Top/Flop
st.subheader("Top & Flop prodotti")
tabs = st.tabs(["Top ROAS", "Flop (zombie)", "Più spesa", "Scatter spesa/ROAS"])

with tabs[0]:
    top = df[df["cost"] > 0].copy()
    top["roas"] = top["conv_value"] / top["cost"]
    cols = [c for c in ["id", "title", "brand", "clicks", "cost", "conversions", "conv_value", "roas"] if c in top.columns]
    st.dataframe(top.nlargest(50, "roas")[cols], use_container_width=True)

with tabs[1]:
    flop = df[(df["clicks"] >= 20) & (df["conversions"] == 0)].copy()
    flop = flop.nlargest(50, "cost")
    cols = [c for c in ["id", "title", "brand", "clicks", "cost", "conversions"] if c in flop.columns]
    st.dataframe(flop[cols], use_container_width=True)
    st.caption(f"{len(df[(df['clicks'] >= 20) & (df['conversions'] == 0)])} prodotti zombie totali")

with tabs[2]:
    cols = [c for c in ["id", "title", "brand", "clicks", "cost", "conversions", "conv_value"] if c in df.columns]
    st.dataframe(df.nlargest(50, "cost")[cols], use_container_width=True)

with tabs[3]:
    plot_df = df[df["clicks"] > 0].copy()
    plot_df["roas"] = plot_df["conv_value"] / plot_df["cost"].replace(0, 1e-9)
    fig = px.scatter(plot_df.head(2000), x="cost", y="roas",
                     size="clicks", hover_data=["title"] if "title" in plot_df.columns else None,
                     title="Spesa vs ROAS", log_x=True)
    fig.add_hline(y=1, line_dash="dash", line_color="red")
    st.plotly_chart(fig, use_container_width=True)

# Performance per brand / categoria
st.subheader("Performance per dimensione")
dim = st.selectbox("Raggruppa per", [c for c in ["brand", "product_type", "google_product_category",
                                                   "brand", "google_product_category"] if c in df.columns])
if dim:
    grp = df.groupby(dim).agg(
        prodotti=("id", "count") if "id" in df.columns else ("clicks", "count"),
        clicks=("clicks", "sum"),
        cost=("cost", "sum"),
        conv=("conversions", "sum"),
        value=("conv_value", "sum"),
    ).reset_index()
    grp["roas"] = grp["value"] / grp["cost"].replace(0, pd.NA)
    grp = grp.sort_values("cost", ascending=False).head(30)
    st.dataframe(grp, use_container_width=True)
    fig = px.bar(grp, x=dim, y="cost", color="roas",
                 color_continuous_scale="RdYlGn", title=f"Spesa per {dim} (colore = ROAS)")
    st.plotly_chart(fig, use_container_width=True)
