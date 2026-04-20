"""UI helpers: tema modern light + blu tech (Linear/Vercel/Stripe inspired)."""
import streamlit as st

HORIZON_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=Geist:wght@400;500;600;700;800&display=swap');
@import url('https://fonts.googleapis.com/css2?family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@20..48,100..700,0..1,-50..200&display=swap');

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

/* Preserve Streamlit Material Symbols icons (overrides the `*` rule above) */
[data-testid="stIconMaterial"],
span.material-symbols-rounded,
span.material-icons,
span.material-icons-outlined,
span.material-icons-rounded,
span.material-icons-sharp {
    font-family: 'Material Symbols Rounded', 'Material Icons' !important;
    font-weight: normal !important;
    font-style: normal !important;
    font-variation-settings: 'FILL' 0, 'wght' 400, 'GRAD' 0, 'opsz' 24;
    letter-spacing: normal !important;
    text-transform: none !important;
    white-space: nowrap !important;
    word-wrap: normal !important;
    direction: ltr !important;
    -webkit-font-feature-settings: 'liga';
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
/* Specificità alta per battere emotion CSS: #root + tag + attribute */
#root section[data-testid="stSidebar"],
#root section.stSidebar,
html body section[data-testid="stSidebar"],
html body section[data-testid="stSidebar"][aria-expanded="false"],
html body section[data-testid="stSidebar"][aria-expanded="true"] {
    background: #FFFFFF !important;
    border-right: 1px solid #E5E7EB !important;
    padding-top: 0.5rem !important;
    min-width: 244px !important;
    max-width: 340px !important;
    width: 300px !important;
    transform: translateX(0) !important;
    position: relative !important;
    left: 0 !important;
    top: 0 !important;
    visibility: visible !important;
    display: block !important;
    opacity: 1 !important;
    z-index: 10 !important;
    flex: 0 0 300px !important;
}
/* Rendi il toggle button non necessario (nascondiamo per evitare confusione) */
[data-testid="stBaseButton-headerNoPadding"] {
    display: inline-flex !important;
    visibility: visible !important;
    opacity: 1 !important;
    pointer-events: auto !important;
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

/* Primary buttons — make sure ALL inner text is white (override any cascaded color) */
button[kind="primary"], .stButton > button[kind="primary"], .stDownloadButton > button[kind="primary"] {
    background: var(--blue-500) !important;
    background-image: linear-gradient(180deg, #3D7DF3 0%, #2F6FED 100%) !important;
    color: #FFFFFF !important;
    border: 1px solid var(--blue-600) !important;
    font-weight: 600 !important;
    box-shadow: var(--shadow-blue), inset 0 1px 0 rgba(255,255,255,0.15) !important;
    text-shadow: 0 1px 0 rgba(0,0,0,0.08);
}
button[kind="primary"] *,
button[kind="primary"] p,
button[kind="primary"] div,
button[kind="primary"] span,
button[kind="primary"] strong,
.stButton > button[kind="primary"] * {
    color: #FFFFFF !important;
}
button[kind="primary"]:hover {
    background-image: linear-gradient(180deg, #3070F0 0%, #2160DC 100%) !important;
    border-color: #1A4BB5 !important;
    color: #FFFFFF !important;
    box-shadow: 0 8px 22px rgba(47, 111, 237, 0.35), inset 0 1px 0 rgba(255,255,255,0.2) !important;
    transform: translateY(-1px);
}
button[kind="primary"]:active {
    transform: translateY(0);
    background-image: linear-gradient(180deg, #2160DC 0%, #1A4BB5 100%) !important;
    box-shadow: 0 2px 6px rgba(47, 111, 237, 0.25), inset 0 2px 4px rgba(0,0,0,0.12) !important;
}
button[kind="primary"]:focus:not(:focus-visible) { outline: none; }
button[kind="primary"]:focus-visible {
    outline: 3px solid rgba(47, 111, 237, 0.35) !important;
    outline-offset: 2px;
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


_SIDEBAR_FORCE_OPEN_JS = """
<script>
(function ensureSidebarOpen() {
    const doc = (window.parent && window.parent.document) || document;
    function forceStyles(sb) {
        sb.style.setProperty('min-width', '244px', 'important');
        sb.style.setProperty('max-width', '340px', 'important');
        sb.style.setProperty('width', '300px', 'important');
        sb.style.setProperty('transform', 'translateX(0)', 'important');
        sb.style.setProperty('visibility', 'visible', 'important');
        sb.style.setProperty('display', 'block', 'important');
        sb.style.setProperty('opacity', '1', 'important');
        sb.style.setProperty('flex', '0 0 300px', 'important');
    }
    function apply() {
        const sb = doc.querySelector('[data-testid="stSidebar"]');
        if (!sb) return false;
        forceStyles(sb);
        return true;
    }
    // Apply ogni 200ms per 15s — cattura anche re-render Streamlit
    let tries = 0;
    const iv = setInterval(() => {
        apply();
        if (++tries > 75) clearInterval(iv);
    }, 200);
    // MutationObserver permanente — riapplica se Streamlit cambia stile sidebar
    try {
        const obs = new MutationObserver(() => apply());
        obs.observe(doc.body, {subtree: true, childList: true, attributes: true,
                               attributeFilter: ['style', 'aria-expanded']});
    } catch (_) {}
})();
</script>
"""


def apply_theme():
    st.markdown(HORIZON_CSS, unsafe_allow_html=True)
    # JS deve girare in iframe component per accedere a window.parent.document
    try:
        import streamlit.components.v1 as _components
        _components.html(_SIDEBAR_FORCE_OPEN_JS, height=0, width=0)
    except Exception:
        pass


def page_header(title: str, subtitle: str = ""):
    st.markdown(f"# {title}")
    if subtitle:
        st.caption(subtitle)


def onboarding_card(force: bool = False):
    """First-run tutorial shown above the Home hero.

    Hides itself once the user clicks 'Ho capito'. Tracks state in
    session_state['_onboarded']. Pass `force=True` to display unconditionally
    (used from a 'Rivedi tutorial' button).
    """
    dismissed = st.session_state.get("_onboarded", False)
    if dismissed and not force:
        return
    st.markdown(
        """
        <div style='background:linear-gradient(135deg, #EEF4FF 0%, #FAFAFB 100%);
                    border:1px solid #DCE7FE; border-radius:16px; padding:20px 24px;
                    margin-bottom:20px; position:relative; overflow:hidden;'>
            <div style='font-size:0.72rem; color:#2F6FED; font-weight:700;
                        letter-spacing:0.08em; text-transform:uppercase; margin-bottom:6px;'>
                Benvenuto
            </div>
            <div style='font-size:1.15rem; font-weight:700; color:#0A0A0F; margin-bottom:8px;'>
                Come funziona Feed Enricher Pro
            </div>
            <ol style='margin:6px 0 12px 18px; color:#4B5563; font-size:0.88rem; line-height:1.8;'>
                <li><b>Settings</b> — incolla la tua API key Claude (costa, vai piano)</li>
                <li><b>Upload Feed</b> — carica XML/CSV da URL o file (Shopify/Magento/WooCommerce)</li>
                <li><b>Enrichment AI</b> — scegli settore e lancia: titoli, descrizioni, attributi</li>
                <li><b>Catalog Optimizer</b> — scarica TSV Google + Meta pronti all'upload</li>
            </ol>
            <div style='color:#6B7280; font-size:0.78rem; margin-top:6px;'>
                Suggerimento: prova subito con <b>Carica demo</b> sotto (500 prodotti finti).
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.button("Ho capito · nascondi", key="_onboarding_dismiss"):
        st.session_state["_onboarded"] = True
        st.rerun()


def api_key_banner():
    """Show warning banner on top of page if Anthropic API key missing.

    Includes inline CTA to jump to Settings. Safe to call from any page
    - renders nothing when key is present.
    """
    cfg = st.session_state.get("config", {}) or {}
    has_key = bool(cfg.get("anthropic_api_key") or cfg.get("openai_api_key"))
    if has_key:
        return
    st.markdown(
        "<div style='background:#FEF3C7; border:1px solid #F59E0B; "
        "border-left:4px solid #F59E0B; padding:14px 18px; border-radius:12px; "
        "margin-bottom:20px; display:flex; align-items:center; justify-content:space-between; gap:16px;'>"
        "<div><strong style='color:#92400E;'>API key mancante</strong> "
        "<span style='color:#78350F;'>— l'enrichment AI richiede una chiave Claude o OpenAI. "
        "Vai su Settings per configurarla.</span></div>"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button("Apri Settings →", key="_api_key_banner_cta", type="primary"):
        st.switch_page("client_pages/settings.py")


def render_sidebar_status():
    """Compact status panel in sidebar: API key state + active project."""
    cfg = st.session_state.get("config", {}) or {}
    has_anthropic = bool(cfg.get("anthropic_api_key"))
    has_openai = bool(cfg.get("openai_api_key"))

    api_status = "●  AI pronto" if (has_anthropic or has_openai) else "○  API key mancante"
    api_color = "#10B981" if (has_anthropic or has_openai) else "#EF4444"

    df = st.session_state.get("feed_df")
    n_products = len(df) if df is not None else 0
    feed_line = (
        f"<div style='color:#4B5563; font-size:0.78rem;'>"
        f"<span style='color:#10B981;'>●</span>&nbsp;&nbsp;Feed: <b>{n_products:,}</b> prodotti</div>"
        if n_products > 0
        else "<div style='color:#9CA3AF; font-size:0.78rem;'>○&nbsp;&nbsp;Nessun feed caricato</div>"
    )

    st.markdown(
        f"""
        <div style='background:#F4F5F7; border:1px solid #E5E7EB; border-radius:10px;
                    padding:10px 12px; margin:6px 0 14px; font-size:0.78rem;'>
            <div style='color:{api_color}; font-weight:600; margin-bottom:4px;'>{api_status}</div>
            {feed_line}
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# STEPPER (wizard progress indicator)
# ============================================================
def stepper(steps: list[str], current: int):
    """Visual progress indicator for multi-step flows.

    Args:
        steps: list of labels, one per step (e.g. ["Upload", "Settore", "AI", "Export"])
        current: 1-based index of the currently active step
    """
    total = len(steps)
    pct = int(((current - 1) / max(total - 1, 1)) * 100) if total > 1 else 100
    nodes = []
    for i, label in enumerate(steps, start=1):
        if i < current:
            state, bg, fg, border = "done", "#2F6FED", "#FFFFFF", "#2F6FED"
            icon_html = "✓"
        elif i == current:
            state, bg, fg, border = "active", "#FFFFFF", "#2F6FED", "#2F6FED"
            icon_html = str(i)
        else:
            state, bg, fg, border = "pending", "#FFFFFF", "#9CA3AF", "#E5E7EB"
            icon_html = str(i)
        nodes.append(
            f"<div class='step-node step-{state}' style='text-align:center; flex:1; position:relative;'>"
            f"<div style='width:36px; height:36px; border-radius:50%; margin:0 auto; "
            f"display:flex; align-items:center; justify-content:center; background:{bg}; "
            f"color:{fg}; border:2px solid {border}; font-weight:700; font-size:0.9rem; "
            f"box-shadow:{'0 2px 8px rgba(47,111,237,0.25)' if state=='active' else 'none'};'>"
            f"{icon_html}</div>"
            f"<div style='margin-top:8px; font-size:0.75rem; font-weight:{600 if state!='pending' else 400}; "
            f"color:{'#0A0A0F' if state!='pending' else '#9CA3AF'};'>{label}</div>"
            f"</div>"
        )

    st.markdown(
        "<div style='position:relative; padding:8px 12px 20px;'>"
        f"<div style='position:absolute; top:26px; left:12%; right:12%; height:2px; background:#E5E7EB; z-index:0;'></div>"
        f"<div style='position:absolute; top:26px; left:12%; width:calc({pct}% * 0.76); height:2px; background:#2F6FED; z-index:0; transition:width 0.3s;'></div>"
        f"<div style='display:flex; align-items:flex-start; position:relative; z-index:1;'>{''.join(nodes)}</div>"
        "</div>",
        unsafe_allow_html=True,
    )


# ============================================================
# EMPTY STATE — graceful page when prerequisite missing
# ============================================================
def empty_state(icon: str, title: str, description: str, cta_label: str | None = None,
                cta_page: str | None = None, cta_key: str | None = None):
    """Render a centered empty state with optional CTA button.

    Replaces `st.warning(...) + st.stop()` pattern with a designed placeholder.
    """
    st.markdown(
        f"""
        <div style='text-align:center; padding:64px 32px; max-width:520px; margin:40px auto;
                    background:#FFFFFF; border:1px solid #E5E7EB; border-radius:16px;
                    box-shadow:0 1px 3px rgba(10,10,15,0.04);'>
            <div style='font-size:3rem; margin-bottom:12px; opacity:0.7;'>{icon}</div>
            <div style='font-size:1.25rem; font-weight:700; color:#0A0A0F; margin-bottom:8px;'>{title}</div>
            <div style='font-size:0.9rem; color:#6B7280; line-height:1.55; margin-bottom:20px;'>{description}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if cta_label and cta_page:
        col = st.columns([1, 2, 1])[1]
        with col:
            if st.button(cta_label, type="primary", use_container_width=True,
                         key=cta_key or f"_empty_cta_{cta_page}"):
                st.switch_page(cta_page)


# ============================================================
# ERROR BOUNDARY
# ============================================================
def guarded(block_name: str = "questa operazione"):
    """Decorator / context manager to render exceptions as a friendly error card.

    Use as context manager:
        with guarded("enrichment"):
            do_heavy_stuff()
    """
    import contextlib
    import traceback

    @contextlib.contextmanager
    def _cm():
        try:
            yield
        except Exception as e:  # noqa: BLE001
            tb = traceback.format_exc(limit=6)
            st.markdown(
                f"""
                <div style='background:#FEF2F2; border:1px solid #FCA5A5; border-left:4px solid #EF4444;
                            padding:14px 18px; border-radius:12px; margin:12px 0;'>
                    <div style='color:#991B1B; font-weight:700; margin-bottom:4px;'>
                        Errore durante {block_name}
                    </div>
                    <div style='color:#7F1D1D; font-size:0.88rem;'>{type(e).__name__}: {e}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            with st.expander("Dettagli tecnici (per debug)", expanded=False):
                st.code(tb, language="text")
            st.stop()

    return _cm()


# ============================================================
# COST ESTIMATOR
# ============================================================
# Prezzi pubblici Claude + OpenAI (USD per 1M token · Apr 2026)
# Chiavi: nome modello. Valori: input / output / tier qualità 1-5
_PRICES = {
    # ===== Anthropic Claude =====
    "claude-opus-4-6":           {"input": 15.00, "output": 75.00, "tier": 5, "family": "claude"},
    "claude-sonnet-4-6":         {"input": 3.00,  "output": 15.00, "tier": 4, "family": "claude"},
    "claude-haiku-4-5":          {"input": 1.00,  "output": 5.00,  "tier": 3, "family": "claude"},
    "claude-haiku-4-5-20251001": {"input": 1.00,  "output": 5.00,  "tier": 3, "family": "claude"},
    "claude-haiku-3-5":          {"input": 0.80,  "output": 4.00,  "tier": 2, "family": "claude"},

    # ===== OpenAI GPT-5 family =====
    "gpt-5":                     {"input": 1.25,  "output": 10.00, "tier": 5, "family": "openai"},
    "gpt-5-mini":                {"input": 0.25,  "output": 2.00,  "tier": 4, "family": "openai"},
    "gpt-5-nano":                {"input": 0.05,  "output": 0.40,  "tier": 2, "family": "openai"},

    # ===== OpenAI GPT-4.1 family =====
    "gpt-4.1":                   {"input": 2.00,  "output": 8.00,  "tier": 4, "family": "openai"},
    "gpt-4.1-mini":              {"input": 0.40,  "output": 1.60,  "tier": 3, "family": "openai"},
    "gpt-4.1-nano":              {"input": 0.10,  "output": 0.40,  "tier": 2, "family": "openai"},

    # ===== OpenAI GPT-4o family =====
    "gpt-4o":                    {"input": 2.50,  "output": 10.00, "tier": 4, "family": "openai"},
    "gpt-4o-mini":               {"input": 0.15,  "output": 0.60,  "tier": 3, "family": "openai"},

    # ===== OpenAI o-series reasoning =====
    "o3":                        {"input": 2.00,  "output": 8.00,  "tier": 5, "family": "openai"},
    "o3-mini":                   {"input": 0.50,  "output": 2.00,  "tier": 4, "family": "openai"},
    "o4-mini":                   {"input": 1.10,  "output": 4.40,  "tier": 4, "family": "openai"},

    # ===== Legacy =====
    "gpt-4-turbo":               {"input": 10.00, "output": 30.00, "tier": 4, "family": "openai"},
    "gpt-3.5-turbo":             {"input": 0.50,  "output": 1.50,  "tier": 2, "family": "openai"},
}


def estimate_cost(n_rows: int, model: str,
                  tokens_in_per_row: int = 300,
                  tokens_out_per_row: int = 1400,
                  system_prompt_tokens: int = 1000,
                  use_cache: bool = True,
                  use_batch: bool = False) -> dict:
    """Cost estimate for enrichment of N rows with given model.

    Defaults aggiornati al schema GMC+Meta esteso (80+ attributi, product_detail
    8-20 entries, product_highlight 6-10 bullets, rich_text_description HTML):
      - output medio 1800 token (range realistico 1500-2500, max 3500)
      - input payload prodotto 350 token
      - system prompt 5200 token (base + schema + sector brief)
      - prompt caching Anthropic: prima call scrive cache (+25% costo),
        successive leggono cache a 10% del prezzo input

    Returns: dict con input/output/cache/total USD + EUR + token counts
    """
    p = _PRICES.get(model, _PRICES["claude-sonnet-4-6"])

    # Output costo lineare
    total_out = n_rows * tokens_out_per_row
    usd_out = total_out / 1_000_000 * p["output"]

    # Input: con caching il system prompt viene scritto una volta, letto N-1 volte
    # cache write = 1.25x input, cache read = 0.10x input (politica Anthropic)
    user_content_tokens = n_rows * tokens_in_per_row

    if use_cache and n_rows > 1:
        # Prima call paga pieno input + cache write (+25% sui token cached)
        first_call_in = system_prompt_tokens + tokens_in_per_row
        first_call_cache_write = system_prompt_tokens * 0.25  # surcharge
        # Resto delle call: user content pieno + cache read (10% prezzo su system)
        remaining_user = (n_rows - 1) * tokens_in_per_row
        cache_read_tokens = (n_rows - 1) * system_prompt_tokens
        usd_in = (
            (first_call_in + first_call_cache_write + remaining_user)
            / 1_000_000 * p["input"]
            + cache_read_tokens / 1_000_000 * p["input"] * 0.10
        )
        total_in_equivalent = int(
            first_call_in + first_call_cache_write + remaining_user + cache_read_tokens
        )
    else:
        # Senza caching: paga system prompt per ogni call
        total_in_tokens = n_rows * (system_prompt_tokens + tokens_in_per_row)
        usd_in = total_in_tokens / 1_000_000 * p["input"]
        total_in_equivalent = total_in_tokens

    total_usd = usd_in + usd_out

    # Batch API: Anthropic Message Batches + OpenAI Batch API = 50% sconto su tutto
    # Trade-off: response time fino a 24h (sync per cron notturno)
    if use_batch:
        total_usd *= 0.50

    eur = total_usd * 0.93  # EUR/USD 2026

    return {
        "input_usd": usd_in,
        "output_usd": usd_out,
        "total_usd": total_usd,
        "total_eur": eur,
        "tokens_in": total_in_equivalent,
        "tokens_out": total_out,
        "tokens_per_row_out": tokens_out_per_row,
        "tokens_per_row_in": tokens_in_per_row,
        "use_cache": use_cache,
        "use_batch": use_batch,
    }


def cost_estimate_card(n_rows: int, model: str):
    """Display cost estimate card + full model projection for the current batch."""
    if n_rows <= 0:
        return
    est_cached = estimate_cost(n_rows, model, use_cache=True)
    est_nocache = estimate_cost(n_rows, model, use_cache=False)
    est_batch = estimate_cost(n_rows, model, use_cache=True, use_batch=True)
    savings_cache = est_nocache["total_eur"] - est_cached["total_eur"]
    savings_cache_pct = int(savings_cache / est_nocache["total_eur"] * 100) if est_nocache["total_eur"] else 0
    savings_batch = est_cached["total_eur"] - est_batch["total_eur"]

    tone_color = (
        "#10B981" if est_cached["total_eur"] < 5
        else ("#F59E0B" if est_cached["total_eur"] < 30 else "#EF4444")
    )
    st.markdown(
        f"""
        <div style='background:#F9FAFB; border:1px solid #E5E7EB; border-radius:12px;
                    padding:16px 20px; margin:8px 0;'>
            <div style='display:flex; justify-content:space-between; align-items:flex-start; gap:20px; flex-wrap:wrap;'>
                <div>
                    <div style='font-size:0.72rem; color:#6B7280; text-transform:uppercase;
                                letter-spacing:0.08em; font-weight:600; margin-bottom:4px;'>
                        Stima costo · {model}
                    </div>
                    <div style='font-size:1.75rem; font-weight:800; color:{tone_color};
                                letter-spacing:-0.02em; line-height:1;'>
                        ~ €{est_cached['total_eur']:.2f}
                    </div>
                    <div style='font-size:0.72rem; color:#10B981; margin-top:4px; font-weight:600;'>
                        prompt caching attivo · risparmi €{savings_cache:.2f} ({savings_cache_pct}%)
                    </div>
                    <div style='font-size:0.7rem; color:#2F6FED; margin-top:2px;'>
                        Batch API 24h → €{est_batch['total_eur']:.2f} (−€{savings_batch:.2f}, 50% sconto)
                    </div>
                </div>
                <div style='font-size:0.76rem; color:#4B5563; line-height:1.65; text-align:right;'>
                    <b>{n_rows:,}</b> prodotti<br>
                    ~{est_cached['tokens_per_row_in']} tok in/riga<br>
                    ~{est_cached['tokens_per_row_out']} tok out/riga<br>
                    ${est_cached['total_usd']:.2f} USD totali
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def cost_projection_table(n_rows: int):
    """Compare TUTTI i modelli disponibili per il batch corrente."""
    if n_rows <= 0:
        return
    rows = []
    # Ordina per prezzo crescente
    for name, meta in sorted(_PRICES.items(), key=lambda kv: kv[1]["input"] + kv[1]["output"]):
        est = estimate_cost(n_rows, name, use_cache=True)
        est_batch = estimate_cost(n_rows, name, use_cache=True, use_batch=True)
        tier_stars = "⭐" * meta["tier"]
        rows.append({
            "modello": name,
            "famiglia": meta["family"],
            "qualità": tier_stars,
            "€ con caching": round(est["total_eur"], 2),
            "€ caching + batch": round(est_batch["total_eur"], 2),
            "$/M input": meta["input"],
            "$/M output": meta["output"],
        })
    import pandas as _pd
    df = _pd.DataFrame(rows)
    st.markdown(f"**Proiezione costo su {n_rows:,} prodotti · tutti i modelli**")
    st.dataframe(
        df,
        use_container_width=True,
        height=min(70 + len(df) * 34, 560),
        column_config={
            "modello":            st.column_config.TextColumn("Modello", width="medium"),
            "famiglia":           st.column_config.TextColumn("Famiglia", width="small"),
            "qualità":            st.column_config.TextColumn("Qualità", width="small"),
            "€ con caching":      st.column_config.NumberColumn("€ con caching", format="€%.2f"),
            "€ caching + batch":  st.column_config.NumberColumn("€ caching+batch", format="€%.2f"),
            "$/M input":          st.column_config.NumberColumn("$/M in", format="$%.2f"),
            "$/M output":         st.column_config.NumberColumn("$/M out", format="$%.2f"),
        },
        hide_index=True,
    )
    st.caption(
        "**Caching** = prompt caching Anthropic/OpenAI (system prompt scritto 1 volta, letto a 10% del prezzo). "
        "**Batch API** = invio async, risultati entro 24h, sconto 50% su tutto. "
        "Ideale per re-enrichment notturno cron di cataloghi interi."
    )


# ============================================================
# DIFF PREVIEW — compare before/after enrichment
# ============================================================
def diff_view(label: str, before: str, after: str):
    """Render a side-by-side before/after diff card."""
    import html
    before_html = html.escape((before or "—").strip()) or "—"
    after_html = html.escape((after or "—").strip()) or "—"
    changed = before_html != after_html
    border = "#E5E7EB" if not changed else "#DCE7FE"
    st.markdown(
        f"""
        <div style='border:1px solid {border}; border-radius:12px; margin:8px 0; overflow:hidden;
                    background:#FFFFFF;'>
            <div style='background:#F4F5F7; padding:8px 14px; font-size:0.8rem; font-weight:600;
                        color:#4B5563; border-bottom:1px solid {border};'>{label}</div>
            <div style='display:grid; grid-template-columns:1fr 1fr; gap:0;'>
                <div style='padding:12px 14px; background:#FEF2F2; border-right:1px solid {border};
                            font-size:0.85rem; color:#7F1D1D; white-space:pre-wrap; word-break:break-word;'>
                    <div style='font-size:0.7rem; color:#EF4444; text-transform:uppercase;
                                font-weight:600; margin-bottom:6px; letter-spacing:0.05em;'>Prima</div>
                    {before_html}
                </div>
                <div style='padding:12px 14px; background:#ECFDF5;
                            font-size:0.85rem; color:#065F46; white-space:pre-wrap; word-break:break-word;'>
                    <div style='font-size:0.7rem; color:#10B981; text-transform:uppercase;
                                font-weight:600; margin-bottom:6px; letter-spacing:0.05em;'>Dopo</div>
                    {after_html}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# LOADING PROGRESS — richer than plain spinner
# ============================================================
class LoadingProgress:
    """Contextual progress tracker with ETA. Use as context manager.

        with LoadingProgress("Enrichment AI", total=len(df)) as p:
            for i, row in enumerate(df.itertuples()):
                ...
                p.update(i+1, subtitle=f"Prodotto: {row.title[:40]}")
    """
    def __init__(self, title: str, total: int):
        import time
        self.title = title
        self.total = max(total, 1)
        self._container = st.empty()
        self._bar = st.progress(0.0)
        self._start = time.time()
        self._t = time

    def __enter__(self):
        self._render(0, "")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._container.empty()
            self._bar.empty()
        return False

    def update(self, done: int, subtitle: str = ""):
        done = min(done, self.total)
        pct = done / self.total
        self._bar.progress(pct)
        elapsed = self._t.time() - self._start
        eta = (elapsed / max(done, 1)) * (self.total - done) if done else None
        self._render(done, subtitle, elapsed, eta)

    def _render(self, done: int, subtitle: str, elapsed: float = 0, eta: float | None = None):
        eta_str = ""
        if eta is not None and eta > 0:
            m, s = divmod(int(eta), 60)
            eta_str = f"· ~{m}:{s:02d} rimanenti"
        elapsed_str = ""
        if elapsed > 0:
            em, es = divmod(int(elapsed), 60)
            elapsed_str = f"{em}:{es:02d} trascorsi"
        subtitle_html = (
            f"<div style='font-size:0.78rem; color:#6B7280; margin-top:4px;'>{subtitle}</div>"
            if subtitle else ""
        )
        self._container.markdown(
            f"""
            <div style='background:#FFFFFF; border:1px solid #DCE7FE; border-radius:12px;
                        padding:12px 16px; margin:8px 0;'>
                <div style='display:flex; justify-content:space-between; align-items:center;'>
                    <div style='font-weight:600; color:#0A0A0F;'>{self.title}</div>
                    <div style='font-size:0.8rem; color:#4B5563; font-variant-numeric:tabular-nums;'>
                        {done:,} / {self.total:,} · {elapsed_str} {eta_str}
                    </div>
                </div>
                {subtitle_html}
            </div>
            """,
            unsafe_allow_html=True,
        )
