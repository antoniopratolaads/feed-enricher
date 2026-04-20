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

df = st.session_state["feed_df"]

# ============================================================
# CONFIG ENRICHMENT
# ============================================================
c1, c2, c3, c4 = st.columns(4)
_ALL_MODELS = [
    # Anthropic Claude
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-haiku-3-5",
    # OpenAI GPT-5
    "gpt-5",
    "gpt-5-mini",
    "gpt-5-nano",
    # OpenAI GPT-4.1
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    # OpenAI GPT-4o
    "gpt-4o",
    "gpt-4o-mini",
    # OpenAI reasoning
    "o3",
    "o3-mini",
    "o4-mini",
]
model = c1.selectbox(
    "Modello", _ALL_MODELS,
    index=_ALL_MODELS.index("claude-sonnet-4-6"),
    help="Sweet spot qualità/costo: claude-sonnet-4-6 o gpt-4.1-mini. "
         "Per risparmiare al massimo: claude-haiku-4-5, gpt-4.1-nano, gpt-5-nano.",
)

sectors = ["(generico)", "✨ auto (multi-settore)"] + list_sectors()
default_idx = sectors.index("abbigliamento") if "abbigliamento" in sectors else 0
sector_choice = c2.selectbox(
    "Settore (best practice)",
    sectors,
    index=default_idx,
    help=(
        "• (generico): prompt base, nessuna specializzazione\n"
        "• auto (multi-settore): il tool classifica ogni prodotto e applica le regole del suo settore\n"
        "• settore specifico: applica best practice YAML di quel settore a TUTTI i prodotti"
    ),
)
if sector_choice == "(generico)":
    sector = ""
elif sector_choice.startswith("✨ auto"):
    sector = "auto"
else:
    sector = sector_choice

limit = c3.number_input("Limite prodotti (0 = tutti)", min_value=0, value=min(50, len(df)), step=10)
workers = c4.slider("Parallelismo", 1, 15, 5)

overwrite = st.checkbox(
    "Sovrascrivi `title` e `description` con la versione AI (consigliato)",
    value=True,
    help="Gli originali vengono salvati in `title_original` / `description_original` come backup. "
         "Vengono anche popolati colore/taglia/materiale/brand se mancanti."
)

if sector == "auto":
    with st.expander("🔎 Anteprima classificazione automatica", expanded=True):
        from utils import sector_classifier
        preview_df = df.head(limit) if limit else df
        with st.spinner(f"Classifico {len(preview_df)} prodotti..."):
            summary = sector_classifier.summarize(preview_df)
        st.caption(
            "Ogni prodotto riceverà le regole del settore rilevato. "
            "I prodotti non classificati (nessun match) useranno il prompt generico."
        )
        st.dataframe(summary, use_container_width=True, height=min(40 + len(summary) * 38, 320),
                      column_config={
                          "_sector_detected": st.column_config.TextColumn("Settore rilevato", width="medium"),
                          "_sector_confidence": st.column_config.TextColumn("Confidence"),
                          "count": st.column_config.NumberColumn("Prodotti", width="small"),
                      })
        # Quick sample table
        full_detect = sector_classifier.classify_dataframe(preview_df.head(20))
        st.caption("**Esempio prime 20 righe:**")
        st.dataframe(
            full_detect[[c for c in ("id", "title", "_sector_detected", "_sector_confidence")
                         if c in full_detect.columns]].rename(columns={
                "_sector_detected": "settore",
                "_sector_confidence": "conf.",
            }),
            use_container_width=True, height=260,
        )

# ============================================================
# STYLE GUIDE — coerenza cross-prodotto (1 call Haiku upfront)
# ============================================================
from utils import catalog_style

_style_ns = f"session_{st.session_state.get('session_id', 'default')}"
existing_guide = catalog_style.load_guide(_style_ns)

sgc1, sgc2, sgc3 = st.columns([2, 2, 1])
use_style_guide = sgc1.checkbox(
    "🧭 Usa style guide catalogo (coerenza cross-prodotto)",
    value=bool(existing_guide),
    help=(
        "Analizza un campione del catalogo con Claude Haiku (~€0.01) ed estrae:\n"
        "- Formula titolo uniforme\n"
        "- Tono voce\n"
        "- Pattern tassonomia\n"
        "- Vocabolario preferito e vietato\n\n"
        "Lo style guide viene iniettato nel system prompt di OGNI enrichment "
        "successivo. Risultato: 100 prodotti con output coerente come da un "
        "singolo prompt, non isolati. La guide resta cachata — zero overhead per chiamata."
    ),
)
style_guide_text = ""
if use_style_guide:
    if sgc2.button("Genera / rigenera style guide", use_container_width=True,
                    disabled=not st.session_state.get("api_key")):
        with st.spinner("Analisi campione catalogo..."):
            new_guide = catalog_style.analyze_catalog(
                df, st.session_state["api_key"], sample_size=12
            )
        if new_guide and "_error" not in new_guide:
            catalog_style.save_guide(_style_ns, new_guide)
            existing_guide = new_guide
            st.toast("Style guide generato", icon="🧭")
            st.rerun()
        else:
            st.error(f"Errore generazione: {new_guide.get('_error', '?')}")
    if existing_guide:
        style_guide_text = catalog_style.format_for_prompt(existing_guide)
        sgc3.metric("Token guide", len(style_guide_text) // 3)
        with st.expander("Anteprima style guide"):
            st.json(existing_guide)

if sector and sector != "auto":
    with st.expander(f"📚 Best practice attive: {sector}"):
        s = load_sector(sector)
        if s.get("title", {}).get("formula"):
            st.markdown(f"**Formula titolo**: `{s['title']['formula']}`")
        if examples := s.get("title", {}).get("formula_examples"):
            st.markdown("**Esempi**: " + "  \n• ".join([""] + examples))
        if forb := s.get("title", {}).get("forbidden_words"):
            st.markdown(f"**Parole vietate**: {', '.join(forb)}")
        st.caption(f"Editabile in `config/sectors/{sector}.yaml`")

n_to_process = limit or len(df)

# Cache hit preview
use_cache = st.checkbox(
    "Usa cache (riusa enrichment precedenti per prodotti invariati)",
    value=True,
    help="Risparmia fino al 90% dei costi AI quando aggiorni un feed già processato. "
         "Il match avviene su hash di id, title, description, brand, prezzo, attributi.",
)

cache_ns = f"{st.session_state.get('session_id','default')}__{sector or 'generic'}"
cached_rows: dict = {}
if use_cache:
    try:
        preview_subset = df.head(n_to_process) if limit else df
        cached_rows, _ = enrich_cache.get_cached(
            preview_subset,
            namespace="shared_v1",
            model=model, sector=sector, provider="anthropic",
        )
    except Exception:
        cached_rows = {}

n_hit = len(cached_rows)
n_miss = n_to_process - n_hit

hit_rate_color = "#10B981" if n_hit > 0 else "#9CA3AF"
st.markdown(
    f"<div style='display:flex; gap:16px; font-size:0.82rem; color:#4B5563; margin:6px 0 12px;'>"
    f"<span><span style='color:{hit_rate_color};'>●</span>&nbsp;Cache hit: <b>{n_hit}</b></span>"
    f"<span><span style='color:#2F6FED;'>●</span>&nbsp;Da processare con AI: <b>{n_miss}</b></span>"
    f"</div>",
    unsafe_allow_html=True,
)

# Cost estimate — based only on miss (cache skips AI call)
cost_estimate_card(n_miss, model)

with st.expander(f"💰 Confronta tutti i modelli su {n_miss:,} prodotti", expanded=False):
    cost_projection_table(n_miss)
    st.markdown(
        "**Strategie per risparmiare ancora:**\n"
        "- **Cache hash prodotto** (già attivo): re-enrichment dopo update feed = 70-95% dei prodotti in cache\n"
        "- **Delta sync** (pagina Clienti): enrichment SOLO sui prodotti nuovi/modificati nel feed\n"
        "- **Batch API 24h**: sconto 50% su input+output, ideale per cron notturno cataloghi grandi\n"
        "- **Modello ibrido**: Haiku/gpt-4o-mini per bulk + Sonnet/gpt-5 solo per prodotti flaggati a bassa qualità\n"
        "- **Limite prodotti**: testa prima con limit=10-50 per validare settore e prompt template"
    )

bcol1, bcol2 = st.columns([2, 1])
launch = bcol1.button("Avvia enrichment", type="primary", use_container_width=True)
if bcol2.button("Pulisci cache", use_container_width=True,
                help="Forza re-enrichment di tutto il feed al prossimo run"):
    enrich_cache.clear("shared_v1")
    st.success("Cache pulita")
    st.rerun()

if launch:
    with guarded("enrichment AI"):
        if n_miss == 0 and n_hit > 0:
            # Tutto in cache — ricostruisci direttamente
            enriched_rows = df.head(n_to_process).copy() if limit else df.copy()
            for idx, result in cached_rows.items():
                for k, v in (result or {}).items():
                    if v is not None:
                        enriched_rows.at[idx, k] = v
            enriched_rows["_enrichment_status"] = "cached"
            st.session_state["enriched_df"] = enriched_rows
        else:
            with LoadingProgress("Enrichment AI in corso", total=n_miss or n_to_process) as lp:
                def cb(d, t):
                    lp.update(d, subtitle=f"{d}/{t} prodotti processati")

                enriched = enrich_dataframe(
                    df, api_key=st.session_state["api_key"], model=model,
                    max_workers=workers, limit=limit or None, progress_callback=cb,
                    sector=sector, overwrite_title_description=overwrite,
                    max_tokens=int(st.session_state.get("config", {}).get("max_tokens", 3500)),
                    style_guide_text=style_guide_text,
                )

            # Salva i risultati OK in cache per riuso futuro
            if use_cache and "_enrichment_status" in enriched.columns:
                try:
                    good = enriched[enriched["_enrichment_status"] == "ok"]
                    pairs = []
                    for idx, row in good.iterrows():
                        src = df.loc[idx].to_dict() if idx in df.index else row.to_dict()
                        result = {k: row.get(k) for k in row.index
                                  if k not in ("_enrichment_status",) and pd.notna(row.get(k))}
                        pairs.append((src, result))
                    enrich_cache.store(pairs, namespace="shared_v1",
                                       model=model, sector=sector, provider="anthropic")
                except Exception:
                    pass

            # Ripristina risultati cache nelle righe saltate
            if cached_rows:
                for idx, result in cached_rows.items():
                    if idx in enriched.index:
                        for k, v in (result or {}).items():
                            if v is not None:
                                enriched.at[idx, k] = v
                        enriched.at[idx, "_enrichment_status"] = "cached"

            st.session_state["enriched_df"] = enriched
        st.session_state["merged_df"] = None
        from utils.history import save_snapshot
        save_snapshot(st.session_state["session_id"], st.session_state)

        # If driven from a Client feed (Clienti page handoff), remove enriched
        # keys from the pending queue and merge into that feed's cumulative
        # enriched.parquet so subsequent syncs know they're done.
        client_slug = st.session_state.get("_enrich_client_slug")
        feed_slug = st.session_state.get("_enrich_feed_slug")
        if client_slug and feed_slug:
            try:
                from utils import clients as _cs
                from utils import feed_diff as _fd
                final = st.session_state.get("enriched_df")
                if final is not None and not final.empty:
                    strat = (_cs.get_feed(client_slug, feed_slug) or {}).get("id_strategy", "hierarchical")
                    enriched_keys = [
                        _fd.product_key(r.to_dict(), strategy=strat)
                        for _, r in final.iterrows()
                    ]
                    removed_cnt = _cs.remove_pending(client_slug, feed_slug, enriched_keys)
                    # Merge into cumulative enriched
                    prev = _cs.load_enriched(client_slug, feed_slug)
                    if prev is None or prev.empty:
                        merged = final.copy()
                    else:
                        # Drop overlapping keys from prev then concat
                        prev_keys = [
                            _fd.product_key(r.to_dict(), strategy=strat)
                            for _, r in prev.iterrows()
                        ]
                        mask = [k not in enriched_keys for k in prev_keys]
                        merged = pd.concat([prev[mask], final], ignore_index=True)
                    _cs.save_enriched(client_slug, feed_slug, merged)
                    _cs.log_event(client_slug, feed_slug, "enrichment_applied",
                                  {"enriched": int(len(final)), "removed_from_pending": removed_cnt})
                    st.info(f"💼 {removed_cnt} prodotti rimossi dalla coda · "
                            f"enriched.parquet del feed aggiornato")
            except Exception as _e:  # noqa
                st.warning(f"Hook client-feed non riuscito (non critico): {_e}")

        st.success(f"Enrichment completato · {n_hit} da cache, {n_miss} elaborati")

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

# Lista completa campi GMC ufficiali (ordine spec)
_google_order = ["id"] + [t for t, _, _, _ in GOOGLE_FIELDS if t != "id"]
google_cols = [c for c in _google_order if c in enriched.columns]
# Solo campi popolati per non mostrare colonne tutte vuote
google_cols = [c for c in google_cols
               if c == "id" or enriched[c].astype(str).str.strip().replace({"nan": "", "None": ""}).ne("").any()]

# Lista completa campi Meta ufficiali
_meta_order = ["id"] + [t for t, _, _ in META_FIELDS if t != "id"]
meta_cols = [c for c in _meta_order if c in enriched.columns]
meta_cols = [c for c in meta_cols
             if c == "id" or enriched[c].astype(str).str.strip().replace({"nan": "", "None": ""}).ne("").any()]

# Tutti gli attributi (compresi Meta extras + meta-internal)
_all_order = ["id"] + [t for t, _, _, _ in GOOGLE_FIELDS if t != "id"] + \
             [t for t, _, _ in META_FIELDS if t not in {x for x, _, _, _ in GOOGLE_FIELDS}]
other_cols = [c for c in enriched.columns if c not in _all_order]
all_cols = [c for c in _all_order if c in enriched.columns] + other_cols
all_cols = [c for c in all_cols
            if c == "id" or enriched[c].astype(str).str.strip().replace({"nan": "", "None": ""}).ne("").any()]

# Column config sharing
_col_cfg = {
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
