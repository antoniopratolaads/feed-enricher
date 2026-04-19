"""Feed Enricher Pro — entry point con navigation a gruppi."""
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
from utils.ui import apply_theme, render_sidebar_status

init_state()
init_session(st.session_state)
if "config" not in st.session_state:
    st.session_state["config"] = load_config()
    if st.session_state["config"].get("anthropic_api_key"):
        st.session_state["api_key"] = st.session_state["config"]["anthropic_api_key"]

# ============================================================
# DEFINIZIONE PAGINE — raggruppate (cliente / labelizer)
# ============================================================
client_pages = [
    st.Page("client_pages/home.py",            title="Home",                icon=":material/home:", default=True),
    st.Page("client_pages/wizard.py",          title="Wizard Enrichment",   icon=":material/auto_awesome:"),
    st.Page("client_pages/upload_feed.py",     title="Upload Feed",         icon=":material/upload_file:"),
    st.Page("client_pages/enrichment_ai.py",   title="Enrichment AI",       icon=":material/bolt:"),
    st.Page("client_pages/scarica_catalogo.py", title="Scarica Catalogo",   icon=":material/download:"),
    st.Page("client_pages/progetti.py",        title="Progetti",            icon=":material/folder:"),
    st.Page("client_pages/settings.py",        title="Settings",            icon=":material/settings:"),
]

labelizer_pages = [
    st.Page("labelizer_pages/hub.py",                title="Hub",                 icon=":material/dashboard:"),
    st.Page("labelizer_pages/google_ads.py",         title="Google Ads",          icon=":material/campaign:"),
    st.Page("labelizer_pages/meta_ads.py",           title="Meta Ads",            icon=":material/ads_click:"),
    st.Page("labelizer_pages/shopify.py",            title="Shopify",             icon=":material/storefront:"),
    st.Page("labelizer_pages/label_performance.py",  title="Label Performance",   icon=":material/speed:"),
    st.Page("labelizer_pages/label_margine.py",      title="Label Margine",       icon=":material/euro:"),
    st.Page("labelizer_pages/label_stagionalita.py", title="Label Stagionalità",  icon=":material/calendar_month:"),
    st.Page("labelizer_pages/label_stock.py",        title="Label Stock",         icon=":material/inventory_2:"),
    st.Page("labelizer_pages/feed_supplementare.py", title="Feed Supplementare",  icon=":material/table_chart:"),
    st.Page("labelizer_pages/analytics.py",          title="Analytics",           icon=":material/analytics:"),
]

pg = st.navigation(
    {
        "Cliente": client_pages,
        "Labelizer": labelizer_pages,
    },
    position="sidebar",
    expanded=True,
)

apply_theme()

# ============================================================
# SIDEBAR header + status (API key, progetto attivo)
# ============================================================
with st.sidebar:
    st.markdown(
        "<div style='padding:6px 4px 18px; font-weight:700; font-size:1rem; "
        "color:#0A0A0F; letter-spacing:-0.01em;'>"
        "<span style='color:#2F6FED;'>◐</span>&nbsp;&nbsp;Feed Enricher Pro</div>",
        unsafe_allow_html=True,
    )

render_sidebar_status()

pg.run()
