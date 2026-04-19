"""Pagina Progetti & History: gestione progetti persistenti."""
import streamlit as st
from pathlib import Path
import pandas as pd

from utils.state import init_state
from utils.ui import apply_theme
from utils.history import (
    init_session, list_projects, read_history, list_outputs,
    delete_session, open_in_finder, save_snapshot, restore_snapshot,
    set_project_name, get_project_name, get_project_info, touch_project,
    clone_project, BASE_DIR, session_dir,
)

init_state()
apply_theme()
init_session(st.session_state)

current_sid = st.session_state["session_id"]
current_name = get_project_name(current_sid)

st.title("Progetti")
st.caption("Ogni progetto salva TUTTO (feed, arricchimenti AI, label, performance) e puoi riaprirlo quando vuoi per continuare. "
           "Path: `~/.feed_enricher/sessions/`")

# ============================================================
# PROGETTO CORRENTE
# ============================================================
st.markdown("### Progetto corrente")
info = get_project_info(current_sid)
is_named = bool(info)

with st.container():
    c1, c2 = st.columns([3, 2])
    with c1:
        new_name = st.text_input("Nome progetto",
                                  value=current_name if is_named else "",
                                  placeholder="Es: 'Catalogo Nike SS26' oppure 'Test refinement premium'")
        new_desc = st.text_area("Descrizione (opzionale)",
                                 value=info.get("description", ""),
                                 placeholder="Note sul progetto, obiettivi, stato...",
                                 height=70)
        if st.button("💾 Salva nome e descrizione", type="primary"):
            set_project_name(current_sid, new_name, new_desc)
            save_snapshot(current_sid, st.session_state)
            st.success(f"Progetto rinominato: **{new_name or current_sid}**")
            st.rerun()
    with c2:
        st.caption(f"ID tecnico: `{current_sid}`")
        if is_named:
            st.caption(f"Creato: {info.get('created', '—')}")
            st.caption(f"Ultimo accesso: {info.get('last_opened', '—')}")
        else:
            st.warning("Progetto senza nome. Dagliene uno per non perderlo tra gli altri.")

st.markdown("#### Azioni")
a1, a2, a3, a4 = st.columns(4)
if a1.button("💾 Salva snapshot ora", use_container_width=True):
    save_snapshot(current_sid, st.session_state)
    st.success("Snapshot salvato")
if a2.button("📂 Apri cartella", use_container_width=True):
    open_in_finder(session_dir(current_sid))
if a3.button("📋 Clona progetto", use_container_width=True,
              help="Duplica il progetto in uno nuovo (per sperimentare senza rischi)"):
    if is_named:
        new_id = clone_project(current_sid, f"{current_name} (copia)")
        st.success(f"Clonato: vai in Progetti e aprilo")
    else:
        st.warning("Nomina il progetto prima di clonarlo")
if a4.button("✨ Nuovo progetto", use_container_width=True):
    st.session_state["session_id"] = None
    for k in ("feed_df", "merged_df", "enriched_df", "gads_df", "raw_df", "labels"):
        if k in st.session_state:
            del st.session_state[k]
    init_session(st.session_state)
    st.rerun()

# stato corrente
events = read_history(current_sid)
outputs = list_outputs(current_sid)
snap_dir = session_dir(current_sid) / "snapshot"
has_snap = snap_dir.exists() and any(snap_dir.iterdir())

m1, m2, m3, m4 = st.columns(4)
m1.metric("Eventi", len(events))
m2.metric("File generati", len(outputs))
m3.metric("Snapshot", "✅" if has_snap else "—")
df_current = st.session_state.get("feed_df")
m4.metric("Prodotti caricati", f"{len(df_current):,}" if df_current is not None else "—")

if outputs:
    with st.expander(f"File generati ({len(outputs)})"):
        for f in outputs:
            size_kb = f.stat().st_size / 1024
            c = st.columns([4, 1, 1])
            c[0].markdown(f"📄 `{f.name}` · {size_kb:.1f} KB")
            with f.open("rb") as fh:
                c[1].download_button("Download", fh.read(), file_name=f.name, key=f"d_{f.name}",
                                      use_container_width=True)
            if c[2].button("Elimina", key=f"x_{f.name}", use_container_width=True):
                f.unlink()
                st.rerun()

if events:
    with st.expander(f"Cronologia eventi ({len(events)})"):
        for e in reversed(events[-100:]):
            payload = ", ".join(f"{k}={v}" for k, v in e.get("payload", {}).items())
            st.markdown(f"- `{e['ts']}` · **{e['event']}** {payload}")

st.divider()

# ============================================================
# INDICE SQLITE (riepilogo veloce)
# ============================================================
from utils import sqlite_store as _sqlite

with st.expander("🗂️ Indice SQLite (ricerca eventi cross-sessione)", expanded=False):
    ic1, ic2, ic3 = st.columns([2, 1, 1])
    if ic1.button("Rebuild indice da JSONL", help="Rescansiona tutte le sessioni e reindicizza"):
        with st.spinner("Rebuilding..."):
            n = _sqlite.rebuild_from_jsonl()
        st.toast(f"Reindicizzati {n} eventi", icon="✅")

    s = _sqlite.stats()
    ic2.metric("Sessioni indicizzate", s["sessions"])
    ic3.metric("Eventi totali", s["events"])

    st.caption(f"DB path: `{s['db_path']}`")

    search_q = st.text_input("Cerca sessione (project_name o session_id)",
                              placeholder="es. Nike, 2026-04")
    if search_q:
        results = _sqlite.search_sessions(q=search_q, limit=20)
        if not results:
            st.info("Nessun risultato.")
        else:
            st.dataframe(
                pd.DataFrame([{
                    "session_id": r["session_id"],
                    "project_name": r["project_name"] or "—",
                    "updated_at": r["updated_at"],
                    "enriched": "✓" if r["has_enrichment"] else "",
                } for r in results]),
                use_container_width=True, height=240,
            )

# ============================================================
# TUTTI I PROGETTI
# ============================================================
st.markdown("### Tutti i progetti")
st.caption("Ordinati per ultimo accesso. Clicca **▶ Apri progetto** per ricaricarlo e continuare.")

projects = list_projects()
if not projects:
    st.info("Nessun progetto.")
else:
    # filtro
    f1, f2 = st.columns([2, 1])
    search = f1.text_input("Cerca per nome/descrizione", placeholder="Es: Nike")
    show_unnamed = f2.checkbox("Mostra anche progetti senza nome", value=False)

    filtered = projects
    if not show_unnamed:
        filtered = [p for p in filtered if p.get("is_named")]
    if search:
        s = search.lower()
        filtered = [p for p in filtered
                     if s in p.get("name", "").lower() or s in p.get("description", "").lower()]

    st.caption(f"{len(filtered)} progetti")

    for p in filtered:
        is_current = p["id"] == current_sid
        snap_exists = (Path(p["path"]) / "snapshot").exists() and \
                       any((Path(p["path"]) / "snapshot").iterdir())

        name = p.get("name", p["id"])
        desc = p.get("description", "")

        with st.container():
            c = st.columns([3, 1, 1, 1])
            title_bits = [f"**{name}**"]
            if is_current: title_bits.append("🟢 corrente")
            if not p.get("is_named"): title_bits.append("*(senza nome)*")
            c[0].markdown(" · ".join(title_bits))
            if desc:
                c[0].caption(desc)
            meta_bits = [f"{p['events']} eventi", f"{p['files']} file", f"{p['size_kb']} KB"]
            if snap_exists: meta_bits.append("💾 snapshot")
            c[0].caption(" · ".join(meta_bits) + f" · ultimo accesso: {p.get('last_opened', '—')}")

            if c[1].button("📂", key=f"o_{p['id']}", use_container_width=True, help="Apri cartella"):
                open_in_finder(Path(p["path"]))

            if c[2].button("▶ Apri progetto" if not is_current else "—",
                           key=f"l_{p['id']}", use_container_width=True,
                           disabled=is_current,
                           type="primary" if not is_current and snap_exists else "secondary"):
                # pulisci state corrente
                for k in ("feed_df", "merged_df", "enriched_df", "gads_df", "raw_df", "labels"):
                    if k in st.session_state:
                        del st.session_state[k]
                if snap_exists:
                    restore_snapshot(p["id"], st.session_state)
                else:
                    st.session_state["session_id"] = p["id"]
                touch_project(p["id"])
                st.success(f"Aperto: **{name}**")
                st.rerun()

            if not is_current and c[3].button("🗑️", key=f"d_{p['id']}", use_container_width=True,
                                                 help="Elimina progetto"):
                delete_session(p["id"])
                st.rerun()

        st.markdown("---")
