"""Pagina 0: Settings — gestione API keys e configurazione AI."""
import streamlit as st

from utils.state import init_state
from utils.ui import apply_theme
from utils.config import (
    load_config, save_config, clear_config, mask_key,
    test_anthropic, test_openai, CONFIG_FILE,
)

init_state()
apply_theme()

st.title("Settings")
st.caption("Configura le API keys e i modelli AI usati per l'enrichment")

# carica config attuale (file → session)
if "config_loaded" not in st.session_state:
    cfg = load_config()
    st.session_state["config"] = cfg
    st.session_state["config_loaded"] = True
    # propaga la chiave Claude alla session_state usata dall'enrichment
    if cfg.get("anthropic_api_key"):
        st.session_state["api_key"] = cfg["anthropic_api_key"]

cfg = st.session_state["config"]


def _autosave(key: str, value):
    """Salva su disco appena cambia un valore. Trasparente per l'utente."""
    if cfg.get(key) != value:
        cfg[key] = value
        save_config(cfg)
        if key == "anthropic_api_key" and value:
            st.session_state["api_key"] = value
        # toast in alto a destra
        try:
            st.toast(f"💾 Salvato: {key.replace('_', ' ')}", icon="✅")
        except Exception:
            pass

# ============================================================
# STATUS PANEL
# ============================================================
st.markdown("### Stato configurazione")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Provider attivo", cfg["provider"].title())
c2.metric("Anthropic", "Configurato" if cfg["anthropic_api_key"] else "Non impostato",
          delta=mask_key(cfg["anthropic_api_key"]) if cfg["anthropic_api_key"] else None)
c3.metric("OpenAI", "Configurato" if cfg["openai_api_key"] else "Non impostato",
          delta=mask_key(cfg["openai_api_key"]) if cfg["openai_api_key"] else None)
c4.metric("Persistenza", "Su disco" if CONFIG_FILE.exists() else "Solo sessione")

st.divider()

# ============================================================
# PROVIDER SELECTION
# ============================================================
st.markdown("### Provider AI predefinito")
st.caption("Quale provider usare per l'enrichment quando entrambi sono configurati")

_provider = st.radio(
    "Provider",
    options=["anthropic", "openai"],
    index=0 if cfg["provider"] == "anthropic" else 1,
    format_func=lambda x: {"anthropic": "Anthropic Claude (consigliato)", "openai": "OpenAI"}[x],
    horizontal=True,
    label_visibility="collapsed",
)
_autosave("provider", _provider)

st.divider()

# ============================================================
# TABS PER PROVIDER
# ============================================================
tab1, tab2, tab3 = st.tabs(["Anthropic Claude", "OpenAI", "Parametri & avanzate"])

with tab1:
    st.markdown("#### Anthropic Claude")
    st.caption("Ottieni la chiave da [console.anthropic.com](https://console.anthropic.com/settings/keys) — formato `sk-ant-...`")

    _ant_key = st.text_input(
        "API Key Anthropic",
        value=cfg["anthropic_api_key"],
        type="password",
        placeholder="sk-ant-api03-...",
        key="ant_key",
        help="Si salva automaticamente quando premi Invio o esci dal campo.",
    )
    _autosave("anthropic_api_key", _ant_key)

    _ant_model = st.selectbox(
        "Modello",
        options=[
            "claude-sonnet-4-6",
            "claude-haiku-4-5-20251001",
            "claude-opus-4-6",
        ],
        index=["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"]
              .index(cfg["anthropic_model"]) if cfg["anthropic_model"] in
              ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"] else 0,
        help="Sonnet = migliore qualità/prezzo. Haiku = veloce ed economico. Opus = massima qualità.",
    )
    _autosave("anthropic_model", _ant_model)

    cc1, cc2 = st.columns([1, 3])
    if cc1.button("Test connessione", key="test_ant", use_container_width=True):
        if not cfg["anthropic_api_key"]:
            cc2.warning("Inserisci prima la API key")
        else:
            with cc2:
                with st.spinner("Test in corso..."):
                    ok, msg = test_anthropic(cfg["anthropic_api_key"], cfg["anthropic_model"])
                if ok:
                    st.success(f"Connessione OK · {msg}")
                else:
                    st.error(f"Errore: {msg}")

with tab2:
    st.markdown("#### OpenAI")
    st.caption("Ottieni la chiave da [platform.openai.com/api-keys](https://platform.openai.com/api-keys) — formato `sk-...` o `sk-proj-...`")

    _oai_key = st.text_input(
        "API Key OpenAI",
        value=cfg["openai_api_key"],
        type="password",
        placeholder="sk-proj-...",
        key="oai_key",
        help="Si salva automaticamente.",
    )
    _autosave("openai_api_key", _oai_key)

    _oai_model = st.selectbox(
        "Modello",
        options=["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"],
        index=["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"]
              .index(cfg["openai_model"]) if cfg["openai_model"] in
              ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"] else 0,
        help="gpt-4o-mini = ottimo rapporto qualità/prezzo per enrichment massivo.",
    )
    _autosave("openai_model", _oai_model)

    cc1, cc2 = st.columns([1, 3])
    if cc1.button("Test connessione", key="test_oai", use_container_width=True):
        if not cfg["openai_api_key"]:
            cc2.warning("Inserisci prima la API key")
        else:
            with cc2:
                with st.spinner("Test in corso..."):
                    ok, msg = test_openai(cfg["openai_api_key"], cfg["openai_model"])
                if ok:
                    st.success(f"Connessione OK · {msg}")
                else:
                    st.error(f"Errore: {msg}")

with tab3:
    st.markdown("#### Parametri di generazione")
    c1, c2, c3 = st.columns(3)
    _autosave("max_tokens", c1.number_input("Max tokens per prodotto", 256, 4096,
                                              int(cfg["max_tokens"]), 128))
    _autosave("temperature", c2.slider("Temperature", 0.0, 1.0,
                                        float(cfg["temperature"]), 0.05))
    _autosave("max_workers", c3.slider("Parallelismo (worker)", 1, 20,
                                        int(cfg["max_workers"])))
    _autosave("default_limit", st.number_input("Limite default prodotti per enrichment",
                                                 10, 10000, int(cfg["default_limit"]), 10))

    st.markdown("#### Variabili d'ambiente (opzionali)")
    st.caption("Se imposti queste env vars all'avvio dell'app, sovrascrivono le chiavi salvate:")
    st.code("export ANTHROPIC_API_KEY='sk-ant-...'\nexport OPENAI_API_KEY='sk-proj-...'", language="bash")

st.divider()

# ============================================================
# AZIONI
# ============================================================
st.markdown("### Salvataggio")

a1, a2, a3, a4 = st.columns([1, 1, 1, 2])

if a1.button("Salva su disco", type="primary", use_container_width=True,
             help=f"Salva in {CONFIG_FILE} (permessi 600, solo owner)"):
    path = save_config(cfg)
    # propaga subito alla sessione attiva
    if cfg["anthropic_api_key"]:
        st.session_state["api_key"] = cfg["anthropic_api_key"]
    st.success(f"Salvato in `{path}`")

if a2.button("Applica solo a sessione", use_container_width=True,
             help="Non scrive su disco, vale solo per questa sessione"):
    st.session_state["config"] = cfg
    if cfg["anthropic_api_key"]:
        st.session_state["api_key"] = cfg["anthropic_api_key"]
    st.success("Configurazione applicata alla sessione")

if a3.button("Cancella file", use_container_width=True,
             help="Rimuove il file di configurazione dal disco"):
    if clear_config():
        st.success("File cancellato")
    else:
        st.info("Nessun file da cancellare")

a4.caption(f"Path: `{CONFIG_FILE}`")

st.divider()

# ============================================================
# INFO
# ============================================================
with st.expander("Sicurezza & privacy"):
    st.markdown("""
    - Le chiavi vengono salvate **solo in locale** in `~/.feed_enricher/config.json` con permessi `600` (solo il tuo utente può leggere)
    - Nessuna chiave viene mai inviata a server esterni se non al provider AI corrispondente
    - Per non salvare nulla su disco, usa **"Applica solo a sessione"** o le **variabili d'ambiente**
    - Per ambienti condivisi (cloud, docker), usa sempre le env vars
    """)

with st.expander("Come funziona il fallback tra provider"):
    st.markdown("""
    L'enrichment usa il provider impostato come **predefinito** (sopra). Se la chiave manca, prova l'altro provider configurato.
    Puoi cambiare provider al volo nella pagina Enrichment AI senza ripassare da Settings.
    """)
