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
tab1, tab2, tab3, tab4 = st.tabs(["Anthropic Claude", "OpenAI", "Parametri & avanzate", "Prompt templates"])

with tab1:
    st.markdown("#### Anthropic Claude")
    st.caption("Ottieni la chiave da [console.anthropic.com](https://console.anthropic.com/settings/keys) — formato `sk-ant-...`")

    key_col, status_col = st.columns([3, 1])
    with key_col:
        _ant_key = st.text_input(
            "API Key Anthropic",
            value=cfg["anthropic_api_key"],
            type="password",
            placeholder="sk-ant-api03-...",
            key="ant_key",
            help=(
                "**Si salva automaticamente quando premi Invio o esci dal campo.**\n\n"
                f"Percorso: `{CONFIG_FILE}` (permessi 600, solo owner).\n\n"
                "La chiave persiste anche dopo chiusura browser / riavvio container "
                "perché il file è montato su volume Docker. "
                "Viene usata solo per chiamate ad api.anthropic.com."
            ),
        )
    _autosave("anthropic_api_key", _ant_key)
    with status_col:
        st.markdown("<div style='height:26px;'></div>", unsafe_allow_html=True)  # align
        if cfg.get("anthropic_api_key") and CONFIG_FILE.exists():
            preview = mask_key(cfg["anthropic_api_key"])
            st.markdown(
                f"<div style='background:#ECFDF5; border:1px solid #A7F3D0;"
                f"border-radius:8px; padding:6px 10px; font-size:0.78rem; color:#065F46;'>"
                f"<b>✓ Salvata su disco</b><br>"
                f"<span style='color:#047857; font-family:monospace; font-size:0.72rem;'>{preview}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='background:#FEF3C7; border:1px solid #F59E0B;"
                "border-radius:8px; padding:6px 10px; font-size:0.78rem; color:#92400E;'>"
                "○ Non salvata</div>",
                unsafe_allow_html=True,
            )

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

    key_col, status_col = st.columns([3, 1])
    with key_col:
        _oai_key = st.text_input(
            "API Key OpenAI",
            value=cfg["openai_api_key"],
            type="password",
            placeholder="sk-proj-...",
            key="oai_key",
            help=(
                "**Si salva automaticamente.**\n\n"
                f"Percorso: `{CONFIG_FILE}` (permessi 600).\n\n"
                "La chiave persiste fra sessioni e riavvii container."
            ),
        )
    _autosave("openai_api_key", _oai_key)
    with status_col:
        st.markdown("<div style='height:26px;'></div>", unsafe_allow_html=True)
        if cfg.get("openai_api_key") and CONFIG_FILE.exists():
            preview = mask_key(cfg["openai_api_key"])
            st.markdown(
                f"<div style='background:#ECFDF5; border:1px solid #A7F3D0;"
                f"border-radius:8px; padding:6px 10px; font-size:0.78rem; color:#065F46;'>"
                f"<b>✓ Salvata su disco</b><br>"
                f"<span style='color:#047857; font-family:monospace; font-size:0.72rem;'>{preview}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='background:#FEF3C7; border:1px solid #F59E0B;"
                "border-radius:8px; padding:6px 10px; font-size:0.78rem; color:#92400E;'>"
                "○ Non salvata</div>",
                unsafe_allow_html=True,
            )

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
    _autosave("max_tokens", c1.number_input(
        "Max tokens per prodotto", 512, 8192, int(cfg["max_tokens"]), 256,
        help=(
            "**Lunghezza massima della risposta AI per ogni prodotto.**\n\n"
            "1 token ≈ 0.75 parole italiane. 3500 token = ~2600 parole / 18000 caratteri.\n\n"
            "- 1024: titoli + descrizioni brevi — **troppo poco** con schema GMC completo\n"
            "- 2048: schema medio, rischio tronca su prodotti ricchi\n"
            "- 3500 (default): schema completo 40+ attributi + product_highlight + product_detail\n"
            "- 5000+: descrizioni molto lunghe o cataloghi complessi (elettronica spec-heavy)\n\n"
            "⚠️ Più alto = più costo output. Se vedi status 'empty:max_tokens' alza questo valore.\n"
            "⚠️ Valori >4096 richiedono modelli che supportano extended output (Sonnet 4.6/Opus)."
        ),
    ))
    _autosave("temperature", c2.slider(
        "Temperature", 0.0, 1.0, float(cfg["temperature"]), 0.05,
        help=(
            "**Creatività del modello AI (0.0 = deterministico, 1.0 = creativo).**\n\n"
            "Controlla la variabilità delle risposte per lo stesso input:\n"
            "- **0.0-0.2**: risposte quasi identiche ad ogni run. Massima consistenza. "
            "Usa per cataloghi dove titoli e descrizioni devono seguire formule rigide.\n"
            "- **0.3-0.5** (consigliato): buon bilanciamento fra consistenza e naturalezza. "
            "Default 0.4.\n"
            "- **0.6-0.8**: linguaggio più vario, utile per copywriting emozionale o cataloghi "
            "con prodotti molto simili che altrimenti suonerebbero ripetitivi.\n"
            "- **0.9-1.0**: massima creatività, rischio di hallucinations o testi fuori-tono. "
            "Sconsigliato per feed Google Merchant.\n\n"
            "⚠️ Se noti titoli troppo simili fra loro, alza a 0.5-0.6. "
            "Se Claude inventa dettagli, abbassa a 0.2-0.3."
        ),
    ))
    _autosave("max_workers", c3.slider(
        "Parallelismo (worker)", 1, 20, int(cfg["max_workers"]),
        help=(
            "**Numero di richieste AI lanciate in parallelo.**\n\n"
            "Ogni 'worker' chiama Claude per un prodotto diverso contemporaneamente. "
            "Moltiplica la velocità di enrichment MA aumenta il rischio di rate-limit sull'API.\n\n"
            "- **1**: sequenziale, massima sicurezza, lento (1 prodotto per volta)\n"
            "- **3-5** (consigliato): bilanciato per tier API standard Anthropic\n"
            "- **10-15**: veloce, richiede tier API alto (Build/Scale)\n"
            "- **20**: massimo, solo per account Enterprise senza rate limit\n\n"
            "Esempio: 100 prodotti con parallelismo 5 = ~20 chiamate sequenziali "
            "(100 ÷ 5), non 100. Se Claude genera in ~4s, totale ~80s invece di 400s.\n\n"
            "⚠️ Se vedi errori '429 rate_limit_exceeded', abbassa a 3-5."
        ),
    ))
    _autosave("default_limit", st.number_input(
        "Limite default prodotti per enrichment",
        10, 10000, int(cfg["default_limit"]), 10,
        help="Valore preselezionato nel campo 'Limite prodotti' in Enrichment AI. Puoi sempre sovrascriverlo.",
    ))

    st.markdown("#### Variabili d'ambiente (opzionali)")
    st.caption("Se imposti queste env vars all'avvio dell'app, sovrascrivono le chiavi salvate:")
    st.code("export ANTHROPIC_API_KEY='sk-ant-...'\nexport OPENAI_API_KEY='sk-proj-...'", language="bash")

with tab4:
    from utils import prompts as _prompts
    from utils.enrichment import list_sectors as _list_sectors, get_default_base_prompt

    st.markdown("#### Prompt templates")
    st.caption(
        "Override del system prompt per settore. Se non esiste un template per il settore "
        "scelto in Enrichment, viene usato il prompt base di default."
    )

    existing_sectors = list(_prompts.list_sectors())
    yaml_sectors = list(_list_sectors())
    all_choices = sorted(set(existing_sectors + yaml_sectors + ["_default"]))

    sector_choice = st.selectbox(
        "Settore",
        options=all_choices,
        index=all_choices.index("_default") if "_default" in all_choices else 0,
        help="Usa `_default` per override globale, oppure un nome settore (es. `abbigliamento`).",
        key="_prompt_sector",
    )

    versions = _prompts.list_versions(sector_choice)
    active = _prompts.get_active(sector_choice)

    if versions:
        st.markdown(f"**Versioni salvate** ({len(versions)})")
        for v in reversed(versions[-10:]):  # show last 10
            is_active = active and v["version"] == active["version"]
            badge = "✅ attiva" if is_active else ""
            with st.expander(
                f"v{v['version']} · {v.get('created_at','?')} · {v.get('note','')} {badge}",
                expanded=False,
            ):
                st.code(v["body"][:2000] + ("... [tronc.]" if len(v["body"]) > 2000 else ""),
                        language="markdown")
                vc1, vc2, vc3 = st.columns(3)
                if vc1.button("Attiva", key=f"activate_{sector_choice}_{v['version']}",
                              disabled=is_active, use_container_width=True):
                    _prompts.set_active(sector_choice, v["version"])
                    st.toast(f"Versione {v['version']} attivata", icon="✅")
                    st.rerun()
                if vc2.button("Carica in editor", key=f"load_{sector_choice}_{v['version']}",
                              use_container_width=True):
                    st.session_state["_prompt_editor_body"] = v["body"]
                    st.session_state["_prompt_editor_note"] = v.get("note", "")
                    st.rerun()
                if vc3.button("Elimina", key=f"delete_{sector_choice}_{v['version']}",
                              disabled=is_active, use_container_width=True,
                              help="Non puoi eliminare la versione attiva"):
                    _prompts.delete_version(sector_choice, v["version"])
                    st.rerun()

    st.divider()
    st.markdown("**Nuova versione**")

    # If no editor body set yet, pre-fill with default base or last active
    if "_prompt_editor_body" not in st.session_state:
        if active:
            st.session_state["_prompt_editor_body"] = active["body"]
        else:
            st.session_state["_prompt_editor_body"] = get_default_base_prompt()

    note = st.text_input("Nota (cosa cambia in questa versione)",
                         value=st.session_state.get("_prompt_editor_note", ""),
                         placeholder="es. titoli più aggressivi, enfasi su taglie")
    body = st.text_area(
        "System prompt",
        value=st.session_state.get("_prompt_editor_body", ""),
        height=360,
        help="Markdown supportato. Mantieni la struttura JSON finale coi nomi UFFICIALI Google/Meta.",
    )

    pc1, pc2, pc3 = st.columns([1, 1, 3])
    if pc1.button("Salva nuova versione", type="primary", use_container_width=True,
                  disabled=not body.strip()):
        ver = _prompts.save_version(sector_choice, body, note=note.strip())
        st.toast(f"Salvata v{ver} · attivata", icon="✨")
        st.session_state["_prompt_editor_note"] = ""
        st.rerun()
    if pc2.button("Reset a default", use_container_width=True):
        st.session_state["_prompt_editor_body"] = get_default_base_prompt()
        st.session_state["_prompt_editor_note"] = ""
        st.rerun()

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

