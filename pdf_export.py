"""
Logitech Brand Intelligence — PDF Export Module
Generates a professional multi-page PDF report.
Call generate_pdf_report(intel_df, scores_df, alerts, history_df) 
"""

from io import BytesIO
from datetime import datetime
import pandas as pd

from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph,
    Spacer, PageBreak, HRFlowable
)

# ─────────────────────────────────────────────
# Colour palette
# ─────────────────────────────────────────────
BLUE       = colors.HexColor("#1e40af")
LIGHT_BLUE = colors.HexColor("#dbeafe")
GREEN      = colors.HexColor("#16a34a")
RED        = colors.HexColor("#dc2626")
AMBER      = colors.HexColor("#d97706")
GREY       = colors.HexColor("#f1f5f9")
WHITE      = colors.white
BLACK      = colors.black


def _header_style(styles):
    return ParagraphStyle(
        "ReportHeader",
        parent=styles["Title"],
        fontSize=22,
        textColor=BLUE,
        spaceAfter=4,
    )

def _section_style(styles):
    return ParagraphStyle(
        "SectionHead",
        parent=styles["Heading2"],
        fontSize=13,
        textColor=BLUE,
        spaceBefore=12,
        spaceAfter=4,
    )

def _caption_style(styles):
    return ParagraphStyle(
        "Caption",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=6,
    )

def _table_style(header_color=None):
    hc = header_color or BLUE
    return TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0),  hc),
        ("TEXTCOLOR",    (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",     (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",     (0, 0), (-1, -1), 8),
        ("ROWBACKGROUNDS",(0,1), (-1, -1), [WHITE, GREY]),
        ("GRID",         (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("PADDING",      (0, 0), (-1, -1), 5),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ])


def generate_pdf_report(
    intel_df:   pd.DataFrame,
    scores_df:  pd.DataFrame,
    alerts:     dict,
    history_df: pd.DataFrame,
) -> BytesIO:
    """
    Build and return a PDF report as a BytesIO buffer.
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(letter),
        leftMargin=0.6*inch, rightMargin=0.6*inch,
        topMargin=0.6*inch,  bottomMargin=0.6*inch,
    )
    styles = getSampleStyleSheet()
    H   = _header_style(styles)
    S   = _section_style(styles)
    Cap = _caption_style(styles)
    N   = styles["Normal"]
    story = []

    now_str = datetime.now().strftime("%B %d, %Y  %H:%M")

    # ════════════════════════════════════════════
    # PAGE 1 — Cover + Executive Summary
    # ════════════════════════════════════════════
    story.append(Paragraph("Logitech Brand Intelligence Report", H))
    story.append(Paragraph(f"Generated: {now_str}", Cap))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=10))

    # KPI summary table
    story.append(Paragraph("Executive Summary", S))
    avg_price    = f"${intel_df['price'].mean():.2f}"     if not intel_df.empty and intel_df['price'].notna().any()        else "N/A"
    avg_rating   = f"{intel_df['rating'].mean():.2f} ★"  if not intel_df.empty and intel_df['rating'].notna().any()       else "N/A"
    total_reviews= f"{int(intel_df['review_count'].sum()):,}" if not intel_df.empty                                        else "N/A"
    in_stock_pct = f"{intel_df['in_stock'].mean()*100:.0f}%" if not intel_df.empty                                        else "N/A"
    avg_score    = f"{scores_df['opportunity_score'].mean():.1f}/100" if not scores_df.empty                              else "N/A"
    channels     = str(intel_df["channel_id"].nunique())  if not intel_df.empty else "0"
    products     = str(intel_df["product_id"].nunique())  if not intel_df.empty else "0"
    data_points  = str(len(intel_df))

    kpi_data = [
        ["Metric",                "Value",       "Metric",              "Value"],
        ["Avg Price",             avg_price,     "Avg Rating",          avg_rating],
        ["Total Reviews",         total_reviews, "In Stock %",          in_stock_pct],
        ["Avg Opportunity Score", avg_score,     "Channels with Data",  channels],
        ["Products Tracked",      products,      "Total Data Points",   data_points],
    ]
    kpi_table = Table(kpi_data, colWidths=[2.2*inch, 1.5*inch, 2.2*inch, 1.5*inch])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, 0),  BLUE),
        ("TEXTCOLOR",   (0, 0), (-1, 0),  WHITE),
        ("FONTNAME",    (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTNAME",    (0, 1), (0, -1),  "Helvetica-Bold"),
        ("FONTNAME",    (2, 1), (2, -1),  "Helvetica-Bold"),
        ("FONTSIZE",    (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),  [WHITE, GREY]),
        ("GRID",        (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
        ("PADDING",     (0, 0), (-1, -1), 6),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 0.2*inch))

    # Alert summary
    story.append(Paragraph("Alert Summary", S))
    alert_data = [
        ["Alert Type",          "Count", "Action Required"],
        ["🔴 Out of Stock",     str(len(alerts.get("oos", []))),         "Pause ad spend immediately"],
        ["📉 Price Drops",      str(len(alerts.get("price_drop", []))),  "Review pricing strategy"],
        ["📈 Price Spikes",     str(len(alerts.get("price_spike", []))), "Check above MSRP urgently"],
        ["⚠️ MAP Violations",  str(len(alerts.get("map", []))),         "Escalate to channel manager"],
        ["🏆 High Opportunity", str(len(alerts.get("high_opp", []))),   "Increase ad budget now"],
    ]
    at = Table(alert_data, colWidths=[2.5*inch, 1*inch, 4*inch])
    at.setStyle(_table_style())
    story.append(at)

    story.append(PageBreak())

    # ════════════════════════════════════════════
    # PAGE 2 — Opportunity Scores
    # ════════════════════════════════════════════
    story.append(Paragraph("Opportunity Scores Leaderboard", S))
    story.append(Paragraph(
        "Top product-channel combinations ranked by opportunity score. "
        "Score combines velocity, price competitiveness, distribution gap, and content quality.",
        Cap
    ))
    if not scores_df.empty:
        cols = ["product_name", "channel_name", "opportunity_score",
                "opportunity_tier", "ad_recommendation", "stock_risk", "action_notes"]
        avail = [c for c in cols if c in scores_df.columns]
        top = scores_df[avail].sort_values("opportunity_score", ascending=False).head(25)
        headers = [c.replace("_", " ").title() for c in avail]
        col_w   = [2.2*inch, 1.3*inch, 0.9*inch, 0.6*inch, 1.1*inch, 0.7*inch]
        if "action_notes" in avail:
            col_w.append(2.5*inch)
        rows = [headers] + [
            [str(round(v, 1)) if isinstance(v, float) else str(v) if v is not None else ""
             for v in row]
            for row in top.values.tolist()
        ]
        t = Table(rows, colWidths=col_w[:len(avail)], repeatRows=1)
        t.setStyle(_table_style())
        story.append(t)
    else:
        story.append(Paragraph("No opportunity scores available.", N))

    story.append(PageBreak())

    # ════════════════════════════════════════════
    # PAGE 3 — Price Intelligence
    # ════════════════════════════════════════════
    story.append(Paragraph("Price Intelligence", S))
    story.append(Paragraph(
        "Latest scraped prices across all channels. "
        "Negative discount % indicates price below MSRP (MAP risk).",
        Cap
    ))
    if not intel_df.empty:
        cols2 = ["product_name", "channel_name", "price", "original_price",
                 "discount_pct", "rating", "review_count", "in_stock"]
        avail2 = [c for c in cols2 if c in intel_df.columns]
        top2 = intel_df[avail2].sort_values("product_name").head(35)
        headers2 = [c.replace("_", " ").title() for c in avail2]
        col_w2 = [2.0*inch, 1.2*inch, 0.7*inch, 0.9*inch,
                  0.7*inch, 0.6*inch, 0.9*inch, 0.6*inch][:len(avail2)]
        rows2 = [headers2] + [
            [str(round(v, 2)) if isinstance(v, float) else str(v) if v is not None else ""
             for v in row]
            for row in top2.values.tolist()
        ]
        t2 = Table(rows2, colWidths=col_w2, repeatRows=1)
        t2.setStyle(_table_style())
        story.append(t2)
    else:
        story.append(Paragraph("No price data available.", N))

    story.append(PageBreak())

    # ════════════════════════════════════════════
    # PAGE 4 — Active Alerts Detail
    # ════════════════════════════════════════════
    story.append(Paragraph("Active Alerts Detail", S))

    def _alert_table(items, columns, title, header_color=None):
        if not items:
            return
        story.append(Paragraph(title, ParagraphStyle(
            "ah", parent=styles["Heading3"], fontSize=10,
            textColor=header_color or BLUE, spaceBefore=8
        )))
        df = pd.DataFrame(items)
        avail = [c for c in columns if c in df.columns]
        if not avail:
            return
        headers = [c.replace("_", " ").title() for c in avail]
        rows = [headers] + [
            [str(round(v, 2)) if isinstance(v, float) else str(v) if v is not None else ""
             for v in row]
            for row in df[avail].values.tolist()
        ]
        cw = [max(1.0, 9.5 / len(avail))*inch] * len(avail)
        t = Table(rows, colWidths=cw, repeatRows=1)
        t.setStyle(_table_style(header_color))
        story.append(t)
        story.append(Spacer(1, 0.1*inch))

    _alert_table(
        alerts.get("oos", []),
        ["product", "channel", "last_price", "scraped_at"],
        "🔴 Out of Stock", RED
    )
    _alert_table(
        alerts.get("price_drop", []),
        ["product", "channel", "old_price", "new_price", "change_pct"],
        "📉 Price Drops", GREEN
    )
    _alert_table(
        alerts.get("price_spike", []),
        ["product", "channel", "old_price", "new_price", "change_pct"],
        "📈 Price Spikes", AMBER
    )
    _alert_table(
        alerts.get("map", []),
        ["product", "channel", "price", "msrp", "below_pct"],
        "⚠️ MAP Violations", RED
    )
    _alert_table(
        alerts.get("high_opp", []),
        ["product", "channel", "score", "tier", "ad_rec"],
        "🏆 High Opportunity", BLUE
    )

    # ── Footer note ───────────────────────────────────────────
    story.append(Spacer(1, 0.3*inch))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BLUE))
    story.append(Paragraph(
        f"Logitech Brand Intelligence Platform — Confidential  |  {now_str}",
        Cap
    ))

    doc.build(story)
    buf.seek(0)
    return buf