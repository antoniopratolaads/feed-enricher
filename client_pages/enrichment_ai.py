"""Pagina 4: Enrichment AI via Claude (taxonomy + attributi + titoli) + Chat refinement."""
import streamlit as st
import pandas as pd
from anthropic import Anthropic

from utils.state import init_state
from utils.ui import (
    apply_theme, api_key_banner, empty_state, guarded,
    cost_estimate_card, cost_projection_table, diff_view, LoadingProgress,
)
from utils.enrichment import (
    enrich_dataframe, refine_product, chat_about_data, DEFAULT_MODEL,
    list_sectors, load_sector,
)
from utils.exporter import to_excel_bytes
from utils import cache as enrich_cache

init_state()
apply_theme()
api_key_banner()

st.title("Enrichment AI")
st.caption("Classificazione Google Taxonomy + estrazione attributi + riscrittura titoli/descrizioni · Chat con Claude per affinare")

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
    "Le **Opzioni avanzate** in fondo controllano modello/settore/target."
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
    display_df.insert(0, "✔ Seleziona", False)
    if "_enrichment_status" in display_df.columns:
        display_df["Stato"] = display_df["_enrichment_status"].apply(_badge)
        display_df.drop(columns=["_enrichment_status"], inplace=True)

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
        "Stato": st.column_config.TextColumn(width="small",
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
# OPZIONI AVANZATE
# ============================================================
with st.expander("⚙️ Opzioni avanzate (modello, settore, target)", expanded=False):
    ac1, ac2, ac3 = st.columns(3)
    _ALL_MODELS = [
        "claude-opus-4-6", "claude-sonnet-4-6", "claude-haiku-4-5-20251001",
        "claude-haiku-3-5", "gpt-5", "gpt-5-mini", "gpt-5-nano",
        "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano", "gpt-4o", "gpt-4o-mini",
        "o3", "o3-mini", "o4-mini",
    ]
    model = ac1.selectbox("Modello AI", _ALL_MODELS,
                           index=_ALL_MODELS.index("claude-sonnet-4-6"),
                           help="Default Sonnet 4.6. Economia: Haiku / gpt-4.1-nano.")

    sectors = ["(generico)", "✨ auto (multi-settore)"] + list_sectors()
    default_idx = sectors.index("abbigliamento") if "abbigliamento" in sectors else 0
    sector_choice = ac2.selectbox("Settore best practice", sectors, index=default_idx)
    sector = "" if sector_choice == "(generico)" else \
             ("auto" if sector_choice.startswith("✨ auto") else sector_choice)

    target_choice = ac3.radio(
        "Target", options=["both", "google", "meta"],
        format_func=lambda v: {"both": "🛒📘 Entrambi",
                                 "google": "🛒 Solo Google",
                                 "meta": "📘 Solo Meta"}[v],
        horizontal=True,
    )

    ac4, ac5, ac6 = st.columns(3)
    workers = ac4.slider("Parallelismo", 1, 15, 5,
                          help="Chiamate API simultanee. 5 = sweet spot.")
    overwrite = ac5.checkbox("Sovrascrivi title/description", value=True,
                              help="Originali salvati in title_original/description_original.")
    use_cache = ac6.checkbox("Usa cache hash", value=True,
                               help="Riusa enrichment invariato (hash contenuto prodotto).")

    # Style guide
    from utils import catalog_style
    _style_ns = f"session_{st.session_state.get('session_id', 'default')}"
    existing_guide = catalog_style.load_guide(_style_ns)
    sg1, sg2 = st.columns([2, 1])
    use_style_guide = sg1.checkbox(
        "🧭 Style guide catalogo (coerenza cross-prodotto)",
        value=bool(existing_guide),
        help="Analizza campione catalogo → estrae formula titolo / tono / vocabolario. "
             "Iniettato in ogni prompt. ~€0.01 una volta.",
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
# RISULTATI
# ============================================================
st.divider()

# ============================================================
# AZIONI POST-ENRICHMENT (undo + diff preview toggle)
# ============================================================
ac1, ac2, ac3 = st.columns([1, 1, 2])
if ac1.button("↶ Undo enrichment",
              help="Ripristina title/description originali dalle colonne _original",
              use_container_width=True):
    with guarded("undo enrichment"):
        restored = enriched.copy()
        for src, dst in (("title_original", "title"), ("description_original", "description")):
            if src in restored.columns:
                mask = restored[src].notna() & restored[src].astype(str).ne("")
                restored.loc[mask, dst] = restored.loc[mask, src]
        restored["_enrichment_status"] = "reverted"
        st.session_state["enriched_df"] = restored
        st.toast("Ripristinati i valori originali", icon="↶")
        st.rerun()

show_diff = ac2.toggle("📊 Diff prima/dopo", value=False,
                       help="Mostra confronto side-by-side tra originale e versione AI")

st.subheader("Risultati")
ok = (enriched["_enrichment_status"] == "ok").sum()
cached_n = (enriched["_enrichment_status"] == "cached").sum()
errors = enriched["_enrichment_status"].astype(str).str.startswith("error").sum()
c1, c2, c3, c4 = st.columns(4)
c1.metric("OK", int(ok))
c2.metric("Da cache", int(cached_n))
c3.metric("Errori", int(errors))
c4.metric("Vuoti", len(enriched) - int(ok) - int(cached_n) - int(errors))

# ============================================================
# DOWNLOAD CATALOGO (in cima ai risultati - ben visibile)
# ============================================================
if int(ok) + int(cached_n) > 0:
    from utils.catalog_optimizer import build_google_feed as _bgf, build_meta_feed as _bmf
    st.markdown(
        "<div style='background:linear-gradient(135deg, #2F6FED 0%, #1A4BB5 100%); "
        "border-radius:14px; padding:16px 20px; color:#fff; margin:10px 0 14px;'>"
        "<div style='font-weight:700; font-size:1rem;'>📥 Scarica catalogo arricchito</div>"
        "<div style='font-size:0.85rem; opacity:0.9; margin-top:4px;'>"
        "TSV Google + CSV Meta pronti per upload diretto a Merchant Center / Commerce Manager."
        "</div></div>",
        unsafe_allow_html=True,
    )
    try:
        _dl_google = _bgf(enriched, currency="EUR")
        _dl_meta = _bmf(enriched, currency="EUR")
        dlc1, dlc2, dlc3 = st.columns(3)
        dlc1.download_button(
            "⬇️ TSV Google (GMC-ready)",
            _dl_google.to_csv(index=False, sep="\t").encode("utf-8"),
            file_name="google_feed.tsv", mime="text/tab-separated-values",
            use_container_width=True, type="primary",
        )
        dlc2.download_button(
            "⬇️ CSV Meta (Commerce-ready)",
            _dl_meta.to_csv(index=False).encode("utf-8"),
            file_name="meta_feed.csv", mime="text/csv",
            use_container_width=True, type="primary",
        )
        if dlc3.button("Vai a Catalog Optimizer →", use_container_width=True,
                        key="_go_catalog_opt",
                        help="Export avanzati: Excel, XML, validation report, delta diff, bundle ZIP"):
            st.switch_page("client_pages/scarica_catalogo.py")
    except Exception as _e:
        st.warning(f"Errore build feed: {_e}")

# Diff preview for first N products that were actually modified
if show_diff:
    st.markdown("#### Anteprima diff (primi 10 prodotti modificati)")
    if "title_original" not in enriched.columns:
        st.caption("_Nessuna colonna `title_original` — l'enrichment non ha sovrascritto i titoli._")
    else:
        diffed = enriched[
            enriched["title_original"].notna()
            & (enriched["title"].astype(str) != enriched["title_original"].astype(str))
        ].head(10)
        if diffed.empty:
            st.caption("_Nessun prodotto modificato in questo batch._")
        for _, row in diffed.iterrows():
            diff_view(
                f"{row.get('id', '?')} · {row.get('brand', '')}".strip(" ·"),
                row.get("title_original", ""),
                row.get("title", ""),
            )
    st.divider()

from utils.catalog_optimizer import GOOGLE_FIELDS, META_FIELDS

tabs = st.tabs(["🛒 Variante Google", "📘 Variante Meta", "🏷️ Tutti gli attributi"])

# Badge visivo per enrichment status — prima colonna nelle tab
def _status_badge(s: str) -> str:
    s = str(s).strip().lower()
    if s == "ok":
        return "🟢 OK"
    if s == "cached":
        return "🔵 Cache"
    if s == "reverted":
        return "↶ Undo"
    if s.startswith("error"):
        return "🔴 Errore"
    if s.startswith("empty"):
        return "🟡 Vuoto"
    return "⚪ —"

if "_enrichment_status" in enriched.columns:
    enriched = enriched.copy()
    enriched["✨ Stato"] = enriched["_enrichment_status"].apply(_status_badge)

# Lista completa campi GMC ufficiali (ordine spec) — badge come prima colonna
_google_order = ["✨ Stato", "id"] + [t for t, _, _, _ in GOOGLE_FIELDS if t != "id"]
google_cols = [c for c in _google_order if c in enriched.columns]
# Solo campi popolati per non mostrare colonne tutte vuote
google_cols = [c for c in google_cols
               if c in ("✨ Stato", "id") or
               enriched[c].astype(str).str.strip().replace({"nan": "", "None": ""}).ne("").any()]

# Lista completa campi Meta ufficiali — badge come prima colonna
_meta_order = ["✨ Stato", "id"] + [t for t, _, _ in META_FIELDS if t != "id"]
meta_cols = [c for c in _meta_order if c in enriched.columns]
meta_cols = [c for c in meta_cols
             if c in ("✨ Stato", "id") or
             enriched[c].astype(str).str.strip().replace({"nan": "", "None": ""}).ne("").any()]

# Tutti gli attributi (compresi Meta extras + meta-internal)
_all_order = ["✨ Stato", "id"] + [t for t, _, _, _ in GOOGLE_FIELDS if t != "id"] + \
             [t for t, _, _ in META_FIELDS if t not in {x for x, _, _, _ in GOOGLE_FIELDS}]
other_cols = [c for c in enriched.columns if c not in _all_order]
all_cols = [c for c in _all_order if c in enriched.columns] + other_cols
all_cols = [c for c in all_cols
            if c in ("✨ Stato", "id") or
            enriched[c].astype(str).str.strip().replace({"nan": "", "None": ""}).ne("").any()]

# Column config sharing
_col_cfg = {
    "✨ Stato":               st.column_config.TextColumn("Enrichment", width="small",
                                help="🟢 OK = processato ora · 🔵 Cache = da cache · "
                                     "↶ Undo = ripristinato · 🔴 Errore · 🟡 Vuoto · ⚪ non arricchito"),
    "title":                  st.column_config.TextColumn(width="large"),
    "description":            st.column_config.TextColumn(width="large"),
    "title_meta":             st.column_config.TextColumn("title_meta (Meta)", width="large"),
    "short_description":      st.column_config.TextColumn("short_description (Meta)", width="medium"),
    "rich_text_description":  st.column_config.TextColumn("rich_text_description (HTML)", width="large"),
    "product_highlight":      st.column_config.TextColumn(width="large"),
    "product_detail":         st.column_config.TextColumn(width="large"),
    "google_product_category": st.column_config.TextColumn(width="medium"),
    "product_type":           st.column_config.TextColumn(width="medium"),
}

with tabs[0]:
    st.caption(
        f"**{len(google_cols)-1}** campi GMC ufficiali popolati su {len([t for t,_,_,_ in GOOGLE_FIELDS])} disponibili. "
        "Limiti: title ≤150 char, description ≤5000, product_highlight bullet ≤150 ciascuno."
    )
    st.dataframe(
        enriched[google_cols].head(100),
        use_container_width=True, height=420,
        column_config=_col_cfg,
    )
    with st.expander("ℹ️ Legenda campi Google (spec ufficiale 2026)"):
        st.markdown(
            "- **Obbligatori**: id, title, description, link, image_link, availability, price, condition, brand, google_product_category\n"
            "- **Identità**: gtin, mpn, identifier_exists, item_group_id\n"
            "- **Apparel**: gender, age_group, color, size, size_type, size_system, material, pattern\n"
            "- **Bundle/multipack**: is_bundle, multipack\n"
            "- **Prezzo**: sale_price, unit_pricing_measure, unit_pricing_base_measure, installment, subscription_cost, loyalty_points\n"
            "- **Spedizione**: shipping_weight/length/width/height, shipping_label, ships_from_country, handling_time\n"
            "- **Energia**: energy_efficiency_class + min/max\n"
            "- **Highlights**: product_highlight (array ≤10 bullet), product_detail (structured section:name=value)\n"
            "- **Certification**: array [{authority, name, code}] (EPREL, FSC, Bio, ...)\n"
            "- **Media**: additional_image_link, lifestyle_image_link, video_link\n"
            "- **Destinazione/tasse**: included_destination, excluded_destination, tax_category, promotion_id\n"
            "- **Custom labels**: custom_label_0..4"
        )

with tabs[1]:
    st.caption(
        f"**{len(meta_cols)-1}** campi Meta Commerce ufficiali popolati su {len([t for t,_,_ in META_FIELDS])} disponibili. "
        "Limiti: title ≤200, description ≤9999, short_description ≤200."
    )
    st.dataframe(
        enriched[meta_cols].head(100),
        use_container_width=True, height=420,
        column_config=_col_cfg,
    )
    with st.expander("ℹ️ Legenda campi Meta Catalog"):
        st.markdown(
            "- **Obbligatori**: id, title, description, availability, condition, price, link, image_link, brand\n"
            "- **Meta-only**: title_meta (diventa 'title' nel feed), short_description, rich_text_description (HTML), fb_product_category, origin_country\n"
            "- **EU GPSR compliance**: manufacturer_info, manufacturer_part_number, importer_name, importer_address\n"
            "- **Commerce**: commerce_tax_category, status (active/archived/staging)\n"
            "- **Custom**: custom_label_0..4 + custom_number_0..4 (numeric per ranking)\n"
            "- **Media**: video [{tag, url}] strutturato multi-video"
        )

with tabs[2]:
    st.caption(f"Tutti i **{len(all_cols)-1}** attributi popolati (GMC + Meta + metadata interni).")
    st.dataframe(
        enriched[all_cols].head(100),
        use_container_width=True, height=420,
        column_config=_col_cfg,
    )

from utils.catalog_optimizer import build_google_feed, build_meta_feed

st.markdown("#### Download")
st.caption(
    "**TSV Google / CSV Meta** = pronti per upload diretto. "
    "**Raw** = dump completo per audit. Puoi escludere colonne specifiche prima dell'export."
)

# Build Google / Meta ready dataframes
try:
    _google_ready = build_google_feed(enriched, currency="EUR")
except Exception as _e:
    _google_ready = None
    st.warning(f"Errore Google feed: {_e}")
try:
    _meta_ready = build_meta_feed(enriched, currency="EUR")
except Exception as _e:
    _meta_ready = None
    st.warning(f"Errore Meta feed: {_e}")

# Column exclusion UI
with st.expander("🧹 Escludi colonne dall'export", expanded=False):
    ex_cols_g = st.multiselect(
        "Colonne da escludere dal TSV Google",
        options=list(_google_ready.columns) if _google_ready is not None else [],
        default=[],
        key="_excl_google",
    )
    ex_cols_m = st.multiselect(
        "Colonne da escludere dal CSV Meta",
        options=list(_meta_ready.columns) if _meta_ready is not None else [],
        default=[],
        key="_excl_meta",
    )
    ex_cols_raw = st.multiselect(
        "Colonne da escludere dal CSV raw",
        options=list(enriched.columns),
        default=[c for c in enriched.columns if c.startswith("_") or c.endswith("_original")],
        key="_excl_raw",
    )

dc1, dc2, dc3, dc4 = st.columns(4)

if _google_ready is not None:
    _gdf = _google_ready.drop(columns=ex_cols_g, errors="ignore")
    dc1.download_button(
        "⬇️ TSV Google (GMC-ready)",
        _gdf.to_csv(index=False, sep="\t").encode("utf-8"),
        file_name="google_feed.tsv",
        mime="text/tab-separated-values",
        use_container_width=True,
        help=f"{len(_gdf.columns)} colonne. Upload diretto su Google Merchant Center → Feed → Aggiungi → Carica TSV.",
    )

if _meta_ready is not None:
    _mdf = _meta_ready.drop(columns=ex_cols_m, errors="ignore")
    dc2.download_button(
        "⬇️ CSV Meta (Commerce-ready)",
        _mdf.to_csv(index=False).encode("utf-8"),
        file_name="meta_feed.csv",
        mime="text/csv",
        use_container_width=True,
        help=f"{len(_mdf.columns)} colonne. Upload diretto su Meta Commerce Manager → Cataloghi → Aggiungi prodotti → Da file di dati.",
    )

# Excel multi-foglio (no exclusion su Excel per semplicità)
dc3.download_button(
    "Excel arricchito",
    to_excel_bytes({"enriched": enriched}),
    "feed_enriched.xlsx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
    help="Excel con tutti i dati arricchiti (raw, per audit).",
)

# CSV raw con esclusione
_raw_df = enriched.drop(columns=ex_cols_raw, errors="ignore")
dc4.download_button(
    f"CSV raw ({len(_raw_df.columns)} col.)",
    _raw_df.to_csv(index=False).encode("utf-8"),
    "feed_enriched_raw.csv",
    "text/csv",
    use_container_width=True,
    help="Default: esclude colonne interne (_*) e originali (_original). Personalizzabile sopra.",
)

# ============================================================
# QUALITY — taxonomy suggestions + spell check
# ============================================================
with st.expander("🧭 Quality post-enrichment (taxonomy + spell check)", expanded=False):
    qc1, qc2 = st.columns(2)

    with qc1:
        st.markdown("**Taxonomy autocomplete**")
        st.caption("Suggerisce `google_product_category` via fuzzy match sulla tassonomia ufficiale Google.")
        if st.button("Suggerisci categorie mancanti", key="_tax_suggest"):
            from utils.taxonomy import suggest_bulk
            missing = enriched[
                enriched.get("google_product_category", "").astype(str).str.strip().eq("")
            ].head(30)
            if missing.empty:
                st.info("Tutti i prodotti hanno già `google_product_category`.")
            else:
                with st.spinner(f"Matching su {len(missing)} prodotti..."):
                    suggestions = suggest_bulk(
                        missing["title"].fillna("").astype(str),
                        missing.get("brand", "").fillna("").astype(str) if "brand" in missing.columns else [""] * len(missing),
                    )
                # Present table
                rows = []
                for (idx, row), sug in zip(missing.iterrows(), suggestions):
                    rows.append({
                        "id": row.get("id", ""),
                        "title": str(row.get("title", ""))[:60],
                        "suggerimento": sug["path"] if sug else "—",
                        "score": sug["score"] if sug else 0,
                        "_idx": idx,
                    })
                suggest_df = pd.DataFrame(rows)
                st.dataframe(suggest_df.drop(columns=["_idx"]),
                              use_container_width=True, height=320)

                if st.button("Applica suggerimenti (score ≥ 60)", key="_tax_apply"):
                    applied = 0
                    for r in rows:
                        if r["score"] >= 60 and r["suggerimento"] != "—":
                            enriched.at[r["_idx"], "google_product_category"] = r["suggerimento"]
                            applied += 1
                    st.session_state["enriched_df"] = enriched
                    st.success(f"Applicati {applied} suggerimenti.")
                    st.rerun()

    with qc2:
        st.markdown("**Spell check italiano**")
        st.caption("Flagga parole non riconosciute in `title` e `description` (possibili hallucinations).")
        if st.button("Esegui spell check (primi 500)", key="_spell_run"):
            from utils.spell_check import check_dataframe
            with st.spinner("Analizzo testi..."):
                issues = check_dataframe(enriched, cols=("title", "description"), limit=500)
            if not issues:
                st.success("Nessun errore rilevato (o dizionario IT non disponibile).")
            else:
                st.warning(f"{len(issues)} possibili errori trovati")
                df_issues = pd.DataFrame([{
                    "riga": i.row_idx,
                    "campo": i.column,
                    "parola": i.word,
                    "suggerimento": i.suggestion or "—",
                } for i in issues[:200]])
                st.dataframe(df_issues, use_container_width=True, height=320)
                if len(issues) > 200:
                    st.caption(f"_Mostrati primi 200 su {len(issues)} totali._")

# ============================================================
# REFINEMENT — applica istruzione custom a un sottoinsieme
# ============================================================
st.divider()
st.subheader("Affina i risultati con istruzioni custom")
st.caption("Selezioni un sottoinsieme e dai a Claude un'istruzione (es. *titoli più aggressivi per i prodotti zombie*).")

rc1, rc2, rc3 = st.columns([2, 2, 1])
brand_filter = rc1.multiselect("Filtra per brand",
                                options=sorted(enriched["brand"].dropna().unique()) if "brand" in enriched.columns else [])
status_filter = rc2.multiselect("Filtra per status",
                                 options=["ok", "empty", "error"], default=[])

mask = pd.Series([True] * len(enriched), index=enriched.index)
if brand_filter:
    mask &= enriched["brand"].isin(brand_filter)
if status_filter:
    mask &= enriched["_enrichment_status"].astype(str).isin(status_filter) | \
            enriched["_enrichment_status"].astype(str).str.startswith(tuple(status_filter))

selected = enriched[mask]
rc3.metric("Selezionati", len(selected))

instruction = st.text_area(
    "Istruzione per Claude",
    placeholder="Es: rendi i titoli più orientati al beneficio. Aggiungi parole chiave search-friendly. "
                "Massimo 100 caratteri. Mantieni il brand all'inizio.",
    height=80,
)

rcc1, rcc2 = st.columns([1, 4])
n_apply = rcc1.number_input("Max prodotti da aggiornare", 1, 500, min(20, len(selected)), 5,
                              help="Limita per controllare costo")
if rcc2.button("Applica refinement", type="primary", disabled=not instruction or not len(selected)):
    client = Anthropic(api_key=st.session_state["api_key"])
    progress = st.progress(0)
    target = selected.head(n_apply)
    updated = 0
    for i, (idx, row) in enumerate(target.iterrows()):
        result = refine_product(client, row.to_dict(), instruction, model=model)
        if result and "_error" not in result:
            for k in ("title", "description"):
                if result.get(k):
                    enriched.at[idx, k] = result[k]
            updated += 1
        progress.progress((i + 1) / len(target))
    st.session_state["enriched_df"] = enriched
    st.success(f"Aggiornati {updated}/{len(target)} prodotti")
    st.rerun()

# ============================================================
# CHAT CON CLAUDE
# ============================================================
st.divider()
st.subheader("💬 Chat con Claude sul tuo catalogo")
st.caption("Chiedi consigli, idee di refinement, analisi delle label. Il contesto del catalogo è già caricato.")

if "enrich_chat" not in st.session_state:
    st.session_state["enrich_chat"] = []

# pulsanti rapidi
sug1, sug2, sug3, sug4 = st.columns(4)
suggestions = {
    sug1: "Quali brand hanno i titoli più poveri da migliorare?",
    sug2: "Suggerisci 3 istruzioni di refinement per i prodotti senza vendite Shopify",
    sug3: "Come dovrei impostare le custom_label per massimizzare ROAS?",
    sug4: "Genera un'istruzione per riscrivere i titoli in stile premium",
}
for col, q in suggestions.items():
    if col.button(q, use_container_width=True, key=f"sug_{hash(q)}"):
        st.session_state["enrich_chat"].append({"role": "user", "content": q})
        st.rerun()

# render history
for msg in st.session_state["enrich_chat"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

prompt = st.chat_input("Scrivi un messaggio a Claude...")
if prompt:
    st.session_state["enrich_chat"].append({"role": "user", "content": prompt})
    st.rerun()

# se l'ultimo è user, rispondi
if st.session_state["enrich_chat"] and st.session_state["enrich_chat"][-1]["role"] == "user":
    with st.chat_message("assistant"):
        with st.spinner("Claude sta pensando..."):
            # build context summary
            ctx_lines = [f"Prodotti totali: {len(enriched)}"]
            if "brand" in enriched.columns:
                top_brands = enriched["brand"].value_counts().head(5).to_dict()
                ctx_lines.append(f"Top brand: {top_brands}")
            if "clicks" in enriched.columns:
                roas = enriched["conv_value"].sum() / enriched["cost"].sum() if enriched["cost"].sum() else 0
                ctx_lines.append(f"ROAS GAds: {roas:.2f}x · Spesa: €{enriched['cost'].sum():.0f}")
                zombie = ((enriched["clicks"] >= 30) & (enriched["conversions"] == 0)).sum()
                ctx_lines.append(f"Zombie: {zombie}")
            if "shopify_units_sold" in enriched.columns:
                no_sales = (enriched["shopify_units_sold"] == 0).sum()
                ctx_lines.append(f"Senza vendite Shopify: {no_sales}")
            if "title" in enriched.columns:
                avg_len = enriched["title"].astype(str).str.len().mean()
                ctx_lines.append(f"Lunghezza media title: {avg_len:.0f} char")
            ctx = "\n".join(ctx_lines)

            client = Anthropic(api_key=st.session_state["api_key"])
            reply = chat_about_data(client, st.session_state["enrich_chat"], ctx, model=model)
            st.markdown(reply)
            st.session_state["enrich_chat"].append({"role": "assistant", "content": reply})

cc1, cc2 = st.columns([1, 4])
if cc1.button("Pulisci chat", use_container_width=True):
    st.session_state["enrich_chat"] = []
    st.rerun()
