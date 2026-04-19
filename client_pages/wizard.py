"""Wizard Cliente: 4 step lineari per il data enrichment."""
import streamlit as st
import pandas as pd
import io, zipfile

from utils.state import init_state, current_df
from utils.ui import apply_theme
from utils.history import (
    init_session, save_snapshot, log_event, set_project_name, get_project_name,
    get_project_info, list_projects, restore_snapshot, touch_project, save_output,
)
from utils.config import load_config
from utils.feed_parser import load_feed, normalize_columns, list_excel_sheets, parse_excel_feed, get_alias_report
from utils.enrichment import enrich_dataframe, list_sectors, load_sector
from utils.catalog_optimizer import build_google_feed, build_meta_feed, validate_feed
from utils.exporter import to_excel_bytes, to_gmc_xml

init_state()
apply_theme()
init_session(st.session_state)

if "config" not in st.session_state:
    st.session_state["config"] = load_config()
    if st.session_state["config"].get("anthropic_api_key"):
        st.session_state["api_key"] = st.session_state["config"]["anthropic_api_key"]

if "wizard_step" not in st.session_state:
    st.session_state["wizard_step"] = 1

step = st.session_state["wizard_step"]

def go(n):
    st.session_state["wizard_step"] = n
    st.rerun()


# ============================================================
# STEPPER VISUALE — CLICCABILE
# ============================================================
def render_stepper(current: int):
    steps_def = [
        (1, "Progetto"),
        (2, "Upload Feed"),
        (3, "Enrichment AI"),
        (4, "Scarica Catalogo"),
    ]
    # CSS specifico per i bottoni-step
    st.markdown("""
    <style>
    div[data-testid="column"] .step-btn-active button {
        background: #2F6FED !important;
        color: white !important; border: 1px solid #2F6FED !important;
        min-height: 70px !important; padding: 14px 12px !important;
        font-weight: 600 !important; font-size: 0.85rem !important;
        box-shadow: 0 4px 14px rgba(47, 111, 237, 0.25) !important;
        border-radius: 12px !important;
        white-space: normal !important; line-height: 1.3 !important;
    }
    div[data-testid="column"] .step-btn-done button {
        background: #ECFDF5 !important;
        color: #047857 !important; border: 1px solid #A7F3D0 !important;
        min-height: 70px !important; padding: 14px 12px !important;
        font-weight: 600 !important; font-size: 0.85rem !important;
        border-radius: 12px !important;
        white-space: normal !important; line-height: 1.3 !important;
    }
    div[data-testid="column"] .step-btn-todo button {
        background: #FFFFFF !important;
        color: #6B7280 !important;
        border: 1px dashed #D1D5DB !important;
        min-height: 70px !important; padding: 14px 12px !important;
        font-weight: 500 !important; font-size: 0.85rem !important;
        border-radius: 12px !important;
        white-space: normal !important; line-height: 1.3 !important;
    }
    div[data-testid="column"] .step-btn-todo button:hover {
        background: #EEF4FF !important;
        color: #2F6FED !important;
        border-color: #2F6FED !important; border-style: solid !important;
    }
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(len(steps_def))
    for i, (num, label) in enumerate(steps_def):
        with cols[i]:
            if num < current:
                cls = "step-btn-done"; status = "✓"
            elif num == current:
                cls = "step-btn-active"; status = str(num)
            else:
                cls = "step-btn-todo"; status = str(num)
            st.markdown(f"<div class='{cls}'>", unsafe_allow_html=True)
            label_btn = f"{status}  ·  {label}"
            if st.button(label_btn, key=f"step_btn_{num}",
                          use_container_width=True,
                          help=f"Vai allo step {num}: {label}"):
                go(num)
            st.markdown("</div>", unsafe_allow_html=True)


# ============================================================
# HEADER + PROJECT SWITCHER
# ============================================================
hc1, hc2 = st.columns([3, 2])
with hc1:
    st.markdown("# Wizard Data Enrichment")
    current_pname = get_project_name(st.session_state["session_id"])
    is_named_proj = bool(get_project_info(st.session_state["session_id"]))
    badge = current_pname if is_named_proj else "(progetto senza nome)"
    st.caption(f"Progetto attivo · **{badge}** · Salvataggio automatico")

with hc2:
    # Project switcher inline — selectbox + 'cambia/nuovo'
    all_projects = [p for p in list_projects() if p.get("is_named")]
    options = ["— Cambia progetto —"] + [p["name"] for p in all_projects] + ["✨ Nuovo progetto..."]
    chosen = st.selectbox(
        "Cambia progetto",
        options,
        index=0,
        key="wiz_proj_switch",
        label_visibility="collapsed",
    )
    if chosen == "✨ Nuovo progetto...":
        # crea sessione vuota e torna allo step 1
        st.session_state["session_id"] = None
        for k in ("feed_df", "merged_df", "enriched_df", "gads_df", "raw_df", "labels", "_alias_report"):
            st.session_state.pop(k, None)
        init_session(st.session_state)
        st.session_state["wizard_step"] = 1
        st.rerun()
    elif chosen != "— Cambia progetto —":
        target = next((p for p in all_projects if p["name"] == chosen), None)
        if target and target["id"] != st.session_state["session_id"]:
            for k in ("feed_df", "merged_df", "enriched_df", "gads_df", "raw_df", "labels", "_alias_report"):
                st.session_state.pop(k, None)
            restore_snapshot(target["id"], st.session_state)
            touch_project(target["id"])
            # decidi auto a quale step andare
            if st.session_state.get("enriched_df") is not None:
                st.session_state["wizard_step"] = 4
            elif st.session_state.get("feed_df") is not None:
                st.session_state["wizard_step"] = 3
            else:
                st.session_state["wizard_step"] = 2
            st.rerun()

render_stepper(step)
st.divider()


# ============================================================
# STEP 1 — PROGETTO
# ============================================================
if step == 1:
    st.markdown("## Step 1 · Crea o apri un progetto")
    st.caption("I progetti salvano tutto il lavoro (feed, enrichment, label) e puoi riaprirli quando vuoi.")

    sid = st.session_state["session_id"]
    info = get_project_info(sid)
    is_named = bool(info)

    if is_named:
        st.success(f"✅ Stai lavorando sul progetto: **{get_project_name(sid)}**")
        c1, c2 = st.columns(2)
        if c1.button("Continua su questo progetto →", type="primary", use_container_width=True):
            go(2)
        if c2.button("Cambia o crea nuovo", use_container_width=True):
            del st.session_state["session_id"]
            for k in ("feed_df", "merged_df", "enriched_df", "gads_df", "raw_df", "labels"):
                st.session_state.pop(k, None)
            init_session(st.session_state)
            st.rerun()
    else:
        tabs = st.tabs(["✨ Nuovo progetto", "📂 Apri esistente"])
        with tabs[0]:
            pname = st.text_input("Nome progetto",
                                   placeholder="Es: Catalogo Nike SS26",
                                   key="wiz_pname")
            pdesc = st.text_area("Descrizione (opzionale)", height=60, key="wiz_pdesc",
                                  placeholder="Obiettivi, contesto...")
            if st.button("Crea e continua", type="primary", disabled=not pname.strip(),
                          use_container_width=True):
                set_project_name(sid, pname, pdesc)
                save_snapshot(sid, st.session_state)
                go(2)

        with tabs[1]:
            projects = [p for p in list_projects() if p.get("is_named")]
            if not projects:
                st.info("Nessun progetto salvato.")
            else:
                for p in projects[:15]:
                    c = st.columns([4, 1])
                    c[0].markdown(f"**{p['name']}**")
                    if p.get("description"): c[0].caption(p["description"])
                    c[0].caption(f"{p['events']} eventi · ultimo accesso: {p.get('last_opened', '—')}")
                    if c[1].button("▶ Apri", key=f"wo_{p['id']}", type="primary",
                                    use_container_width=True):
                        for k in ("feed_df", "merged_df", "enriched_df", "gads_df", "raw_df", "labels"):
                            st.session_state.pop(k, None)
                        restore_snapshot(p["id"], st.session_state)
                        touch_project(p["id"])
                        go(2)


# ============================================================
# STEP 2 — UPLOAD FEED
# ============================================================
elif step == 2:
    st.markdown("## Step 2 · Carica il feed prodotto")
    st.caption(f"Progetto: **{get_project_name(st.session_state['session_id'])}**")

    df_existing = st.session_state.get("feed_df")
    if df_existing is not None:
        st.success(f"✅ Feed già caricato: {len(df_existing):,} prodotti da `{st.session_state.get('feed_source', '—')}`")
        st.dataframe(df_existing.head(20), use_container_width=True, height=300)
        c1, c2, c3 = st.columns(3)
        if c1.button("← Indietro", use_container_width=True):
            go(1)
        if c2.button("🔄 Sostituisci feed", use_container_width=True):
            st.session_state.pop("feed_df", None)
            st.session_state.pop("merged_df", None)
            st.session_state.pop("enriched_df", None)
            st.rerun()
        if c3.button("Avanti → Enrichment", type="primary", use_container_width=True):
            go(3)
    else:
        tabs = st.tabs(["📁 Da File", "🌐 Da URL"])
        df = None; source = ""
        with tabs[0]:
            up = st.file_uploader(
                "Carica catalogo · XML, CSV, TSV, **Excel** (.xlsx/.xls), JSON",
                type=["xml", "csv", "tsv", "json", "txt", "xlsx", "xls", "xlsm"],
                help="Excel multi-foglio supportato: scegli quale foglio importare",
            )
            if up is not None:
                content = up.read()
                # se è Excel con più fogli, fai scegliere
                if up.name.lower().endswith((".xlsx", ".xls", ".xlsm")):
                    try:
                        sheets = list_excel_sheets(content)
                    except Exception as e:
                        st.error(f"Errore lettura Excel: {e}")
                        sheets = []
                    if len(sheets) > 1:
                        chosen = st.selectbox(f"Excel multi-foglio ({len(sheets)}). Quale?", sheets)
                    else:
                        chosen = sheets[0] if sheets else 0
                    if st.button("Importa foglio", type="primary"):
                        with st.spinner(f"Importo '{chosen}'..."):
                            try:
                                df = parse_excel_feed(content, sheet_name=chosen)
                                source = f"{up.name} · foglio: {chosen}"
                            except Exception as e:
                                st.error(f"Errore: {e}")
                else:
                    with st.spinner("Parso il file..."):
                        try:
                            df = load_feed(content, filename=up.name)
                            source = up.name
                        except Exception as e:
                            st.error(f"Errore: {e}")
        with tabs[1]:
            url = st.text_input("URL feed", placeholder="https://example.com/feed.xml")
            if st.button("Scarica", disabled=not url):
                with st.spinner("Scarico..."):
                    try:
                        df = load_feed(url); source = url
                    except Exception as e:
                        st.error(f"Errore: {e}")

        if df is not None and len(df):
            df = normalize_columns(df)
            aliases = get_alias_report(df)
            st.session_state["raw_df"] = df.copy()
            st.session_state["feed_df"] = df.copy()
            st.session_state["feed_source"] = source
            st.session_state["_alias_report"] = aliases
            st.session_state["enriched_df"] = None
            st.session_state["merged_df"] = None
            save_snapshot(st.session_state["session_id"], st.session_state)
            st.success(f"✅ {len(df):,} prodotti caricati")
            if aliases:
                st.info(f"🔄 Riconosciuti **{len(aliases)} alias** di colonna (Shopify/WooCommerce/altro):  \n"
                        + " · ".join(f"`{a['originale']}` → `{a['mappato_a']}`" for a in aliases))
            st.rerun()

        if st.button("← Indietro", use_container_width=False):
            go(1)


# ============================================================
# STEP 3 — ENRICHMENT AI
# ============================================================
elif step == 3:
    st.markdown("## Step 3 · Enrichment AI")
    df = current_df()
    if df is None:
        st.error("Manca il feed.")
        if st.button("← Indietro"): go(2)
        st.stop()

    if not st.session_state.get("api_key"):
        st.warning("⚠️ Inserisci la Claude API Key in **Settings**.")
        if st.button("Apri Settings"):
            st.switch_page("client_pages/settings.py")
        st.stop()

    enriched = st.session_state.get("enriched_df")

    if enriched is None:
        st.info(f"Pronto a processare **{len(df):,} prodotti**. L'AI applicherà best practice settoriali.")

        c1, c2, c3 = st.columns(3)
        sectors = ["(generico)"] + list_sectors()
        sector_choice = c1.selectbox("Settore (best practice)", sectors,
                                      index=1 if "abbigliamento" in sectors else 0,
                                      help="Carica regole settoriali")
        sector = "" if sector_choice == "(generico)" else sector_choice
        model = c2.selectbox("Modello", ["claude-sonnet-4-6", "claude-haiku-4-5-20251001",
                                          "claude-opus-4-6"], index=0)
        limit = c3.number_input("Quanti prodotti", 1, len(df), min(50, len(df)), 10)

        cost = limit * 0.004
        st.info(f"💰 Costo stimato Sonnet: **~${cost:.2f}** per {limit} prodotti · ⏱ ~{limit*1.5/60:.1f} min")

        if sector:
            with st.expander(f"📚 Best practice: {sector}"):
                s = load_sector(sector)
                if f := s.get("title", {}).get("formula"): st.markdown(f"**Formula titolo**: `{f}`")
                if ex := s.get("title", {}).get("formula_examples"):
                    st.markdown("**Esempi**:\n- " + "\n- ".join(ex[:3]))

        c1, c2 = st.columns([1, 2])
        if c1.button("← Indietro", use_container_width=True): go(2)
        if c2.button("🚀 Avvia Enrichment", type="primary", use_container_width=True):
            progress = st.progress(0, text="Avvio...")
            def cb(d, t): progress.progress(d/t, text=f"{d}/{t} prodotti")
            try:
                enr = enrich_dataframe(df, api_key=st.session_state["api_key"], model=model,
                                        max_workers=5, limit=limit, progress_callback=cb,
                                        sector=sector, overwrite_title_description=True)
                st.session_state["enriched_df"] = enr
                save_snapshot(st.session_state["session_id"], st.session_state)
                log_event(st.session_state["session_id"], "enrichment_done",
                          {"n": limit, "sector": sector, "model": model})
                st.rerun()
            except Exception as e:
                st.error(f"Errore: {e}")
    else:
        ok = (enriched["_enrichment_status"] == "ok").sum() if "_enrichment_status" in enriched.columns else len(enriched)
        st.success(f"✅ Enrichment completato · {ok}/{len(enriched)} OK")

        # preview before/after
        st.markdown("### 👁 Anteprima before/after (5 prodotti)")
        sample = enriched.head(5)
        for _, row in sample.iterrows():
            with st.container():
                c1, c2 = st.columns(2)
                c1.markdown("**Originale**")
                c1.markdown(f"📝 *{row.get('title_original', row.get('title', ''))[:120]}*")
                c1.caption(row.get('description_original', row.get('description', ''))[:200])
                c2.markdown("**AI Ottimizzato**")
                c2.markdown(f"✨ **{row.get('title', '')[:120]}**")
                c2.caption(row.get('description', '')[:200])
                st.markdown("---")

        c1, c2, c3 = st.columns(3)
        if c1.button("← Indietro", use_container_width=True): go(2)
        if c2.button("🔄 Rigenera", use_container_width=True):
            st.session_state["enriched_df"] = None
            st.rerun()
        if c3.button("Avanti → Scarica", type="primary", use_container_width=True): go(4)


# ============================================================
# STEP 4 — DOWNLOAD CATALOGO
# ============================================================
elif step == 4:
    st.markdown("## Step 4 · Scarica il catalogo ottimizzato")
    df = current_df()
    if df is None:
        st.error("Manca il feed.")
        if st.button("← Indietro"): go(3)
        st.stop()

    currency = st.selectbox("Valuta", ["EUR", "USD", "GBP", "CHF"], index=0)

    with st.spinner("Genero feed Google e Meta..."):
        google_df = build_google_feed(df, currency=currency)
        meta_df = build_meta_feed(df, currency=currency)

    # validation summary
    g_val = validate_feed(google_df, "google")
    m_val = validate_feed(meta_df, "meta")
    g_err = (g_val["stato"].isin(["ERROR", "MISSING_COLUMN"])).sum()
    m_err = (m_val["stato"].isin(["ERROR", "MISSING_COLUMN"])).sum()

    c1, c2 = st.columns(2)
    c1.metric("Google MC · prodotti", len(google_df), f"{g_err} errori" if g_err else "OK")
    c2.metric("Meta Catalog · prodotti", len(meta_df), f"{m_err} errori" if m_err else "OK")

    tabs = st.tabs(["🛒 Google", "📘 Meta", "📦 Bundle ZIP"])
    with tabs[0]:
        st.dataframe(google_df.head(30), use_container_width=True, height=300)
        d1, d2, d3 = st.columns(3)
        d1.download_button("TSV (preferito GMC)",
                            google_df.to_csv(index=False, sep="\t").encode("utf-8"),
                            "google_feed.tsv", "text/tab-separated-values", use_container_width=True)
        d2.download_button("Excel", to_excel_bytes({"google_feed": google_df}),
                            "google_feed.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
        d3.download_button("XML", to_gmc_xml(google_df, "Google Feed").encode("utf-8"),
                            "google_feed.xml", "application/xml", use_container_width=True)

    with tabs[1]:
        st.dataframe(meta_df.head(30), use_container_width=True, height=300)
        d1, d2, d3 = st.columns(3)
        d1.download_button("CSV (preferito Meta)",
                            meta_df.to_csv(index=False).encode("utf-8"),
                            "meta_feed.csv", "text/csv", use_container_width=True)
        d2.download_button("Excel", to_excel_bytes({"meta_feed": meta_df}),
                            "meta_feed.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
        d3.download_button("XML", to_gmc_xml(meta_df, "Meta Feed").encode("utf-8"),
                            "meta_feed.xml", "application/xml", use_container_width=True)

    with tabs[2]:
        st.markdown("**Bundle completo** con tutti i formati + report di validazione + README di upload.")
        if st.button("📦 Genera ZIP", type="primary", use_container_width=True):
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("google/google_feed.tsv", google_df.to_csv(index=False, sep="\t"))
                zf.writestr("google/google_feed.csv", google_df.to_csv(index=False))
                zf.writestr("google/google_feed.xml", to_gmc_xml(google_df, "Google Feed"))
                zf.writestr("google/google_feed.xlsx", to_excel_bytes({"google_feed": google_df}))
                zf.writestr("google/validation_report.csv", g_val.to_csv(index=False))
                zf.writestr("meta/meta_feed.csv", meta_df.to_csv(index=False))
                zf.writestr("meta/meta_feed.xml", to_gmc_xml(meta_df, "Meta Feed"))
                zf.writestr("meta/meta_feed.xlsx", to_excel_bytes({"meta_feed": meta_df}))
                zf.writestr("meta/validation_report.csv", m_val.to_csv(index=False))
                zf.writestr("README.md", """# Feed ottimizzati

## google/
- google_feed.tsv ← preferito da GMC
- google_feed.xml, .csv, .xlsx ← formati alternativi

## meta/
- meta_feed.csv ← preferito da Meta Commerce Manager

## Upload
**GMC**: GMC → Feed → Aggiungi nuovo → Carica TSV/XML
**Meta**: Catalogo → Aggiungi prodotti → Da file di dati
""")
            bundle = buf.getvalue()
            st.download_button("⬇️ Scarica bundle.zip", bundle,
                                file_name=f"feed_bundle_{currency}.zip",
                                mime="application/zip",
                                use_container_width=True, type="primary")
            save_output(st.session_state["session_id"], "feed_bundle.zip", bundle)
            st.success("Salvato anche nella cartella sessione (vedi pagina **Progetti**)")

    st.divider()
    c1, c2, c3 = st.columns(3)
    if c1.button("← Indietro", use_container_width=True): go(3)
    if c2.button("🏠 Home", use_container_width=True):
        st.switch_page("client_pages/home.py")
    if c3.button("🏷️ Vai al Labelizer", use_container_width=True):
        st.switch_page("labelizer_pages/hub.py")
