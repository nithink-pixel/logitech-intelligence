"""
Logitech Brand Intelligence — Global Price Comparison Module
Uses live FX rates from exchangerate-api.com (free, no API key needed)
"""

import pandas as pd
import plotly.express as px
import streamlit as st
import requests
from datetime import datetime, timezone

# ─────────────────────────────────────────────────────────────
# Fallback rates (used if API is unavailable)
# ─────────────────────────────────────────────────────────────
FALLBACK_FX = {
    "amazon_us": 1.000,
    "amazon_uk": 1.270,
    "amazon_de": 1.080,
    "amazon_fr": 1.080,
    "amazon_it": 1.080,
    "amazon_es": 1.080,
    "amazon_ca": 0.730,
    "amazon_jp": 0.0067,
    "amazon_au": 0.630,
    "amazon_in": 0.012,
    "amazon_mx": 0.049,
    "amazon_sg": 0.740,
}

CHANNEL_CURRENCY = {
    "amazon_us": "USD",
    "amazon_uk": "GBP",
    "amazon_de": "EUR",
    "amazon_fr": "EUR",
    "amazon_it": "EUR",
    "amazon_es": "EUR",
    "amazon_ca": "CAD",
    "amazon_jp": "JPY",
    "amazon_au": "AUD",
    "amazon_in": "INR",
    "amazon_mx": "MXN",
    "amazon_sg": "SGD",
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


@st.cache_data(ttl=3600)  # Cache for 1 hour
def fetch_live_fx_rates() -> tuple[dict, str, bool]:
    """
    Fetch live FX rates from exchangerate-api.com.
    Returns (rates_dict, timestamp, is_live).
    rates_dict maps channel_id -> USD conversion rate.
    """
    try:
        resp = requests.get(
            "https://api.exchangerate-api.com/v4/latest/USD",
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            live_rates = data.get("rates", {})
            fx_map = {}
            for channel, currency in CHANNEL_CURRENCY.items():
                if currency in live_rates and live_rates[currency] != 0:
                    fx_map[channel] = round(1 / live_rates[currency], 6)
                else:
                    fx_map[channel] = FALLBACK_FX.get(channel, 1.0)
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            return fx_map, timestamp, True
    except Exception:
        pass

    # Fallback
    timestamp = "Fallback rates (API unavailable)"
    return FALLBACK_FX.copy(), timestamp, False


def render_global_tab(history_df: pd.DataFrame):
    """Render the Global Price Comparison tab."""
    st.subheader("🌍 Global Amazon Price Comparison")

    # Fetch live rates
    fx_rates, fx_timestamp, is_live = fetch_live_fx_rates()

    if is_live:
        st.success(f"✅ Live exchange rates — updated {fx_timestamp}")
    else:
        st.warning(f"⚠️ Using fallback rates — {fx_timestamp}")

    if history_df.empty:
        st.info("No data yet. Run the scraper on global Amazon channels first.")
        return

    amazon_channels = list(CHANNEL_CURRENCY.keys())
    df = history_df[history_df["channel_id"].isin(amazon_channels)].copy()

    if df.empty:
        st.info("No Amazon marketplace data found.")
        return

    # Latest price per product per channel
    latest = (
        df.sort_values("scraped_at")
        .groupby(["product_id", "channel_id", "product_name", "product_category", "msrp"])
        .last()
        .reset_index()[["product_id", "channel_id", "product_name",
                         "product_category", "msrp", "price", "scraped_at"]]
    )

    latest["fx_rate"]       = latest["channel_id"].map(fx_rates)
    latest["price_usd"]     = (latest["price"] * latest["fx_rate"]).round(2)
    latest["market"]        = latest["channel_id"].map(MARKET_LABELS)
    latest["currency"]      = latest["channel_id"].map(CHANNEL_CURRENCY)
    latest["symbol"]        = latest["channel_id"].map(CURRENCY_SYMBOLS)
    latest["local_price_str"] = latest.apply(
        lambda r: f"{r['symbol']}{r['price']:.2f}" if pd.notna(r["price"]) else "N/A",
        axis=1
    )
    latest["short_name"] = latest["product_name"].str.replace("Logitech ", "", regex=False)

    # Sanity check: filter prices outside $5-$500 USD range (FX conversion errors)
    suspect = (latest["price_usd"] < 5) | (latest["price_usd"] > 500)
    suspect_count = int(suspect.sum())
    if suspect_count > 0:
        st.warning(
            f"Excluded {suspect_count} listings with suspicious prices after FX conversion "
            f"(outside $5-$500 USD range). Likely scraper read wrong number from local page."
        )
        latest = latest[~suspect].copy()


    # ── Controls ──────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    with col_a:
        all_products = sorted(latest["product_name"].unique().tolist())
        sel_products = st.multiselect(
            "Filter Products", all_products, default=all_products,
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

    # ── Chart 1: Grouped bar ──────────────────────────────────
    if view_mode == "By Product":
        fig = px.bar(
            filtered.sort_values("price_usd"),
            x="market", y="price_usd",
            color="market",
            facet_col="short_name", facet_col_wrap=2,
            title="Price by Market per Product (USD equivalent)",
            labels={"price_usd": "Price (USD)", "market": "Market"},
            custom_data=["local_price_str", "product_name", "currency"],
        )
        fig.update_traces(
            hovertemplate="<b>%{customdata[1]}</b><br>"
                          "Market: %{x}<br>"
                          "USD: $%{y:.2f}<br>"
                          "Local: %{customdata[0]} (%{customdata[2]})<extra></extra>"
        )
        fig.update_layout(height=600, showlegend=False)
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        st.plotly_chart(fig, use_container_width=True)
    else:
        fig = px.bar(
            filtered.sort_values("price_usd"),
            x="short_name", y="price_usd",
            color="short_name",
            facet_col="market", facet_col_wrap=3,
            title="Price by Product per Market (USD equivalent)",
            labels={"price_usd": "Price (USD)", "short_name": "Product"},
            custom_data=["local_price_str", "market", "currency"],
        )
        fig.update_traces(
            hovertemplate="<b>%{x}</b><br>"
                          "Market: %{customdata[1]}<br>"
                          "USD: $%{y:.2f}<br>"
                          "Local: %{customdata[0]} (%{customdata[2]})<extra></extra>"
        )
        fig.update_layout(height=700, showlegend=False)
        fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
        st.plotly_chart(fig, use_container_width=True)

    # ── Chart 2: Heatmap ──────────────────────────────────────
    st.subheader("Price Heatmap — All Products × All Markets (USD)")
    pivot = filtered.pivot_table(
        index="short_name", columns="market",
        values="price_usd", aggfunc="mean"
    ).round(2)
    if not pivot.empty:
        fig2 = px.imshow(
            pivot, text_auto=True,
            color_continuous_scale="RdYlGn_r",
            title="Price Heatmap (USD) — Green = Cheapest",
            aspect="auto",
        )
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)

    # ── Chart 3: Cheapest market ──────────────────────────────
    st.subheader("Cheapest Market per Product")
    cheapest = (
        filtered.loc[filtered.groupby("product_name")["price_usd"].idxmin()]
        [["short_name", "market", "price_usd", "local_price_str", "msrp", "currency"]].copy()
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
            x="price_usd", y="short_name",
            color="market", orientation="h",
            title="Cheapest Available Price (USD)",
            labels={"price_usd": "Price (USD)", "short_name": ""},
            text="market",
        )
        fig3.update_layout(height=400, showlegend=False,
                           yaxis={"categoryorder": "total ascending"})
        fig3.update_traces(textposition="inside")
        st.plotly_chart(fig3, use_container_width=True)

    with col2:
        st.markdown("**Best Deal Summary**")
        display = cheapest[["short_name", "market", "price_usd",
                             "local_price_str", "currency", "deal"]]
        display.columns = ["Product", "Cheapest Market", "USD Price",
                           "Local Price", "Currency", "vs MSRP"]
        st.dataframe(display, hide_index=True, use_container_width=True, height=380)

    # ── Chart 4: Arbitrage ────────────────────────────────────
    st.subheader("Price Arbitrage Opportunity")
    spread = filtered.groupby("product_name").agg(
        min_price=("price_usd", "min"),
        max_price=("price_usd", "max"),
        markets=("market", "nunique"),
    ).reset_index()
    spread["spread_usd"] = (spread["max_price"] - spread["min_price"]).round(2)
    spread["spread_pct"] = (spread["spread_usd"] / spread["min_price"] * 100).round(1)
    spread["short_name"] = spread["product_name"].str.replace("Logitech ", "", regex=False)
    spread = spread.sort_values("spread_usd", ascending=False)

    fig4 = px.bar(
        spread, x="spread_usd", y="short_name",
        orientation="h", color="spread_pct",
        color_continuous_scale="Reds",
        title="Price Spread Across Markets — Higher = More Arbitrage",
        labels={"spread_usd": "Price Spread (USD)", "short_name": ""},
        text=spread["spread_pct"].apply(lambda x: f"{x}%"),
    )
    fig4.update_layout(height=380, coloraxis_showscale=False,
                       yaxis={"categoryorder": "total ascending"})
    fig4.update_traces(textposition="outside")
    st.plotly_chart(fig4, use_container_width=True)

    # ── Live FX Rates panel ───────────────────────────────────
    with st.expander("💱 Live Exchange Rates"):
        fx_df = pd.DataFrame([
            {
                "Market": MARKET_LABELS[k],
                "Currency": CHANNEL_CURRENCY[k],
                "1 Local = USD": f"${fx_rates[k]:.4f}",
                "Source": "🟢 Live" if is_live else "🟡 Fallback",
            }
            for k in CHANNEL_CURRENCY
            if k in filtered["channel_id"].values
        ])
        st.dataframe(fx_df, hide_index=True, use_container_width=True)
        if is_live:
            st.caption(f"Rates fetched from exchangerate-api.com at {fx_timestamp}. "
                       f"Cached for 1 hour.")
        else:
            st.caption("Could not reach exchange rate API. Using approximate fallback rates.")

        if st.button("🔄 Force Refresh Rates"):
            st.cache_data.clear()
            st.rerun()