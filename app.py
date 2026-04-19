"""Feed Enricher Pro — entry point con navigazione a 2 sezioni separate."""
import streamlit as st

st.set_page_config(
    page_title="Feed Enricher Pro",
    page_icon="◐",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"Get Help": None, "Report a bug": None, "About": None},
)

from utils.state import init_state
from utils.history import init_session
from utils.config import load_config
from utils.ui import apply_theme

init_state()
init_session(st.session_state)
if "config" not in st.session_state:
    st.session_state["config"] = load_config()
    if st.session_state["config"].get("anthropic_api_key"):
        st.session_state["api_key"] = st.session_state["config"]["anthropic_api_key"]

# ============================================================
# DEFINIZIONE PAGINE
# ============================================================
client_pages = [
    st.Page("client_pages/home.py",            title="Home",                default=True),
    st.Page("client_pages/wizard.py",          title="Wizard Enrichment"),
    st.Page("client_pages/progetti.py",        title="Progetti"),
    st.Page("client_pages/settings.py",        title="Settings"),
    st.Page("client_pages/upload_feed.py",     title="Upload Feed"),
    st.Page("client_pages/enrichment_ai.py",   title="Enrichment AI"),
    st.Page("client_pages/scarica_catalogo.py", title="Scarica Catalogo"),
]

labelizer_pages = [
    st.Page("labelizer_pages/hub.py",                title="Hub",                default=True),
    st.Page("labelizer_pages/google_ads.py",         title="Google Ads"),
    st.Page("labelizer_pages/meta_ads.py",           title="Meta Ads"),
    st.Page("labelizer_pages/shopify.py",            title="Shopify"),
    st.Page("labelizer_pages/label_performance.py",  title="Label Performance"),
    st.Page("labelizer_pages/label_margine.py",      title="Label Margine"),
    st.Page("labelizer_pages/label_stagionalita.py", title="Label Stagionalità"),
    st.Page("labelizer_pages/label_stock.py",        title="Label Stock"),
    st.Page("labelizer_pages/feed_supplementare.py", title="Feed Supplementare"),
    st.Page("labelizer_pages/analytics.py",          title="Analytics"),
]

section = st.session_state.get("_section", "cliente")

# Lista flat (no group header) — la separazione visuale è data dal nostro switch
active_pages = client_pages if section == "cliente" else labelizer_pages
pg = st.navigation(active_pages, position="sidebar")

# ============================================================
# SIDEBAR — top section switcher (pill style)
# ============================================================
apply_theme()

with st.sidebar:
    # Header app
    st.markdown(
        "<div style='padding:8px 4px 14px; font-weight:700; font-size:1rem; "
        "color:#0A0A0F; letter-spacing:-0.01em;'>"
        "<span style='color:#2F6FED;'>◐</span>&nbsp;&nbsp;Feed Enricher Pro</div>",
        unsafe_allow_html=True,
    )

    # Section switcher (radio-style segmented)
    new_section = st.radio(
        "Sezione",
        options=["cliente", "labelizer"],
        format_func=lambda x: {"cliente": "Cliente", "labelizer": "Labelizer"}[x],
        index=0 if section == "cliente" else 1,
        horizontal=True,
        label_visibility="collapsed",
        key="_section_radio",
    )
    if new_section != section:
        st.session_state["_section"] = new_section
        st.rerun()

    st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)

pg.run()
