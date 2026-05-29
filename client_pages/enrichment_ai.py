"""Enrichment AI — selezione + lancio. Refinement/chat → client_pages/refine_chat.py."""
import streamlit as st
import pandas as pd

from utils.state import init_state
from utils.ui import (
    apply_theme, api_key_banner, empty_state, guarded,
    cost_estimate_card, cost_projection_table, LoadingProgress,
)
from utils.enrichment import enrich_dataframe, list_sectors, load_sector
from utils import cache as enrich_cache
from utils import clients as _cs

init_state()
apply_theme()
api_key_banner()

st.title("Enrichment AI")
st.caption("Classificazione Google Taxonomy + estrazione attributi + riscrittura titoli/descrizioni · Chat con Claude per affinare")

# ============================================================
# CLIENT + FEED SELECTOR — banner in alto.
# Permette di scegliere cliente/feed attivo e caricarne snapshot
# (preferendo enriched.parquet se esiste).
# ============================================================
_all_clients = _cs.list_clients()


def _load_feed_from_client(client_slug: str, feed_slug: str) -> tuple[pd.DataFrame | None, str]:
    """Carica feed attivo. Preferisce enriched.parquet, fallback snapshot più recente."""
    enr = _cs.load_enriched(client_slug, feed_slug)
    if enr is not None and not enr.empty:
        return enr, "enriched"
    snap = _cs.get_latest_snapshot(client_slug, feed_slug)
    if snap is not None and not snap.empty:
        return snap, "snapshot"
    return None, ""


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

        # default: active client in session, or most-recent
        default_client = st.session_state.get("_active_client_choice") or _client_slugs[0]
        if default_client not in _client_slugs:
            default_client = _client_slugs[0]

        sel1, sel2, sel3 = st.columns([2, 2, 1.2])
        chosen_client = sel1.selectbox(
            "Cliente",
            options=_client_slugs,
            index=_client_slugs.index(default_client),
            format_func=lambda s: _slug_to_name.get(s, s),
            key="_active_client_choice",
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
            # default: sessione o primo
            default_feed = st.session_state.get("_active_feed_choice") or _feed_slugs[0]
            if default_feed not in _feed_slugs:
                default_feed = _feed_slugs[0]

            chosen_feed = sel2.selectbox(
                "Feed",
                options=_feed_slugs,
                index=_feed_slugs.index(default_feed),
                format_func=lambda s: _feed_slug_to_name.get(s, s),
                key="_active_feed_choice",
            )

            # Info feed selezionato
            _fmeta = next((f for f in _feeds if f["slug"] == chosen_feed), {})
            _enr_preview = _cs.load_enriched(chosen_client, chosen_feed)
            _snap_count = _fmeta.get("n_snapshots", 0)
            _pending_count = _fmeta.get("n_pending", 0)
            _has_enriched = _enr_preview is not None and not _enr_preview.empty
            _n_rows_available = len(_enr_preview) if _has_enriched else (
                len(_cs.get_latest_snapshot(chosen_client, chosen_feed) or [])
            )

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

            # stato attuale vs selezionato
            _current_bound = (
                st.session_state.get("_enrich_client_slug") == chosen_client
                and st.session_state.get("_enrich_feed_slug") == chosen_feed
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
                    st.session_state["feed_df"] = loaded_df
                    st.session_state["enriched_df"] = loaded_df.copy()
                    st.session_state["merged_df"] = None
                    st.session_state["_enrich_client_slug"] = chosen_client
                    st.session_state["_enrich_feed_slug"] = chosen_feed
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
                    "Puoi caricare un URL/file o usare il dataset demo.",
        cta_label="Vai a Upload Feed →",
        cta_page="client_pages/upload_feed.py",
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
    "Usa i filtri per restringere, poi spunta i prodotti. "
    "La configurazione AI è sotto la tabella."
)

# ============================================================
# FILTRI
# ============================================================
fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 2])
search = fc1.text_input("🔎 Cerca title/brand/id", placeholder="es. Nike, T-shirt, ABC123",
                         key="_enrich_search")
brand_options = sorted(df["brand"].dropna().astype(str).unique().tolist()) \
                 if "brand" in df.columns else []
brand_filter = fc2.multiselect("Brand", options=brand_options, default=[],
                                 key="_enrich_brand_filter")
cat_col = "google_product_category" if "google_product_category" in df.columns \
          else ("product_type" if "product_type" in df.columns else None)
cat_options = sorted(df[cat_col].dropna().astype(str).unique().tolist()) if cat_col else []
cat_filter = fc3.multiselect("Categoria" if cat_col else "Categoria (non disp.)",
                              options=cat_options, default=[], key="_enrich_cat_filter",
                              disabled=not cat_col)
status_choice = fc4.selectbox("Status enrichment",
                               options=["Tutti", "Solo non arricchiti", "Solo arricchiti", "Solo errori"],
                               index=0, key="_enrich_status_filter")

mask = pd.Series([True] * len(df), index=df.index)
if search:
    s = search.lower()
    search_cols = [c for c in ("title", "brand", "id", "product_type") if c in df.columns]
    text_mask = pd.Series([False] * len(df), index=df.index)
    for c in search_cols:
        text_mask |= df[c].astype(str).str.lower().str.contains(s, na=False)
    mask &= text_mask
if brand_filter and "brand" in df.columns:
    mask &= df["brand"].astype(str).isin(brand_filter)
if cat_filter and cat_col:
    mask &= df[cat_col].astype(str).isin(cat_filter)
if status_choice == "Solo non arricchiti":
    mask &= ~_status_lower.isin(["ok", "cached"])
elif status_choice == "Solo arricchiti":
    mask &= _status_lower.isin(["ok", "cached"])
elif status_choice == "Solo errori":
    mask &= _status_lower.str.startswith("error")

filtered = df[mask].copy()

# ============================================================
# TABELLA SELEZIONE (checkbox + badge status)
# ============================================================
selected_indices: list = []
if filtered.empty:
    st.info("Nessun prodotto corrisponde ai filtri.")
else:
    def _badge(s):
        s = str(s).strip().lower()
        return {"ok": "🟢 OK", "cached": "🔵 Cache", "reverted": "↶ Undo"}.get(s,
               "🔴 Errore" if s.startswith("error") else
               "🟡 Vuoto" if s.startswith("empty") else "⚪ —")

    # Vista toggle: compatta (essenziale) vs estesa (TUTTI i campi GMC popolati)
    view_mode = st.radio(
        "Vista tabella",
        options=["Compatta", "Estesa (tutti gli attributi GMC)",
                  "Solo Google", "Solo Meta"],
        index=0, horizontal=True, key="_view_mode",
        label_visibility="collapsed",
        help="Compatta = 5 colonne base · Estesa = tutti i campi GMC popolati · "
             "Solo Google / Solo Meta = colonne specifiche per piattaforma",
    )

    from utils.catalog_optimizer import GOOGLE_FIELDS as _GFL, META_FIELDS as _MFL

    if view_mode == "Compatta":
        display_cols = [c for c in ("id", "title", "brand", "price", "_enrichment_status")
                         if c in filtered.columns]
    elif view_mode == "Estesa (tutti gli attributi GMC)":
        order = [t for t, _, _, _ in _GFL] + \
                [t for t, _, _ in _MFL if t not in {x for x, _, _, _ in _GFL}]
        # Tieni _enrichment_status alla fine per badge
        display_cols = ["id"] + [c for c in order if c != "id" and c in filtered.columns]
        # Filtra colonne totalmente vuote per non rumorose
        display_cols = [c for c in display_cols
                         if c in ("id", "_enrichment_status") or
                         filtered[c].astype(str).str.strip().replace({"nan": "", "None": ""}).ne("").any()]
        display_cols.append("_enrichment_status") if "_enrichment_status" in filtered.columns and "_enrichment_status" not in display_cols else None
    elif view_mode == "Solo Google":
        order = [t for t, _, _, _ in _GFL]
        display_cols = [c for c in order if c in filtered.columns]
        display_cols = [c for c in display_cols
                         if c == "id" or
                         filtered[c].astype(str).str.strip().replace({"nan": "", "None": ""}).ne("").any()]
        if "_enrichment_status" in filtered.columns:
            display_cols.append("_enrichment_status")
    else:  # Solo Meta
        order = [t for t, _, _ in _MFL]
        display_cols = [c for c in order if c in filtered.columns]
        display_cols = [c for c in display_cols
                         if c == "id" or
                         filtered[c].astype(str).str.strip().replace({"nan": "", "None": ""}).ne("").any()]
        if "_enrichment_status" in filtered.columns:
            display_cols.append("_enrichment_status")

    display_df = filtered[display_cols].copy()
    # Stato pinned vicino a checkbox (prima colonna dopo Seleziona)
    if "_enrichment_status" in display_df.columns:
        stato_series = display_df["_enrichment_status"].apply(_badge)
        display_df.drop(columns=["_enrichment_status"], inplace=True)
    else:
        stato_series = pd.Series(["⚪ —"] * len(display_df), index=display_df.index)
    display_df.insert(0, "Stato", stato_series)
    display_df.insert(0, "✔ Seleziona", False)

    # Quick action buttons
    sc1, sc2, sc3, sc4, sc5 = st.columns([1.4, 1.4, 1.4, 1.6, 2.2])
    if sc1.button(f"✔ Tutti visibili ({len(filtered):,})",
                    use_container_width=True, key="_sel_all_visible"):
        st.session_state["_force_sel"] = filtered.index.tolist()
    if sc2.button("🟢 Non arricchiti visibili", use_container_width=True, key="_sel_unenr"):
        un_idx = filtered[~filtered["_enrichment_status"].astype(str).str.strip().str.lower()
                          .isin(["ok", "cached"])].index.tolist()
        st.session_state["_force_sel"] = un_idx
    if sc3.button("☐ Deseleziona tutti", use_container_width=True, key="_sel_none"):
        st.session_state["_force_sel"] = []

    # Seleziona primi N visibili (per batch rapido)
    with sc4:
        n_quick = st.number_input("Primi N", min_value=1, max_value=max(len(filtered), 1),
                                    value=min(50, len(filtered)), step=10, key="_sel_n",
                                    label_visibility="collapsed")
    if sc5.button(f"⚡ Seleziona primi {int(n_quick):,} visibili",
                    use_container_width=True, key="_sel_first_n"):
        st.session_state["_force_sel"] = filtered.index[:int(n_quick)].tolist()

    forced = st.session_state.get("_force_sel")
    if forced is not None:
        display_df["✔ Seleziona"] = display_df.index.isin(forced)
        st.session_state["_force_sel"] = None

    _col_cfg_table = {
        "✔ Seleziona": st.column_config.CheckboxColumn(width="small", pinned=True),
        "id":          st.column_config.TextColumn(width="medium"),
        "title":       st.column_config.TextColumn(width="large"),
        "description": st.column_config.TextColumn(width="large"),
        "brand":       st.column_config.TextColumn(width="small"),
        "price":       st.column_config.TextColumn(width="small"),
        "product_highlight":       st.column_config.TextColumn(width="large"),
        "product_detail":          st.column_config.TextColumn(width="large"),
        "google_product_category": st.column_config.TextColumn(width="medium"),
        "product_type":            st.column_config.TextColumn(width="medium"),
        "title_meta":              st.column_config.TextColumn(width="large"),
        "short_description":       st.column_config.TextColumn(width="medium"),
        "rich_text_description":   st.column_config.TextColumn(width="large"),
        "Stato": st.column_config.TextColumn(width="small", pinned=True,
                    help="🟢 OK · 🔵 Cache · 🔴 Errore · 🟡 Vuoto · ⚪ non arricchito"),
    }
    _height = 480 if view_mode != "Compatta" else 380
    edited = st.data_editor(
        display_df,
        use_container_width=True, height=_height, hide_index=True,
        column_config=_col_cfg_table,
        disabled=[c for c in display_df.columns if c != "✔ Seleziona"],
        key=f"_edit_selection_{view_mode}",
    )
    selected_indices = edited.index[edited["✔ Seleziona"]].tolist()

    if view_mode != "Compatta":
        st.caption(f"_Mostrate **{len(display_cols) - 1}** colonne attributi "
                    f"(solo popolate). Scrolla orizzontalmente per vederle tutte._")

    st.markdown(
        f"<div style='background:#EEF4FF; border:1px solid #DCE7FE; border-radius:10px; "
        f"padding:10px 14px; font-weight:600; color:#2F6FED; text-align:center; margin:8px 0;'>"
        f"✨ {len(selected_indices):,} selezionati · {len(filtered):,} visibili · {n_total:,} totali"
        f"</div>",
        unsafe_allow_html=True,
    )

# ============================================================
# CONFIGURAZIONE — sempre visibile (modello, settore, target)
# ============================================================
st.markdown("### ⚙️ Configurazione enrichment")
st.caption("Scelte che impattano costo e qualità output.")

cfg1, cfg2, cfg3 = st.columns(3)
_ALL_MODELS = [
    "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001",
    "claude-haiku-3-5", "gpt-5", "gpt-5-mini", "gpt-5-nano",
    "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini",
    "o3", "o3-mini", "o4-mini",
]
model = cfg1.selectbox(
    "🤖 Modello AI", _ALL_MODELS,
    index=_ALL_MODELS.index("claude-sonnet-4-6"),
    help="Sonnet 4.6 = sweet spot (€3-15/M tok). Haiku 4.5 / gpt-4.1-nano = economici.",
)
sectors = ["(generico)", "✨ auto (multi-settore)"] + list_sectors()
default_idx = sectors.index("abbigliamento") if "abbigliamento" in sectors else 0
sector_choice = cfg2.selectbox(
    "📚 Settore best practice", sectors, index=default_idx,
    help="Applica regole settoriali dal YAML (formula titolo, tono, parole vietate). "
         "'auto' = detecta per-prodotto.",
)
sector = "" if sector_choice == "(generico)" else \
         ("auto" if sector_choice.startswith("✨ auto") else sector_choice)
target_choice = cfg3.radio(
    "🎯 Target", options=["both", "google", "meta"],
    format_func=lambda v: {"both": "🛒📘 Entrambi",
                             "google": "🛒 Solo Google",
                             "meta": "📘 Solo Meta"}[v],
    horizontal=True,
    help="Scegli se arricchire anche i campi Meta-only (risparmio ~15% se solo Google).",
)

# Avanzate (parallelismo, cache, style guide) — in expander
with st.expander("⚙️ Opzioni avanzate", expanded=False):
    ac4, ac5, ac6 = st.columns(3)
    workers = ac4.slider("Parallelismo", 1, 15, 5,
                          help="Chiamate API simultanee. 5 = sweet spot.")
    overwrite = ac5.checkbox("Sovrascrivi title/description", value=True,
                              help="Originali salvati in title_original/description_original.")
    use_cache = ac6.checkbox("Usa cache hash", value=True,
                               help="Riusa enrichment invariato (hash contenuto prodotto).")

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

# ============================================================
# CACHE + STIMA COSTO
# ============================================================
n_selected = len(selected_indices)
cached_rows: dict = {}
n_hit = 0
n_miss = n_selected
if n_selected > 0 and use_cache:
    try:
        cached_rows, _ = enrich_cache.get_cached(
            df.loc[selected_indices], namespace="shared_v1",
            model=model, sector=sector, provider="anthropic",
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
                help="Rimuove tutti i risultati cached — forza re-enrichment."):
    enrich_cache.clear("shared_v1")
    st.toast("Cache pulita", icon="🧹")
    st.rerun()

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
                enrich_cache.store(pairs, namespace="shared_v1",
                                     model=model, sector=sector, provider="anthropic")
            except Exception:
                pass

        if cached_rows:
            for idx, result in cached_rows.items():
                if idx in enriched_subset.index:
                    for k, v in (result or {}).items():
                        if v is not None:
                            enriched_subset.at[idx, k] = v
                    enriched_subset.at[idx, "_enrichment_status"] = "cached"

        # Merge subset nel df principale
        for col in enriched_subset.columns:
            if col not in df.columns:
                df[col] = ""
            df.loc[enriched_subset.index, col] = enriched_subset[col]

        st.session_state["feed_df"] = df
        st.session_state["enriched_df"] = df
        st.session_state["merged_df"] = None
        from utils.history import save_snapshot
        save_snapshot(st.session_state["session_id"], st.session_state)

        # Hook client integration
        client_slug = st.session_state.get("_enrich_client_slug")
        feed_slug = st.session_state.get("_enrich_feed_slug")
        if client_slug and feed_slug:
            try:
                from utils import clients as _cs
                from utils import feed_diff as _fd
                strat = (_cs.get_feed(client_slug, feed_slug) or {}).get("id_strategy", "hierarchical")
                enriched_keys = [_fd.product_key(r.to_dict(), strategy=strat)
                                  for _, r in df.iterrows()]
                _cs.remove_pending(client_slug, feed_slug, enriched_keys)
                _cs.save_enriched(client_slug, feed_slug, df)
            except Exception:
                pass

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
