"""Gestione Clienti → Feed → Sync & Diff & Pending enrichment."""
import streamlit as st
import pandas as pd

from utils import state
from utils.state import init_state
from utils.ui import apply_theme, api_key_banner, empty_state, stepper
from utils import clients as cs
from utils import feed_diff
from utils.feed_parser import load_feed, normalize_columns
from utils.enrichment import list_sectors

# Opzioni settore condivise tra form-creazione e pannello-dettaglio feed.
# Etichette → valore salvato nel feed.json (""=generico, "auto"=per-prodotto).
_SECTOR_GENERIC = "(generico)"
_SECTOR_AUTO = "✨ auto (multi-settore)"


def _sector_options() -> list[str]:
    return [_SECTOR_GENERIC, _SECTOR_AUTO] + list_sectors()


def _sector_to_value(choice: str) -> str:
    if choice == _SECTOR_GENERIC:
        return ""
    if choice.startswith("✨ auto"):
        return "auto"
    return choice


def _sector_to_index(value: str, options: list[str]) -> int:
    """Indice del selectbox dato il valore salvato nel feed.json."""
    if not value:
        return options.index(_SECTOR_GENERIC)
    if value == "auto":
        return options.index(_SECTOR_AUTO)
    return options.index(value) if value in options else options.index(_SECTOR_GENERIC)

init_state()
apply_theme()
api_key_banner()

st.title("Clienti & Feed")
stepper(["Cliente & Sorgente", "Enrichment", "Refine", "Export"], 1)
st.caption(
    "Ogni cliente può avere N feed. Ogni sync salva uno snapshot storico e "
    "calcola il delta vs ultimo snapshot: nuovi, modificati, rimossi. "
    "I prodotti nuovi/modificati vanno in coda enrichment."
)

# ============================================================
# SELECTOR CLIENTE
# Key page-scoped ("_clienti_client_sel") con valore = SLUG puro.
# Il contesto attivo (cliente, feed) è gestito da utils.state.set_active.
# ============================================================
existing = cs.list_clients()
_NEW_CLIENT = "➕ Nuovo cliente..."
client_opts = [_NEW_CLIENT] + [c["slug"] for c in existing]
_client_names = {c["slug"]: c["name"] for c in existing}

# Default: cliente attivo se presente tra le opzioni, altrimenti il primo reale.
_active_c, _active_f = state.get_active()
if _active_c in client_opts:
    _client_default_idx = client_opts.index(_active_c)
else:
    _client_default_idx = 1 if len(client_opts) > 1 else 0

selected = st.selectbox(
    "Cliente attivo", client_opts, index=_client_default_idx,
    format_func=lambda s: s if s == _NEW_CLIENT else f"{_client_names.get(s, s)}  ({s})",
    key="_clienti_client_sel",
)

current_slug: str | None = None
if selected == _NEW_CLIENT:
    with st.form("_new_client_form"):
        new_name = st.text_input("Nome cliente", placeholder="Es. Nike IT, Rossi Auto, Oasi del Pulito")
        new_notes = st.text_area("Note (opz.)", placeholder="Descrizione cliente, referente, eccetera")
        submitted = st.form_submit_button("Crea cliente", type="primary")
        if submitted and new_name.strip():
            try:
                slug = cs.create_client(new_name, new_notes)
                st.success(f"Cliente creato: {slug}")
                st.rerun()
            except FileExistsError as e:
                st.error(str(e))
            except ValueError as e:
                st.error(str(e))
    st.stop()
else:
    current_slug = selected  # ora è lo slug puro
    cs.touch_client(current_slug)

client = cs.get_client(current_slug)
if not client:
    empty_state(
        icon="👥",
        title="Cliente non trovato",
        description=f"Il cliente '{current_slug}' non esiste più. Crea un cliente nuovo.",
    )
    st.stop()

# ============================================================
# INTESTAZIONE CLIENTE
# ============================================================
hc1, hc2 = st.columns([3, 1])
with hc1:
    st.markdown(f"### {client['name']}")
    st.caption(f"Slug: `{client['slug']}` · creato {client.get('created_at', '?')[:10]}")
    if client.get("notes"):
        st.caption(f"_Note:_ {client['notes']}")
with hc2:
    if st.button("🗑️ Elimina cliente", key="_del_client", use_container_width=True):
        st.session_state["_confirm_del_client"] = True

if st.session_state.get("_confirm_del_client"):
    st.warning(
        f"Eliminerai PERMANENTEMENTE il cliente **{client['name']}** e tutti i suoi feed + snapshot. "
        "Operazione irreversibile."
    )
    co1, co2 = st.columns(2)
    if co1.button("✓ Conferma eliminazione", type="primary"):
        cs.delete_client(current_slug)
        st.session_state["_confirm_del_client"] = False
        st.toast("Cliente eliminato", icon="🗑️")
        st.rerun()
    if co2.button("Annulla"):
        st.session_state["_confirm_del_client"] = False
        st.rerun()

st.divider()

# ============================================================
# LISTA FEED DEL CLIENTE
# ============================================================
st.markdown("### Feed del cliente")

feeds = cs.list_feeds(current_slug)

fc1, fc2 = st.columns([3, 1])
with fc2:
    if st.button("➕ Aggiungi feed", use_container_width=True, key="_add_feed"):
        st.session_state["_show_add_feed"] = True

if st.session_state.get("_show_add_feed"):
    st.markdown("#### Crea nuovo feed + primo snapshot")
    st.caption(
        "Inserisci nome feed. Poi scegli sorgente: URL (scarica e processa) "
        "oppure upload file (XML/CSV/TSV/JSON/XLSX). Il primo snapshot viene salvato automaticamente."
    )
    nf_name = st.text_input("Nome feed", placeholder="Es. catalogo-principale, outlet, b2b",
                              key="_nf_name")
    nf_strategy = st.selectbox(
        "Strategia identificazione prodotto",
        ["hierarchical", "id", "gtin", "mpn", "hash"],
        key="_nf_strategy",
        help=(
            "Come identificare lo 'stesso prodotto' tra sync diversi.\n"
            "- hierarchical (consigliato): id → gtin → mpn → hash(title+brand+price)\n"
            "- id: usa solo SKU\n"
            "- gtin / mpn: usa solo quello\n"
            "- hash: sempre hash su title+brand+price"
        ),
    )
    nf_sector_opts = _sector_options()
    nf_sector_choice = st.selectbox(
        "Settore best practice (enrichment)",
        nf_sector_opts, index=0, key="_nf_sector",
        help=(
            "Ereditato dall'enrichment di questo feed: applica le regole "
            "settoriali (formula titolo, tono, parole vietate).\n"
            "- (generico): nessuna regola settoriale\n"
            "- auto: detecta il settore per-prodotto\n"
            "- uno specifico: forza quel settore"
        ),
    )
    nf_sector = _sector_to_value(nf_sector_choice)
    nf_notes = st.text_area("Note (opz.)", key="_nf_notes")

    src_tab1, src_tab2 = st.tabs(["🌐 Da URL", "📁 Da file"])

    with src_tab1:
        nf_url = st.text_input("URL del feed",
                                 placeholder="https://store.com/products.xml",
                                 key="_nf_url")
        if st.button("Crea feed + scarica", type="primary",
                       disabled=not (nf_name.strip() and nf_url.strip()),
                       key="_nf_submit_url"):
            try:
                slug = cs.create_feed(current_slug, nf_name, nf_url, "url",
                                       nf_strategy, nf_notes, sector=nf_sector)
                with st.spinner("Download feed..."):
                    raw = load_feed(nf_url)
                    parsed = normalize_columns(raw)
                    cs.save_snapshot(current_slug, slug, parsed)
                st.session_state["_show_add_feed"] = False
                st.session_state["_clienti_feed_sel"] = slug
                state.set_active(current_slug, slug)
                st.success(f"✅ Feed '{nf_name}' creato · {len(parsed)} prodotti caricati")
                st.rerun()
            except (FileExistsError, ValueError, FileNotFoundError) as e:
                st.error(str(e))
            except Exception as e:
                import traceback
                st.error(f"Errore: {type(e).__name__}: {e}")
                with st.expander("Debug"):
                    st.code(traceback.format_exc())

    with src_tab2:
        nf_file = st.file_uploader(
            "File feed (XML / CSV / TSV / JSON / XLSX)",
            type=["xml", "csv", "tsv", "json", "xlsx"],
            key="_nf_file",
        )
        if st.button("Crea feed + carica file", type="primary",
                       disabled=not (nf_name.strip() and nf_file is not None),
                       key="_nf_submit_file"):
            try:
                slug = cs.create_feed(current_slug, nf_name, "", "upload",
                                       nf_strategy, nf_notes, sector=nf_sector)
                with st.spinner("Parsing file..."):
                    raw_bytes = nf_file.read()
                    if not raw_bytes:
                        st.error("File vuoto.")
                    else:
                        raw = load_feed(raw_bytes, filename=nf_file.name)
                        parsed = normalize_columns(raw)
                        cs.save_snapshot(current_slug, slug, parsed)
                        st.session_state["_show_add_feed"] = False
                        st.session_state["_clienti_feed_sel"] = slug
                        state.set_active(current_slug, slug)
                        st.success(
                            f"✅ Feed '{nf_name}' creato · {len(parsed)} prodotti caricati"
                        )
                        st.rerun()
            except (FileExistsError, ValueError, FileNotFoundError) as e:
                st.error(str(e))
            except Exception as e:
                import traceback
                st.error(f"Errore: {type(e).__name__}: {e}")
                with st.expander("Debug"):
                    st.code(traceback.format_exc())

    if st.button("Annulla", key="_nf_cancel"):
        st.session_state["_show_add_feed"] = False
        st.rerun()

if not feeds:
    st.info("Nessun feed per questo cliente. Crea il primo con 'Aggiungi feed'.")
    st.stop()

# Tabella feed panoramica
overview_rows = []
for f in feeds:
    overview_rows.append({
        "feed": f["name"],
        "slug": f["slug"],
        "sorgente": f.get("source_type", "?"),
        "ultimo_sync": (f.get("last_sync_at") or "—")[:19].replace("T", " "),
        "snapshot": f.get("n_snapshots", 0),
        "pending": f.get("n_pending", 0),
    })
st.dataframe(
    pd.DataFrame(overview_rows),
    use_container_width=True,
    height=min(120 + len(overview_rows) * 36, 320),
    column_config={
        "pending": st.column_config.NumberColumn(
            "Pending enrichment", help="Prodotti in coda per enrichment manuale"),
        "snapshot": st.column_config.NumberColumn(
            "N snapshot", help="Numero di versioni storiche del feed"),
    },
)

st.divider()

# ============================================================
# DETTAGLIO FEED
# Key page-scoped ("_clienti_feed_sel") con valore = SLUG puro.
# La scelta cliente+feed diventa il contesto attivo via set_active.
# ============================================================
feed_slugs = [f["slug"] for f in feeds]
_feed_names = {f["slug"]: f["name"] for f in feeds}
# Default: feed attivo se è di questo cliente ed esiste tra le opzioni.
if _active_c == current_slug and _active_f in feed_slugs:
    _feed_default_idx = feed_slugs.index(_active_f)
else:
    _feed_default_idx = 0
active_feed = st.selectbox(
    "Feed attivo", feed_slugs, index=_feed_default_idx,
    format_func=lambda s: _feed_names.get(s, s),
    key="_clienti_feed_sel",
)
# Promuovi la coppia (cliente, feed) scelta a contesto attivo. set_active è
# no-op se invariato, quindi non resetta i df se l'utente non ha cambiato nulla.
state.set_active(current_slug, active_feed)

feed = cs.get_feed(current_slug, active_feed)
if not feed:
    st.error("Feed non trovato.")
    st.stop()

st.markdown(f"#### Feed: {feed['name']}")
c = st.columns(5)
c[0].metric("Ultimo sync",
             (feed.get("last_sync_at") or "—")[:10])
c[1].metric("Snapshot totali", feed.get("n_snapshots", 0))
c[2].metric("Pending enrichment", feed.get("n_pending", 0))
c[3].metric("Strategia ID", feed.get("id_strategy", "?"))
# Settore corrente: "" → generico per la vista.
_cur_sector = (feed.get("sector") or "").strip()
c[4].metric("Settore", _cur_sector or "generico")

# Editor settore feed: persistito via update_feed, è il DEFAULT proposto in
# Enrichment AI (feed legacy senza campo sector → fallback "(generico)").
fsec_opts = _sector_options()
fsec_choice = st.selectbox(
    "Settore best practice del feed",
    fsec_opts, index=_sector_to_index(_cur_sector, fsec_opts),
    key=f"_feed_sector_{active_feed}",
    help="Ereditato come default dall'enrichment di questo feed. "
         "Salva per renderlo persistente.",
)
fsec_value = _sector_to_value(fsec_choice)
if fsec_value != _cur_sector:
    if st.button("💾 Salva settore feed", key=f"_save_feed_sector_{active_feed}"):
        cs.update_feed(current_slug, active_feed, sector=fsec_value)
        st.toast("Settore feed aggiornato", icon="📚")
        st.rerun()

# ============================================================
# SYNC (upload nuovo feed)
# ============================================================
st.markdown("##### Carica nuovo snapshot")

sync_tab1, sync_tab2 = st.tabs(["Da URL", "Da file"])

new_df: pd.DataFrame | None = None

with sync_tab1:
    sync_url = st.text_input(
        "URL del feed",
        value=feed.get("source_url", "") or "",
        placeholder="https://store.com/products.xml",
        key="_sync_url",
    )
    if st.button("Scarica & processa", type="primary", key="_dl_url",
                  disabled=not sync_url.strip()):
        with st.spinner("Download in corso..."):
            try:
                raw = load_feed(sync_url)
                new_df = normalize_columns(raw)
                st.session_state["_pending_new_df"] = new_df
                if sync_url != feed.get("source_url"):
                    cs.update_feed(current_slug, active_feed, source_url=sync_url)
                st.success(f"Feed scaricato · {len(new_df)} prodotti")
                st.rerun()
            except Exception as e:  # noqa
                st.error(f"Errore download: {e}")

with sync_tab2:
    uploaded = st.file_uploader(
        "File feed (XML / CSV / TSV / JSON / XLSX)",
        type=["xml", "csv", "tsv", "json", "xlsx"],
        key="_feed_upload",
    )
    if uploaded and st.button("Processa file", type="primary", key="_proc_file"):
        with st.spinner("Parsing..."):
            try:
                raw_bytes = uploaded.read()
                if not raw_bytes:
                    st.error("File vuoto.")
                else:
                    raw = load_feed(raw_bytes, filename=uploaded.name)
                    new_df = normalize_columns(raw)
                    st.session_state["_pending_new_df"] = new_df
                    st.success(f"File processato · {len(new_df)} prodotti")
                    st.rerun()
            except Exception as e:
                import traceback
                st.error(f"Errore parsing: {type(e).__name__}: {e}")
                with st.expander("Debug traceback"):
                    st.code(traceback.format_exc())

# ============================================================
# DELTA VIEW — quando c'è un nuovo df da confrontare
# ============================================================
new_df = st.session_state.get("_pending_new_df")
if new_df is not None and not new_df.empty:
    st.divider()
    st.markdown("##### Delta vs ultimo snapshot")

    old_df = cs.get_latest_snapshot(current_slug, active_feed)
    delta = feed_diff.compute_delta(old_df, new_df, strategy=feed.get("id_strategy", "hierarchical"))

    mc = st.columns(4)
    mc[0].metric("🟢 Nuovi", len(delta.added))
    mc[1].metric("🟡 Modificati", len(delta.modified))
    mc[2].metric("🔴 Rimossi", len(delta.removed))
    mc[3].metric("⚪ Invariati", len(delta.unchanged))

    # Nuovi
    if delta.added:
        with st.expander(f"🟢 {len(delta.added)} prodotti nuovi", expanded=True):
            preview_cols = [c for c in ("_product_key", "id", "title", "brand", "price", "gtin")
                            if c in delta.new_rows.columns]
            st.dataframe(delta.new_rows[preview_cols].head(50),
                          use_container_width=True, height=260)
            if len(delta.new_rows) > 50:
                st.caption(f"_Mostrati primi 50 su {len(delta.new_rows)}._")

    # Modificati
    if delta.modified:
        with st.expander(f"🟡 {len(delta.modified)} prodotti modificati"):
            preview_cols = [c for c in ("_product_key", "id", "title", "brand", "price")
                            if c in delta.modified_rows.columns]
            st.dataframe(delta.modified_rows[preview_cols].head(50),
                          use_container_width=True, height=260)

    # Rimossi
    if delta.removed:
        with st.expander(f"🔴 {len(delta.removed)} prodotti rimossi"):
            preview_cols = [c for c in ("_product_key", "id", "title", "brand")
                            if c in delta.removed_rows.columns]
            st.dataframe(delta.removed_rows[preview_cols].head(50),
                          use_container_width=True, height=260)
            st.caption("_I prodotti rimossi dal nuovo feed non verranno eliminati "
                        "dalle enrichment precedenti, solo segnalati._")

    st.divider()
    st.markdown("##### Conferma sync")
    conf_col1, conf_col2 = st.columns([3, 2])
    with conf_col1:
        enrich_new = st.checkbox("Aggiungi nuovi e modificati alla coda enrichment",
                                  value=True,
                                  help="Gli SKU vengono accodati per enrichment manuale (non lancia ancora)")
    with conf_col2:
        if st.button("✓ Salva snapshot + aggiorna coda", type="primary",
                      use_container_width=True, key="_confirm_sync"):
            # Save snapshot
            cs.save_snapshot(current_slug, active_feed, new_df)
            # Update pending queue
            if enrich_new:
                cs.add_pending(current_slug, active_feed, delta.added, reason="new")
                cs.add_pending(current_slug, active_feed, delta.modified, reason="modified")
            cs.log_event(current_slug, active_feed, "sync_confirmed", {
                "added": len(delta.added),
                "modified": len(delta.modified),
                "removed": len(delta.removed),
            })
            # Clear pending new df
            st.session_state.pop("_pending_new_df", None)
            st.toast("Snapshot salvato · coda aggiornata", icon="✅")
            st.rerun()

# ============================================================
# PENDING ENRICHMENT (coda)
# ============================================================
st.divider()
st.markdown("##### Coda enrichment")

pending = cs.get_pending(current_slug, active_feed)
if not pending:
    st.info("Nessun prodotto in coda. Al prossimo sync i nuovi/modificati finiranno qui.")
else:
    # Intersect pending keys with latest snapshot rows for display
    latest = cs.get_latest_snapshot(current_slug, active_feed)
    if latest is None or latest.empty:
        st.warning("Nessuno snapshot per il feed — impossibile mostrare dettagli.")
    else:
        pending_keys = [e["key"] for e in pending]
        key_to_row: dict[str, int] = {}
        for idx, row in latest.iterrows():
            key = feed_diff.product_key(row.to_dict(),
                                         strategy=feed.get("id_strategy", "hierarchical"))
            if key in pending_keys and key not in key_to_row:
                key_to_row[key] = idx

        pending_df = latest.loc[list(key_to_row.values())].copy() if key_to_row else pd.DataFrame()
        if pending_df.empty:
            st.warning(
                f"{len(pending)} chiavi in coda ma nessuna corrisponde allo snapshot corrente. "
                "Possibile delta con snapshot obsoleto."
            )
        else:
            pending_df["_product_key"] = [k for k, _ in key_to_row.items() if _ in pending_df.index]
            reasons = {e["key"]: e.get("reason", "") for e in pending}
            pending_df["_reason"] = pending_df["_product_key"].map(reasons)

            # Selection UI
            st.caption("Seleziona i prodotti da enrichare (spunta la colonna `select`).")
            show_cols = [c for c in ("_product_key", "_reason", "id", "title", "brand", "price", "gtin")
                          if c in pending_df.columns]
            display_df = pending_df[show_cols].copy()
            display_df.insert(0, "select", False)
            edited = st.data_editor(
                display_df,
                use_container_width=True,
                height=min(150 + len(display_df) * 32, 500),
                key="_pending_editor",
                column_config={
                    "select": st.column_config.CheckboxColumn("✔"),
                    "_product_key": st.column_config.TextColumn("key", width="medium"),
                    "_reason": st.column_config.TextColumn("motivo", width="small"),
                },
                disabled=[c for c in display_df.columns if c != "select"],
            )

            selected_rows = edited[edited["select"]]
            pcol1, pcol2, pcol3 = st.columns([1, 1, 3])
            select_all = pcol1.button(f"Seleziona tutti ({len(pending_df)})",
                                        use_container_width=True)
            if select_all:
                # Mark all as selected in the df state
                pending_df["_product_key"].tolist()
                st.session_state["_enrich_selected_keys"] = pending_df["_product_key"].tolist()
                # Contesto già = (current_slug, active_feed): set_active no-op,
                # non resetta i df. Riconfermato per chiarezza del handoff.
                state.set_active(current_slug, active_feed)
                st.switch_page("client_pages/enrichment_ai.py")

            if pcol2.button(f"Enrichment selezionati ({len(selected_rows)})",
                             type="primary", use_container_width=True,
                             disabled=selected_rows.empty):
                # Pass selected subset to Enrichment page via session state
                sel_keys = selected_rows["_product_key"].tolist()
                st.session_state["_enrich_selected_keys"] = sel_keys
                state.set_active(current_slug, active_feed)
                # Load feed_df = snapshot subset
                sel_rows = pending_df[pending_df["_product_key"].isin(sel_keys)]
                st.session_state["feed_df"] = sel_rows.drop(
                    columns=[c for c in ("_product_key", "_reason") if c in sel_rows.columns],
                    errors="ignore",
                )
                st.switch_page("client_pages/enrichment_ai.py")

            pcol3.caption(
                "Gli enrichment completati saranno rimossi automaticamente dalla coda. "
                "Usa 'Rimuovi da coda senza enrichment' per scartare."
            )

            if st.button("✗ Rimuovi selezionati da coda (senza enrichment)",
                          disabled=selected_rows.empty, key="_remove_pending"):
                removed = cs.remove_pending(current_slug, active_feed,
                                              selected_rows["_product_key"].tolist())
                st.toast(f"Rimossi {removed} prodotti dalla coda", icon="🗑️")
                st.rerun()

# ============================================================
# STORICO EVENTI
# ============================================================
with st.expander("📜 Storico eventi feed"):
    events = cs.read_events(current_slug, active_feed, limit=50)
    if not events:
        st.caption("_Nessun evento registrato._")
    else:
        st.dataframe(
            pd.DataFrame(events),
            use_container_width=True, height=min(100 + len(events) * 28, 320),
        )

# ============================================================
# AZIONI MANUTENZIONE
# ============================================================
with st.expander("⚙️ Manutenzione feed"):
    mc1, mc2 = st.columns(2)
    with mc1:
        keep_n = st.number_input("Conserva ultimi N snapshot", 1, 100, 20)
        if st.button("🧹 Pulisci snapshot vecchi", use_container_width=True):
            deleted = cs.prune_snapshots(current_slug, active_feed, keep_last_n=int(keep_n))
            st.toast(f"Eliminati {deleted} snapshot", icon="🧹")
            st.rerun()
    with mc2:
        if st.button("🗑️ Elimina questo feed (irreversibile)",
                      use_container_width=True, key="_del_feed"):
            st.session_state["_confirm_del_feed"] = True

    if st.session_state.get("_confirm_del_feed"):
        st.warning(f"Elimini permanentemente il feed **{feed['name']}** "
                    "e tutti i suoi snapshot + coda + storico.")
        if st.button("✓ Conferma", type="primary"):
            cs.delete_feed(current_slug, active_feed)
            st.session_state.pop("_confirm_del_feed", None)
            st.toast("Feed eliminato", icon="🗑️")
            st.rerun()
