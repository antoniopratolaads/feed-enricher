"""Pagina 4: Enrichment AI via Claude (taxonomy + attributi + titoli) + Chat refinement."""
import streamlit as st
import pandas as pd
from anthropic import Anthropic

from utils.state import init_state
from utils.ui import apply_theme
from utils.enrichment import (
    enrich_dataframe, refine_product, chat_about_data, DEFAULT_MODEL,
    list_sectors, load_sector,
)
from utils.exporter import to_excel_bytes

init_state()
apply_theme()

st.title("4. Enrichment AI (Claude)")
st.caption("Classificazione Google Taxonomy + estrazione attributi + riscrittura titoli/descrizioni · Chat con Claude per affinare")

if st.session_state.get("feed_df") is None:
    st.warning("Carica prima un feed nella pagina **Upload Feed**.")
    st.stop()
if not st.session_state.get("api_key"):
    st.warning("Inserisci la Claude API Key in **0. Settings** o nella sidebar.")
    st.stop()

df = st.session_state["feed_df"]

# ============================================================
# CONFIG ENRICHMENT
# ============================================================
c1, c2, c3, c4 = st.columns(4)
model = c1.selectbox("Modello", ["claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"], index=0)

sectors = ["(generico)"] + list_sectors()
sector_choice = c2.selectbox("Settore (best practice)", sectors, index=1 if "abbigliamento" in sectors else 0,
                              help="Carica regole settoriali dal YAML in config/sectors/")
sector = "" if sector_choice == "(generico)" else sector_choice

limit = c3.number_input("Limite prodotti (0 = tutti)", min_value=0, value=min(50, len(df)), step=10)
workers = c4.slider("Parallelismo", 1, 15, 5)

overwrite = st.checkbox(
    "Sovrascrivi `title` e `description` con la versione AI (consigliato)",
    value=True,
    help="Gli originali vengono salvati in `title_original` / `description_original` come backup. "
         "Vengono anche popolati colore/taglia/materiale/brand se mancanti."
)

if sector:
    with st.expander(f"📚 Best practice attive: {sector}"):
        s = load_sector(sector)
        if s.get("title", {}).get("formula"):
            st.markdown(f"**Formula titolo**: `{s['title']['formula']}`")
        if examples := s.get("title", {}).get("formula_examples"):
            st.markdown("**Esempi**: " + "  \n• ".join([""] + examples))
        if forb := s.get("title", {}).get("forbidden_words"):
            st.markdown(f"**Parole vietate**: {', '.join(forb)}")
        st.caption(f"Editabile in `config/sectors/{sector}.yaml`")

st.info(f"Costo stimato Sonnet ≈ ${(limit or len(df))*0.004:.2f} per {limit or len(df)} prodotti")

if st.button("Avvia enrichment", type="primary"):
    progress = st.progress(0, text="Avvio...")
    def cb(d, t): progress.progress(d/t, text=f"{d}/{t} prodotti")
    try:
        enriched = enrich_dataframe(df, api_key=st.session_state["api_key"], model=model,
                                     max_workers=workers, limit=limit or None, progress_callback=cb,
                                     sector=sector, overwrite_title_description=overwrite)
        st.session_state["enriched_df"] = enriched
        st.session_state["merged_df"] = None
        from utils.history import save_snapshot
        save_snapshot(st.session_state["session_id"], st.session_state)
        st.success(f"Enrichment completato")
    except Exception as e:
        st.error(f"Errore: {e}")

enriched = st.session_state.get("enriched_df")
if enriched is None:
    st.stop()

# ============================================================
# RISULTATI
# ============================================================
st.divider()
st.subheader("Risultati")
ok = (enriched["_enrichment_status"] == "ok").sum()
errors = enriched["_enrichment_status"].astype(str).str.startswith("error").sum()
c1, c2, c3 = st.columns(3)
c1.metric("OK", int(ok))
c2.metric("Errori", int(errors))
c3.metric("Vuoti", len(enriched) - ok - errors)

tabs = st.tabs(["🛒 Variante Google", "📘 Variante Meta", "🏷️ Tutti gli attributi"])

google_cols = [c for c in ["id", "title", "description", "brand", "google_product_category",
                            "product_type", "color", "size", "material", "gender", "age_group",
                            "pattern", "condition"] if c in enriched.columns]
meta_cols = [c for c in ["id", "title_meta", "description_meta_short", "description",
                          "brand", "google_product_category", "color", "size", "material",
                          "gender", "age_group", "condition"] if c in enriched.columns]

with tabs[0]:
    st.caption("Campi ottimizzati per **Google Merchant Center** (title ≤150, description ≤5000)")
    st.dataframe(enriched[google_cols].head(100), use_container_width=True, height=320,
                  column_config={
                      "title": st.column_config.TextColumn(width="large"),
                      "description": st.column_config.TextColumn(width="large"),
                  })

with tabs[1]:
    st.caption("Campi ottimizzati per **Meta Catalog** (title ≤200, short_description ≤200, description ≤9999)")
    st.dataframe(enriched[meta_cols].head(100), use_container_width=True, height=320,
                  column_config={
                      "title_meta": st.column_config.TextColumn("title (Meta)", width="large"),
                      "description_meta_short": st.column_config.TextColumn("short_description (Meta)", width="medium"),
                      "description": st.column_config.TextColumn("description", width="large"),
                  })

with tabs[2]:
    all_cols = ["id"] + [c for c in enriched.columns if c not in ("id", "_enrichment_status")] + ["_enrichment_status"]
    st.dataframe(enriched[all_cols].head(100), use_container_width=True, height=320)

dc1, dc2 = st.columns(2)
dc1.download_button("Excel arricchito", to_excel_bytes({"enriched": enriched}),
                     "feed_enriched.xlsx",
                     "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                     use_container_width=True)
dc2.download_button("CSV arricchito", enriched.to_csv(index=False).encode("utf-8"),
                     "feed_enriched.csv", "text/csv", use_container_width=True)

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
