"""Enrichment AI — selezione + lancio. Refinement/chat → client_pages/refine_chat.py."""
import streamlit as st
import pandas as pd

from utils import state
from utils.state import init_state
from utils.ui import (
    apply_theme, api_key_banner, empty_state, guarded, stepper,
    cost_estimate_card, cost_projection_table, LoadingProgress, status_badge,
    export_status_badge,
)
from utils.catalog_optimizer import compute_export_status
from utils.enrichment import enrich_dataframe, list_sectors, load_sector
from utils import cache as enrich_cache
from utils import clients as _cs

init_state()
apply_theme()
api_key_banner()

st.title("Enrichment AI")
stepper(["Cliente & Sorgente", "Enrichment", "Refine", "Export"], 2)
st.caption("Classificazione Google Taxonomy + estrazione attributi + riscrittura titoli/descrizioni · Chat con Claude per affinare")

# ============================================================
# CLIENT + FEED SELECTOR — banner in alto.
# Permette di scegliere cliente/feed attivo e caricarne snapshot
# (preferendo enriched.parquet se esiste).
# ============================================================
_all_clients = _cs.list_clients()


def _cache_namespace() -> str:
    """Namespace cache PER-CLIENTE (P0.4): isola i risultati tra clienti.

    Se non c'è cliente attivo (path demo / feed in sessione senza binding)
    usa "_session" — isolato e non condiviso tra clienti diversi.
    """
    cslug, _ = state.get_active()
    return f"client_{cslug}" if cslug else "_session"


def _style_guide_hash(text: str) -> str:
    """Hash breve dello style_guide_text per l'extra dell'hash cache."""
    import hashlib
    return hashlib.md5((text or "").encode("utf-8")).hexdigest()[:12]


def _load_feed_from_client(client_slug: str, feed_slug: str) -> tuple[pd.DataFrame | None, str]:
    """Carica feed attivo: overlay enriched→snapshot per _product_key (P0.2).

    Vede i prodotti nuovi (presenti nello snapshot ma non in enriched) e non
    serve quelli rimossi dal feed. La strategy è quella salvata nel feed.json.
    """
    strat = (_cs.get_feed(client_slug, feed_slug) or {}).get("id_strategy", "hierarchical")
    return _cs.load_feed_merged(client_slug, feed_slug, strategy=strat)


with st.container():
    st.markdown(
        "<div style='background:#F4F5F7; border:1px solid #E5E7EB; border-radius:12px; "
        "padding:14px 16px; margin:6px 0 18px;'>"
        "<div style='font-size:0.78rem; color:#6B7280; font-weight:600; "
        "text-transform:uppercase; letter-spacing:0.04em; margin-bottom:8px;'>"
        "◐&nbsp;&nbsp;Contesto cliente</div></div>",
        unsafe_allow_html=True,
    )
    if not _all_clients:
        st.info(
            "Nessun cliente salvato. Crea il primo dalla pagina **Clienti & Feed** "
            "per tracciare feed multipli per cliente."
        )
        if st.button("→ Vai a Clienti & Feed", key="_goto_clients", use_container_width=True):
            st.switch_page("client_pages/clienti.py")
    else:
        _slug_to_name = {c["slug"]: c.get("name", c["slug"]) for c in _all_clients}
        _client_slugs = list(_slug_to_name.keys())

        # default: cliente attivo (contesto unico) se valido, altrimenti il primo
        _act_client, _act_feed = state.get_active()
        default_client = _act_client if _act_client in _client_slugs else _client_slugs[0]

        sel1, sel2, sel3 = st.columns([2, 2, 1.2])
        chosen_client = sel1.selectbox(
            "Cliente",
            options=_client_slugs,
            index=_client_slugs.index(default_client),
            format_func=lambda s: _slug_to_name.get(s, s),
            key="_enrich_client_sel",
        )

        _feeds = _cs.list_feeds(chosen_client)
        if not _feeds:
            sel2.selectbox("Feed", options=["(nessun feed)"], disabled=True,
                            key="_enrich_feed_empty")
            sel3.write("")
            st.caption(
                f"Cliente **{_slug_to_name[chosen_client]}** non ha feed. "
                "Aggiungine uno da **Clienti & Feed**."
            )
        else:
            _feed_slug_to_name = {f["slug"]: f.get("name", f["slug"]) for f in _feeds}
            _feed_slugs = list(_feed_slug_to_name.keys())
            # default: feed attivo se appartiene al cliente scelto, altrimenti primo
            if _act_client == chosen_client and _act_feed in _feed_slugs:
                default_feed = _act_feed
            else:
                default_feed = _feed_slugs[0]

            chosen_feed = sel2.selectbox(
                "Feed",
                options=_feed_slugs,
                index=_feed_slugs.index(default_feed),
                format_func=lambda s: _feed_slug_to_name.get(s, s),
                key="_enrich_feed_sel",
            )

            # Promuovi la scelta a contesto attivo (SLUG puri). No-op se
            # invariato → non resetta i df già caricati in sessione.
            state.set_active(chosen_client, chosen_feed)

            # Info feed selezionato
            _fmeta = next((f for f in _feeds if f["slug"] == chosen_feed), {})
            _enr_preview = _cs.load_enriched(chosen_client, chosen_feed)
            _snap_count = _fmeta.get("n_snapshots", 0)
            _pending_count = _fmeta.get("n_pending", 0)
            _has_enriched = _enr_preview is not None and not _enr_preview.empty
            if _has_enriched:
                _n_rows_available = len(_enr_preview)
            else:
                _snap_preview = _cs.get_latest_snapshot(chosen_client, chosen_feed)
                _n_rows_available = len(_snap_preview) if _snap_preview is not None else 0

            # CTA carica
            with sel3:
                st.write("")  # align
                load_clicked = st.button(
                    f"📥 Carica",
                    key="_load_feed_btn",
                    use_container_width=True,
                    type="primary",
                    disabled=(_n_rows_available == 0),
                    help="Carica questo feed come dataset attivo (sostituisce quello in sessione).",
                )

            # stato attuale vs selezionato: il contesto attivo coincide con la
            # scelta corrente e c'è un feed effettivamente caricato in sessione.
            _act_c_now, _act_f_now = state.get_active()
            _current_bound = (
                _act_c_now == chosen_client
                and _act_f_now == chosen_feed
                and st.session_state.get("feed_df") is not None
            )
            _status_line = (
                f"**{_slug_to_name[chosen_client]}** · feed **{_feed_slug_to_name[chosen_feed]}** · "
                f"{_n_rows_available:,} prodotti disponibili · "
                f"{_snap_count} snapshot · {_pending_count} pending · "
                + ("🟢 Caricato in sessione" if _current_bound else "⚪ Non caricato")
            )
            st.caption(_status_line)

            if load_clicked:
                loaded_df, source = _load_feed_from_client(chosen_client, chosen_feed)
                if loaded_df is None:
                    st.error("Nessun snapshot/enriched disponibile per questo feed.")
                else:
                    # set_active prima del load: assicura contesto coerente e
                    # azzera eventuali df di un contesto precedente.
                    state.set_active(chosen_client, chosen_feed)
                    st.session_state["feed_df"] = loaded_df
                    st.session_state["enriched_df"] = loaded_df.copy()
                    st.session_state["merged_df"] = None
                    _cs.touch_client(chosen_client)
                    st.toast(
                        f"Feed {_feed_slug_to_name[chosen_feed]} caricato "
                        f"({len(loaded_df):,} prodotti · da {source})",
                        icon="📥",
                    )
                    st.rerun()


if st.session_state.get("feed_df") is None:
    empty_state(
        icon="📦",
        title="Nessun feed caricato",
        description="Carica prima un feed prodotto per poter lanciare l'enrichment AI. "
                    "Crea cliente/feed e sincronizza da Clienti & Feed.",
        cta_label="Vai a Clienti & Feed →",
        cta_page="client_pages/clienti.py",
        cta_key="_empty_upload",
    )
    st.stop()
if not st.session_state.get("api_key"):
    empty_state(
        icon="🔑",
        title="API key non configurata",
        description="L'enrichment AI richiede una chiave Claude. Configurala in Settings "
                    "(salvata in locale, non inviata ai server).",
        cta_label="Configura API key →",
        cta_page="client_pages/settings.py",
        cta_key="_empty_settings",
    )
    st.stop()

# Usa enriched_df come sorgente principale se esiste, altrimenti feed_df.
# Questo garantisce che selezione + Risultati vedano la stessa data.
df = st.session_state.get("enriched_df")
if df is None or df.empty:
    df = st.session_state["feed_df"].copy()
    st.session_state["enriched_df"] = df

# ── P0 selezione: normalizza l'index a RangeIndex 0..n-1 stabile e UNIVOCO ──
# L'identità di selezione è l'indice-riga del df. Il df arriva da
# parquet/merge_enriched/load_feed_merged e NON garantisce un index 0..n-1:
# dopo un round-trip parquet o un concat l'index può avere duplicati o buchi.
# Con index NON univoco lo slice di pagina (filtered.iloc[...]) può contenere un
# valore che ricompare su un'altra pagina → la selezione "si sposta" sul
# prodotto sbagliato e df.loc[selected_indices] restituisce più righe per lo
# stesso indice (regressione P0). reset_index(drop=True) rende l'index 0..n-1
# univoco e stabile, coerente fra df, slice di pagina e launch.
# È SAFE per la persistenza: merge_enriched fa upsert per _product_key (non per
# indice), quindi reindicizzare non cambia nulla a valle. Riscriviamo lo STESSO
# oggetto reindicizzato in sessione così anche il merge per-indice della vista
# (df.loc[enriched_subset.index]) e il launch (df.loc[selected_indices])
# lavorano sullo STESSO spazio di indici stabile.
if not (isinstance(df.index, pd.RangeIndex) and df.index.is_unique):
    df = df.reset_index(drop=True)
    st.session_state["enriched_df"] = df

# ============================================================
# HEADER METRICS
# ============================================================
if "_enrichment_status" not in df.columns:
    df["_enrichment_status"] = ""
_status_lower = df["_enrichment_status"].astype(str).str.strip().str.lower()
n_total = len(df)
n_enriched = int(_status_lower.isin(["ok", "cached"]).sum())
n_todo = n_total - n_enriched

mc = st.columns(3)
mc[0].metric("Prodotti totali", f"{n_total:,}")
mc[1].metric("Già arricchiti", f"{n_enriched:,}", help="Status 'ok' o 'cached'")
mc[2].metric("Da arricchire", f"{n_todo:,}", help="Non arricchiti o con errore")

st.markdown("### Seleziona prodotti da arricchire")
st.caption(
    "Scegli un preset, restringi con i filtri, poi spunta i prodotti. "
    "La selezione persiste tra le pagine. La configurazione AI è sotto."
)

# ============================================================
# PRODUCT CARD GRID (Fase 2c)
# IDENTITÀ DI SELEZIONE = INDICE DI RIGA del df (univoco e stabile in
# sessione). Niente product_key per la selezione: con strategy 'hash'
# (fallback) due prodotti distinti senza id/gtin/mpn ma con stesso
# title|brand|price collasserebbero sulla stessa key → enrichment su N
# righe invece di 1 (costo ×N, dato sbagliato sul "gemello"). L'indice
# evita la collisione.
# product_key resta usato SOLO per il match col preset "Da arricchire"
# (intersezione con la coda pending del feed).
# ============================================================
import html as _html

# --- product_key UNA volta per rerun (rischio #1: niente iterrows ripetuti) ---
# La strategy è quella del feed attivo; in path demo (no feed) si usa "id".
_act_client_pk, _act_feed_pk = state.get_active()
if _act_client_pk and _act_feed_pk:
    _pk_strategy = (_cs.get_feed(_act_client_pk, _act_feed_pk) or {}).get(
        "id_strategy", "hierarchical")
else:
    _pk_strategy = "id"  # demo / feed non bindato: id stabile come key


def _STATUS_TEXT(status, level: str = "") -> str:
    """Compromesso testuale per la cella Stato in tabella (no HTML).

    Combina asse enrichment (`_enrichment_status`) + livello export (`level`),
    stessa precedenza di export_status_badge §5. Palette coerente con i badge.
    """
    s = str(status or "").strip().lower()
    lvl = str(level or "").strip().lower()
    if s.startswith("error"):
        return "✕ Errore"
    if s in ("cached", "stale"):
        return "↻ Da rivedere"
    if lvl == "pronto_export":
        return "✓ Pronto export"
    if lvl == "arricchito":
        return "● Arricchito"
    return "○ Grezzo"


# --- product_keys MEMOIZZATE su fingerprint del df (solo per match pending) ---
# Le key servono SOLO al preset "Da arricchire" (intersezione con la coda),
# non per identificare la selezione → cache-arle è sicuro. Il fingerprint
# cambia quando il df cambia (es. dopo enrichment) → le key si ricalcolano.
def _df_fingerprint(_df: pd.DataFrame) -> str:
    """Fingerprint stabile per cache key (hash contenuto + shape)."""
    try:
        import hashlib
        h = pd.util.hash_pandas_object(_df, index=True).values
        return hashlib.md5(h.tobytes()).hexdigest() + f"_{_df.shape[0]}x{_df.shape[1]}"
    except Exception:
        return f"{_df.shape[0]}x{_df.shape[1]}_{hash(tuple(_df.columns))}"


@st.cache_data(show_spinner=False, max_entries=4)
def _cached_pkeys(fp: str, strategy: str, _df: pd.DataFrame) -> pd.Series:
    """Series _pkey allineata all'index del df (memoizzata su fingerprint).

    `_df` ha l'underscore così Streamlit non prova a hasharlo: la cache key
    reale è `fp` (+ strategy). Usa product_keys_for_df di feed_diff così la
    key coincide con quella di pending/merge_enriched.
    """
    from utils import feed_diff as _fd
    keys = _fd.product_keys_for_df(_df, strategy=strategy)
    # Fallback per le righe la cui key è vuota (es. strategy 'id' senza id):
    # hash del contenuto, coerente con feed_diff.product_key(strategy='hash').
    empty = keys.isin(["", "h:"]) | keys.isna()
    if empty.any():
        recs = _df.loc[empty].to_dict("records")
        keys.loc[empty] = [_fd.product_key(r, strategy="hash") for r in recs]
    return keys


_pkey = _cached_pkeys(_df_fingerprint(df), _pk_strategy, df)

# ── IDENTITÀ DI SELEZIONE = set di INDICI-RIGA del df (univoci/stabili) ──────
# Fonte di verità unica. Selezionare una card seleziona ESATTAMENTE quella
# riga, mai la gemella con stesso title|brand|price.
if "selected_row_ids" not in st.session_state:
    st.session_state["selected_row_ids"] = set()
selected_row_ids: set = st.session_state["selected_row_ids"]
# Tieni solo indici ancora presenti nel df (dopo reload il df cambia index).
selected_row_ids &= set(df.index)

# ── HANDOFF da clienti.py (Fix 4): _enrich_selected_keys (lista di
# product_key dei pending) → traduci in indici-riga UNA volta e consuma. ──────
_handoff_keys = st.session_state.pop("_enrich_selected_keys", None)
if _handoff_keys:
    _hk = set(_handoff_keys)
    selected_row_ids |= set(_pkey[_pkey.isin(_hk)].index.tolist())

# Coda pending del feed attivo (stesse key di feed_diff) → preset "Da arricchire".
_pending_keys: set = set()
if _act_client_pk and _act_feed_pk:
    try:
        # get_pending ritorna entry con campo "key" = product_key (feed_diff).
        _pending_keys = {p.get("key") for p in
                          _cs.get_pending(_act_client_pk, _act_feed_pk)
                          if p.get("key")}
    except Exception:
        _pending_keys = set()


# ── selection_version: token che cambia su bulk/filtro/preset/pagina così i
# checkbox dello slice si RICREANO con il value corretto (Fix 3). Senza, una
# widget-key già in session_state ignora il nuovo value= → card accesa /
# checkbox vuoto dopo "Seleziona pagina"/"Deseleziona tutto". ──────────────────
if "_sel_version" not in st.session_state:
    st.session_state["_sel_version"] = 0


def _bump_sel_version() -> None:
    st.session_state["_sel_version"] = st.session_state.get("_sel_version", 0) + 1


# ── Callback selezione card: legge la key del widget, muta solo il set ──────
def _toggle_card(row_id, widget_key: str) -> None:
    if st.session_state.get(widget_key):
        selected_row_ids.add(row_id)
    else:
        selected_row_ids.discard(row_id)


def _reset_page() -> None:
    """Torna a pagina 1 quando cambiano preset/filtri/vista/page-size.

    Bump anche selection_version: i checkbox dello slice si ricreano con il
    value coerente (evita key vecchie spuntate su prodotto diverso).
    """
    st.session_state["_card_page"] = 1
    _bump_sel_version()


# ============================================================
# BARRA AZIONI — 3 fasce: preset · filtri · contatore+azioni+vista
# ============================================================
# Fascia 1: preset segmentato (segmented_control con fallback radio)
_preset_opts = ["⭐ Da arricchire", "⚠ Errori", "Tutti"]
if hasattr(st, "segmented_control"):
    preset = st.segmented_control(
        "Preset", options=_preset_opts, default="⭐ Da arricchire",
        key="_enrich_preset", on_change=_reset_page, label_visibility="collapsed",
    ) or "⭐ Da arricchire"
else:  # fallback Streamlit < segmented_control
    preset = st.radio(
        "Preset", options=_preset_opts, index=0, horizontal=True,
        key="_enrich_preset", on_change=_reset_page, label_visibility="collapsed",
    )

# Fascia 2: filtri (restringono la vista, NON preselezionano)
fc1, fc2, fc3 = st.columns([3, 2, 2])
search = fc1.text_input("Cerca", placeholder="Cerca per titolo o ID…",
                         key="_enrich_search", on_change=_reset_page,
                         label_visibility="collapsed")
brand_options = sorted(df["brand"].dropna().astype(str).unique().tolist()) \
                 if "brand" in df.columns else []
brand_filter = fc2.multiselect("Brand", options=brand_options, default=[],
                                 key="_enrich_brand_filter", on_change=_reset_page,
                                 placeholder="Brand")
cat_col = "google_product_category" if "google_product_category" in df.columns \
          else ("product_type" if "product_type" in df.columns else None)
cat_options = sorted(df[cat_col].dropna().astype(str).unique().tolist()) if cat_col else []
cat_filter = fc3.multiselect("Categoria", options=cat_options, default=[],
                              key="_enrich_cat_filter", on_change=_reset_page,
                              placeholder="Categoria", disabled=not cat_col)

# --- maschera filtri + preset (in pandas, una volta) -------------------------
mask = pd.Series([True] * len(df), index=df.index)
if search:
    s = search.lower()
    search_cols = [c for c in ("title", "id") if c in df.columns]
    text_mask = pd.Series([False] * len(df), index=df.index)
    for c in search_cols:
        text_mask |= df[c].astype(str).str.lower().str.contains(s, na=False, regex=False)
    mask &= text_mask
if brand_filter and "brand" in df.columns:
    mask &= df["brand"].astype(str).isin(brand_filter)
if cat_filter and cat_col:
    mask &= df[cat_col].astype(str).isin(cat_filter)

# Preset: "Da arricchire" = non ok/cached UNITO ai pending del feed.
if preset == "⭐ Da arricchire":
    todo_mask = ~_status_lower.isin(["ok", "cached"])
    if _pending_keys:
        todo_mask |= _pkey.isin(_pending_keys)
    mask &= todo_mask
elif preset == "⚠ Errori":
    mask &= _status_lower.str.startswith("error")
# "Tutti" → nessun vincolo di stato

filtered = df[mask].copy()  # mantiene l'index originale del df = id di selezione

# ============================================================
# VIEW SETUP — pagina, page-size, vista (card/tabella)
# ============================================================
if "_card_page" not in st.session_state:
    st.session_state["_card_page"] = 1

# Fascia 3: contatore + azioni bulk + vista + page size
n_visible = len(filtered)
n_selected_live = len(selected_row_ids)
tc1, tc2 = st.columns([3, 2])
tc1.markdown(
    f"<div style='padding-top:6px; font-size:0.9rem; color:#4B5563;'>"
    f"<b>{n_visible:,}</b> prodotti · "
    f"<span style='color:#2F6FED; font-weight:600;'>{n_selected_live:,} selezionati</span>"
    f"</div>",
    unsafe_allow_html=True,
)
with tc2:
    vcol, pcol = st.columns([2, 1])
    _view_opts = ["▦ Card", "☰ Tabella"]
    if hasattr(st, "segmented_control"):
        view = vcol.segmented_control(
            "Vista", options=_view_opts, default="▦ Card",
            key="_enrich_view", on_change=_reset_page, label_visibility="collapsed",
        ) or "▦ Card"
    else:
        view = vcol.radio("Vista", options=_view_opts, index=0, horizontal=True,
                           key="_enrich_view", on_change=_reset_page,
                           label_visibility="collapsed")
    page_size = pcol.selectbox("Per pagina", options=[24, 48], index=0,
                                key="_enrich_page_size", on_change=_reset_page,
                                label_visibility="collapsed")

# Azioni bulk: operano sullo SLICE corrente (pagina) o azzerano tutto.
ac1, ac2, _ac3 = st.columns([1.4, 1.4, 3.2])

# --- paginazione: clamp pagina + slice ---------------------------------------
total_pages = max((n_visible + page_size - 1) // page_size, 1)
page = min(max(int(st.session_state.get("_card_page", 1)), 1), total_pages)
st.session_state["_card_page"] = page
start = (page - 1) * page_size
page_slice = filtered.iloc[start:start + page_size]
page_ids = page_slice.index.tolist()  # indici-riga = id di selezione dello slice

if ac1.button("Seleziona pagina", use_container_width=True, key="_sel_page",
               disabled=page_slice.empty):
    selected_row_ids.update(page_ids)
    _bump_sel_version()  # ricrea i checkbox dello slice col value aggiornato
    st.rerun()
if ac2.button("Deseleziona tutto", use_container_width=True, key="_sel_none",
               disabled=not selected_row_ids):
    selected_row_ids.clear()
    _bump_sel_version()
    st.rerun()

# ============================================================
# EMPTY STATES
# ============================================================
if filtered.empty:
    if preset == "⚠ Errori":
        empty_state(
            icon="✅", title="Nessun errore",
            description="Tutti i prodotti elaborati sono andati a buon fine.",
        )
    else:
        empty_state(
            icon="🔍", title="Nessun prodotto trovato",
            description="Nessun prodotto corrisponde ai filtri. "
                        "Prova a rimuovere un filtro o cambia preset.",
        )
elif view == "☰ Tabella":
    # ============================================================
    # VISTA TABELLA — data_editor sullo STESSO selected_row_ids.
    # La selezione in tabella riconcilia il set SENZA perdere altre pagine.
    # ============================================================
    base_cols = [c for c in ("image_link", "id", "title", "brand", "price")
                  if c in page_slice.columns]
    tbl = page_slice[base_cols].copy()
    # _rowid = indice-riga del df (id di selezione univoco), non product_key.
    tbl.insert(0, "_rowid", page_ids)
    tbl.insert(0, "Seleziona", [rid in selected_row_ids for rid in page_ids])
    # Stato per-prodotto sullo SLICE visibile (24/48), non su tutto il df:
    # combina asse enrichment + livello export (compute_export_status per riga).
    tbl["Stato"] = [
        _STATUS_TEXT(
            page_slice.iloc[i].get("_enrichment_status", ""),
            compute_export_status(page_slice.iloc[i])[0],
        )
        for i in range(len(page_slice))
    ]

    _img_col = (st.column_config.ImageColumn("Img", width="small")
                if hasattr(st.column_config, "ImageColumn")
                else st.column_config.TextColumn("Img", width="small"))
    _tbl_cfg = {
        "Seleziona": st.column_config.CheckboxColumn("☑", width="small", pinned=True),
        "_rowid": None,  # nascondi id tecnico
        "image_link": _img_col,
        "id": st.column_config.TextColumn("ID", width="small"),
        "title": st.column_config.TextColumn("Title", width="large"),
        "brand": st.column_config.TextColumn("Brand", width="small"),
        "price": st.column_config.TextColumn("Prezzo", width="small"),
        "Stato": st.column_config.TextColumn("Stato", width="small", pinned=True),
    }
    # key dipende da selection_version → la tabella si ricrea col value
    # corretto dopo bulk/filtro/preset (Fix 3), senza perdere altre pagine.
    _sv = st.session_state["_sel_version"]
    edited = st.data_editor(
        tbl, use_container_width=True, height=520, hide_index=True,
        column_config=_tbl_cfg,
        disabled=[c for c in tbl.columns if c != "Seleziona"],
        key=f"_edit_table_{page}_{page_size}_{_sv}",
    )
    # Riconcilia SOLO le righe di questa pagina (non toccare altre pagine).
    for _rid, _sel in zip(edited["_rowid"].tolist(), edited["Seleziona"].tolist()):
        if _sel:
            selected_row_ids.add(_rid)
        else:
            selected_row_ids.discard(_rid)
else:
    # ============================================================
    # VISTA CARD — st.columns(4) fisso; card HTML + checkbox nativo.
    # Renderizza SOLO lo slice (max 48) → rischio #1 risolto.
    # ============================================================
    # NB: NON reset_index → l'index resta l'id di selezione di ogni riga.
    rows = page_slice
    _sv = st.session_state["_sel_version"]
    for block_start in range(0, len(rows), 4):
        cols = st.columns(4)
        for col_i in range(4):
            r_i = block_start + col_i
            if r_i >= len(rows):
                continue
            row = rows.iloc[r_i]
            row_id = page_ids[r_i]  # indice-riga = id di selezione univoco
            is_sel = row_id in selected_row_ids

            # Immagine: image_link → additional_image_link, solo https.
            img_url = ""
            for _imc in ("image_link", "additional_image_link"):
                v = str(row.get(_imc, "") or "").strip()
                if v.lower().startswith("https://"):
                    img_url = v
                    break
            if img_url:
                img_html = (f"<div class='pc-imgwrap'>"
                            f"<img loading='lazy' src='{_html.escape(img_url, quote=True)}' "
                            f"alt=''></div>")
            else:
                img_html = (
                    "<div class='pc-imgwrap'><div class='pc-noimg'>"
                    "<div class='pc-noimg-icon'>▦</div>"
                    "<div class='pc-noimg-txt'>Nessuna immagine</div></div></div>"
                )

            # Title / brand / price (escapati, prezzo mono con fallback —).
            title_txt = _html.escape(str(row.get("title", "") or "").strip()) or "—"
            brand_txt = str(row.get("brand", "") or "").strip()
            brand_html = (f"<div class='pc-brand'>{_html.escape(brand_txt)}</div>"
                          if brand_txt else "")
            price_txt = str(row.get("price", "") or "").strip()
            if price_txt and price_txt.lower() not in ("nan", "none"):
                price_html = f"<div class='pc-price'>{_html.escape(price_txt)}</div>"
            else:
                price_html = "<div class='pc-price pc-price-empty'>—</div>"

            check_html = "<div class='pc-check'>✓</div>" if is_sel else ""
            sel_cls = " is-selected" if is_sel else ""
            # Status export calcolato SOLO sulla riga visibile (slice 24/48),
            # non sull'intero catalogo: la card è già limitata alla pagina.
            _exp_level = compute_export_status(row)[0]
            card_html = (
                f"<div class='preview-card product-card{sel_cls}'>"
                f"{check_html}{img_html}"
                f"<div class='pc-body'>"
                f"{export_status_badge(row.get('_enrichment_status', ''), _exp_level)}"
                f"<div class='pc-title'>{title_txt}</div>"
                f"{brand_html}{price_html}"
                f"</div></div>"
            )
            with cols[col_i]:
                st.markdown(card_html, unsafe_allow_html=True)
                # widget-key include row_id (univoco) + selection_version: si
                # ricrea col value corretto dopo bulk/filtro (Fix 3).
                wkey = f"sel_{row_id}_{page}_{_sv}"
                st.checkbox("Seleziona", value=is_sel, key=wkey,
                             on_change=_toggle_card, args=(row_id, wkey))

    # ── Paginazione (in fondo) ──────────────────────────────────────────────
    nav_prev, nav_mid, nav_next = st.columns([1, 2, 1])
    if nav_prev.button("‹ Precedente", use_container_width=True,
                        key="_pg_prev", disabled=(page <= 1)):
        st.session_state["_card_page"] = page - 1
        _bump_sel_version()  # i checkbox della nuova pagina nascono col value giusto
        st.rerun()
    nav_mid.markdown(
        f"<div style='text-align:center; padding-top:8px; color:#4B5563; "
        f"font-size:0.88rem;'>Pagina <b>{page}</b> / {total_pages}</div>",
        unsafe_allow_html=True,
    )
    if nav_next.button("Successiva ›", use_container_width=True,
                        key="_pg_next", disabled=(page >= total_pages)):
        st.session_state["_card_page"] = page + 1
        _bump_sel_version()
        st.rerun()

# ============================================================
# selected_indices (contratto launch a valle): la selezione È GIÀ per
# indice-riga, quindi è l'intersezione col df corrente. df.loc[...] riceve
# ESATTAMENTE le righe spuntate (mai la gemella → Fix BLOCCANTE).
# ============================================================
selected_indices = [i for i in df.index if i in selected_row_ids]

# ============================================================
# CONFIGURAZIONE — sempre visibile (qualità, settore, target, riscrittura)
# ============================================================
st.markdown("### ⚙️ Configurazione enrichment")
st.caption("Scelte che impattano costo e qualità output.")

# Solo modelli Anthropic: enrich_product chiama sempre l'API Anthropic, i
# modelli OpenAI generavano solo errori.
_ALL_MODELS = [
    "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001",
    "claude-haiku-3-5",
]
# 3 livelli di qualità → model-id risolto. Il contratto launch/enrich_dataframe
# riceve sempre il model-id stringa, non il livello (vedi `model` più sotto).
_QUALITY_LEVELS = {
    "Economico": "claude-haiku-4-5-20251001",
    "Bilanciato": "claude-sonnet-4-6",
    "Massima qualità": "claude-opus-4-6",
}
_QUALITY_COST = {"Economico": "$", "Bilanciato": "$$", "Massima qualità": "$$$"}

cfg1, cfg2, cfg3 = st.columns(3)
with cfg1:
    quality = st.segmented_control(
        "🎚️ Livello qualità", list(_QUALITY_LEVELS.keys()),
        default="Bilanciato",
        help="Economico = Haiku 4.5 ($). Bilanciato = Sonnet 4.6 ($$, sweet spot). "
             "Massima qualità = Opus 4.6 ($$$).",
    )
    if quality is None:  # segmented_control può tornare None se deselezionato
        quality = "Bilanciato"
    st.caption(f"Costo relativo: **{_QUALITY_COST[quality]}**")
# Settore ereditato dal feed attivo (2d.1): default = sector salvato nel
# feed.json. Feed legacy senza campo sector → fallback "(generico)".
sectors = ["(generico)", "✨ auto (multi-settore)"] + list_sectors()
_active_c0, _active_f0 = state.get_active()
_feed_sector = ""
if _active_c0 and _active_f0:
    _feed_sector = (_cs.get_feed(_active_c0, _active_f0) or {}).get("sector", "") or ""
if not _feed_sector:
    _default_sec_idx = 0  # "(generico)"
elif _feed_sector == "auto":
    _default_sec_idx = 1  # "✨ auto (multi-settore)"
elif _feed_sector in sectors:
    _default_sec_idx = sectors.index(_feed_sector)
else:
    _default_sec_idx = 0
sector_choice = cfg2.selectbox(
    "📚 Settore best practice", sectors, index=_default_sec_idx,
    help="Default ereditato dal feed attivo. Applica regole settoriali dal YAML "
         "(formula titolo, tono, parole vietate). 'auto' = detecta per-prodotto.",
)
sector = "" if sector_choice == "(generico)" else \
         ("auto" if sector_choice.startswith("✨ auto") else sector_choice)
# Salva l'override come settore del feed (persistito via update_feed).
if _active_c0 and _active_f0 and sector != _feed_sector:
    if cfg2.button("💾 Salva come settore del feed", key="_save_sector_feed",
                    use_container_width=True):
        _cs.update_feed(_active_c0, _active_f0, sector=sector)
        st.toast("Settore del feed aggiornato", icon="📚")
        st.rerun()
target_choice = cfg3.radio(
    "🎯 Target", options=["both", "google", "meta"],
    format_func=lambda v: {"both": "🛒📘 Entrambi",
                             "google": "🛒 Solo Google",
                             "meta": "📘 Solo Meta"}[v],
    horizontal=True,
    help="Scegli se arricchire anche i campi Meta-only (risparmio ~15% se solo Google).",
)

# Riscrittura title/description — scelta esplicita visibile (2d.3). Gli
# originali restano sempre salvati in title_original/description_original.
_OW_REWRITE = "Riscrivi titoli e descrizioni"
_OW_KEEP = "Mantieni testi esistenti, riempi solo i campi mancanti"
overwrite_choice = st.radio(
    "✍️ Testi prodotto", options=[_OW_REWRITE, _OW_KEEP], index=0,
    help="'Riscrivi' rigenera titolo+descrizione (originali ripristinabili). "
         "'Mantieni' tocca solo i campi vuoti.",
)
overwrite = overwrite_choice == _OW_REWRITE

# Avanzate (parallelismo, cache, style guide, override modello) — in expander
with st.expander("⚙️ Opzioni avanzate", expanded=False):
    ac4, ac6, ac7 = st.columns(3)
    workers = ac4.slider("Parallelismo", 1, 15, 5,
                          help="Chiamate API simultanee. 5 = sweet spot.")
    use_cache = ac6.checkbox("Usa cache hash", value=True,
                               help="Riusa enrichment invariato (hash contenuto prodotto).")
    # Override power-user: se impostato vince sul livello qualità (2d.2).
    _model_override = ac7.selectbox(
        "Modello specifico (override)", ["(usa livello)"] + _ALL_MODELS,
        index=0,
        help="Per power-user: forza un model-id preciso, ignorando il livello qualità.",
    )

    from utils import catalog_style
    _style_ns = f"session_{st.session_state.get('session_id', 'default')}"
    existing_guide = catalog_style.load_guide(_style_ns)
    sg1, sg2 = st.columns([2, 1])
    use_style_guide = sg1.checkbox(
        "🧭 Style guide catalogo (coerenza cross-prodotto)",
        value=bool(existing_guide),
        help="Analizza campione → estrae formula/tono/vocabolario. ~€0.01 una volta.",
    )
    style_guide_text = ""
    if use_style_guide:
        if sg2.button("Genera / rigenera", use_container_width=True,
                        disabled=not st.session_state.get("api_key")):
            with st.spinner("Analisi campione..."):
                new_g = catalog_style.analyze_catalog(df, st.session_state["api_key"], sample_size=12)
            if new_g and "_error" not in new_g:
                catalog_style.save_guide(_style_ns, new_g)
                st.toast("Style guide generato", icon="🧭")
                st.rerun()
            else:
                st.error(f"Errore: {new_g.get('_error', '?')}")
        if existing_guide:
            style_guide_text = catalog_style.format_for_prompt(existing_guide)
            st.caption(f"Guide attivo · ~{len(style_guide_text)//3} token")

    if sector and sector != "auto":
        with st.expander(f"📚 Best practice {sector}"):
            s = load_sector(sector)
            if s.get("title", {}).get("formula"):
                st.markdown(f"**Formula titolo**: `{s['title']['formula']}`")
            if forb := s.get("title", {}).get("forbidden_words"):
                st.markdown(f"**Vietate**: {', '.join(forb)}")

# Risoluzione finale del modello (2d.2): l'override power-user vince sul
# livello qualità; il contratto a valle riceve sempre il model-id stringa.
if _model_override != "(usa livello)":
    model = _model_override
else:
    model = _QUALITY_LEVELS[quality]

# ============================================================
# CACHE + STIMA COSTO
# ============================================================
n_selected = len(selected_indices)
cached_rows: dict = {}
n_hit = 0
n_miss = n_selected
_cache_ns = _cache_namespace()
_style_extra = _style_guide_hash(style_guide_text)
if n_selected > 0 and use_cache:
    try:
        cached_rows, _ = enrich_cache.get_cached(
            df.loc[selected_indices], namespace=_cache_ns,
            model=model, sector=sector, provider="anthropic",
            target=target_choice, extra=_style_extra,
        )
        n_hit = len(cached_rows)
        n_miss = n_selected - n_hit
    except Exception:
        pass

if n_selected > 0:
    pc1, pc2, pc3 = st.columns(3)
    pc1.metric("Selezionati", n_selected)
    pc2.metric("🔵 Cache hit (gratis)", n_hit)
    pc3.metric("🟢 Da processare AI", n_miss)
    cost_estimate_card(n_miss, model)
    with st.expander(f"💰 Confronta tutti i modelli su {n_miss:,} prodotti"):
        cost_projection_table(n_miss)

# ============================================================
# LAUNCH
# ============================================================
st.divider()
lc1, lc2 = st.columns([4, 1])
launch = lc1.button(
    f"🚀 Avvia enrichment su {n_selected:,} prodotti",
    type="primary", use_container_width=True,
    disabled=(n_selected == 0),
)
if lc2.button("🧹 Pulisci cache", use_container_width=True,
                help="Rimuove i risultati cached del cliente attivo — forza re-enrichment."):
    enrich_cache.clear(_cache_ns)
    st.toast("Cache pulita", icon="🧹")
    st.rerun()

# Conferma dinamica dell'effetto sui testi prodotto (2d.3).
if n_selected > 0:
    if overwrite:
        st.caption(f"Riscriverà titolo + descrizione di {n_selected:,} prodotti "
                    "(originali ripristinabili).")
    else:
        st.caption("Manterrà i testi esistenti, popolerà solo i campi vuoti.")

if launch:
    with guarded("enrichment AI"):
        selected_df = df.loc[selected_indices].copy()

        with LoadingProgress("Enrichment AI in corso", total=n_miss or n_selected) as lp:
            def cb(d, t):
                lp.update(d, subtitle=f"{d}/{t} prodotti processati")
            enriched_subset = enrich_dataframe(
                selected_df, api_key=st.session_state["api_key"], model=model,
                max_workers=workers, limit=None, progress_callback=cb,
                sector=sector, overwrite_title_description=overwrite,
                max_tokens=int(st.session_state.get("config", {}).get("max_tokens", 3500)),
                style_guide_text=style_guide_text,
                skip_already_enriched=False,
                target=target_choice,
            )

        if use_cache and "_enrichment_status" in enriched_subset.columns:
            try:
                good = enriched_subset[enriched_subset["_enrichment_status"] == "ok"]
                pairs = []
                for idx, row in good.iterrows():
                    src = selected_df.loc[idx].to_dict() if idx in selected_df.index else row.to_dict()
                    result = {k: row.get(k) for k in row.index
                              if k not in ("_enrichment_status",) and pd.notna(row.get(k))}
                    pairs.append((src, result))
                enrich_cache.store(pairs, namespace=_cache_ns,
                                     model=model, sector=sector, provider="anthropic",
                                     target=target_choice, extra=_style_extra)
            except Exception:
                pass

        if cached_rows:
            for idx, result in cached_rows.items():
                if idx in enriched_subset.index:
                    for k, v in (result or {}).items():
                        if v is not None:
                            enriched_subset.at[idx, k] = v
                    enriched_subset.at[idx, "_enrichment_status"] = "cached"

        # Merge subset nel df principale (vista immediata in sessione).
        # NB: per la persistenza usiamo clients.merge_enriched (upsert per
        # _product_key); qui il merge per indice serve solo alla vista corrente
        # perché selected_df/enriched_subset condividono l'indice di df.
        for col in enriched_subset.columns:
            if col not in df.columns:
                df[col] = ""
            df.loc[enriched_subset.index, col] = enriched_subset[col]

        # Hook client integration: enriched.parquet è la fonte di verità.
        # merge_enriched fa UPSERT per _product_key (non perde gli altri
        # prodotti, non si rompe al reload parquet). remove_pending toglie
        # dalla coda SOLO i prodotti effettivamente arricchiti in questo run.
        client_slug, feed_slug = state.get_active()
        if client_slug and feed_slug:
            try:
                from utils import clients as _cs
                from utils import feed_diff as _fd
                strat = (_cs.get_feed(client_slug, feed_slug) or {}).get("id_strategy", "hierarchical")
                merged = _cs.merge_enriched(client_slug, feed_slug, enriched_subset, strategy=strat)
                df = merged
                # P1.3: rimuovi dalla coda solo le key dei prodotti ok/cached
                done = enriched_subset[enriched_subset.get(
                    "_enrichment_status", pd.Series(dtype=str)
                ).astype(str).str.strip().str.lower().isin(["ok", "cached"])]
                done_keys = [_fd.product_key(r.to_dict(), strategy=strat)
                              for _, r in done.iterrows()]
                _cs.remove_pending(client_slug, feed_slug, done_keys)
            except Exception:
                pass

        st.session_state["feed_df"] = df
        st.session_state["enriched_df"] = df
        st.session_state["merged_df"] = None

        st.success(f"✅ Completato · {n_hit} da cache, {n_miss} elaborati AI")
        st.rerun()

st.divider()

enriched = st.session_state.get("enriched_df")
if enriched is None:
    st.stop()

# ============================================================
# RISULTATI — minimalista con CTA verso Refine e Catalog Optimizer
# ============================================================
ok = int((enriched.get("_enrichment_status", pd.Series()).astype(str) == "ok").sum())
cached_n = int((enriched.get("_enrichment_status", pd.Series()).astype(str) == "cached").sum())
errors = int(enriched.get("_enrichment_status", pd.Series()).astype(str).str.startswith("error").sum())
empty_n = int(len(enriched) - ok - cached_n - errors)

if ok + cached_n == 0:
    st.info("Nessun prodotto arricchito ancora. Seleziona e clicca **🚀 Avvia enrichment** sopra.")
    st.stop()

st.subheader("✅ Risultati enrichment")
rm1, rm2, rm3, rm4 = st.columns(4)
rm1.metric("🟢 OK", ok)
rm2.metric("🔵 Da cache", cached_n)
rm3.metric("🔴 Errori", errors)
rm4.metric("⚪ Vuoti/pending", empty_n)

st.markdown("### Prossimi passi")
ncs = st.columns(2)
with ncs[0]:
    st.markdown(
        "<div style='background:linear-gradient(135deg, #8B5CF6 0%, #6D28D9 100%); "
        "border-radius:14px; padding:20px; color:#fff; height:100%;'>"
        "<div style='font-weight:700; font-size:1rem; margin-bottom:6px;'>"
        "✨ Refine & Chat</div>"
        "<div style='font-size:0.85rem; opacity:0.9;'>"
        "Affina titoli/descrizioni con istruzioni custom su sottoinsiemi. "
        "Diff prima/dopo. Chat con Claude sul catalogo."
        "</div></div>",
        unsafe_allow_html=True,
    )
    if st.button("Apri Refine & Chat →", type="primary", use_container_width=True,
                  key="_go_refine"):
        st.switch_page("client_pages/refine_chat.py")

with ncs[1]:
    st.markdown(
        "<div style='background:linear-gradient(135deg, #2F6FED 0%, #1A4BB5 100%); "
        "border-radius:14px; padding:20px; color:#fff; height:100%;'>"
        "<div style='font-weight:700; font-size:1rem; margin-bottom:6px;'>"
        "📥 Catalog Optimizer</div>"
        "<div style='font-size:0.85rem; opacity:0.9;'>"
        "Scarica feed GMC-ready + Meta Commerce. Validazione, quality check, "
        "delta sync, bundle ZIP completo."
        "</div></div>",
        unsafe_allow_html=True,
    )
    if st.button("Apri Catalog Optimizer →", type="primary", use_container_width=True,
                  key="_go_catalog"):
        st.switch_page("client_pages/scarica_catalogo.py")
