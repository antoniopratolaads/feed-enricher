"""Home Cliente: hero moderno + action cards + status progetto."""
import streamlit as st
import pandas as pd

from utils.state import init_state, current_df
from utils.ui import apply_theme, api_key_banner, onboarding_card
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

# First-run onboarding (dismissable)
onboarding_card()

# API key warning banner (renders only when no key configured)
api_key_banner()

# ============================================================
# HERO — gradient blue + intro
# ============================================================
st.markdown(
    """
    <div style='background:linear-gradient(135deg, #2F6FED 0%, #1A4BB5 100%);
                border-radius:24px; padding:44px 48px; color:#FFFFFF;
                margin-bottom:28px; box-shadow:0 24px 52px rgba(47,111,237,0.22);
                position:relative; overflow:hidden;'>
        <div style='position:absolute; top:-80px; right:-60px; width:380px; height:380px;
                    background:radial-gradient(circle, rgba(255,255,255,0.14), transparent 60%);
                    pointer-events:none;'></div>
        <div style='position:absolute; bottom:-120px; left:-80px; width:340px; height:340px;
                    background:radial-gradient(circle, rgba(255,255,255,0.08), transparent 70%);
                    pointer-events:none;'></div>
        <div style='position:relative; z-index:1;'>
            <div style='display:inline-block; background:rgba(255,255,255,0.16);
                        border:1px solid rgba(255,255,255,0.22); color:#FFFFFF;
                        font-size:0.72rem; letter-spacing:0.15em; text-transform:uppercase;
                        font-weight:700; padding:5px 12px; border-radius:999px; margin-bottom:16px;'>
                AI · Feed optimization
            </div>
            <div style='font-size:2.75rem; font-weight:800; letter-spacing:-0.035em;
                        line-height:1.05; margin-bottom:14px;'>
                Feed Enricher Pro
            </div>
            <div style='font-size:1.1rem; opacity:0.92; max-width:620px; line-height:1.55;'>
                Carica il feed prodotto, Claude lo arricchisce con best practice settoriali,
                scarichi il catalogo ottimizzato per Google Merchant Center + Meta Catalog.
                <b style='color:#FFFFFF;'>Pronto in 5 minuti.</b>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# ACTION CARDS — 3 CTA modernissime
# ============================================================
df = current_df()
df_loaded = df is not None
api_ok = bool(cfg.get("anthropic_api_key"))

# Clickable card effect: bigger button on top, rich card below
st.markdown(
    """
    <style>
    .home-action-card {
        background:#FFFFFF;
        border:1px solid #E5E7EB;
        border-radius:18px;
        padding:24px 24px 20px;
        height:100%;
        transition:all 0.2s ease;
        position:relative;
        overflow:hidden;
        min-height:230px;
        display:flex; flex-direction:column; gap:12px;
    }
    .home-action-card::before {
        content:"";
        position:absolute; top:0; left:0; right:0; height:3px;
        background:linear-gradient(90deg, #2F6FED, #8B5CF6);
        opacity:0.9;
    }
    .home-action-card.muted::before {
        background:linear-gradient(90deg, #D1D5DB, #9CA3AF);
    }
    .home-action-card:hover {
        transform:translateY(-2px);
        box-shadow:0 12px 28px rgba(10,10,15,0.08);
        border-color:#DCE7FE;
    }
    .home-action-icon {
        width:48px; height:48px; border-radius:14px;
        display:flex; align-items:center; justify-content:center;
        font-size:1.5rem; color:#FFFFFF;
        background:linear-gradient(135deg, #2F6FED, #8B5CF6);
        box-shadow:0 6px 16px rgba(47,111,237,0.25);
        flex-shrink:0;
    }
    .home-action-icon.green {
        background:linear-gradient(135deg, #10B981, #059669);
        box-shadow:0 6px 16px rgba(16,185,129,0.25);
    }
    .home-action-icon.purple {
        background:linear-gradient(135deg, #8B5CF6, #6D28D9);
        box-shadow:0 6px 16px rgba(139,92,246,0.25);
    }
    .home-action-title {
        font-size:1.1rem; font-weight:700; color:#0A0A0F;
        letter-spacing:-0.015em; line-height:1.25;
    }
    .home-action-desc {
        font-size:0.85rem; color:#6B7280; line-height:1.55;
        flex-grow:1;
    }
    .home-action-meta {
        display:flex; gap:6px; flex-wrap:wrap; margin-top:4px;
    }
    .home-action-chip {
        font-size:0.7rem; color:#4B5563;
        background:#F4F5F7; border:1px solid #E5E7EB;
        padding:3px 8px; border-radius:999px; font-weight:500;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

col_a, col_b, col_c = st.columns(3, gap="medium")

with col_a:
    st.markdown(
        """
        <div class='home-action-card'>
            <div class='home-action-icon'>✦</div>
            <div class='home-action-title'>Avvia Wizard Enrichment</div>
            <div class='home-action-desc'>
                Flusso guidato in 4 step: progetto → upload feed → AI enrichment → scarica catalogo.
                Salvataggio automatico, puoi riprendere in ogni momento.
            </div>
            <div class='home-action-meta'>
                <span class='home-action-chip'>⏱ ~5 min</span>
                <span class='home-action-chip'>Consigliato</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Inizia ora →", type="primary", use_container_width=True, key="_cta_wizard"):
        st.switch_page("client_pages/wizard.py")

with col_b:
    st.markdown(
        """
        <div class='home-action-card'>
            <div class='home-action-icon green'>◉</div>
            <div class='home-action-title'>Prova con dati demo</div>
            <div class='home-action-desc'>
                Dataset finto realistico con 500 prodotti, performance GAds simulate,
                Shopify con distribuzione Pareto. Zero setup.
            </div>
            <div class='home-action-meta'>
                <span class='home-action-chip'>500 prodotti</span>
                <span class='home-action-chip'>No API key</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Carica demo", use_container_width=True, key="_cta_demo"):
        with st.spinner("Genero dati realistici..."):
            load_demo_into_session(st.session_state, 500)
        log_event(st.session_state["session_id"], "demo_loaded", {"n": 500})
        save_snapshot(st.session_state["session_id"], st.session_state)
        st.success("Demo caricata · 500 prodotti pronti.")
        st.rerun()

with col_c:
    st.markdown(
        """
        <div class='home-action-card'>
            <div class='home-action-icon purple'>◆</div>
            <div class='home-action-title'>Come funziona</div>
            <div class='home-action-desc'>
                Guida completa step-by-step. Setup, pipeline, feature avanzate,
                export Google + Meta, FAQ. Perfetto per il primo avvio.
            </div>
            <div class='home-action-meta'>
                <span class='home-action-chip'>Docs in-app</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Leggi la guida", use_container_width=True, key="_cta_guide"):
        st.switch_page("client_pages/come_funziona.py")

st.markdown("<div style='height:28px;'></div>", unsafe_allow_html=True)

# ============================================================
# CHECKLIST REQUISITI — più compatta
# ============================================================
project_named = bool(get_project_info(st.session_state["session_id"]))

col_left, col_right = st.columns([3, 2], gap="large")

with col_left:
    st.markdown("### Checklist setup")
    items = [
        ("Feed prodotto caricato", df_loaded,
         "XML · CSV · TSV · JSON · Excel · da URL o file", "client_pages/upload_feed.py"),
        ("API Key Claude configurata", api_ok,
         "Per la generazione AI. Salvata solo in locale.", "client_pages/settings.py"),
        ("Progetto salvato", project_named,
         "Dai un nome al progetto per riaprirlo quando vuoi.", "client_pages/progetti.py"),
    ]
    for title, ok, desc, target in items:
        icon = "●" if ok else "○"
        icon_color = "#10B981" if ok else "#D1D5DB"
        state_label = "Completato" if ok else "Da fare"
        state_bg = "#ECFDF5" if ok else "#F4F5F7"
        state_color = "#047857" if ok else "#6B7280"
        st.markdown(
            f"""
            <div style='background:#FFFFFF; border:1px solid #E5E7EB;
                        border-left:3px solid {icon_color};
                        padding:14px 18px; border-radius:12px; margin-bottom:10px;
                        display:flex; align-items:center; justify-content:space-between; gap:14px;
                        box-shadow:0 1px 2px rgba(10,10,15,0.04);'>
                <div style='flex:1;'>
                    <div style='display:flex; align-items:center; gap:10px;'>
                        <span style='color:{icon_color};font-size:15px;'>{icon}</span>
                        <b style='color:#0A0A0F; font-size:0.94rem;'>{title}</b>
                    </div>
                    <div style='color:#6B7280; font-size:0.82rem; margin-left:24px; margin-top:2px;'>
                        {desc}
                    </div>
                </div>
                <div style='background:{state_bg}; color:{state_color}; font-size:0.72rem;
                            font-weight:600; padding:4px 10px; border-radius:999px;
                            text-transform:uppercase; letter-spacing:0.04em;'>
                    {state_label}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

with col_right:
    st.markdown("### Cosa ottieni")
    st.markdown(
        """
        <div style='background:linear-gradient(180deg, #FAFAFB 0%, #FFFFFF 100%);
                    border:1px solid #E5E7EB; border-left:4px solid #10B981;
                    border-radius:14px; padding:20px 22px;
                    box-shadow:0 1px 2px rgba(10,10,15,0.04);'>
            <div style='font-weight:700; color:#0A0A0F; margin-bottom:10px; font-size:0.95rem;'>
                Deliverables
            </div>
            <ul style='margin:0; padding-left:18px; line-height:2; color:#4B5563; font-size:0.88rem;'>
                <li>Titoli ottimizzati <b>Google + Meta</b></li>
                <li>Descrizioni arricchite settoriali</li>
                <li>Attributi popolati (colore, taglia, materiale)</li>
                <li>Categoria <b>Google taxonomy</b></li>
                <li>Custom label performance / margine</li>
                <li>Bundle ZIP pronto da caricare</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# SE C'E' GIA' UN PROGETTO IN CORSO
# ============================================================
if df is not None:
    st.divider()
    pname = get_project_name(st.session_state["session_id"])
    st.markdown(f"### Progetto attivo · {pname}")
    c = st.columns(4)
    c[0].metric("Prodotti", f"{len(df):,}")
    c[1].metric("Brand", df["brand"].nunique() if "brand" in df.columns else "—")
    enriched_done = (df.get("title", pd.Series()).astype(str).str.len().mean() > 70) \
        if "title" in df.columns else False
    c[2].metric("Enrichment", "✓ fatto" if enriched_done else "da fare")
    c[3].metric("Sessione", st.session_state["session_id"][-8:])

    col_a, col_b = st.columns(2)
    if col_a.button("Continua nel wizard →", type="primary", use_container_width=True,
                    key="_cta_continue"):
        st.switch_page("client_pages/wizard.py")
    if col_b.button("Gestisci progetti", use_container_width=True, key="_cta_projects"):
        st.switch_page("client_pages/progetti.py")
