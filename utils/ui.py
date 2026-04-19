"""UI helpers: tema modern light + blu tech (Linear/Vercel/Stripe inspired)."""
import streamlit as st

HORIZON_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Geist:wght@400;500;600;700;800&display=swap');

/* ============================================================
   COLOR SYSTEM — clean tech (light + blue)
   ============================================================ */
:root {
    /* Surfaces */
    --bg-base: #FAFAFB;
    --bg-elevated: #FFFFFF;
    --bg-subtle: #F4F5F7;
    --bg-card: #FFFFFF;
    --bg-card-hover: #F9FAFB;

    /* Borders */
    --border: #E5E7EB;
    --border-strong: #D1D5DB;
    --border-focus: #2F6FED;

    /* Text */
    --text-primary: #0A0A0F;
    --text-secondary: #4B5563;
    --text-muted: #9CA3AF;

    /* Accents — electric blue family */
    --blue-50: #EEF4FF;
    --blue-100: #DCE7FE;
    --blue-500: #2F6FED;
    --blue-600: #2160DC;
    --blue-700: #1A4BB5;
    --blue-glow: rgba(47, 111, 237, 0.15);

    /* Semantic */
    --success: #10B981;
    --success-bg: #ECFDF5;
    --warning: #F59E0B;
    --warning-bg: #FFFBEB;
    --danger: #EF4444;
    --danger-bg: #FEF2F2;

    /* Shadows (clean, layered) */
    --shadow-xs: 0 1px 2px rgba(10, 10, 15, 0.04);
    --shadow-sm: 0 1px 3px rgba(10, 10, 15, 0.06), 0 1px 2px rgba(10, 10, 15, 0.04);
    --shadow-md: 0 4px 12px rgba(10, 10, 15, 0.06), 0 2px 4px rgba(10, 10, 15, 0.04);
    --shadow-lg: 0 12px 28px rgba(10, 10, 15, 0.08), 0 4px 8px rgba(10, 10, 15, 0.04);
    --shadow-blue: 0 4px 14px rgba(47, 111, 237, 0.20);

    --radius-sm: 8px;
    --radius-md: 12px;
    --radius-lg: 16px;
    --radius-xl: 20px;
}

/* ============================================================
   GLOBAL
   ============================================================ */
* {
    font-family: 'Geist', 'Inter', -apple-system, BlinkMacSystemFont, system-ui, sans-serif !important;
    -webkit-font-smoothing: antialiased;
}

html, body, .stApp {
    background: var(--bg-base) !important;
    color: var(--text-primary) !important;
}

.stApp::before {
    content: '';
    position: fixed; top: 0; left: 0; right: 0; height: 400px;
    background:
        radial-gradient(ellipse at 20% 0%, rgba(47, 111, 237, 0.04), transparent 50%),
        radial-gradient(ellipse at 80% 0%, rgba(47, 111, 237, 0.03), transparent 60%);
    pointer-events: none; z-index: 0;
}

.main > div { padding-top: 2.5rem; padding-bottom: 4rem; max-width: 1380px; position: relative; z-index: 1; }

/* ============================================================
   TYPOGRAPHY
   ============================================================ */
h1 {
    font-weight: 700 !important;
    font-size: 2.5rem !important;
    letter-spacing: -0.035em !important;
    line-height: 1.1 !important;
    color: var(--text-primary) !important;
    background: none !important;
    -webkit-text-fill-color: var(--text-primary) !important;
    margin-bottom: 0.5rem !important;
}
h2 {
    font-weight: 700 !important;
    font-size: 1.625rem !important;
    letter-spacing: -0.025em !important;
    color: var(--text-primary) !important;
    margin-top: 2rem !important;
    margin-bottom: 1rem !important;
}
h3 {
    font-weight: 600 !important;
    font-size: 1.125rem !important;
    letter-spacing: -0.015em !important;
    color: var(--text-primary) !important;
    margin-bottom: 0.6rem !important;
}
h4 { font-weight: 600 !important; font-size: 0.95rem !important; color: var(--text-primary) !important; }

p, .stMarkdown { color: var(--text-primary); line-height: 1.6; }
.stCaption, [data-testid="stCaptionContainer"], small {
    color: var(--text-secondary) !important;
    font-size: 0.875rem !important;
    font-weight: 400 !important;
}

/* ============================================================
   SIDEBAR
   ============================================================ */
[data-testid="stSidebar"] {
    background: var(--bg-elevated) !important;
    border-right: 1px solid var(--border) !important;
    padding-top: 0.5rem;
}
[data-testid="stSidebar"] h3 {
    font-size: 0.7rem !important;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted) !important;
    font-weight: 600 !important;
}
[data-testid="stSidebarNav"] a {
    border-radius: var(--radius-sm) !important;
    padding: 8px 12px !important;
    margin: 2px 0 !important;
    transition: all 0.12s ease !important;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
}
[data-testid="stSidebarNav"] a:hover {
    background: var(--bg-subtle) !important;
    color: var(--text-primary) !important;
}
[data-testid="stSidebarNav"] a[aria-current="page"] {
    background: var(--blue-50) !important;
    color: var(--blue-600) !important;
    font-weight: 600 !important;
}

/* ============================================================
   METRICS — clean white cards
   ============================================================ */
[data-testid="stMetric"] {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 20px 22px !important;
    transition: all 0.18s ease;
    box-shadow: var(--shadow-xs);
    min-height: 0;
}
[data-testid="stMetric"]:hover {
    border-color: var(--border-strong);
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
}
[data-testid="stMetricValue"] {
    font-size: 2rem !important;
    font-weight: 700 !important;
    line-height: 1.2 !important;
    color: var(--text-primary) !important;
    background: none !important;
    -webkit-text-fill-color: var(--text-primary) !important;
    letter-spacing: -0.025em;
}
[data-testid="stMetricLabel"] {
    font-size: 0.75rem !important;
    color: var(--text-muted) !important;
    font-weight: 500 !important;
    text-transform: none !important;
    letter-spacing: normal !important;
    margin-bottom: 6px !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.8rem !important;
    font-weight: 500 !important;
}

/* ============================================================
   BUTTONS
   ============================================================ */
.stButton > button, .stDownloadButton > button, .stLinkButton > a {
    background: var(--bg-elevated) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    padding: 9px 18px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    letter-spacing: -0.005em !important;
    transition: all 0.15s ease !important;
    box-shadow: var(--shadow-xs) !important;
    line-height: 1.4 !important;
    height: auto !important;
    min-height: unset !important;
}
.stButton > button:hover, .stDownloadButton > button:hover, .stLinkButton > a:hover {
    background: var(--bg-subtle) !important;
    border-color: var(--border-strong) !important;
    color: var(--text-primary) !important;
    box-shadow: var(--shadow-sm) !important;
}

/* Primary buttons */
button[kind="primary"], .stButton > button[kind="primary"] {
    background: var(--blue-500) !important;
    color: white !important;
    border: 1px solid var(--blue-500) !important;
    font-weight: 600 !important;
    box-shadow: var(--shadow-blue) !important;
}
button[kind="primary"]:hover {
    background: var(--blue-600) !important;
    border-color: var(--blue-600) !important;
    color: white !important;
    box-shadow: 0 6px 18px rgba(47, 111, 237, 0.30) !important;
    transform: translateY(-1px);
}

/* ============================================================
   TABS — pill segmented
   ============================================================ */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: var(--bg-subtle);
    padding: 4px;
    border-radius: var(--radius-md);
    border: 1px solid var(--border);
    width: fit-content;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    padding: 7px 16px !important;
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    color: var(--text-secondary) !important;
    background: transparent !important;
    transition: all 0.15s !important;
    min-height: 0 !important;
}
.stTabs [data-baseweb="tab"]:hover { color: var(--text-primary) !important; }
.stTabs [aria-selected="true"] {
    background: var(--bg-elevated) !important;
    color: var(--blue-600) !important;
    font-weight: 600 !important;
    box-shadow: var(--shadow-xs);
}

/* ============================================================
   INPUTS
   ============================================================ */
.stTextInput input, .stTextArea textarea, .stNumberInput input,
[data-baseweb="input"] > div, [data-baseweb="textarea"] > div {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-primary) !important;
    transition: all 0.15s !important;
}
.stTextInput input:focus, .stTextArea textarea:focus, .stNumberInput input:focus {
    border-color: var(--border-focus) !important;
    box-shadow: 0 0 0 3px var(--blue-glow) !important;
    outline: none !important;
}
.stSelectbox > div > div, [data-baseweb="select"] > div {
    background: var(--bg-elevated) !important;
    border-color: var(--border) !important;
    border-radius: var(--radius-md) !important;
}
.stTextInput label, .stSelectbox label, .stTextArea label, .stNumberInput label,
.stSlider label, .stRadio label, .stCheckbox label, .stFileUploader label {
    font-weight: 500 !important;
    font-size: 0.875rem !important;
    color: var(--text-primary) !important;
    margin-bottom: 6px !important;
}

/* Slider */
[data-baseweb="slider"] [role="slider"] {
    background: var(--blue-500) !important;
    border: 3px solid white !important;
    box-shadow: 0 2px 8px rgba(47, 111, 237, 0.30) !important;
}
[data-baseweb="slider"] [data-testid="stTickBarMin"],
[data-baseweb="slider"] [data-testid="stTickBarMax"] { color: var(--text-muted) !important; }

/* ============================================================
   DATAFRAMES
   ============================================================ */
[data-testid="stDataFrame"], [data-testid="stTable"] {
    border-radius: var(--radius-md);
    overflow: hidden;
    border: 1px solid var(--border) !important;
    box-shadow: var(--shadow-xs);
}
[data-testid="stDataFrame"] table { background: var(--bg-elevated) !important; }
[data-testid="stDataFrame"] th {
    background: var(--bg-subtle) !important;
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    font-size: 0.75rem !important;
    border-bottom: 1px solid var(--border) !important;
}
[data-testid="stDataFrame"] td {
    color: var(--text-primary) !important;
    font-size: 0.85rem !important;
}

/* ============================================================
   ALERTS
   ============================================================ */
.stAlert, [data-testid="stAlert"] {
    border-radius: var(--radius-md) !important;
    padding: 14px 18px !important;
    border: 1px solid var(--border) !important;
    background: var(--bg-elevated) !important;
    box-shadow: var(--shadow-xs);
}
[data-testid="stAlert"][kind="info"] {
    background: var(--blue-50) !important; border-color: var(--blue-100) !important;
}
[data-testid="stAlert"][kind="success"] {
    background: var(--success-bg) !important; border-color: #A7F3D0 !important;
}
[data-testid="stAlert"][kind="warning"] {
    background: var(--warning-bg) !important; border-color: #FDE68A !important;
}
[data-testid="stAlert"][kind="error"] {
    background: var(--danger-bg) !important; border-color: #FECACA !important;
}

/* ============================================================
   HERO CARD
   ============================================================ */
.hero-card {
    background:
        radial-gradient(ellipse at 100% 0%, rgba(47,111,237,0.10), transparent 55%),
        linear-gradient(135deg, #1A1F2E 0%, #0F1623 100%);
    border: 1px solid #1F2937;
    border-radius: 24px;
    padding: 44px 40px;
    color: white;
    margin-bottom: 28px;
    position: relative;
    overflow: hidden;
    box-shadow: var(--shadow-lg);
}
.hero-card::after {
    content: '';
    position: absolute; bottom: -50%; right: -10%;
    width: 320px; height: 320px;
    background: radial-gradient(circle, rgba(47,111,237,0.18) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}
.hero-card h2 {
    font-weight: 700 !important;
    font-size: 2.4rem !important;
    color: white !important;
    margin: 0 0 12px !important;
    letter-spacing: -0.03em;
    line-height: 1.1;
}
.hero-card p {
    color: rgba(255,255,255,0.72);
    font-size: 1rem;
    line-height: 1.6;
    margin: 0; max-width: 620px;
}

/* ============================================================
   PREVIEW / STEP CARDS
   ============================================================ */
.preview-card, .step-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 22px 24px;
    margin-bottom: 12px;
    transition: all 0.18s ease;
    box-shadow: var(--shadow-xs);
}
.preview-card:hover, .step-card:hover {
    border-color: var(--border-strong);
    box-shadow: var(--shadow-md);
    transform: translateY(-1px);
}
.step-done { border-left: 3px solid var(--success); }
.step-pending { border-left: 3px solid var(--blue-500); }
.step-todo { border-left: 3px solid var(--border-strong); opacity: 0.7; }

.step-num {
    display: inline-flex; align-items: center; justify-content: center;
    width: 26px; height: 26px;
    border-radius: 8px;
    background: var(--blue-500);
    color: white;
    font-weight: 700;
    font-size: 12px;
    margin-right: 12px;
}

/* ============================================================
   PROGRESS
   ============================================================ */
.stProgress > div > div { background: var(--blue-500) !important; border-radius: 99px !important; }
.stProgress > div { border-radius: 99px !important; background: var(--bg-subtle) !important; }

/* ============================================================
   DIVIDERS
   ============================================================ */
hr { border-color: var(--border) !important; margin: 2rem 0 !important; }

/* ============================================================
   EXPANDERS — FIX overflow
   ============================================================ */
[data-testid="stExpander"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    box-shadow: var(--shadow-xs);
    overflow: hidden;
}
[data-testid="stExpander"] details > summary,
[data-testid="stExpander"] summary {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 14px 18px !important;
    font-weight: 500 !important;
    color: var(--text-primary) !important;
    cursor: pointer;
    line-height: 1.5 !important;
    list-style: none !important;
    min-height: auto !important;
}
[data-testid="stExpander"] summary:hover { background: var(--bg-subtle) !important; }
[data-testid="stExpander"] [data-testid="stExpanderDetails"],
[data-testid="stExpander"] > div:nth-child(2) {
    background: transparent !important;
    border: none !important;
    border-top: 1px solid var(--border) !important;
    padding: 16px 18px !important;
}

/* ============================================================
   CODE BLOCKS
   ============================================================ */
code {
    background: var(--blue-50) !important;
    color: var(--blue-700) !important;
    padding: 2px 7px !important;
    border-radius: 6px !important;
    font-size: 0.85em !important;
    font-family: 'Geist Mono', 'JetBrains Mono', monospace !important;
    border: 1px solid var(--blue-100);
    font-weight: 500;
}
pre code {
    background: var(--bg-subtle) !important;
    color: var(--text-primary) !important;
    border: none;
    display: block;
    padding: 14px !important;
}

/* ============================================================
   FILE UPLOADER
   ============================================================ */
[data-testid="stFileUploader"] section {
    background: var(--bg-elevated) !important;
    border: 2px dashed var(--border-strong) !important;
    border-radius: var(--radius-lg) !important;
    padding: 28px !important;
    transition: all 0.15s !important;
}
[data-testid="stFileUploader"] section:hover {
    border-color: var(--blue-500) !important;
    background: var(--blue-50) !important;
}
[data-testid="stFileUploader"] button {
    background: var(--blue-500) !important;
    color: white !important;
    border: none !important;
}

/* ============================================================
   TOAST
   ============================================================ */
[data-testid="stToast"] {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--radius-md) !important;
    box-shadow: var(--shadow-lg) !important;
    color: var(--text-primary) !important;
}

/* ============================================================
   PLOTLY
   ============================================================ */
.js-plotly-plot, .plotly { background: transparent !important; }
.js-plotly-plot .plotly .modebar { background: transparent !important; }

/* ============================================================
   RADIO / CHECKBOX
   ============================================================ */
[data-testid="stRadio"] [role="radiogroup"] { gap: 8px; }
[data-baseweb="radio"] { font-weight: 500; }

/* ============================================================
   MICRO INTERACTIONS
   ============================================================ */
@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
.main > div > div { animation: fadeInUp 0.3s cubic-bezier(0.4, 0, 0.2, 1); }

/* Selection */
::selection { background: var(--blue-500); color: white; }

/* ============================================================
   HIDE STREAMLIT NATIVE CHROME (deploy badge, menu, footer, tooltip)
   ============================================================ */
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stToolbar"],
.stDeployButton, header [data-testid="stStatusWidget"] {
    visibility: hidden !important;
    display: none !important;
}

/* Top-right keyboard tooltip "keyb..." e widget di stato */
[data-testid="stHeader"] {
    background: transparent !important;
    height: 0 !important;
}

/* Hide section header / separator nella sidebar (usiamo il nostro switch) */
[data-testid="stSidebarNavSeparator"] { display: none !important; }
[data-testid="stSidebarNav"] [role="heading"],
[data-testid="stSidebarNav"] > div > div:first-child:not([class*="link"]),
[data-testid="stSidebarNav"] section header { display: none !important; }

/* Radio segmented (per il section switcher) */
[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {
    background: #F4F5F7;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 4px;
    gap: 4px !important;
    width: 100%;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    flex: 1; margin: 0 !important;
    background: transparent !important;
    border-radius: 7px !important;
    padding: 6px 12px !important;
    cursor: pointer;
    transition: all 0.15s;
    text-align: center;
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    font-size: 0.825rem !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
    background: rgba(255,255,255,0.6) !important;
    color: var(--text-primary) !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label[data-baseweb="radio"] > div:first-child,
[data-testid="stSidebar"] [data-testid="stRadio"] input { display: none !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
    background: #FFFFFF !important;
    color: var(--blue-600) !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 3px rgba(10,10,15,0.08);
}

</style>
"""


def apply_theme():
    st.markdown(HORIZON_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = ""):
    st.markdown(f"# {title}")
    if subtitle:
        st.caption(subtitle)
