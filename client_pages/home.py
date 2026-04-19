"""Home Cliente: hero + recap requisiti + entry point."""
import streamlit as st
import pandas as pd

from utils.state import init_state, current_df
from utils.ui import apply_theme, api_key_banner
from utils.history import init_session, save_snapshot, log_event, get_project_name, get_project_info
from utils.config import load_config
from utils.demo_data import load_demo_into_session

init_state()
apply_theme()
init_session(st.session_state)

if "config" not in st.session_state:
    st.session_state["config"] = load_config()
    if st.session_state["config"].get("anthropic_api_key"):
        st.session_state["api_key"] = st.session_state["config"]["anthropic_api_key"]

cfg = st.session_state.get("config", {})

# API key warning banner (renders only when no key configured)
api_key_banner()

# ============================================================
# HERO
# ============================================================
st.markdown("""
<div class='hero-card'>
    <h2>Feed Enricher Pro</h2>
    <p>Carica il tuo feed prodotto, l'AI lo arricchisce con best practice settoriali, scarichi il catalogo ottimizzato per Google e Meta. <br>Pronto in 5 minuti.</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# RECAP REQUISITI — checklist
# ============================================================
df_loaded = st.session_state.get("feed_df") is not None
api_ok = bool(cfg.get("anthropic_api_key"))
project_named = bool(get_project_info(st.session_state["session_id"]))

st.markdown("### Cosa serve per il Data Enrichment")

c1, c2 = st.columns([2, 1])
with c1:
    items = [
        ("Feed prodotto in XML / CSV / TSV / JSON / Excel",
         "Il catalogo da caricare (anche da URL)", df_loaded),
        ("API Key di Claude (Anthropic)",
         "Per la generazione AI dei testi · Configurabile in Settings", api_ok),
        ("Settore merceologico",
         "L'AI applica best practice (abbigliamento, condizionatori, cosmesi)", True),
        ("Tempo stimato ~5 minuti",
         "Setup 1 min · Upload 30s · Enrichment 2-4 min su 50 prodotti", True),
    ]
    for title, desc, ok in items:
        icon = "●" if ok else "○"
        icon_color = "#10B981" if ok else "#D1D5DB"
        border_color = "#A7F3D0" if ok else "#E5E7EB"
        st.markdown(
            f"<div style='background:#FFFFFF; border:1px solid {border_color}; "
            f"border-left:3px solid {icon_color}; "
            f"padding:14px 18px; border-radius:12px; margin-bottom:8px; "
            f"box-shadow:0 1px 2px rgba(10,10,15,0.04);'>"
            f"<div style='display:flex;align-items:center;gap:10px;'>"
            f"<span style='color:{icon_color};font-size:14px;'>{icon}</span>"
            f"<b style='color:#0A0A0F;font-size:0.92rem;'>{title}</b></div>"
            f"<span style='color:#6B7280; font-size:0.82rem; margin-left:24px;'>{desc}</span>"
            f"</div>", unsafe_allow_html=True
        )

with c2:
    st.markdown("""
    <div class='preview-card' style='border-left:4px solid #10B981;'>
    <h4 style='margin:0 0 10px;'>Cosa ottieni</h4>
    <ul style='line-height:1.9; opacity:0.9; padding-left:18px;'>
        <li>Titoli ottimizzati Google + Meta</li>
        <li>Descrizioni arricchite</li>
        <li>Attributi popolati (colore, taglia, materiale...)</li>
        <li>Categoria Google taxonomy</li>
        <li>Bundle ZIP pronto da caricare</li>
    </ul>
    </div>
    """, unsafe_allow_html=True)

st.divider()

# ============================================================
# CTA — PRIMARI
# ============================================================
st.markdown("### Inizia")
b1, b2, b3 = st.columns(3)
with b1:
    if st.button("Avvia Wizard Enrichment →", type="primary", use_container_width=True,
                 help="Flusso guidato in 4 step. Consigliato."):
        st.switch_page("client_pages/wizard.py")
with b2:
    if st.button("Carica demo (500 prodotti)", use_container_width=True,
                 help="Dataset finto realistico per esplorare la app"):
        with st.spinner("Genero dati realistici..."):
            load_demo_into_session(st.session_state, 500)
        log_event(st.session_state["session_id"], "demo_loaded", {"n": 500})
        save_snapshot(st.session_state["session_id"], st.session_state)
        st.success("Demo caricata!")
        st.rerun()
with b3:
    if st.button("Apri Labelizer ↗", use_container_width=True,
                 help="Sezione avanzata per custom_label"):
        st.switch_page("labelizer_pages/hub.py")

# ============================================================
# SE C'E' GIA' UN PROGETTO IN CORSO
# ============================================================
df = current_df()
if df is not None:
    st.divider()
    pname = get_project_name(st.session_state["session_id"])
    st.markdown(f"### Progetto attivo · {pname}")
    c = st.columns(4)
    c[0].metric("Prodotti", f"{len(df):,}")
    c[1].metric("Brand", df["brand"].nunique() if "brand" in df.columns else "—")
    enriched_done = (df.get("title", df.get("title", pd.Series())).astype(str).str.len().mean()
                      > 70) if "title" in df.columns else False
    c[2].metric("Enrichment", "✅ fatto" if enriched_done else "⚪ da fare")
    c[3].metric("Sessione", st.session_state["session_id"][-8:])

    col_a, col_b = st.columns(2)
    if col_a.button("Continua nel wizard →", type="primary", use_container_width=True):
        st.switch_page("client_pages/wizard.py")
    if col_b.button("Gestisci progetti", use_container_width=True):
        st.switch_page("client_pages/progetti.py")

