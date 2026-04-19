"""Pagina 12: Genera cataloghi ottimizzati per Google Merchant Center e Meta Catalog."""
import streamlit as st
import pandas as pd
import plotly.express as px

from utils.state import init_state, current_df
from utils.ui import apply_theme, empty_state
from utils.catalog_optimizer import (
    build_google_feed, build_meta_feed, validate_feed, title_quality_check,
    GOOGLE_FIELDS,
)
from utils.exporter import to_excel_bytes, to_gmc_xml
from utils.validation import quality_summary, find_duplicates, validate_gtins, validate_images

init_state()
apply_theme()

import zipfile, io
from utils.history import save_output

st.title("Catalog Optimizer · Google + Meta")
st.caption("Genera feed ottimizzati con best practice per Google Merchant Center e Meta Catalog (Facebook/Instagram). "
           "Usa i campi ufficiali (`title`, `description`, `brand`, `color`, `size`, ecc.) generati dall'enrichment AI e normalizza availability/condition/price.")

df = current_df()
if df is None:
    empty_state(
        icon="📦",
        title="Nessun feed caricato",
        description="Carica prima un feed prodotto. Il Catalog Optimizer userà enrichment + label "
                    "per produrre export Google Merchant e Meta Catalog.",
        cta_label="Vai a Upload Feed →",
        cta_page="client_pages/upload_feed.py",
        cta_key="_empty_upload_opt",
    )
    st.stop()

# ============================================================
# QUALITY CHECKS — pre-export sanity
# ============================================================
with st.expander("🔎 Quality check catalogo (pre-export)", expanded=False):
    qs = quality_summary(df)
    qc = st.columns(5)
    qc[0].metric("Prodotti totali", f"{qs.total_rows:,}")
    qc[1].metric("GTIN validi", f"{qs.gtin.get('valid', 0):,}",
                  delta=f"{qs.gtin.get('invalid', 0)} invalidi" if qs.gtin.get('invalid') else None,
                  delta_color="inverse" if qs.gtin.get('invalid') else "normal")
    qc[2].metric("Duplicati title+desc", qs.duplicates,
                  delta_color="inverse" if qs.duplicates else "normal")
    qc[3].metric("Titoli corti (<30ch)", qs.short_titles,
                  delta_color="inverse" if qs.short_titles else "normal")
    qc[4].metric("Description corte (<80ch)", qs.short_descriptions,
                  delta_color="inverse" if qs.short_descriptions else "normal")

    if qs.duplicates:
        dups = find_duplicates(df, ("title", "description")).head(30)
        st.markdown("**Duplicati rilevati** (primi 30 — raggruppati per `_dup_group`)")
        st.dataframe(
            dups[[c for c in ("id", "brand", "title", "description", "_dup_group") if c in dups.columns]],
            use_container_width=True, height=240,
        )

    if qs.gtin.get('invalid'):
        bad = df[df.get("gtin", "").astype(str).apply(
            lambda x: bool(x.strip()) and len(x.strip().split('.')[0]) in (8, 12, 13, 14)
        )].head(20) if "gtin" in df.columns else pd.DataFrame()

    if st.button("🖼️ Verifica dimensioni immagini (primi 50)", key="_img_check",
                  help="HEAD request per ogni URL immagine. Warning se <800×800px."):
        if "image_link" not in df.columns:
            st.warning("Nessuna colonna `image_link` nel feed.")
        else:
            with st.spinner("Verifica immagini..."):
                issues = validate_images(df["image_link"].dropna().tolist(), limit=50)
            if not issues:
                st.success("Tutte le immagini OK (primi 50).")
            else:
                st.warning(f"{len(issues)} problemi rilevati")
                st.dataframe(
                    pd.DataFrame([{
                        "url": i.url[:60] + "..." if len(i.url) > 60 else i.url,
                        "motivo": i.reason,
                        "width": i.width, "height": i.height,
                    } for i in issues]),
                    use_container_width=True, height=240,
                )

# ============================================================
# CONFIG
# ============================================================
c1, c2 = st.columns(2)
currency = c1.selectbox("Valuta", ["EUR", "USD", "GBP", "CHF"], index=0)
target_platform = c2.radio("Target", ["Google", "Meta", "Entrambi"], horizontal=True)

st.divider()

# ============================================================
# BUILD
# ============================================================
google_df = build_google_feed(df, currency=currency) if target_platform in ("Google", "Entrambi") else None
meta_df = build_meta_feed(df, currency=currency) if target_platform in ("Meta", "Entrambi") else None

# ============================================================
# GOOGLE PANEL
# ============================================================
if google_df is not None:
    st.subheader("🛒 Google Merchant Center")
    val = validate_feed(google_df, "google")

    errors = (val["stato"] == "ERROR").sum()
    warns = (val["stato"] == "WARN").sum()
    ok = (val["stato"] == "OK").sum()
    missing = (val["stato"] == "MISSING_COLUMN").sum()

    k = st.columns(4)
    k[0].metric("Prodotti", f"{len(google_df):,}")
    k[1].metric("Campi OK", ok, delta_color="normal")
    k[2].metric("Warning", warns, delta_color="off")
    k[3].metric("Errori", errors + missing, delta_color="inverse" if errors else "normal")

    tabs = st.tabs(["Anteprima feed", "Validazione campi", "Qualità titoli", "Export"])

    with tabs[0]:
        st.dataframe(google_df.head(50), use_container_width=True, height=400)
        st.caption("Mostrati 50 prodotti su " + f"{len(google_df):,}")

    with tabs[1]:
        st.markdown("**Stato campi GMC** (verde = OK, giallo = warning, rosso = errore)")
        def _color(v):
            if v == "ERROR" or v == "MISSING_COLUMN":
                return "background-color: rgba(255,107,107,0.2)"
            if v == "WARN":
                return "background-color: rgba(255,165,0,0.2)"
            return "background-color: rgba(0,217,163,0.15)"
        st.dataframe(
            val.style.applymap(_color, subset=["stato"]),
            use_container_width=True, height=500,
        )

    with tabs[2]:
        q = title_quality_check(google_df)
        kc = st.columns(4)
        kc[0].metric("Lunghezza media", f"{q['title_len_avg'][0]:.0f}")
        kc[1].metric("Ideale (70-150)", int(q["ideal_70_150"][0]))
        kc[2].metric("Troppo corti (<40)", int(q["too_short_<40"][0]),
                     delta_color="inverse" if q["too_short_<40"][0] else "off")
        kc[3].metric("Duplicati", int(q["duplicates"][0]),
                     delta_color="inverse" if q["duplicates"][0] else "off")

        # distribuzione lunghezze
        lens = google_df["title"].astype(str).str.len()
        fig = px.histogram(lens, nbins=40, color_discrete_sequence=["#2F6FED"],
                            title="Distribuzione lunghezza titoli")
        fig.add_vline(x=70, line_dash="dash", line_color="#10B981")
        fig.add_vline(x=150, line_dash="dash", line_color="#10B981")
        fig.update_layout(height=320, plot_bgcolor="rgba(0,0,0,0)",
                           paper_bgcolor="rgba(0,0,0,0)", showlegend=False,
                           xaxis_title="Caratteri", yaxis_title="")
        st.plotly_chart(fig, use_container_width=True)

    with tabs[3]:
        e1, e2, e3, e4 = st.columns(4)
        e1.download_button("CSV (TSV per GMC)",
                            google_df.to_csv(index=False, sep="\t").encode("utf-8"),
                            "google_feed.tsv", "text/tab-separated-values",
                            use_container_width=True,
                            help="GMC accetta TSV (tab-separated) come formato preferito")
        e2.download_button("Excel",
                            to_excel_bytes({"google_feed": google_df}),
                            "google_feed.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
        e3.download_button("XML (RSS 2.0 GMC)",
                            to_gmc_xml(google_df, "Google Feed").encode("utf-8"),
                            "google_feed.xml", "application/xml",
                            use_container_width=True)
        e4.download_button("CSV standard",
                            google_df.to_csv(index=False).encode("utf-8"),
                            "google_feed.csv", "text/csv",
                            use_container_width=True)

        st.info("**Come usarlo**: GMC → Feed → Aggiungi nuovo → carica TSV/XML, "
                "oppure connetti il file via Google Sheets per refresh automatico.")

    st.divider()

# ============================================================
# META PANEL
# ============================================================
if meta_df is not None:
    st.subheader("📘 Meta Catalog (Facebook + Instagram)")
    val = validate_feed(meta_df, "meta")

    errors = (val["stato"] == "ERROR").sum()
    warns = (val["stato"] == "WARN").sum()
    ok = (val["stato"] == "OK").sum()

    k = st.columns(4)
    k[0].metric("Prodotti", f"{len(meta_df):,}")
    k[1].metric("Campi OK", ok)
    k[2].metric("Warning", warns)
    k[3].metric("Errori", errors)

    tabs = st.tabs(["Anteprima feed", "Validazione", "Qualità titoli", "Export"])

    with tabs[0]:
        st.dataframe(meta_df.head(50), use_container_width=True, height=400)

    with tabs[1]:
        def _color(v):
            if v in ("ERROR", "MISSING_COLUMN"):
                return "background-color: rgba(255,107,107,0.2)"
            if v == "WARN":
                return "background-color: rgba(255,165,0,0.2)"
            return "background-color: rgba(0,217,163,0.15)"
        st.dataframe(val.style.applymap(_color, subset=["stato"]),
                      use_container_width=True, height=500)

    with tabs[2]:
        q = title_quality_check(meta_df)
        kc = st.columns(4)
        kc[0].metric("Lunghezza media", f"{q['title_len_avg'][0]:.0f}")
        kc[1].metric("Sotto 200 (Meta limit)", int((meta_df["title"].astype(str).str.len() <= 200).sum()))
        kc[2].metric("Troppo corti (<40)", int(q["too_short_<40"][0]))
        kc[3].metric("Duplicati", int(q["duplicates"][0]))

    with tabs[3]:
        e1, e2, e3 = st.columns(3)
        e1.download_button("CSV (Meta format)",
                            meta_df.to_csv(index=False).encode("utf-8"),
                            "meta_feed.csv", "text/csv",
                            use_container_width=True)
        e2.download_button("Excel",
                            to_excel_bytes({"meta_feed": meta_df}),
                            "meta_feed.xlsx",
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True)
        e3.download_button("XML",
                            to_gmc_xml(meta_df, "Meta Feed").encode("utf-8"),
                            "meta_feed.xml", "application/xml",
                            use_container_width=True)

        st.info("**Come usarlo**: Commerce Manager → Cataloghi → Aggiungi prodotti → "
                "Da file di dati. Meta supporta CSV, TSV, XML, Google Sheets.")

# ============================================================
# DOWNLOAD BUNDLE FINALE
# ============================================================
st.divider()
st.subheader("📦 Bundle finale — tutti i feed ottimizzati in un ZIP")
st.caption("Pacchetto unico con tutti i formati pronti per Google Merchant Center, Meta Commerce Manager e per backup.")

if st.button("Genera ZIP completo", type="primary", use_container_width=True):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        if google_df is not None:
            zf.writestr("google/google_feed.tsv", google_df.to_csv(index=False, sep="\t"))
            zf.writestr("google/google_feed.csv", google_df.to_csv(index=False))
            zf.writestr("google/google_feed.xml", to_gmc_xml(google_df, "Google Feed"))
            zf.writestr("google/google_feed.xlsx", to_excel_bytes({"google_feed": google_df}))
            zf.writestr("google/validation_report.csv", validate_feed(google_df, "google").to_csv(index=False))
        if meta_df is not None:
            zf.writestr("meta/meta_feed.csv", meta_df.to_csv(index=False))
            zf.writestr("meta/meta_feed.xml", to_gmc_xml(meta_df, "Meta Feed"))
            zf.writestr("meta/meta_feed.xlsx", to_excel_bytes({"meta_feed": meta_df}))
            zf.writestr("meta/validation_report.csv", validate_feed(meta_df, "meta").to_csv(index=False))
        # README dentro lo zip
        readme = """# Feed ottimizzati — Generato da Feed Enricher Pro

## google/
- `google_feed.tsv` ← formato preferito da Google Merchant Center
- `google_feed.xml` ← RSS 2.0 GMC
- `google_feed.csv` / `google_feed.xlsx` ← formati alternativi
- `validation_report.csv` ← stato campi (OK/WARN/ERROR)

## meta/
- `meta_feed.csv` ← formato preferito da Meta Commerce Manager
- `meta_feed.xml` ← XML
- `meta_feed.xlsx` ← Excel

## Come caricarli

**Google Merchant Center**: GMC → Feed → Aggiungi nuovo → Carica TSV/XML
**Meta Commerce Manager**: Catalogo → Aggiungi prodotti → Da file di dati → CSV
"""
        zf.writestr("README.md", readme)
    bundle_bytes = buf.getvalue()

    st.download_button(
        "⬇️ Scarica bundle ZIP",
        bundle_bytes,
        file_name=f"feed_bundle_{currency}.zip",
        mime="application/zip",
        use_container_width=True,
    )

    # salva anche in cartella sessione
    if "session_id" in st.session_state and st.session_state.get("session_id"):
        save_output(st.session_state["session_id"], "feed_bundle.zip", bundle_bytes)
        st.info(f"Bundle salvato anche nella cartella sessione (vedi pagina **History**)")

# ============================================================
# BEST PRACTICE
# ============================================================
st.divider()
with st.expander("📚 Best practice applicate (Google + Meta)"):
    st.markdown("""
**Titoli**
- Formato: `Brand + Tipo prodotto + Attributi chiave (colore, taglia, materiale)`
- Google: 70-150 caratteri (ideale)
- Meta: massimo 200 caratteri
- Niente all-caps, niente emoji ripetute, niente "Acquista ora"

**Descrizioni**
- Google: 500-5000 caratteri, descrizione del prodotto (non promo)
- Meta: short_description ≤ 200 char, description ≤ 9999

**Availability normalizzato**
- Valori: `in stock` · `out of stock` · `preorder` · `backorder`

**Condition**
- Valori: `new` · `refurbished` · `used`

**Price**
- Formato `99.99 EUR` (numero + spazio + ISO 4217)

**Identifier_exists**
- `no` se mancano sia `gtin` sia `mpn`, altrimenti `yes`

**Image link**
- Obbligatorio. Risoluzione min 100x100 (250x250 raccomandato), max 64MB
- HTTPS preferito

**Custom labels**
- Solo per uso interno (segmentazione campagne)
- Da 0 a 4 disponibili in entrambe le piattaforme
""")
