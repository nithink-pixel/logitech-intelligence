"""
Logitech Brand Intelligence — Global Price Comparison Module
Adds a global Amazon price comparison tab to the dashboard.
Import and call render_global_tab(history_df) from dashboard.py
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ─────────────────────────────────────────────────────────────
# Exchange rates to USD (approximate — update periodically)
# ─────────────────────────────────────────────────────────────
FX_TO_USD = {
    "amazon_us": 1.000,   # USD
    "amazon_uk": 1.270,   # GBP
    "amazon_de": 1.080,   # EUR
    "amazon_fr": 1.080,   # EUR
    "amazon_it": 1.080,   # EUR
    "amazon_es": 1.080,   # EUR
    "amazon_ca": 0.730,   # CAD
    "amazon_jp": 0.0067,  # JPY
    "amazon_au": 0.630,   # AUD
    "amazon_in": 0.012,   # INR
    "amazon_mx": 0.049,   # MXN
    "amazon_sg": 0.740,   # SGD
}

MARKET_LABELS = {
    "amazon_us": "🇺🇸 US",
    "amazon_uk": "🇬🇧 UK",
    "amazon_de": "🇩🇪 DE",
    "amazon_fr": "🇫🇷 FR",
    "amazon_it": "🇮🇹 IT",
    "amazon_es": "🇪🇸 ES",
    "amazon_ca": "🇨🇦 CA",
    "amazon_jp": "🇯🇵 JP",
    "amazon_au": "🇦🇺 AU",
    "amazon_in": "🇮🇳 IN",
    "amazon_mx": "🇲🇽 MX",
    "amazon_sg": "🇸🇬 SG",
}

CURRENCY_SYMBOLS = {
    "amazon_us": "$",
    "amazon_uk": "£",
    "amazon_de": "€",
    "amazon_fr": "€",
    "amazon_it": "€",
    "amazon_es": "€",
    "amazon_ca": "C$",
    "amazon_jp": "¥",
    "amazon_au": "A$",
    "amazon_in": "₹",
    "amazon_mx": "MX$",
    "amazon_sg": "S$",
}


def render_global_tab(history_df: pd.DataFrame):
    """Render the Global Price Comparison tab."""
    st.subheader("🌍 Global Amazon Price Comparison")
    st.caption("Prices converted to USD using approximate exchange rates for fair comparison")

    if history_df.empty:
        st.info("No data yet. Run the scraper on global Amazon channels first.")
        return

    # Filter to Amazon channels only
    amazon_channels = list(FX_TO_USD.keys())
    df = history_df[history_df["channel_id"].isin(amazon_channels)].copy()

    if df.empty:
        st.info("No Amazon marketplace data found.")
        return

    # Get latest price per product per channel
    latest = (
        df.sort_values("scraped_at")
        .groupby(["product_id", "channel_id", "product_name", "product_category", "msrp"])
        .last()
        .reset_index()[["product_id", "channel_id", "product_name",
                         "product_category", "msrp", "price", "scraped_at"]]
    )

    # Convert to USD
    latest["fx_rate"] = latest["channel_id"].map(FX_TO_USD)
    latest["price_usd"] = (latest["price"] * latest["fx_rate"]).round(2)
    latest["market"] = latest["channel_id"].map(MARKET_LABELS)
    latest["currency_symbol"] = latest["channel_id"].map(CURRENCY_SYMBOLS)
    latest["local_price_str"] = latest.apply(
        lambda r: f"{r['currency_symbol']}{r['price']:.2f}" if pd.notna(r["price"]) else "N/A",
        axis=1
    )
    latest["short_name"] = latest["product_name"].str.replace("Logitech ", "", regex=False)

    # ── Controls ──────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        all_products = sorted(latest["product_name"].unique().tolist())
        sel_products = st.multiselect(
            "Filter Products", all_products,
            default=all_products,
            key="global_products"
        )
    with col_b:
        view_mode = st.radio(
            "View", ["By Product", "By Market"],
            horizontal=True, key="global_view"
        )

    filtered = latest[latest["product_name"].isin(sel_products)] if sel_products else latest

    if filtered.empty:
        st.warning("No data for selected filters.")
        return

    st.markdown("---")

    # ── Chart 1: Grouped bar — price by market per product ────
    if view_mode == "By Product":
        fig = px.bar(
            filtered.sort_values("price_usd"),
            x="market",
            y="price_usd",
            color="market",
            facet_col="short_name",
            facet_col_wrap=2,
            title="Price by Market per Product (USD equivalent)",
            labels={"price_usd": "Price (USD)", "market": "Market"},
            custom_data=["local_price_str", "product_name", "channel_id"],
        )
        fig.update_traces(
            hovertemplate="<b>%{customdata[1]}</b><br>"
                          "Market: %{x}<br>"
                          "USD: $%{y:.2f}<br>"
                          "Local: %{customdata[0]}<extra></extra>"
        )
        fig.update_layout(
            height=600,
            showlegend=False,
            title_font_size=14,
        )
        fig.for_each_annotation(lambda a: a.update(
            text=a.text.split("=")[-1]
        ))
        st.plotly_chart(fig, use_container_width=True)

    else:  # By Market
        fig = px.bar(
            filtered.sort_values("price_usd"),
            x="short_name",
            y="price_usd",
            color="short_name",
            facet_col="market",
            facet_col_wrap=3,
            title="Price by Product per Market (USD equivalent)",
            labels={"price_usd": "Price (USD)", "short_name": "Product"},
            custom_data=["local_price_str", "market"],
        )
        fig.update_traces(
            hovertemplate="<b>%{x}</b><br>"
                          "Market: %{customdata[1]}<br>"
                          "USD: $%{y:.2f}<br>"
                          "Local: %{customdata[0]}<extra></extra>"
        )
        fig.update_layout(
            height=700,
            showlegend=False,
        )
        fig.for_each_annotation(lambda a: a.update(
            text=a.text.split("=")[-1]
        ))
        st.plotly_chart(fig, use_container_width=True)

    # ── Chart 2: Heatmap — cheapest market per product ────────
    st.subheader("Price Heatmap — All Products × All Markets (USD)")
    pivot = filtered.pivot_table(
        index="short_name",
        columns="market",
        values="price_usd",
        aggfunc="mean"
    ).round(2)

    if not pivot.empty:
        fig2 = px.imshow(
            pivot,
            text_auto=True,
            color_continuous_scale="RdYlGn_r",
            title="Price Heatmap (USD) — Green = Cheapest, Red = Most Expensive",
            aspect="auto",
            labels={"color": "Price (USD)"},
        )
        fig2.update_layout(height=400)
        fig2.update_traces(
            hovertemplate="Product: %{y}<br>Market: %{x}<br>Price: $%{z:.2f}<extra></extra>"
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Chart 3: Cheapest market per product ──────────────────
    st.subheader("Cheapest Market per Product")
    cheapest = (
        filtered.loc[filtered.groupby("product_name")["price_usd"].idxmin()]
        [["short_name", "market", "price_usd", "local_price_str", "msrp"]]
        .copy()
    )
    cheapest["vs_msrp_pct"] = (
        (cheapest["price_usd"] - cheapest["msrp"]) / cheapest["msrp"] * 100
    ).round(1)
    cheapest["deal"] = cheapest["vs_msrp_pct"].apply(
        lambda x: "🟢 Below MSRP" if x < -5 else ("🟡 At MSRP" if x <= 5 else "🔴 Above MSRP")
    )

    col1, col2 = st.columns(2)
    with col1:
        fig3 = px.bar(
            cheapest.sort_values("price_usd"),
            x="price_usd",
            y="short_name",
            color="market",
            orientation="h",
            title="Cheapest Available Price by Product (USD)",
            labels={"price_usd": "Price (USD)", "short_name": ""},
            text="market",
        )
        fig3.update_layout(
            height=400,
            yaxis={"categoryorder": "total ascending"},
            showlegend=False,
        )
        fig3.update_traces(textposition="inside")
        st.plotly_chart(fig3, use_container_width=True)

    with col2:
        st.markdown("**Best Deal Summary**")
        display = cheapest[["short_name", "market", "price_usd", "local_price_str", "deal"]]
        display.columns = ["Product", "Cheapest Market", "USD Price", "Local Price", "vs MSRP"]
        st.dataframe(display, hide_index=True, use_container_width=True, height=380)

    # ── Chart 4: Price spread (max - min) per product ─────────
    st.subheader("Price Arbitrage Opportunity")
    st.caption("Products with the biggest price difference between markets")

    spread = filtered.groupby("product_name").agg(
        min_price=("price_usd", "min"),
        max_price=("price_usd", "max"),
        markets=("market", "nunique"),
    ).reset_index()
    spread["spread_usd"] = (spread["max_price"] - spread["min_price"]).round(2)
    spread["spread_pct"] = (
        spread["spread_usd"] / spread["min_price"] * 100
    ).round(1)
    spread["short_name"] = spread["product_name"].str.replace("Logitech ", "", regex=False)
    spread = spread.sort_values("spread_usd", ascending=False)

    fig4 = px.bar(
        spread,
        x="spread_usd",
        y="short_name",
        orientation="h",
        color="spread_pct",
        color_continuous_scale="Reds",
        title="Price Spread Across Markets (USD) — Higher = More Arbitrage",
        labels={
            "spread_usd": "Price Spread (USD)",
            "short_name": "",
            "spread_pct": "Spread %",
        },
        text=spread["spread_pct"].apply(lambda x: f"{x}%"),
    )
    fig4.update_layout(
        height=380,
        yaxis={"categoryorder": "total ascending"},
        coloraxis_showscale=False,
    )
    fig4.update_traces(textposition="outside")
    st.plotly_chart(fig4, use_container_width=True)

    # ── Exchange rate note ─────────────────────────────────────
    with st.expander("📋 Exchange Rates Used"):
        fx_df = pd.DataFrame([
            {"Market": MARKET_LABELS[k], "Currency": CURRENCY_SYMBOLS[k],
             "Rate to USD": f"1 local = ${v:.4f}"}
            for k, v in FX_TO_USD.items()
            if k in filtered["channel_id"].values
        ])
        st.dataframe(fx_df, hide_index=True, use_container_width=True)
        st.caption("Rates are approximate. Update FX_TO_USD dict in global_comparison.py for live rates.")