"""Pagina 8: esporta feed supplementare con le label scelte mappate su custom_label_0..4."""
import streamlit as st
import pandas as pd

from utils.state import init_state, current_df
from utils.ui import apply_theme
from utils.exporter import supplemental_feed, to_excel_bytes, to_gmc_xml
from utils.pdf_report import build_report

init_state()
apply_theme()

st.title("9. Feed Supplementare")
st.caption("Scegli quali label mappare su custom_label_0..4 ed esporta")

df = current_df()
labels = st.session_state.get("labels", {})

if df is None:
    st.warning("Carica un feed.")
    st.stop()

if not labels:
    st.warning("Nessuna label salvata. Vai nelle pagine **Labels** e clicca 'Salva' su quelle che vuoi usare.")
    st.stop()

st.subheader("Mappatura custom_label")
st.caption("Puoi mappare fino a 5 custom_label (0-4) in Google Merchant Center")

label_names = list(labels.keys())
mapping = {}
cols = st.columns(5)
for i in range(5):
    with cols[i]:
        choice = st.selectbox(
            f"custom_label_{i}",
            options=["—"] + label_names,
            key=f"cl_{i}",
        )
        if choice != "—":
            mapping[f"custom_label_{i}"] = choice

id_col = st.selectbox("Colonna ID", options=df.columns,
                      index=list(df.columns).index("id") if "id" in df.columns else 0)

st.divider()
st.subheader("Varianti Meta")
st.caption("Per Meta Catalog usa i titoli/descrizioni specifici (più lunghi). Se non spunti, usa i campi Google standard.")

overrides = {}
oc = st.columns(2)
if "title_meta" in df.columns and oc[0].checkbox("Usa `title_meta` (≤200 char) per Meta"):
    overrides["title"] = "title_meta"
if "description_meta_short" in df.columns and oc[1].checkbox("Usa `description_meta_short` per Meta short_description"):
    overrides["description"] = "description_meta_short"

# costruzione dataframe per export
working = df.copy()
for target_label, label_name in mapping.items():
    working[target_label] = labels[label_name].reindex(working.index)

extra = list(mapping.keys())
# sostituzioni override
for target, source in overrides.items():
    working[target] = working[source].where(working[source].astype(str).str.strip() != "", working.get(target, ""))
    extra.append(target)

supp = supplemental_feed(working, id_col=id_col, label_mapping=None, extra_cols=list(dict.fromkeys(extra)))
# aggiungi id come prima colonna se non c'è
if "id" not in supp.columns:
    supp.insert(0, "id", working[id_col])

st.subheader("Anteprima feed supplementare")
st.dataframe(supp.head(100), use_container_width=True, height=400)
st.metric("Righe", len(supp))

st.divider()
st.subheader("Export")

c1, c2, c3, c4, c5 = st.columns(5)

sheets = {"supplemental_feed": supp}
# foglio separato per ogni label salvata (come chiesto: "mi gestisco io quali inserire come fogli supplementari")
for name, series in labels.items():
    single = pd.DataFrame({"id": working[id_col], name: series.reindex(working.index)})
    sheets[name[:31]] = single

xlsx = to_excel_bytes(sheets)
c1.download_button("Excel (multi-foglio)", data=xlsx,
                   file_name="feed_supplementare.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                   use_container_width=True)

c2.download_button("CSV (feed principale)", data=supp.to_csv(index=False).encode("utf-8"),
                   file_name="feed_supplementare.csv", mime="text/csv",
                   use_container_width=True)

xml = to_gmc_xml(supp, title="Supplemental Feed")
c3.download_button("XML GMC", data=xml.encode("utf-8"),
                   file_name="feed_supplementare.xml",
                   mime="application/xml", use_container_width=True)

c4.download_button("JSON", data=supp.to_json(orient="records", force_ascii=False).encode("utf-8"),
                   file_name="feed_supplementare.json", mime="application/json",
                   use_container_width=True)

try:
    pdf_bytes = build_report(working, labels)
    c5.download_button("PDF Report", data=pdf_bytes, file_name="feed_report.pdf",
                       mime="application/pdf", use_container_width=True)
except Exception as e:
    c5.button("PDF (errore)", disabled=True, use_container_width=True)

st.info("Per caricarlo in **Google Merchant Center**: Feed → Feed supplementari → Aggiungi nuovo → "
        "scegli Google Sheets o Upload. Il CSV/Excel è pronto per essere importato come Google Sheet.")
