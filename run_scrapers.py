"""
Logitech Brand Intelligence Platform — Streamlit Dashboard
Run: streamlit run dashboard.py
"""

import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime
from io import BytesIO

# ── ReportLab for PDF export ──────────────────────────────────
try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph,
        Spacer, PageBreak
    )
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

DB_PATH = "logitech_intelligence.db"

# ════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Logitech Brand Intelligence",
    page_icon="🖱️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .metric-card {
        background: #1e1e2e; border-radius: 12px;
        padding: 16px 20px; margin-bottom: 8px;
    }
    .tier-A { color: #22c55e; font-weight: 700; }
    .tier-B { color: #3b82f6; font-weight: 700; }
    .tier-C { color: #f59e0b; font-weight: 700; }
    .tier-D { color: #ef4444; font-weight: 700; }
    .stDataFrame { font-size: 13px; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# DATA LOADING
# ════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    intel = pd.read_sql_query("""
        SELECT * FROM v_latest_intelligence
        WHERE scrape_status = 'success'
    """, conn)

    scores = pd.read_sql_query("""
        SELECT * FROM v_latest_scores
    """, conn)

    products = pd.read_sql_query("SELECT * FROM products", conn)
    channels = pd.read_sql_query("SELECT * FROM retail_channels", conn)

    runs = pd.read_sql_query("""
        SELECT * FROM scrape_runs ORDER BY started_at DESC LIMIT 10
    """, conn)

    conn.close()
    return intel, scores, products, channels, runs


def get_tier_color(tier):
    return {"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"}.get(tier, "#888")


# ════════════════════════════════════════════════════════════════
# PDF EXPORT
# ════════════════════════════════════════════════════════════════
def generate_pdf(intel_df, scores_df):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(letter),
                            leftMargin=0.5*inch, rightMargin=0.5*inch,
                            topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet()
    story = []

    # Title
    title_style = ParagraphStyle("title", parent=styles["Title"],
                                  fontSize=20, textColor=colors.HexColor("#1e40af"),
                                  spaceAfter=6)
    story.append(Paragraph("Logitech Brand Intelligence Report", title_style))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y %H:%M')}",
        styles["Normal"]
    ))
    story.append(Spacer(1, 0.2*inch))

    # Summary stats
    sub = ParagraphStyle("sub", parent=styles["Heading2"],
                          fontSize=13, textColor=colors.HexColor("#1e40af"))
    story.append(Paragraph("Executive Summary", sub))
    summary_data = [
        ["Metric", "Value"],
        ["Total Products Tracked", str(intel_df["product_id"].nunique())],
        ["Total Channels with Data", str(intel_df["channel_id"].nunique())],
        ["Total Data Points", str(len(intel_df))],
        ["Avg Price (USD)", f"${intel_df['price'].mean():.2f}" if not intel_df['price'].isnull().all() else "N/A"],
        ["Avg Rating", f"{intel_df['rating'].mean():.2f}" if not intel_df['rating'].isnull().all() else "N/A"],
        ["In Stock %", f"{intel_df['in_stock'].mean()*100:.1f}%"],
    ]
    t = Table(summary_data, colWidths=[3*inch, 2*inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e40af")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ("PADDING", (0,0), (-1,-1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.3*inch))

    # Opportunity scores table
    story.append(Paragraph("Opportunity Scores by Product & Channel", sub))
    if not scores_df.empty:
        cols = ["product_name", "channel_name", "opportunity_score",
                "opportunity_tier", "ad_recommendation", "stock_risk"]
        available = [c for c in cols if c in scores_df.columns]
        top = scores_df[available].sort_values("opportunity_score", ascending=False).head(30)
        header = [c.replace("_", " ").title() for c in available]
        table_data = [header] + top.values.tolist()
        col_w = [2.5*inch, 1.5*inch, 1*inch, 0.7*inch, 1.2*inch, 0.8*inch][:len(available)]
        t2 = Table(table_data, colWidths=col_w, repeatRows=1)
        t2.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e40af")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(t2)
        story.append(PageBreak())

    # Price intelligence table
    story.append(Paragraph("Price Intelligence by Product & Channel", sub))
    if not intel_df.empty:
        cols2 = ["product_name", "channel_name", "price", "original_price",
                 "discount_pct", "rating", "review_count", "in_stock"]
        available2 = [c for c in cols2 if c in intel_df.columns]
        top2 = intel_df[available2].sort_values("product_name").head(40)
        header2 = [c.replace("_", " ").title() for c in available2]
        table_data2 = [header2] + [
            [str(round(v, 2)) if isinstance(v, float) else str(v) for v in row]
            for row in top2.values.tolist()
        ]
        col_w2 = [2.2*inch, 1.2*inch, 0.7*inch, 0.9*inch,
                  0.7*inch, 0.6*inch, 0.9*inch, 0.6*inch][:len(available2)]
        t3 = Table(table_data2, colWidths=col_w2, repeatRows=1)
        t3.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#1e40af")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 8),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#f1f5f9")]),
            ("GRID", (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
            ("PADDING", (0,0), (-1,-1), 4),
        ]))
        story.append(t3)

    doc.build(story)
    buf.seek(0)
    return buf


# ════════════════════════════════════════════════════════════════
# MAIN APP
# ════════════════════════════════════════════════════════════════
def main():
    intel_df, scores_df, products_df, channels_df, runs_df = load_data()

    # ── Sidebar ──────────────────────────────────────────────
    with st.sidebar:
        st.image("https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Logitech_logo.svg/320px-Logitech_logo.svg.png", width=160)
        st.title("Brand Intelligence")
        st.markdown("---")

        categories = ["All"] + sorted(products_df["category"].unique().tolist())
        sel_category = st.selectbox("Category", categories)

        all_channels = sorted(intel_df["channel_id"].unique().tolist()) if not intel_df.empty else []
        sel_channels = st.multiselect("Channels", all_channels, default=all_channels)

        st.markdown("---")
        st.markdown("**Last Runs**")
        if not runs_df.empty:
            for _, run in runs_df.head(3).iterrows():
                st.markdown(
                    f"🕐 `{run['started_at'][:16]}` — "
                    f"{run['total_success']}/{run['total_scraped']} ✓"
                )

        st.markdown("---")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    # ── Filter data ───────────────────────────────────────────
    filtered_intel = intel_df.copy()
    filtered_scores = scores_df.copy()

    if sel_category != "All" and not filtered_intel.empty:
        filtered_intel = filtered_intel[filtered_intel["product_category"] == sel_category]
        filtered_scores = filtered_scores[filtered_scores["product_category"] == sel_category]

    if sel_channels and not filtered_intel.empty:
        filtered_intel = filtered_intel[filtered_intel["channel_id"].isin(sel_channels)]
        filtered_scores = filtered_scores[filtered_scores["channel_id"].isin(sel_channels)]

    # ── Header ────────────────────────────────────────────────
    st.title("🖱️ Logitech Brand Intelligence Platform")
    st.caption(f"Live data across {len(all_channels)} channels · 10 products · {len(intel_df)} data points")

    # ── KPI Row ───────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        avg_price = filtered_intel["price"].mean() if not filtered_intel.empty else 0
        st.metric("Avg Price", f"${avg_price:.2f}")
    with col2:
        avg_rating = filtered_intel["rating"].mean() if not filtered_intel.empty else 0
        st.metric("Avg Rating", f"{avg_rating:.2f} ⭐")
    with col3:
        total_reviews = filtered_intel["review_count"].sum() if not filtered_intel.empty else 0
        st.metric("Total Reviews", f"{int(total_reviews):,}")
    with col4:
        in_stock_pct = filtered_intel["in_stock"].mean() * 100 if not filtered_intel.empty else 0
        st.metric("In Stock", f"{in_stock_pct:.0f}%")
    with col5:
        avg_score = filtered_scores["opportunity_score"].mean() if not filtered_scores.empty else 0
        st.metric("Avg Opp. Score", f"{avg_score:.1f}/100")

    st.markdown("---")

    # ── Tabs ──────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Opportunity Scores",
        "💰 Price Intelligence",
        "⭐ Ratings & Reviews",
        "📦 Stock & Distribution",
        "📋 Raw Data"
    ])

    # ── TAB 1: Opportunity Scores ─────────────────────────────
    with tab1:
        st.subheader("Opportunity Score Leaderboard")
        if filtered_scores.empty:
            st.info("No opportunity scores computed yet. Run the scraper first.")
        else:
            col_a, col_b = st.columns([2, 1])
            with col_a:
                top_scores = filtered_scores.sort_values("opportunity_score", ascending=False).head(20)
                fig = px.bar(
                    top_scores,
                    x="opportunity_score",
                    y="product_name",
                    color="opportunity_tier",
                    orientation="h",
                    color_discrete_map={"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"},
                    hover_data=["channel_name", "ad_recommendation", "stock_risk"],
                    title="Top Opportunity Scores (Product × Channel)",
                    labels={"opportunity_score": "Score (0-100)", "product_name": ""},
                )
                fig.update_layout(height=500, showlegend=True, yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, use_container_width=True)

            with col_b:
                st.markdown("**Tier Distribution**")
                tier_counts = filtered_scores["opportunity_tier"].value_counts().reset_index()
                tier_counts.columns = ["Tier", "Count"]
                fig2 = px.pie(
                    tier_counts, values="Count", names="Tier",
                    color="Tier",
                    color_discrete_map={"A": "#22c55e", "B": "#3b82f6", "C": "#f59e0b", "D": "#ef4444"},
                )
                fig2.update_layout(height=250, margin=dict(t=0, b=0))
                st.plotly_chart(fig2, use_container_width=True)

                st.markdown("**Ad Recommendations**")
                ad_counts = filtered_scores["ad_recommendation"].value_counts().reset_index()
                ad_counts.columns = ["Recommendation", "Count"]
                st.dataframe(ad_counts, hide_index=True, use_container_width=True)

            st.markdown("**Full Scores Table**")
            display_cols = ["product_name", "channel_name", "opportunity_score",
                            "opportunity_tier", "ad_recommendation",
                            "price_trend_7d", "stock_risk", "action_notes"]
            available = [c for c in display_cols if c in filtered_scores.columns]
            st.dataframe(
                filtered_scores[available].sort_values("opportunity_score", ascending=False),
                hide_index=True, use_container_width=True, height=350
            )

    # ── TAB 2: Price Intelligence ─────────────────────────────
    with tab2:
        st.subheader("Price Intelligence")
        if filtered_intel.empty:
            st.info("No price data available.")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                price_by_product = filtered_intel.groupby("product_name")["price"].mean().reset_index()
                price_by_product = price_by_product.sort_values("price", ascending=False)
                fig = px.bar(
                    price_by_product, x="price", y="product_name",
                    orientation="h", color="price",
                    color_continuous_scale="Blues",
                    title="Average Price by Product",
                    labels={"price": "Avg Price (USD)", "product_name": ""},
                )
                fig.update_layout(height=400, coloraxis_showscale=False,
                                  yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, use_container_width=True)

            with col_b:
                price_by_channel = filtered_intel.groupby("channel_name")["price"].mean().reset_index()
                price_by_channel = price_by_channel.sort_values("price")
                fig2 = px.bar(
                    price_by_channel, x="channel_name", y="price",
                    color="price", color_continuous_scale="Greens",
                    title="Average Price by Channel",
                    labels={"price": "Avg Price (USD)", "channel_name": "Channel"},
                )
                fig2.update_layout(height=400, coloraxis_showscale=False,
                                   xaxis_tickangle=-45)
                st.plotly_chart(fig2, use_container_width=True)

            st.markdown("**Price Comparison: All Products × Channels**")
            pivot = filtered_intel.pivot_table(
                index="product_name", columns="channel_name",
                values="price", aggfunc="mean"
            ).round(2)
            if not pivot.empty:
                fig3 = px.imshow(
                    pivot, text_auto=True, color_continuous_scale="RdYlGn_r",
                    title="Price Heatmap (USD)",
                    labels={"color": "Price (USD)"},
                    aspect="auto",
                )
                fig3.update_layout(height=400)
                st.plotly_chart(fig3, use_container_width=True)

            st.markdown("**Discount Analysis**")
            disc = filtered_intel[filtered_intel["discount_pct"].notna()][
                ["product_name", "channel_name", "price", "original_price", "discount_pct"]
            ].sort_values("discount_pct", ascending=False)
            if not disc.empty:
                st.dataframe(disc, hide_index=True, use_container_width=True, height=250)
            else:
                st.caption("No discount data available.")

    # ── TAB 3: Ratings & Reviews ──────────────────────────────
    with tab3:
        st.subheader("Ratings & Review Intelligence")
        if filtered_intel.empty:
            st.info("No ratings data available.")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                rat = filtered_intel.groupby("product_name")["rating"].mean().reset_index().dropna()
                rat = rat.sort_values("rating", ascending=False)
                fig = px.bar(
                    rat, x="rating", y="product_name",
                    orientation="h", color="rating",
                    color_continuous_scale="RdYlGn",
                    range_color=[3.5, 5.0],
                    title="Average Rating by Product",
                    labels={"rating": "Rating (out of 5)", "product_name": ""},
                )
                fig.update_layout(height=400, coloraxis_showscale=False,
                                  yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig, use_container_width=True)

            with col_b:
                rev = filtered_intel.groupby("product_name")["review_count"].max().reset_index().dropna()
                rev = rev.sort_values("review_count", ascending=False)
                fig2 = px.bar(
                    rev, x="review_count", y="product_name",
                    orientation="h", color="review_count",
                    color_continuous_scale="Blues",
                    title="Total Reviews by Product",
                    labels={"review_count": "Review Count", "product_name": ""},
                )
                fig2.update_layout(height=400, coloraxis_showscale=False,
                                   yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig2, use_container_width=True)

            st.markdown("**Rating × Review Count Scatter**")
            scatter_df = filtered_intel.dropna(subset=["rating", "review_count", "price"])
            if not scatter_df.empty:
                fig3 = px.scatter(
                    scatter_df, x="review_count", y="rating",
                    color="product_category", size="price",
                    hover_name="product_name",
                    hover_data=["channel_name", "price"],
                    title="Rating vs Review Count (bubble size = price)",
                    labels={"review_count": "Review Count", "rating": "Rating"},
                    log_x=True,
                )
                fig3.update_layout(height=400)
                st.plotly_chart(fig3, use_container_width=True)

    # ── TAB 4: Stock & Distribution ───────────────────────────
    with tab4:
        st.subheader("Stock & Distribution Analysis")
        if filtered_intel.empty:
            st.info("No stock data available.")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                stock_by_channel = filtered_intel.groupby("channel_name")["in_stock"].mean().reset_index()
                stock_by_channel["in_stock_pct"] = (stock_by_channel["in_stock"] * 100).round(1)
                stock_by_channel = stock_by_channel.sort_values("in_stock_pct", ascending=False)
                fig = px.bar(
                    stock_by_channel, x="channel_name", y="in_stock_pct",
                    color="in_stock_pct",
                    color_continuous_scale="RdYlGn",
                    range_color=[0, 100],
                    title="In-Stock Rate by Channel (%)",
                    labels={"in_stock_pct": "In Stock %", "channel_name": ""},
                )
                fig.update_layout(height=400, coloraxis_showscale=False,
                                  xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)

            with col_b:
                coverage = filtered_intel.groupby("product_name")["channel_id"].nunique().reset_index()
                coverage.columns = ["product_name", "channel_count"]
                coverage = coverage.sort_values("channel_count", ascending=False)
                fig2 = px.bar(
                    coverage, x="channel_count", y="product_name",
                    orientation="h", color="channel_count",
                    color_continuous_scale="Blues",
                    title="Channel Coverage by Product",
                    labels={"channel_count": "# Channels", "product_name": ""},
                )
                fig2.update_layout(height=400, coloraxis_showscale=False,
                                   yaxis={"categoryorder": "total ascending"})
                st.plotly_chart(fig2, use_container_width=True)

            st.markdown("**Stock Status Heatmap**")
            stock_pivot = filtered_intel.pivot_table(
                index="product_name", columns="channel_name",
                values="in_stock", aggfunc="mean"
            ).round(2)
            if not stock_pivot.empty:
                fig3 = px.imshow(
                    stock_pivot, text_auto=True,
                    color_continuous_scale=[[0, "#ef4444"], [1, "#22c55e"]],
                    title="Stock Availability (1=In Stock, 0=Out of Stock)",
                    zmin=0, zmax=1, aspect="auto",
                )
                fig3.update_layout(height=400)
                st.plotly_chart(fig3, use_container_width=True)

            if not filtered_scores.empty and "stock_risk" in filtered_scores.columns:
                st.markdown("**Stock Risk Distribution**")
                risk_counts = filtered_scores["stock_risk"].value_counts().reset_index()
                risk_counts.columns = ["Risk Level", "Count"]
                fig4 = px.pie(
                    risk_counts, values="Count", names="Risk Level",
                    color="Risk Level",
                    color_discrete_map={
                        "LOW": "#22c55e", "MEDIUM": "#f59e0b",
                        "HIGH": "#f97316", "CRITICAL": "#ef4444"
                    },
                    title="Stock Risk Distribution"
                )
                fig4.update_layout(height=300)
                st.plotly_chart(fig4, use_container_width=True)

    # ── TAB 5: Raw Data ───────────────────────────────────────
    with tab5:
        st.subheader("Raw Data Explorer")
        sub1, sub2 = st.tabs(["Price Intelligence", "Opportunity Scores"])

        with sub1:
            st.dataframe(filtered_intel, hide_index=True,
                         use_container_width=True, height=500)
            csv = filtered_intel.to_csv(index=False).encode()
            st.download_button("⬇️ Download CSV", csv,
                               "logitech_intelligence.csv", "text/csv")

        with sub2:
            st.dataframe(filtered_scores, hide_index=True,
                         use_container_width=True, height=500)
            csv2 = filtered_scores.to_csv(index=False).encode()
            st.download_button("⬇️ Download CSV", csv2,
                               "logitech_scores.csv", "text/csv")

    # ── PDF Export ────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📄 Export Report")
    col1, col2 = st.columns([1, 3])
    with col1:
        if REPORTLAB_OK:
            if st.button("Generate PDF Report", type="primary", use_container_width=True):
                with st.spinner("Generating PDF…"):
                    pdf_buf = generate_pdf(filtered_intel, filtered_scores)
                st.download_button(
                    label="⬇️ Download PDF",
                    data=pdf_buf,
                    file_name=f"logitech_intelligence_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
        else:
            st.warning("Install reportlab for PDF export: `pip install reportlab`")
    with col2:
        st.caption(
            "The PDF includes executive summary, opportunity scores leaderboard, "
            "and full price intelligence tables."
        )


if __name__ == "__main__":
    main()