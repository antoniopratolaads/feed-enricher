"""Generatore PDF report con KPI, alert, top/flop tables."""
from __future__ import annotations
import io
from datetime import datetime
import pandas as pd

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

PRIMARY = colors.HexColor("#6C5CE7")
ACCENT = colors.HexColor("#00D9A3")
DARK = colors.HexColor("#1A1D24")
LIGHT = colors.HexColor("#F5F5F8")
MUTED = colors.HexColor("#6B7280")


def _styles():
    s = getSampleStyleSheet()
    s.add(ParagraphStyle(name="Hero", fontName="Helvetica-Bold", fontSize=28,
                         textColor=PRIMARY, alignment=TA_LEFT, spaceAfter=8))
    s.add(ParagraphStyle(name="Sub", fontName="Helvetica", fontSize=11,
                         textColor=MUTED, spaceAfter=20))
    s.add(ParagraphStyle(name="H1", fontName="Helvetica-Bold", fontSize=16,
                         textColor=DARK, spaceBefore=18, spaceAfter=10,
                         borderPadding=6, leftIndent=0))
    s.add(ParagraphStyle(name="H2", fontName="Helvetica-Bold", fontSize=12,
                         textColor=PRIMARY, spaceBefore=10, spaceAfter=6))
    s.add(ParagraphStyle(name="Body2", fontName="Helvetica", fontSize=10,
                         textColor=DARK, spaceAfter=6, leading=14))
    return s


def _kpi_card(label, value, accent=PRIMARY):
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
        ("LINEABOVE", (0, 0), (-1, 0), 3, accent),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), MUTED),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, 1), 16),
        ("TEXTCOLOR", (0, 1), (-1, 1), DARK),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ])
    t = Table([[label.upper()], [value]], colWidths=[4.2 * cm], rowHeights=[0.7 * cm, 1 * cm])
    t.setStyle(style)
    return t


def _kpi_row(items):
    """items = [(label, value, color), ...]"""
    cards = [_kpi_card(l, v, c) for l, v, c in items]
    t = Table([cards], colWidths=[4.5 * cm] * len(cards))
    t.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 4),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    return t


def _table_from_df(df: pd.DataFrame, max_rows: int = 15, col_widths=None):
    df = df.head(max_rows).copy()
    for c in df.columns:
        df[c] = df[c].astype(str).str[:40]
    data = [list(df.columns)] + df.values.tolist()
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), PRIMARY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return t


def build_report(df: pd.DataFrame, labels: dict | None = None) -> bytes:
    """Costruisce un PDF report. df = catalogo (con eventuale GAds/Shopify)."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=1.5 * cm, rightMargin=1.5 * cm,
                            topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    s = _styles()
    el = []

    # ---------- COVER ----------
    el.append(Paragraph("Feed Enricher Pro", s["Hero"]))
    el.append(Paragraph(f"Report generato il {datetime.now().strftime('%d/%m/%Y %H:%M')}", s["Sub"]))

    # ---------- KPI ----------
    el.append(Paragraph("Overview catalogo", s["H1"]))
    total = len(df)
    in_stock = df["availability"].astype(str).str.contains("in stock|in_stock", case=False, na=False).sum() \
        if "availability" in df.columns else 0
    brands_n = df["brand"].nunique() if "brand" in df.columns else 0
    missing_img = df["image_link"].astype(str).str.strip().eq("").sum() if "image_link" in df.columns else 0

    el.append(_kpi_row([
        ("Prodotti", f"{total:,}", PRIMARY),
        ("In stock", f"{in_stock:,}", ACCENT),
        ("Brand", str(brands_n), PRIMARY),
        ("No image", f"{missing_img:,}", colors.HexColor("#FF6B6B") if missing_img else ACCENT),
    ]))
    el.append(Spacer(1, 12))

    if "clicks" in df.columns:
        cost = df["cost"].sum(); val = df["conv_value"].sum()
        el.append(_kpi_row([
            ("Spesa GAds", f"€{cost:,.0f}", PRIMARY),
            ("Conv. value", f"€{val:,.0f}", ACCENT),
            ("ROAS", f"{val/cost if cost else 0:.2f}x", ACCENT if (val/cost if cost else 0) >= 2 else colors.HexColor("#FF6B6B")),
            ("Clicks", f"{int(df['clicks'].sum()):,}", PRIMARY),
        ]))
        el.append(Spacer(1, 12))

    if "shopify_units_sold" in df.columns:
        units = int(df["shopify_units_sold"].sum())
        rev = df["shopify_revenue"].sum() if "shopify_revenue" in df.columns else 0
        with_sales = (df["shopify_units_sold"] > 0).sum()
        el.append(_kpi_row([
            ("Unità vendute", f"{units:,}", ACCENT),
            ("Revenue Shopify", f"€{rev:,.0f}", ACCENT),
            ("Prodotti venduti", f"{with_sales:,}", PRIMARY),
            ("% catalogo attivo", f"{with_sales/total*100:.0f}%", PRIMARY),
        ]))
        el.append(Spacer(1, 12))

    # ---------- ALERTS ----------
    el.append(Paragraph("Alert & insight", s["H1"]))
    alerts = []
    if "clicks" in df.columns:
        zombie = ((df["clicks"] >= 30) & (df["conversions"] == 0)).sum()
        if zombie > 0:
            zc = df.loc[(df["clicks"] >= 30) & (df["conversions"] == 0), "cost"].sum()
            alerts.append(f"<b>{zombie} prodotti zombie</b> (≥30 click, 0 conv) bruciano <b>€{zc:,.0f}</b>")
    if missing_img > 0:
        alerts.append(f"<b>{missing_img} prodotti</b> senza image_link — saranno rifiutati da GMC")
    if "google_product_category" in df.columns:
        no_cat = df["google_product_category"].astype(str).str.strip().eq("").sum()
        if no_cat > 0:
            alerts.append(f"<b>{no_cat} prodotti</b> senza google_product_category — l'enrichment AI può colmare il gap")
    if "shopify_units_sold" in df.columns:
        no_sales = (df["shopify_units_sold"] == 0).sum()
        if no_sales > 0:
            alerts.append(f"<b>{no_sales} prodotti ({no_sales/total*100:.0f}%)</b> senza vendite Shopify")

    if not alerts:
        alerts = ["Nessun alert critico."]
    for a in alerts:
        el.append(Paragraph("• " + a, s["Body2"]))

    el.append(PageBreak())

    # ---------- TOP BRAND ----------
    if "brand" in df.columns:
        el.append(Paragraph("Top 10 brand per prodotti", s["H1"]))
        top = df["brand"].value_counts().head(10).reset_index()
        top.columns = ["Brand", "Prodotti"]
        if "shopify_revenue" in df.columns:
            rev_brand = df.groupby("brand")["shopify_revenue"].sum().to_dict()
            top["Revenue €"] = top["Brand"].map(lambda b: f"{rev_brand.get(b, 0):,.0f}")
        el.append(_table_from_df(top, max_rows=10, col_widths=[6 * cm, 3 * cm, 4 * cm]))
        el.append(Spacer(1, 18))

    # ---------- TOP ROAS ----------
    if "clicks" in df.columns:
        el.append(Paragraph("Top 10 prodotti per ROAS", s["H1"]))
        sub = df[df["cost"] > 0].copy()
        sub["roas"] = sub["conv_value"] / sub["cost"]
        cols_avail = [c for c in ["id", "title", "brand", "cost", "conv_value", "roas"] if c in sub.columns]
        top_roas = sub.nlargest(10, "roas")[cols_avail]
        top_roas["cost"] = top_roas["cost"].round(2)
        top_roas["conv_value"] = top_roas["conv_value"].round(2)
        top_roas["roas"] = top_roas["roas"].round(2)
        el.append(_table_from_df(top_roas, max_rows=10))
        el.append(Spacer(1, 18))

        el.append(Paragraph("Prodotti zombie (≥30 click, 0 conv)", s["H1"]))
        zomb = df[(df["clicks"] >= 30) & (df["conversions"] == 0)].nlargest(10, "cost")
        cols_z = [c for c in ["id", "title", "brand", "clicks", "cost"] if c in zomb.columns]
        if len(zomb):
            el.append(_table_from_df(zomb[cols_z], max_rows=10))
        else:
            el.append(Paragraph("Nessun prodotto zombie identificato.", s["Body2"]))

    # ---------- LABELS ----------
    if labels:
        el.append(PageBreak())
        el.append(Paragraph("Custom Labels generate", s["H1"]))
        for name, series in labels.items():
            el.append(Paragraph(name, s["H2"]))
            dist = series.value_counts().reset_index()
            dist.columns = ["valore", "count"]
            dist["%"] = (dist["count"] / dist["count"].sum() * 100).round(1).astype(str) + "%"
            el.append(_table_from_df(dist, max_rows=10, col_widths=[6 * cm, 3 * cm, 3 * cm]))
            el.append(Spacer(1, 10))

    doc.build(el)
    return buf.getvalue()
