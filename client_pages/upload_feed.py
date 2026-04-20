"""Pagina 1: Upload del feed prodotto + scelta/creazione progetto."""
import streamlit as st
import pandas as pd

from utils.state import init_state
from utils.ui import apply_theme
from utils.feed_parser import load_feed, normalize_columns
from utils.history import (
    init_session, save_snapshot, restore_snapshot, set_project_name,
    get_project_name, get_project_info, list_projects, touch_project,
)

init_state()
apply_theme()
init_session(st.session_state)

st.title("1. Upload Feed")
st.caption("Prima scegli o crea un progetto, poi carica il catalogo. Tutto il lavoro viene salvato e potrai riprenderlo.")

# ============================================================
# STEP 1 — SCELTA / CREAZIONE PROGETTO
# ============================================================
current_sid = st.session_state["session_id"]
current_info = get_project_info(current_sid)
current_name = get_project_name(current_sid)
is_named = bool(current_info)
has_feed = st.session_state.get("feed_df") is not None

st.markdown("### Step 1 · Progetto")

if is_named and has_feed:
    # Siamo dentro un progetto con dati → mostra info + opzione continua
    st.success(f"✅ Stai lavorando sul progetto: **{current_name}**  \n"
                f"Feed già caricato: **{len(st.session_state['feed_df']):,} prodotti** "
                f"(`{st.session_state.get('feed_source', '—')}`)")
    sc1, sc2, sc3 = st.columns(3)
    if sc1.button("🔄 Sostituisci feed di questo progetto", use_container_width=True,
                  help="Mantiene il progetto ma carica un nuovo feed (perdi enrichment/label correnti)"):
        st.session_state["_replace_mode"] = True
        st.rerun()
    if sc2.button("✨ Crea nuovo progetto", use_container_width=True, type="primary"):
        st.session_state["session_id"] = None
        for k in ("feed_df", "merged_df", "enriched_df", "gads_df", "raw_df", "labels"):
            if k in st.session_state: del st.session_state[k]
        st.session_state.pop("_replace_mode", None)
        init_session(st.session_state)
        st.rerun()
    if sc3.button("📂 Apri progetto esistente", use_container_width=True):
        st.session_state["_open_existing"] = True
        st.rerun()

    if not st.session_state.get("_replace_mode") and not st.session_state.get("_open_existing"):
        st.divider()
        st.info("Vai alle pagine successive (2 Google Ads, 3 Shopify, 4 Enrichment AI, Labels...) per continuare a lavorare.")
        st.stop()

# --- Se sei qui, devi scegliere: nuovo OR esistente ---
if st.session_state.get("_open_existing"):
    tabs = st.tabs(["📂 Continua progetto esistente", "✨ Crea nuovo progetto"])
    tab_new_idx, tab_ex_idx = 1, 0
else:
    tabs = st.tabs(["✨ Crea nuovo progetto", "📂 Continua progetto esistente"])
    tab_new_idx, tab_ex_idx = 0, 1

# --- TAB NUOVO PROGETTO ---
with tabs[tab_new_idx]:
    st.markdown("**Dai un nome al progetto** (obbligatorio per poterlo ritrovare dopo)")
    pname = st.text_input("Nome progetto",
                           placeholder="Es: Catalogo Nike SS26 · Test premium refinement · Feed Q2 2026",
                           key="new_project_name")
    pdesc = st.text_area("Descrizione (opzionale)",
                          placeholder="Obiettivi, contesto, cosa vuoi testare...",
                          height=70, key="new_project_desc")

    create_disabled = not pname.strip()
    if st.button("Crea progetto e continua", type="primary", disabled=create_disabled,
                  use_container_width=True):
        # se il current ha già feed lo scarico nel nuovo
        if has_feed and is_named:
            # crea nuovo id pulito
            st.session_state["session_id"] = None
            for k in ("feed_df", "merged_df", "enriched_df", "gads_df", "raw_df", "labels"):
                if k in st.session_state: del st.session_state[k]
            init_session(st.session_state)
        set_project_name(st.session_state["session_id"], pname, pdesc)
        save_snapshot(st.session_state["session_id"], st.session_state)
        st.session_state.pop("_open_existing", None)
        st.session_state.pop("_replace_mode", None)
        st.success(f"Progetto creato: **{pname}**. Ora carica il feed sotto.")
        st.rerun()

# --- TAB PROGETTO ESISTENTE ---
with tabs[tab_ex_idx]:
    projects = [p for p in list_projects() if p.get("is_named")]
    if not projects:
        st.info("Non hai ancora progetti salvati. Crea il primo nella tab accanto.")
    else:
        search = st.text_input("Cerca progetto", placeholder="Nome o descrizione...", key="proj_search")
        filtered = projects
        if search:
            s = search.lower()
            filtered = [p for p in filtered
                         if s in p.get("name", "").lower()
                         or s in p.get("description", "").lower()]

        from utils.history import delete_session, remove_project_meta

        for p in filtered[:20]:
            confirm_key = f"_confirm_del_proj_{p['id']}"
            with st.container():
                c = st.columns([4, 1, 1])
                c[0].markdown(f"**{p['name']}**")
                info_bits = [f"{p['events']} eventi", f"{p['files']} file"]
                if p.get("description"):
                    c[0].caption(p["description"])
                c[0].caption(" · ".join(info_bits) + f" · ultimo accesso: {p.get('last_opened', '—')}")

                if c[1].button("▶ Apri", key=f"open_{p['id']}", type="primary",
                                use_container_width=True):
                    for k in ("feed_df", "merged_df", "enriched_df", "gads_df", "raw_df", "labels"):
                        if k in st.session_state: del st.session_state[k]
                    restore_snapshot(p["id"], st.session_state)
                    touch_project(p["id"])
                    st.session_state.pop("_open_existing", None)
                    st.session_state.pop("_replace_mode", None)
                    st.success(f"Aperto: **{p['name']}**")
                    st.rerun()

                if c[2].button("🗑️", key=f"del_{p['id']}", use_container_width=True,
                                help="Elimina progetto (irreversibile)"):
                    st.session_state[confirm_key] = True

                if st.session_state.get(confirm_key):
                    st.warning(
                        f"Eliminare **{p['name']}** ({p['events']} eventi, {p['files']} file)? "
                        "L'operazione è permanente: cancella la sessione, la history e tutti gli output."
                    )
                    cc1, cc2 = st.columns(2)
                    if cc1.button("✓ Conferma eliminazione", type="primary",
                                   key=f"del_ok_{p['id']}", use_container_width=True):
                        try:
                            delete_session(p["id"])
                        except Exception:
                            pass
                        try:
                            remove_project_meta(p["id"])
                        except Exception:
                            pass
                        st.session_state.pop(confirm_key, None)
                        st.toast(f"Eliminato: {p['name']}", icon="🗑️")
                        st.rerun()
                    if cc2.button("Annulla", key=f"del_no_{p['id']}",
                                    use_container_width=True):
                        st.session_state.pop(confirm_key, None)
                        st.rerun()

# Se non c'è ancora un progetto nominato, non proseguire
if not get_project_info(st.session_state["session_id"]) and not st.session_state.get("_replace_mode"):
    st.stop()

# ============================================================
# STEP 2 — UPLOAD FEED
# ============================================================
st.divider()
st.markdown(f"### Step 2 · Carica il feed nel progetto **{get_project_name(st.session_state['session_id'])}**")

tab1, tab2 = st.tabs(["Da URL", "Da File"])
df = None
source = ""

with tab1:
    url = st.text_input("URL feed", placeholder="https://example.com/feed.xml")
    if st.button("Scarica e analizza", type="primary", disabled=not url):
        with st.spinner("Scarico e parso il feed..."):
            try:
                df = load_feed(url)
                source = url
            except Exception as e:
                st.error(f"Errore: {e}")

with tab2:
    up = st.file_uploader("Carica file", type=["xml", "csv", "tsv", "json", "txt"])
    if up is not None:
        with st.spinner("Parso il file..."):
            try:
                df = load_feed(up.read(), filename=up.name)
                source = up.name
            except Exception as e:
                st.error(f"Errore: {e}")

if df is not None and len(df):
    df = normalize_columns(df)
    st.session_state["raw_df"] = df.copy()
    st.session_state["feed_df"] = df.copy()
    st.session_state["feed_source"] = source
    st.session_state["enriched_df"] = None
    st.session_state["merged_df"] = None
    st.session_state["labels"] = {}
    save_snapshot(st.session_state["session_id"], st.session_state)
    st.session_state.pop("_replace_mode", None)

    st.success(f"Caricati {len(df):,} prodotti con {len(df.columns)} colonne · progetto salvato automaticamente")

    c1, c2, c3 = st.columns(3)
    c1.metric("Prodotti", f"{len(df):,}")
    c2.metric("Colonne", len(df.columns))
    c3.metric("Fonte", source[:40] + "..." if len(source) > 40 else source)

    st.subheader("Mappatura colonne")
    st.dataframe(
        pd.DataFrame({
            "colonna": df.columns,
            "non_vuote": [df[c].astype(str).str.strip().ne("").sum() for c in df.columns],
            "esempio": [str(df[c].iloc[0])[:80] if len(df) else "" for c in df.columns],
        }),
        use_container_width=True,
    )

    st.subheader("Anteprima")
    st.dataframe(df.head(100), use_container_width=True, height=400)

elif st.session_state.get("feed_df") is not None and not st.session_state.get("_replace_mode"):
    st.info(f"Feed già caricato: **{st.session_state['feed_source']}** "
            f"({len(st.session_state['feed_df']):,} righe). Passa alle pagine successive.")
