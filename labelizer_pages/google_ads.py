"""Pagina 3: Import performance da Google Ads Script + script pronto all'uso."""
import streamlit as st
import pandas as pd
import io

from utils.state import init_state, current_df
from utils.ui import apply_theme

init_state()
apply_theme()

st.title("2. Google Ads · Performance")
st.caption("OPZIONALE — Senza GAds puoi comunque usare Enrichment AI, Shopify e tutte le label non-performance. Salta pure se non ti serve.")
st.info("**Step opzionale.** Puoi andare direttamente a *3. Shopify* o *4. Enrichment AI* se non hai/non vuoi caricare dati Google Ads. Le pagine label che richiedono GAds te lo segnaleranno e potrai usare le altre.")

tab1, tab2 = st.tabs(["Script Google Ads (copia/incolla)", "Upload dati performance"])

# ------------ TAB 1: SCRIPT ------------
with tab1:
    st.markdown("""
    ### Come usarlo
    1. Vai su **Google Ads → Strumenti → Scripts → Nuovo script**
    2. Incolla lo script qui sotto
    3. Modifica la variabile `LOOKBACK_DAYS` se vuoi
    4. **Esegui** → genera un Google Sheet con le performance per `offer_id`
    5. Scarica come CSV e caricalo nel tab "Upload dati performance"
    """)

    script = '''// Google Ads Script - Export Shopping Performance per prodotto
// Periodo e livello di dettaglio configurabili

var LOOKBACK_DAYS = 30;       // giorni da analizzare
var SHEET_NAME = "GAds_Product_Performance";
var INCLUDE_ASSET_GROUPS = true;  // per PMax

function main() {
  var end = new Date();
  var start = new Date();
  start.setDate(end.getDate() - LOOKBACK_DAYS);
  var sdate = Utilities.formatDate(start, "UTC", "yyyyMMdd");
  var edate = Utilities.formatDate(end, "UTC", "yyyyMMdd");

  var query =
    "SELECT segments.product_item_id, segments.product_title, " +
    "segments.product_brand, segments.product_type_l1, segments.product_type_l2, " +
    "metrics.impressions, metrics.clicks, metrics.cost_micros, " +
    "metrics.conversions, metrics.conversions_value " +
    "FROM shopping_performance_view " +
    "WHERE segments.date BETWEEN '" + sdate + "' AND '" + edate + "' " +
    "AND segments.product_item_id != ''";

  var rows = [[
    "product_id", "title", "brand", "product_type_l1", "product_type_l2",
    "impressions", "clicks", "cost", "conversions", "conv_value",
    "ctr", "cpc", "cvr", "roas"
  ]];

  var it = AdsApp.search(query);
  while (it.hasNext()) {
    var r = it.next();
    var s = r.segments, m = r.metrics;
    var impr = Number(m.impressions || 0);
    var clicks = Number(m.clicks || 0);
    var cost = Number(m.costMicros || 0) / 1e6;
    var conv = Number(m.conversions || 0);
    var val = Number(m.conversionsValue || 0);
    rows.push([
      s.productItemId, s.productTitle || "", s.productBrand || "",
      s.productTypeL1 || "", s.productTypeL2 || "",
      impr, clicks, cost, conv, val,
      impr ? clicks/impr : 0,
      clicks ? cost/clicks : 0,
      clicks ? conv/clicks : 0,
      cost ? val/cost : 0
    ]);
  }

  var ss = SpreadsheetApp.create(SHEET_NAME + " " + sdate + "-" + edate);
  var sh = ss.getActiveSheet();
  sh.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
  sh.getRange(1, 1, 1, rows[0].length).setFontWeight("bold");
  Logger.log("Sheet creato: " + ss.getUrl());
}
'''
    st.code(script, language="javascript")

    st.download_button(
        "Scarica script .js",
        data=script.encode("utf-8"),
        file_name="gads_product_performance.js",
        mime="text/javascript",
    )

# ------------ TAB 2: UPLOAD ------------
with tab2:
    up = st.file_uploader("CSV o Excel dal Google Sheet generato dallo script", type=["csv", "xlsx", "tsv"])
    if up is not None:
        try:
            if up.name.endswith((".xlsx",)):
                gads = pd.read_excel(up)
            else:
                gads = pd.read_csv(up, sep=None, engine="python")
            gads.columns = [c.lower().strip().replace(" ", "_") for c in gads.columns]
            st.session_state["gads_df"] = gads
            st.success(f"Caricati {len(gads):,} record performance")
            st.dataframe(gads.head(50), use_container_width=True)
        except Exception as e:
            st.error(f"Errore: {e}")

    gads = st.session_state.get("gads_df")
    if gads is not None:
        st.divider()
        st.subheader("Merge con catalogo")

        base = current_df()
        if base is None:
            st.warning("Carica prima un feed.")
        else:
            feed_id_col = st.selectbox("Colonna ID nel feed", options=list(base.columns),
                                       index=list(base.columns).index("id") if "id" in base.columns else 0)
            gads_id_col = st.selectbox("Colonna ID nei dati GAds", options=list(gads.columns),
                                       index=list(gads.columns).index("product_id") if "product_id" in gads.columns else 0)

            if st.button("Esegui merge", type="primary"):
                metric_cols = [c for c in ["impressions", "clicks", "cost", "conversions",
                                            "conv_value", "ctr", "cpc", "cvr", "roas"]
                               if c in gads.columns]
                merged = base.merge(
                    gads[[gads_id_col] + metric_cols].rename(columns={gads_id_col: feed_id_col}),
                    on=feed_id_col, how="left",
                )
                for c in metric_cols:
                    merged[c] = pd.to_numeric(merged[c], errors="coerce").fillna(0)
                st.session_state["merged_df"] = merged
                st.success(f"Merge completato: {len(merged):,} righe, "
                           f"{(merged['clicks'] > 0).sum() if 'clicks' in merged.columns else 0} con traffico")

                st.dataframe(merged.head(50), use_container_width=True)
