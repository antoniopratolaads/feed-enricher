"""Refine & Chat — post-enrichment refinement + chat conversazionale con Claude.

Separata da Enrichment AI per chiarezza del flusso:
  1. Enrichment AI  → primo passaggio automatico
  2. Refine & Chat  → affinamento manuale + analisi conversazionale
  3. Catalog Optimizer → export TSV/CSV/XML + bundle ZIP
"""
import streamlit as st
import pandas as pd
from anthropic import Anthropic

from utils.state import init_state
from utils.ui import apply_theme, api_key_banner, empty_state, guarded, diff_view
from utils.enrichment import refine_product, chat_about_data, DEFAULT_MODEL

init_state()
apply_theme()
api_key_banner()

st.title("Refine & Chat")
st.caption(
    "Affinamento post-enrichment. Applica istruzioni custom a sottoinsiemi o chiedi "
    "consigli a Claude con il contesto del catalogo."
)

if not st.session_state.get("api_key"):
    empty_state(
        icon="🔑",
        title="API key non configurata",
        description="Per usare refinement + chat serve una chiave Claude.",
        cta_label="Configura API key →",
        cta_page="client_pages/settings.py",
        cta_key="_empty_settings_refine",
    )
    st.stop()

enriched = st.session_state.get("enriched_df")
if enriched is None or enriched.empty:
    empty_state(
        icon="✨",
        title="Nessun enrichment eseguito",
        description="Prima fai girare l'enrichment AI su qualche prodotto, poi torna qui "
                    "per affinare i risultati con istruzioni custom o chattare con Claude.",
        cta_label="Vai a Enrichment AI →",
        cta_page="client_pages/enrichment_ai.py",
        cta_key="_empty_enrich",
    )
    st.stop()

cfg = st.session_state.get("config", {})
model = cfg.get("anthropic_model", DEFAULT_MODEL)

# ============================================================
# TABS — Undo / Diff / Refinement / Chat
# ============================================================
tab_undo, tab_diff, tab_refine, tab_chat = st.tabs([
    "↶ Undo", "📊 Diff prima/dopo", "✨ Refinement bulk", "💬 Chat con Claude",
])

# ───── TAB UNDO ─────
with tab_undo:
    st.markdown("### Ripristina titoli/descrizioni originali")
    st.caption(
        "L'enrichment ha salvato gli originali in `title_original` / `description_original`. "
        "Click sotto per ripristinarli e annullare le modifiche AI."
    )
    n_to_revert = int(enriched["_enrichment_status"].astype(str).isin(["ok", "cached"]).sum()) \
                  if "_enrichment_status" in enriched.columns else 0
    st.metric("Prodotti arricchiti (revertibili)", n_to_revert)
    if st.button("↶ Ripristina originali su TUTTI gli arricchiti",
                  disabled=n_to_revert == 0, type="primary"):
        with guarded("undo enrichment"):
            restored = enriched.copy()
            for src, dst in (("title_original", "title"),
                             ("description_original", "description")):
                if src in restored.columns:
                    mask = restored[src].notna() & restored[src].astype(str).ne("")
                    restored.loc[mask, dst] = restored.loc[mask, src]
            restored["_enrichment_status"] = "reverted"
            st.session_state["enriched_df"] = restored
            st.session_state["feed_df"] = restored
            st.toast("Ripristinati gli originali", icon="↶")
            st.rerun()

# ───── TAB DIFF ─────
with tab_diff:
    st.markdown("### Confronto prima/dopo")
    if "title_original" not in enriched.columns:
        st.info("Nessuna colonna `title_original` — l'enrichment non ha ancora sovrascritto.")
    else:
        diffed = enriched[
            enriched["title_original"].notna()
            & (enriched["title"].astype(str) != enriched["title_original"].astype(str))
        ]
        n_show = st.slider("Quanti prodotti mostrare", 5, min(100, max(len(diffed), 5)),
                            min(10, len(diffed)))
        st.caption(f"{len(diffed)} prodotti totali hanno title cambiato dall'AI.")
        for _, row in diffed.head(n_show).iterrows():
            diff_view(
                f"{row.get('id', '?')} · {row.get('brand', '')}".strip(" ·"),
                row.get("title_original", ""),
                row.get("title", ""),
            )

# ───── TAB REFINEMENT ─────
with tab_refine:
    st.markdown("### Affina con istruzione custom su sottoinsieme")
    st.caption(
        "Dai a Claude un'istruzione specifica (es. *titoli più aggressivi per i prodotti zombie*) "
        "e selezioni quali prodotti toccare via filtri."
    )

    rc1, rc2, rc3 = st.columns([2, 2, 1])
    brand_options = sorted(enriched["brand"].dropna().unique()) \
                    if "brand" in enriched.columns else []
    brand_filter = rc1.multiselect("Filtra per brand", options=brand_options, default=[])
    status_filter = rc2.multiselect("Filtra per status",
                                      options=["ok", "cached", "empty", "error"], default=[])

    mask = pd.Series([True] * len(enriched), index=enriched.index)
    if brand_filter:
        mask &= enriched["brand"].isin(brand_filter)
    if status_filter and "_enrichment_status" in enriched.columns:
        status_str = enriched["_enrichment_status"].astype(str).str.lower()
        sfilter = pd.Series([False] * len(enriched), index=enriched.index)
        for s in status_filter:
            sfilter |= status_str.eq(s) | status_str.str.startswith(s)
        mask &= sfilter

    selected = enriched[mask]
    rc3.metric("Prodotti target", len(selected))

    instruction = st.text_area(
        "Istruzione per Claude",
        placeholder="Es: rendi i titoli più orientati al beneficio. Aggiungi parole chiave "
                    "search-friendly. Massimo 100 caratteri. Mantieni il brand all'inizio.",
        height=100,
    )

    rcc1, rcc2 = st.columns([1, 4])
    n_apply = rcc1.number_input("Max prodotti da aggiornare", 1, 500,
                                  min(20, max(len(selected), 1)), 5,
                                  help="Limita per controllare costo (~€0.002/prodotto)")
    if rcc2.button("Applica refinement", type="primary",
                    disabled=not instruction or not len(selected)):
        with guarded("refinement"):
            client = Anthropic(api_key=st.session_state["api_key"])
            progress = st.progress(0.0, text=f"0/{min(int(n_apply), len(selected))}...")
            target = selected.head(int(n_apply))
            updated = 0
            for i, (idx, row) in enumerate(target.iterrows()):
                result = refine_product(client, row.to_dict(), instruction, model=model)
                if result and "_error" not in result:
                    for k in ("title", "description", "title_meta", "description_meta_short",
                              "short_description"):
                        if result.get(k):
                            enriched.at[idx, k] = result[k]
                    updated += 1
                progress.progress((i + 1) / len(target),
                                   text=f"{i+1}/{len(target)} prodotti")
            st.session_state["enriched_df"] = enriched
            st.session_state["feed_df"] = enriched
            st.success(f"✅ Aggiornati {updated}/{len(target)} prodotti")
            st.rerun()

# ───── TAB CHAT ─────
with tab_chat:
    st.markdown("### Chat con Claude sul tuo catalogo")
    st.caption(
        "Claude ha già in contesto: numero prodotti, top brand, ROAS/vendite se presenti, "
        "lunghezza media titoli. Chiedi consigli su refinement, custom_label, anomalie, trend."
    )

    if "enrich_chat" not in st.session_state:
        st.session_state["enrich_chat"] = []

    # Prompt rapidi
    sug1, sug2, sug3, sug4 = st.columns(4)
    suggestions = {
        sug1: "Quali brand hanno i titoli più poveri da migliorare?",
        sug2: "Suggerisci 3 istruzioni di refinement per prodotti senza vendite",
        sug3: "Come impostare le custom_label per massimizzare ROAS?",
        sug4: "Genera un'istruzione per titoli in stile premium",
    }
    for col, q in suggestions.items():
        if col.button(q, use_container_width=True, key=f"sug_{hash(q)}"):
            st.session_state["enrich_chat"].append({"role": "user", "content": q})
            st.rerun()

    # Render history
    for msg in st.session_state["enrich_chat"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("Scrivi un messaggio a Claude...")
    if prompt:
        st.session_state["enrich_chat"].append({"role": "user", "content": prompt})
        st.rerun()

    # Risposta se ultimo messaggio è dell'utente
    if st.session_state["enrich_chat"] and \
       st.session_state["enrich_chat"][-1]["role"] == "user":
        with st.chat_message("assistant"):
            with st.spinner("Claude sta pensando..."):
                # Contesto catalogo
                ctx_lines = [f"Prodotti totali: {len(enriched)}"]
                if "brand" in enriched.columns:
                    top_brands = enriched["brand"].value_counts().head(5).to_dict()
                    ctx_lines.append(f"Top brand: {top_brands}")
                if "clicks" in enriched.columns and "conv_value" in enriched.columns and "cost" in enriched.columns:
                    try:
                        roas = enriched["conv_value"].sum() / enriched["cost"].sum() \
                               if enriched["cost"].sum() else 0
                        ctx_lines.append(f"ROAS GAds: {roas:.2f}x · Spesa: €{enriched['cost'].sum():.0f}")
                        zombie = ((enriched["clicks"] >= 30) & (enriched["conversions"] == 0)).sum()
                        ctx_lines.append(f"Zombie: {zombie}")
                    except Exception:
                        pass
                if "shopify_units_sold" in enriched.columns:
                    try:
                        no_sales = (enriched["shopify_units_sold"] == 0).sum()
                        ctx_lines.append(f"Senza vendite Shopify: {no_sales}")
                    except Exception:
                        pass
                if "title" in enriched.columns:
                    avg_len = enriched["title"].astype(str).str.len().mean()
                    ctx_lines.append(f"Lunghezza media title: {avg_len:.0f} char")
                ctx = "\n".join(ctx_lines)

                client = Anthropic(api_key=st.session_state["api_key"])
                reply = chat_about_data(client, st.session_state["enrich_chat"],
                                         ctx, model=model)
                st.markdown(reply)
                st.session_state["enrich_chat"].append({"role": "assistant", "content": reply})

    cc1, _ = st.columns([1, 4])
    if cc1.button("🗑️ Pulisci chat", use_container_width=True):
        st.session_state["enrich_chat"] = []
        st.rerun()
