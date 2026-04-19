"""Pagina 5: Labelizer hub — sezione separata per dati piattaforme + creazione label."""
import streamlit as st

from utils.state import init_state, current_df
from utils.ui import apply_theme

init_state()
apply_theme()

st.markdown("# 🏷️ Labelizer")
st.caption("Sezione **avanzata e opzionale**. Combina dati di performance (Google Ads, Meta Ads, Shopify) "
           "con il tuo catalogo e crea custom_label intelligenti per Google Merchant Center.")

st.markdown("""
<div style='background: linear-gradient(135deg, rgba(108,92,231,0.15), rgba(0,217,163,0.08));
            border-radius: 16px; padding: 24px; margin: 16px 0;
            border: 1px solid rgba(108,92,231,0.3);'>
<h3 style='margin:0 0 8px;'>Quando usare il Labelizer?</h3>
<p style='margin:0; opacity:0.85;'>Se vuoi spingere oltre il semplice arricchimento del feed e creare segmentazioni intelligenti
basate su performance reali (ROAS, vendite, margine, stock) per ottimizzare le campagne Google Shopping/Performance Max.</p>
</div>
""", unsafe_allow_html=True)

df = current_df()
if df is None:
    st.warning("⚠️ Carica prima un feed in **2. Upload Feed**.")
    st.stop()

# ============================================================
# FLUSSO LABELIZER
# ============================================================
st.markdown("## Flusso Labelizer")

st.markdown("""
1. **Carica i dati performance** (almeno uno):
2. **Crea le label** (almeno uno):
3. **Esporta il feed supplementare** con le label mappate su `custom_label_0..4`
4. **Analizza** le performance complete con dashboard dedicata
""")

st.divider()

# ============================================================
# STATUS PIATTAFORME
# ============================================================
st.markdown("### 📊 Step 1 · Dati piattaforme")
st.caption("Carica i dati di una o più piattaforme. Ogni dato sblocca label specifiche.")

c1, c2, c3 = st.columns(3)
has_gads = "clicks" in df.columns
has_meta = "meta_clicks" in df.columns or "meta_impressions" in df.columns
has_shop = any(c in df.columns for c in ("shopify_units_sold", "cost_of_goods", "shopify_views"))

with c1:
    icon = "✅" if has_gads else "⚪"
    st.markdown(f"#### {icon} Google Ads")
    st.caption("Performance Shopping per ROAS, click, conversioni")
    st.page_link("pages/6_Labelizer_Google_Ads.py", label="Apri →", use_container_width=True)
with c2:
    icon = "✅" if has_meta else "⚪"
    st.markdown(f"#### {icon} Meta Ads")
    st.caption("Facebook + Instagram performance per Advantage+ Shopping")
    st.page_link("pages/7_Labelizer_Meta_Ads.py", label="Apri →", use_container_width=True)
with c3:
    icon = "✅" if has_shop else "⚪"
    st.markdown(f"#### {icon} Shopify")
    st.caption("Vendite, viste, COGS, sell-through reale")
    st.page_link("pages/8_Labelizer_Shopify.py", label="Apri →", use_container_width=True)

st.divider()

# ============================================================
# STATUS LABELS
# ============================================================
st.markdown("### 🏷️ Step 2 · Crea label")
labels_created = st.session_state.get("labels", {})

c1, c2, c3, c4 = st.columns(4)

with c1:
    icon = "✅" if any("performance" in k or "roas" in k for k in labels_created) else "⚪"
    st.markdown(f"#### {icon} Performance")
    st.caption("ROAS tiers, zombie, no_clicks (richiede GAds o Meta Ads)")
    st.page_link("pages/9_Labelizer_Performance.py", label="Apri →", use_container_width=True)
with c2:
    icon = "✅" if any("margin" in k or "price" in k for k in labels_created) else "⚪"
    st.markdown(f"#### {icon} Margine & Prezzo")
    st.caption("Bucket prezzo + margine alto/medio/basso")
    st.page_link("pages/A1_Labelizer_Margine.py", label="Apri →", use_container_width=True)
with c3:
    icon = "✅" if any(k in labels_created for k in ("freshness_label", "bestseller_label",
                                                       "clearance_label", "sellthrough_label",
                                                       "view_to_buy_label")) else "⚪"
    st.markdown(f"#### {icon} Stagionalità")
    st.caption("New, bestseller, clearance, sell-through, view-to-buy")
    st.page_link("pages/A2_Labelizer_Stagionalita.py", label="Apri →", use_container_width=True)
with c4:
    icon = "✅" if "stock_label" in labels_created else "⚪"
    st.markdown(f"#### {icon} Stock")
    st.caption("In/out + low/mid/high (con quantity)")
    st.page_link("pages/A3_Labelizer_Stock.py", label="Apri →", use_container_width=True)

if labels_created:
    st.success(f"📌 **{len(labels_created)} label salvate**: {', '.join(labels_created.keys())}")

st.divider()

# ============================================================
# OUTPUT
# ============================================================
st.markdown("### 📤 Step 3 · Esporta feed supplementare")
st.caption("Mappa le label create sui custom_label_0..4 di GMC ed esporta il feed supplementare.")
c1, c2 = st.columns(2)
c1.page_link("pages/A4_Labelizer_Feed_Supplementare.py", label="🚀 Apri Feed Supplementare",
              use_container_width=True)
c2.page_link("pages/A5_Labelizer_Analytics.py", label="📈 Apri Analytics",
              use_container_width=True)

# ============================================================
# DIFFERENZA col CATALOGO BASE
# ============================================================
st.divider()
with st.expander("Differenza tra Catalogo Base (Cliente) e Labelizer"):
    st.markdown("""
**Catalogo Base** (pagine 0-4 — flusso Cliente, 90% dei casi):
- Upload feed → Enrichment AI → Scarica feed Google + Meta ottimizzato
- Sufficiente per la maggior parte dei merchant che vuole solo migliorare il feed

**Labelizer** (questa sezione, opzionale):
- Aggiunge intelligenza performance-driven
- Richiede dati esterni (GAds, Meta Ads, Shopify export)
- Genera **feed supplementare** con custom_label per segmentare le campagne
- Utile per: agenzie, e-commerce avanzati, ottimizzazione Performance Max/PMax
""")
