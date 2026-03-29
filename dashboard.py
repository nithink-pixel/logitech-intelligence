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

try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    )
    REPORTLAB_OK = True
except ImportError:
    REPORTLAB_OK = False

DB_PATH = "logitech_intelligence.db"

st.set_page_config(
    page_title="Logitech Brand Intelligence",
    page_icon="🖱️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .tier-A { color: #22c55e; font-weight: 700; }
    .tier-B { color: #3b82f6; font-weight: 700; }
    .tier-C { color: #f59e0b; font-weight: 700; }
    .tier-D { color: #ef4444; font-weight: 700; }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# DATA LOADING
# ════════════════════════════════════════════════════════════════
@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    intel = pd.read_sql_query(
        "SELECT * FROM v_latest_intelligence WHERE scrape_status = 'success'", conn
    )
    scores = pd.read_sql_query("SELECT * FROM v_latest_scores", conn)
    products = pd.read_sql_query("SELECT * FROM products", conn)
    channels = pd.read_sql_query("SELECT * FROM retail_channels", conn)
    runs = pd.read_sql_query(
        "SELECT * FROM scrape_runs ORDER BY started_at DESC LIMIT 10", conn
    )
    conn.close()
    return intel, scores, products, channels, runs


@st.cache_data(ttl=300)
def load_price_history():
    conn = sqlite3.connect(DB_PATH)
    history = pd.read_sql_query("""
        SELECT
            pi.product_id,
            pi.channel_id,
            pi.price,
            pi.rating,
            pi.review_count,
            pi.in_stock,
            pi.scraped_at,
            p.name  AS product_name,
            p.category AS product_category,
            p.msrp,
            rc.display_name AS channel_name
        FROM product_intelligence pi
        JOIN products p         ON pi.product_id = p.product_id
        JOIN retail_channels rc ON pi.channel_id = rc.channel_id
        WHERE pi.scrape_status = 'success'
          AND pi.price IS NOT NULL
        ORDER BY pi.scraped_at
    """, conn)
    conn.close()
    if not history.empty:
        history["scraped_at"] = pd.to_datetime(history["scraped_at"])
    return history


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

    title_style = ParagraphStyle("title", parent=styles["Title"],
                                  fontSize=20, textColor=colors.HexColor("#1e40af"),
                                  spaceAfter=6)
    sub = ParagraphStyle("sub", parent=styles["Heading2"],
                          fontSize=13, textColor=colors.HexColor("#1e40af"))

    story.append(Paragraph("Logitech Brand Intelligence Report", title_style))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y %H:%M')}", styles["Normal"]
    ))
    story.append(Spacer(1, 0.2*inch))

    # Summary
    story.append(Paragraph("Executive Summary", sub))
    summary_data = [
        ["Metric", "Value"],
        ["Total Products Tracked", str(intel_df["product_id"].nunique())],
        ["Channels with Data", str(intel_df["channel_id"].nunique())],
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

    # Opportunity scores
    if not scores_df.empty:
        story.append(Paragraph("Opportunity Scores", sub))
        cols = ["product_name", "channel_name", "opportunity_score",
                "opportunity_tier", "ad_recommendation", "stock_risk"]
        available = [c for c in cols if c in scores_df.columns]
        top = scores_df[available].sort_values("opportunity_score", ascending=False).head(30)
        header = [c.replace("_", " ").title() for c in available]
        table_data = [header] + [
            [str(round(v, 1)) if isinstance(v, float) else str(v) for v in row]
            for row in top.values.tolist()
        ]
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

    # Price intelligence
    if not intel_df.empty:
        story.append(Paragraph("Price Intelligence", sub))
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
# MAIN
# ════════════════════════════════════════════════════════════════
def main():
    intel_df, scores_df, products_df, channels_df, runs_df = load_data()
    history_df = load_price_history()

    # ── Sidebar ──────────────────────────────────────────────
    with st.sidebar:
        st.image(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/4/41/Logitech_logo.svg/320px-Logitech_logo.svg.png",
            width=160,
        )
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
                    f"🕐 `{str(run['started_at'])[:16]}` — "
                    f"{run['total_success']}/{run['total_scraped']} ✓"
                )

        st.markdown("---")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

    # ── Filter ────────────────────────────────────────────────
    filtered_intel = intel_df.copy()
    filtered_scores = scores_df.copy()
    filtered_history = history_df.copy()

    if sel_category != "All":
        if not filtered_intel.empty:
            filtered_intel = filtered_intel[filtered_intel["product_category"] == sel_category]
        if not filtered_scores.empty:
            filtered_scores = filtered_scores[filtered_scores["product_category"] == sel_category]
        if not filtered_history.empty:
            filtered_history = filtered_history[filtered_history["product_category"] == sel_category]

    if sel_channels:
        if not filtered_intel.empty:
            filtered_intel = filtered_intel[filtered_intel["channel_id"].isin(sel_channels)]
        if not filtered_scores.empty:
            filtered_scores = filtered_scores[filtered_scores["channel_id"].isin(sel_channels)]
        if not filtered_history.empty:
            filtered_history = filtered_history[filtered_history["channel_id"].isin(sel_channels)]

    # ── Header ────────────────────────────────────────────────
    st.title("🖱️ Logitech Brand Intelligence Platform")
    st.caption(
        f"Live data across {len(all_channels)} channels · "
        f"10 products · {len(intel_df)} data points"
    )

    # ── KPIs ─────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Avg Price", f"${filtered_intel['price'].mean():.2f}" if not filtered_intel.empty else "—")
    with c2:
        st.metric("Avg Rating", f"{filtered_intel['rating'].mean():.2f} ⭐" if not filtered_intel.empty else "—")
    with c3:
        total_rev = int(filtered_intel["review_count"].sum()) if not filtered_intel.empty else 0
        st.metric("Total Reviews", f"{total_rev:,}")
    with c4:
        in_stock_pct = filtered_intel["in_stock"].mean() * 100 if not filtered_intel.empty else 0
        st.metric("In Stock", f"{in_stock_pct:.0f}%")
    with c5:
        avg_score = filtered_scores["opportunity_score"].mean() if not filtered_scores.empty else 0
        st.metric("Avg Opp. Score", f"{avg_score:.1f}/100")

    st.markdown("---")

    # ── Tabs ──────────────────────────────────────────────────
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
        "📈 Price History",
        "📊 Opportunity Scores",
        "💰 Price Intelligence",
        "⭐ Ratings & Reviews",
        "📦 Stock & Distribution",
        "📋 Raw Data",
    ])

    # ══════════════════════════════════════════════════════════
    # TAB 1 — PRICE HISTORY
    # ══════════════════════════════════════════════════════════
    with tab1:
        st.subheader("Price History Over Time")

        if filtered_history.empty:
            st.info("No historical data yet. Run the scraper a few times to build history.")
        else:
            # Controls
            col_a, col_b, col_c = st.columns(3)
            with col_a:
                all_products = sorted(filtered_history["product_name"].unique().tolist())
                sel_products = st.multiselect(
                    "Products", all_products, default=all_products[:3],
                    key="history_products"
                )
            with col_b:
                hist_channels = sorted(filtered_history["channel_id"].unique().tolist())
                sel_hist_channels = st.multiselect(
                    "Channels", hist_channels, default=hist_channels[:3],
                    key="history_channels"
                )
            with col_c:
                metric = st.selectbox(
                    "Metric", ["price", "rating", "review_count"],
                    key="history_metric"
                )

            # Filter
            h = filtered_history.copy()
            if sel_products:
                h = h[h["product_name"].isin(sel_products)]
            if sel_hist_channels:
                h = h[h["channel_id"].isin(sel_hist_channels)]

            if h.empty:
                st.warning("No data for selected filters.")
            else:
                # Line chart — price over time per product per channel
                h["label"] = h["product_name"].str.replace("Logitech ", "", regex=False) + \
                              " — " + h["channel_name"]

                fig = px.line(
                    h.sort_values("scraped_at"),
                    x="scraped_at",
                    y=metric,
                    color="label",
                    markers=True,
                    title=f"{metric.replace('_',' ').title()} Over Time",
                    labels={
                        "scraped_at": "Date",
                        metric: metric.replace("_", " ").title(),
                        "label": "Product — Channel",
                    },
                )
                fig.update_layout(
                    height=500,
                    xaxis_title="Scrape Date",
                    hovermode="x unified",
                    legend=dict(orientation="v", x=1.01, y=1),
                )
                fig.update_traces(line=dict(width=2), marker=dict(size=8))
                st.plotly_chart(fig, use_container_width=True)

                # MSRP reference line
                if metric == "price" and "msrp" in h.columns:
                    st.markdown("---")
                    st.subheader("Price vs MSRP")
                    latest = h.sort_values("scraped_at").groupby(
                        ["product_name", "channel_id"]
                    ).last().reset_index()
                    latest["price_vs_msrp"] = (
                        (latest["price"] - latest["msrp"]) / latest["msrp"] * 100
                    ).round(1)
                    latest["label"] = latest["product_name"].str.replace(
                        "Logitech ", "", regex=False
                    )
                    fig2 = px.bar(
                        latest.sort_values("price_vs_msrp"),
                        x="price_vs_msrp",
                        y="label",
                        color="channel_name",
                        orientation="h",
                        title="Current Price vs MSRP (%)",
                        labels={
                            "price_vs_msrp": "% vs MSRP (negative = below MSRP)",
                            "label": "",
                        },
                        barmode="group",
                    )
                    fig2.add_vline(x=0, line_dash="dash", line_color="white", opacity=0.5)
                    fig2.update_layout(height=450, yaxis={"categoryorder": "total ascending"})
                    st.plotly_chart(fig2, use_container_width=True)

                # Price change table
                st.subheader("Price Change Summary")
                if metric == "price":
                    first = h.sort_values("scraped_at").groupby(
                        ["product_name", "channel_id"]
                    ).first()[["price", "scraped_at"]].rename(
                        columns={"price": "first_price", "scraped_at": "first_seen"}
                    )
                    last = h.sort_values("scraped_at").groupby(
                        ["product_name", "channel_id"]
                    ).last()[["price", "scraped_at", "channel_name"]].rename(
                        columns={"price": "latest_price", "scraped_at": "last_seen"}
                    )
                    summary = first.join(last)
                    summary["change_usd"] = (
                        summary["latest_price"] - summary["first_price"]
                    ).round(2)
                    summary["change_pct"] = (
                        summary["change_usd"] / summary["first_price"] * 100
                    ).round(1)
                    summary = summary.reset_index()
                    summary["trend"] = summary["change_pct"].apply(
                        lambda x: "🔴 Up" if x > 0.5 else ("🟢 Down" if x < -0.5 else "⚪ Stable")
                    )
                    st.dataframe(
                        summary[[
                            "product_name", "channel_name",
                            "first_price", "latest_price",
                            "change_usd", "change_pct", "trend"
                        ]].sort_values("change_pct"),
                        hide_index=True,
                        use_container_width=True,
                        height=350,
                    )

                # Review velocity
                if metric == "review_count":
                    st.subheader("Review Velocity")
                    first_rev = h.sort_values("scraped_at").groupby(
                        ["product_name", "channel_id"]
                    ).first()[["review_count"]].rename(columns={"review_count": "first_count"})
                    last_rev = h.sort_values("scraped_at").groupby(
                        ["product_name", "channel_id"]
                    ).last()[["review_count", "channel_name"]].rename(
                        columns={"review_count": "latest_count"}
                    )
                    vel = first_rev.join(last_rev).reset_index()
                    vel["new_reviews"] = vel["latest_count"] - vel["first_count"]
                    vel = vel[vel["new_reviews"] > 0].sort_values("new_reviews", ascending=False)
                    if not vel.empty:
                        fig3 = px.bar(
                            vel, x="new_reviews",
                            y="product_name", color="channel_name",
                            orientation="h",
                            title="New Reviews Since First Scrape",
                            labels={"new_reviews": "New Reviews", "product_name": ""},
                        )
                        fig3.update_layout(height=400)
                        st.plotly_chart(fig3, use_container_width=True)

    # ══════════════════════════════════════════════════════════
    # TAB 2 — OPPORTUNITY SCORES
    # ══════════════════════════════════════════════════════════
    with tab2:
        st.subheader("Opportunity Score Leaderboard")
        if filtered_scores.empty:
            st.info("No opportunity scores computed yet.")
        else:
            col_a, col_b = st.columns([2, 1])
            with col_a:
                top = filtered_scores.sort_values("opportunity_score", ascending=False).head(20)
                fig = px.bar(
                    top, x="opportunity_score", y="product_name",
                    color="opportunity_tier", orientation="h",
                    color_discrete_map={
                        "A": "#22c55e", "B": "#3b82f6",
                        "C": "#f59e0b", "D": "#ef4444"
                    },
                    hover_data=["channel_name", "ad_recommendation", "stock_risk"],
                    title="Top Opportunity Scores (Product × Channel)",
                    labels={"opportunity_score": "Score (0–100)", "product_name": ""},
                )
                fig.update_layout(
                    height=500, yaxis={"categoryorder": "total ascending"}
                )
                st.plotly_chart(fig, use_container_width=True)

            with col_b:
                tier_counts = filtered_scores["opportunity_tier"].value_counts().reset_index()
                tier_counts.columns = ["Tier", "Count"]
                fig2 = px.pie(
                    tier_counts, values="Count", names="Tier",
                    color="Tier",
                    color_discrete_map={
                        "A": "#22c55e", "B": "#3b82f6",
                        "C": "#f59e0b", "D": "#ef4444"
                    },
                    title="Tier Distribution",
                )
                fig2.update_layout(height=280, margin=dict(t=30, b=0))
                st.plotly_chart(fig2, use_container_width=True)

                st.markdown("**Ad Recommendations**")
                ad = filtered_scores["ad_recommendation"].value_counts().reset_index()
                ad.columns = ["Recommendation", "Count"]
                st.dataframe(ad, hide_index=True, use_container_width=True)

            st.markdown("**Full Scores Table**")
            display_cols = [
                "product_name", "channel_name", "opportunity_score",
                "opportunity_tier", "ad_recommendation",
                "price_trend_7d", "stock_risk", "action_notes"
            ]
            avail = [c for c in display_cols if c in filtered_scores.columns]
            st.dataframe(
                filtered_scores[avail].sort_values("opportunity_score", ascending=False),
                hide_index=True, use_container_width=True, height=350,
            )

    # ══════════════════════════════════════════════════════════
    # TAB 3 — PRICE INTELLIGENCE
    # ══════════════════════════════════════════════════════════
    with tab3:
        st.subheader("Price Intelligence")
        if filtered_intel.empty:
            st.info("No price data available.")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                pprod = filtered_intel.groupby("product_name")["price"].mean().reset_index()
                pprod = pprod.sort_values("price", ascending=False)
                fig = px.bar(
                    pprod, x="price", y="product_name",
                    orientation="h", color="price",
                    color_continuous_scale="Blues",
                    title="Average Price by Product (USD)",
                    labels={"price": "Avg Price", "product_name": ""},
                )
                fig.update_layout(
                    height=400, coloraxis_showscale=False,
                    yaxis={"categoryorder": "total ascending"}
                )
                st.plotly_chart(fig, use_container_width=True)

            with col_b:
                pchan = filtered_intel.groupby("channel_name")["price"].mean().reset_index()
                fig2 = px.bar(
                    pchan.sort_values("price"), x="channel_name", y="price",
                    color="price", color_continuous_scale="Greens",
                    title="Average Price by Channel (USD)",
                    labels={"price": "Avg Price", "channel_name": ""},
                )
                fig2.update_layout(
                    height=400, coloraxis_showscale=False, xaxis_tickangle=-45
                )
                st.plotly_chart(fig2, use_container_width=True)

            pivot = filtered_intel.pivot_table(
                index="product_name", columns="channel_name",
                values="price", aggfunc="mean"
            ).round(2)
            if not pivot.empty:
                fig3 = px.imshow(
                    pivot, text_auto=True, color_continuous_scale="RdYlGn_r",
                    title="Price Heatmap — Product × Channel (USD)",
                    aspect="auto",
                )
                fig3.update_layout(height=420)
                st.plotly_chart(fig3, use_container_width=True)

            disc = filtered_intel[filtered_intel["discount_pct"].notna()][
                ["product_name", "channel_name", "price", "original_price", "discount_pct"]
            ].sort_values("discount_pct", ascending=False)
            if not disc.empty:
                st.markdown("**Active Discounts**")
                st.dataframe(disc, hide_index=True, use_container_width=True, height=250)

    # ══════════════════════════════════════════════════════════
    # TAB 4 — RATINGS & REVIEWS
    # ══════════════════════════════════════════════════════════
    with tab4:
        st.subheader("Ratings & Review Intelligence")
        if filtered_intel.empty:
            st.info("No ratings data.")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                rat = filtered_intel.groupby("product_name")["rating"].mean().reset_index().dropna()
                fig = px.bar(
                    rat.sort_values("rating", ascending=False),
                    x="rating", y="product_name", orientation="h",
                    color="rating", color_continuous_scale="RdYlGn",
                    range_color=[3.5, 5.0],
                    title="Average Rating by Product",
                    labels={"rating": "Rating (out of 5)", "product_name": ""},
                )
                fig.update_layout(
                    height=400, coloraxis_showscale=False,
                    yaxis={"categoryorder": "total ascending"}
                )
                st.plotly_chart(fig, use_container_width=True)

            with col_b:
                rev = filtered_intel.groupby("product_name")["review_count"].max().reset_index().dropna()
                fig2 = px.bar(
                    rev.sort_values("review_count", ascending=False),
                    x="review_count", y="product_name", orientation="h",
                    color="review_count", color_continuous_scale="Blues",
                    title="Max Review Count by Product",
                    labels={"review_count": "Reviews", "product_name": ""},
                )
                fig2.update_layout(
                    height=400, coloraxis_showscale=False,
                    yaxis={"categoryorder": "total ascending"}
                )
                st.plotly_chart(fig2, use_container_width=True)

            scatter_df = filtered_intel.dropna(subset=["rating", "review_count", "price"])
            if not scatter_df.empty:
                fig3 = px.scatter(
                    scatter_df, x="review_count", y="rating",
                    color="product_category", size="price",
                    hover_name="product_name",
                    hover_data=["channel_name", "price"],
                    title="Rating vs Review Count (bubble = price)",
                    log_x=True,
                )
                fig3.update_layout(height=400)
                st.plotly_chart(fig3, use_container_width=True)

    # ══════════════════════════════════════════════════════════
    # TAB 5 — STOCK & DISTRIBUTION
    # ══════════════════════════════════════════════════════════
    with tab5:
        st.subheader("Stock & Distribution Analysis")
        if filtered_intel.empty:
            st.info("No stock data.")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                sb = filtered_intel.groupby("channel_name")["in_stock"].mean().reset_index()
                sb["pct"] = (sb["in_stock"] * 100).round(1)
                fig = px.bar(
                    sb.sort_values("pct", ascending=False),
                    x="channel_name", y="pct",
                    color="pct", color_continuous_scale="RdYlGn",
                    range_color=[0, 100],
                    title="In-Stock Rate by Channel (%)",
                    labels={"pct": "In Stock %", "channel_name": ""},
                )
                fig.update_layout(
                    height=400, coloraxis_showscale=False, xaxis_tickangle=-45
                )
                st.plotly_chart(fig, use_container_width=True)

            with col_b:
                cov = filtered_intel.groupby("product_name")["channel_id"].nunique().reset_index()
                cov.columns = ["product_name", "channels"]
                fig2 = px.bar(
                    cov.sort_values("channels", ascending=False),
                    x="channels", y="product_name", orientation="h",
                    color="channels", color_continuous_scale="Blues",
                    title="Channel Coverage by Product",
                    labels={"channels": "# Channels", "product_name": ""},
                )
                fig2.update_layout(
                    height=400, coloraxis_showscale=False,
                    yaxis={"categoryorder": "total ascending"}
                )
                st.plotly_chart(fig2, use_container_width=True)

            stock_pivot = filtered_intel.pivot_table(
                index="product_name", columns="channel_name",
                values="in_stock", aggfunc="mean"
            ).round(2)
            if not stock_pivot.empty:
                fig3 = px.imshow(
                    stock_pivot, text_auto=True,
                    color_continuous_scale=[[0, "#ef4444"], [1, "#22c55e"]],
                    title="Stock Availability Heatmap",
                    zmin=0, zmax=1, aspect="auto",
                )
                fig3.update_layout(height=420)
                st.plotly_chart(fig3, use_container_width=True)

    # ══════════════════════════════════════════════════════════
    # TAB 6 — RAW DATA
    # ══════════════════════════════════════════════════════════
    with tab6:
        st.subheader("Raw Data Explorer")
        sub1, sub2, sub3 = st.tabs(["Price Intelligence", "Opportunity Scores", "Full History"])

        with sub1:
            st.dataframe(filtered_intel, hide_index=True,
                         use_container_width=True, height=500)
            st.download_button(
                "⬇️ Download CSV", filtered_intel.to_csv(index=False).encode(),
                "logitech_intelligence.csv", "text/csv"
            )

        with sub2:
            st.dataframe(filtered_scores, hide_index=True,
                         use_container_width=True, height=500)
            st.download_button(
                "⬇️ Download CSV", filtered_scores.to_csv(index=False).encode(),
                "logitech_scores.csv", "text/csv"
            )

        with sub3:
            st.dataframe(filtered_history, hide_index=True,
                         use_container_width=True, height=500)
            st.download_button(
                "⬇️ Download Full History CSV",
                filtered_history.to_csv(index=False).encode(),
                "logitech_history.csv", "text/csv"
            )

    # ══════════════════════════════════════════════════════════
    # PDF EXPORT
    # ══════════════════════════════════════════════════════════
    st.markdown("---")
    st.subheader("📄 Export Report")
    col1, col2 = st.columns([1, 3])
    with col1:
        if REPORTLAB_OK:
            if st.button("Generate PDF Report", type="primary", use_container_width=True):
                with st.spinner("Generating PDF…"):
                    pdf_buf = generate_pdf(filtered_intel, filtered_scores)
                st.download_button(
                    "⬇️ Download PDF",
                    data=pdf_buf,
                    file_name=f"logitech_report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
        else:
            st.warning("Install reportlab: `pip install reportlab`")
    with col2:
        st.caption(
            "PDF includes executive summary, opportunity scores, and price intelligence tables."
        )


if __name__ == "__main__":
    main()