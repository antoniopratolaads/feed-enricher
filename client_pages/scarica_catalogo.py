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

# ============================================================
# CACHED WRAPPERS — evitano rebuild su ogni rerun Streamlit.
# Key: hash del DataFrame sorgente + parametri. Reuse tra interazioni
# innocue (radio, selectbox, multiselect) finché df non cambia.
# ============================================================

def _df_fingerprint(df: pd.DataFrame) -> str:
    """Fingerprint stabile per cache key (shape + colonne + hash contenuto)."""
    try:
        h = pd.util.hash_pandas_object(df, index=True).values
        import hashlib
        return hashlib.md5(h.tobytes()).hexdigest() + f"_{df.shape[0]}x{df.shape[1]}"
    except Exception:
        return f"{df.shape[0]}x{df.shape[1]}_{hash(tuple(df.columns))}"


@st.cache_data(show_spinner=False, max_entries=4)
def _cached_build_google(fp: str, currency: str, _df: pd.DataFrame) -> pd.DataFrame:
    return build_google_feed(_df, currency=currency)


@st.cache_data(show_spinner=False, max_entries=4)
def _cached_build_meta(fp: str, currency: str, _df: pd.DataFrame) -> pd.DataFrame:
    return build_meta_feed(_df, currency=currency)


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_validate(fp: str, target: str, _df: pd.DataFrame) -> pd.DataFrame:
    return validate_feed(_df, target)


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_tsv(fp: str, _df: pd.DataFrame) -> bytes:
    return _df.to_csv(index=False, sep="\t").encode("utf-8")


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_csv(fp: str, _df: pd.DataFrame) -> bytes:
    return _df.to_csv(index=False).encode("utf-8")


@st.cache_data(show_spinner=False, max_entries=8)
def _cached_xml(fp: str, title: str, _df: pd.DataFrame) -> bytes:
    return to_gmc_xml(_df, title).encode("utf-8")


@st.cache_data(show_spinner=False, max_entries=4)
def _cached_xlsx(fp: str, sheet: str, _df: pd.DataFrame) -> bytes:
    return to_excel_bytes({sheet: _df})

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

    if qs.gtin.get('invalid') and "gtin" in df.columns:
        gtin_str = df["gtin"].fillna("").apply(lambda v: str(v) if v is not None else "")
        # Maschera: GTIN presente con lunghezza valida ma checksum KO (isValidGtin false)
        from utils.validation import is_valid_gtin
        mask = gtin_str.apply(
            lambda x: bool(x.strip())
                      and len(x.strip().split('.')[0]) in (8, 12, 13, 14)
                      and not is_valid_gtin(x)
        )
        bad = df[mask].head(20)
        if not bad.empty:
            st.markdown("**GTIN con checksum invalido** (primi 20)")
            st.dataframe(
                bad[[c for c in ("id", "brand", "title", "gtin") if c in bad.columns]],
                use_container_width=True, height=240,
            )

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
# BUILD (cached)
# ============================================================
_fp = _df_fingerprint(df)
google_df = _cached_build_google(_fp, currency, df) if target_platform in ("Google", "Entrambi") else None
meta_df = _cached_build_meta(_fp, currency, df) if target_platform in ("Meta", "Entrambi") else None

# Fingerprint dei feed costruiti per cache dei serializer
_fp_google = _df_fingerprint(google_df) if google_df is not None else ""
_fp_meta = _df_fingerprint(meta_df) if meta_df is not None else ""

# ============================================================
# DOWNLOAD RAPIDO — in cima, prima delle validation/quality tabs
# ============================================================
st.markdown(
    "<div style='background:linear-gradient(135deg, #2F6FED 0%, #1A4BB5 100%); "
    "border-radius:14px; padding:18px 22px; color:#fff; margin:14px 0;'>"
    "<div style='font-weight:700; font-size:1.05rem;'>📥 Scarica feed supplementari</div>"
    "<div style='font-size:0.85rem; opacity:0.92; margin-top:4px;'>"
    "Nomi colonna = spec ufficiale. Upload diretto su Merchant Center / Commerce Manager."
    "</div></div>",
    unsafe_allow_html=True,
)
dlc1, dlc2, dlc3, dlc4 = st.columns(4)
# Lazy pattern: TSV/CSV veloci → OK pre-computare. XML più pesante → generato
# al volo solo quando l'utente apre un expander dedicato.
if google_df is not None:
    dlc1.download_button(
        "⬇️ TSV Google",
        _cached_tsv(_fp_google, google_df),
        file_name="google_feed.tsv",
        mime="text/tab-separated-values",
        use_container_width=True, type="primary",
        help="Formato preferito Google Merchant Center (TSV tab-separated).",
    )
    with dlc2:
        if st.toggle("XML Google RSS", key="_toggle_xml_google",
                      help="Genera XML al volo (più lento su feed grandi)."):
            st.download_button(
                "⬇️ XML Google RSS",
                _cached_xml(_fp_google, "Google Feed", google_df),
                file_name="google_feed.xml", mime="application/xml",
                use_container_width=True,
            )
if meta_df is not None:
    dlc3.download_button(
        "⬇️ CSV Meta",
        _cached_csv(_fp_meta, meta_df),
        file_name="meta_feed.csv", mime="text/csv",
        use_container_width=True, type="primary",
        help="Meta Commerce Manager: Cataloghi → Aggiungi prodotti → Da file.",
    )
    with dlc4:
        if st.toggle("XML Meta", key="_toggle_xml_meta",
                      help="Genera XML al volo (più lento su feed grandi)."):
            st.download_button(
                "⬇️ XML Meta",
                _cached_xml(_fp_meta, "Meta Feed", meta_df),
                file_name="meta_feed.xml", mime="application/xml",
                use_container_width=True,
            )

st.caption(
    f"Google: **{len(google_df) if google_df is not None else 0}** prodotti · "
    f"Meta: **{len(meta_df) if meta_df is not None else 0}** prodotti · "
    f"Per Excel, escludi colonne, validation report, delta diff e bundle ZIP: vedi sezioni sotto."
)

st.divider()

# ============================================================
# GOOGLE PANEL
# ============================================================
if google_df is not None:
    st.subheader("🛒 Google Merchant Center")
    val = _cached_validate(_fp_google, "google", google_df)

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
        ex_g = st.multiselect(
            "🧹 Escludi colonne dall'export Google",
            options=list(google_df.columns), default=[],
            key="_scarica_excl_google",
            help="Colonne selezionate non saranno incluse in TSV/CSV/XML/Excel generati qui.",
        )
        _gd = google_df.drop(columns=ex_g, errors="ignore") if ex_g else google_df
        _fp_gd = _df_fingerprint(_gd) if ex_g else _fp_google

        # Lazy: TSV/CSV veloci precomputed (cache). XML/Excel generati on-demand.
        e1, e2, e3, e4 = st.columns(4)
        e1.download_button(f"CSV (TSV per GMC) · {len(_gd.columns)} col.",
                            _cached_tsv(_fp_gd, _gd),
                            "google_feed.tsv", "text/tab-separated-values",
                            use_container_width=True,
                            help="GMC accetta TSV (tab-separated) come formato preferito")
        with e2:
            if st.toggle("Excel", key="_toggle_xlsx_google",
                          help="Build xlsx al volo (lento su feed grandi)."):
                st.download_button("⬇️ Excel",
                                    _cached_xlsx(_fp_gd, "google_feed", _gd),
                                    "google_feed.xlsx",
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True)
        with e3:
            if st.toggle("XML (RSS 2.0 GMC)", key="_toggle_xml_google_exp"):
                st.download_button("⬇️ XML",
                                    _cached_xml(_fp_gd, "Google Feed", _gd),
                                    "google_feed.xml", "application/xml",
                                    use_container_width=True)
        e4.download_button("CSV standard",
                            _cached_csv(_fp_gd, _gd),
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
    val = _cached_validate(_fp_meta, "meta", meta_df)

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
        ex_m = st.multiselect(
            "🧹 Escludi colonne dall'export Meta",
            options=list(meta_df.columns), default=[],
            key="_scarica_excl_meta",
            help="Colonne selezionate non saranno incluse in CSV/XML/Excel.",
        )
        _md = meta_df.drop(columns=ex_m, errors="ignore") if ex_m else meta_df
        _fp_md = _df_fingerprint(_md) if ex_m else _fp_meta

        e1, e2, e3 = st.columns(3)
        e1.download_button(f"CSV (Meta format) · {len(_md.columns)} col.",
                            _cached_csv(_fp_md, _md),
                            "meta_feed.csv", "text/csv",
                            use_container_width=True)
        with e2:
            if st.toggle("Excel", key="_toggle_xlsx_meta"):
                st.download_button("⬇️ Excel",
                                    _cached_xlsx(_fp_md, "meta_feed", _md),
                                    "meta_feed.xlsx",
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                    use_container_width=True)
        with e3:
            if st.toggle("XML", key="_toggle_xml_meta_exp"):
                st.download_button("⬇️ XML",
                                    _cached_xml(_fp_md, "Meta Feed", _md),
                                    "meta_feed.xml", "application/xml",
                                    use_container_width=True)

        st.info("**Come usarlo**: Commerce Manager → Cataloghi → Aggiungi prodotti → "
                "Da file di dati. Meta supporta CSV, TSV, XML, Google Sheets.")

# ============================================================
# EXPORT DIFF — delta vs ultima export
# ============================================================
from utils import export_diff

st.divider()
st.subheader("🔄 Export diff — solo prodotti modificati dall'ultimo export")
st.caption(
    "Riduci le upload incrementali a Google Merchant / Meta caricando solo prodotti nuovi "
    "o modificati rispetto all'ultimo snapshot salvato."
)

if "session_id" not in st.session_state:
    st.info("Diff disponibile solo dentro una sessione (salvataggio progetto richiesto).")
else:
    session_id = st.session_state["session_id"]
    dc1, dc2 = st.columns(2)

    if google_df is not None:
        with dc1:
            st.markdown("**Google**")
            diff = export_diff.compute_diff(session_id, "google", google_df)
            if not diff["has_snapshot"]:
                st.caption("_Nessuno snapshot precedente. Crea il baseline ora._")
            else:
                m = st.columns(3)
                m[0].metric("Nuovi", len(diff["added"]))
                m[1].metric("Modificati", len(diff["modified"]))
                m[2].metric("Rimossi", len(diff["removed"]))
                if not diff["delta_df"].empty:
                    delta_tsv = diff["delta_df"].to_csv(index=False, sep="\t").encode("utf-8")
                    st.download_button(
                        "⬇️ Delta TSV (Google)",
                        delta_tsv,
                        file_name=f"google_delta_{len(diff['delta_df'])}items.tsv",
                        mime="text/tab-separated-values",
                        use_container_width=True,
                    )
            if st.button("Salva snapshot baseline (Google)", key="_snap_google",
                          use_container_width=True):
                export_diff.save_snapshot(session_id, "google", google_df)
                st.toast("Baseline Google aggiornato", icon="📸")
                st.rerun()

    if meta_df is not None:
        with dc2:
            st.markdown("**Meta**")
            diff = export_diff.compute_diff(session_id, "meta", meta_df)
            if not diff["has_snapshot"]:
                st.caption("_Nessuno snapshot precedente. Crea il baseline ora._")
            else:
                m = st.columns(3)
                m[0].metric("Nuovi", len(diff["added"]))
                m[1].metric("Modificati", len(diff["modified"]))
                m[2].metric("Rimossi", len(diff["removed"]))
                if not diff["delta_df"].empty:
                    delta_csv = diff["delta_df"].to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇️ Delta CSV (Meta)",
                        delta_csv,
                        file_name=f"meta_delta_{len(diff['delta_df'])}items.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
            if st.button("Salva snapshot baseline (Meta)", key="_snap_meta",
                          use_container_width=True):
                export_diff.save_snapshot(session_id, "meta", meta_df)
                st.toast("Baseline Meta aggiornato", icon="📸")
                st.rerun()

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
            zf.writestr("google/google_feed.tsv", _cached_tsv(_fp_google, google_df))
            zf.writestr("google/google_feed.csv", _cached_csv(_fp_google, google_df))
            zf.writestr("google/google_feed.xml", _cached_xml(_fp_google, "Google Feed", google_df))
            zf.writestr("google/google_feed.xlsx", _cached_xlsx(_fp_google, "google_feed", google_df))
            zf.writestr("google/validation_report.csv",
                         _cached_validate(_fp_google, "google", google_df).to_csv(index=False))
        if meta_df is not None:
            zf.writestr("meta/meta_feed.csv", _cached_csv(_fp_meta, meta_df))
            zf.writestr("meta/meta_feed.xml", _cached_xml(_fp_meta, "Meta Feed", meta_df))
            zf.writestr("meta/meta_feed.xlsx", _cached_xlsx(_fp_meta, "meta_feed", meta_df))
            zf.writestr("meta/validation_report.csv",
                         _cached_validate(_fp_meta, "meta", meta_df).to_csv(index=False))
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
