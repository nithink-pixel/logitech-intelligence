"""
Logitech Brand Intelligence — Alerts Engine
Detects price drops, spikes, OOS events, MAP violations, and opportunity changes.
Call render_alerts_tab(history_df, intel_df, scores_df) from dashboard.py
"""

import pandas as pd
import streamlit as st
from datetime import datetime, timezone, timedelta


# ─────────────────────────────────────────────
# Alert thresholds (customizable)
# ─────────────────────────────────────────────
PRICE_DROP_PCT     = 5.0    # % drop triggers alert
PRICE_SPIKE_PCT    = 10.0   # % increase triggers alert
MAP_VIOLATION_PCT  = -8.0   # % below MSRP triggers MAP alert
HIGH_OPP_THRESHOLD = 75.0   # opportunity score threshold


def compute_alerts(history_df: pd.DataFrame,
                   intel_df: pd.DataFrame,
                   scores_df: pd.DataFrame) -> dict:
    """
    Compute all alerts from current data.
    Returns dict of alert lists keyed by type.
    """
    alerts = {
        "oos":        [],   # out of stock
        "price_drop": [],   # significant price drop
        "price_spike":[],   # significant price increase
        "map":        [],   # below MAP/MSRP
        "high_opp":   [],   # high opportunity score
    }

    # ── Out of Stock ──────────────────────────────────────────
    if not intel_df.empty and "in_stock" in intel_df.columns:
        oos = intel_df[intel_df["in_stock"] == 0].copy()
        for _, row in oos.iterrows():
            alerts["oos"].append({
                "product": row.get("product_name", row.get("product_id", "")),
                "channel": row.get("channel_name", row.get("channel_id", "")),
                "last_price": row.get("price"),
                "scraped_at": row.get("scraped_at", ""),
            })

    # ── Price Changes (compare latest vs previous scrape) ─────
    if not history_df.empty and "price" in history_df.columns:
        history_df = history_df.copy()
        history_df["scraped_at"] = pd.to_datetime(history_df["scraped_at"], utc=True, errors="coerce")
        history_df = history_df.dropna(subset=["price", "scraped_at"])

        for (pid, cid), group in history_df.groupby(["product_id", "channel_id"]):
            group = group.sort_values("scraped_at")
            if len(group) < 2:
                continue

            latest   = group.iloc[-1]
            previous = group.iloc[-2]

            if not previous["price"] or previous["price"] == 0:
                continue

            change_pct = (latest["price"] - previous["price"]) / previous["price"] * 100

            base = {
                "product":   latest.get("product_name", pid),
                "channel":   latest.get("channel_name", cid),
                "old_price": round(previous["price"], 2),
                "new_price": round(latest["price"], 2),
                "change_pct": round(change_pct, 1),
                "scraped_at": str(latest["scraped_at"])[:16],
            }

            if change_pct <= -PRICE_DROP_PCT:
                alerts["price_drop"].append(base)
            elif change_pct >= PRICE_SPIKE_PCT:
                alerts["price_spike"].append(base)

    # ── MAP / MSRP Violations ─────────────────────────────────
    if not intel_df.empty and "product_msrp" in intel_df.columns:
        for _, row in intel_df.iterrows():
            msrp  = row.get("product_msrp")
            price = row.get("price")
            if not msrp or not price or msrp == 0:
                continue
            pct = (price - msrp) / msrp * 100
            if pct <= MAP_VIOLATION_PCT:
                alerts["map"].append({
                    "product":    row.get("product_name", ""),
                    "channel":    row.get("channel_name", ""),
                    "price":      round(price, 2),
                    "msrp":       round(msrp, 2),
                    "below_pct":  round(abs(pct), 1),
                    "scraped_at": row.get("scraped_at", ""),
                })

    # ── High Opportunity Scores ───────────────────────────────
    if not scores_df.empty and "opportunity_score" in scores_df.columns:
        high = scores_df[scores_df["opportunity_score"] >= HIGH_OPP_THRESHOLD].copy()
        for _, row in high.iterrows():
            alerts["high_opp"].append({
                "product":   row.get("product_name", ""),
                "channel":   row.get("channel_name", ""),
                "score":     round(row["opportunity_score"], 1),
                "tier":      row.get("opportunity_tier", ""),
                "ad_rec":    row.get("ad_recommendation", ""),
                "action":    row.get("action_notes", ""),
            })

    return alerts


def render_alerts_tab(history_df: pd.DataFrame,
                      intel_df: pd.DataFrame,
                      scores_df: pd.DataFrame):
    """Render the Alerts tab in the Streamlit dashboard."""

    st.subheader("🚨 Live Alerts & Notifications")

    alerts = compute_alerts(history_df, intel_df, scores_df)

    total = sum(len(v) for v in alerts.values())
    if total == 0:
        st.success("✅ No alerts — everything looks healthy!")
        return

    # ── Summary KPIs ─────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        n = len(alerts["oos"])
        st.metric("🔴 Out of Stock", n, delta=f"{n} products" if n else None,
                  delta_color="inverse")
    with c2:
        n = len(alerts["price_drop"])
        st.metric("📉 Price Drops", n,
                  delta=f">{PRICE_DROP_PCT}% drop" if n else None,
                  delta_color="normal")
    with c3:
        n = len(alerts["price_spike"])
        st.metric("📈 Price Spikes", n,
                  delta=f">{PRICE_SPIKE_PCT}% rise" if n else None,
                  delta_color="inverse")
    with c4:
        n = len(alerts["map"])
        st.metric("⚠️ MAP Violations", n,
                  delta=f">{abs(MAP_VIOLATION_PCT)}% below MSRP" if n else None,
                  delta_color="inverse")
    with c5:
        n = len(alerts["high_opp"])
        st.metric("🏆 High Opportunity", n,
                  delta=f"Score >{HIGH_OPP_THRESHOLD}" if n else None,
                  delta_color="normal")

    st.markdown("---")

    # ── Threshold controls ────────────────────────────────────
    with st.expander("⚙️ Alert Thresholds"):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.number_input("Price Drop Alert (%)", value=PRICE_DROP_PCT,
                            min_value=1.0, max_value=50.0, step=1.0,
                            key="thresh_drop",
                            help="Alert when price drops by this % since last scrape")
        with col2:
            st.number_input("Price Spike Alert (%)", value=PRICE_SPIKE_PCT,
                            min_value=1.0, max_value=100.0, step=1.0,
                            key="thresh_spike")
        with col3:
            st.number_input("MAP Violation (%)", value=abs(MAP_VIOLATION_PCT),
                            min_value=1.0, max_value=50.0, step=1.0,
                            key="thresh_map",
                            help="Alert when price is this % below MSRP")

    # ── Out of Stock ──────────────────────────────────────────
    if alerts["oos"]:
        st.markdown("### 🔴 Out of Stock")
        oos_df = pd.DataFrame(alerts["oos"])
        oos_df.columns = [c.replace("_", " ").title() for c in oos_df.columns]
        st.dataframe(oos_df, hide_index=True, use_container_width=True)
        st.caption(f"⚡ Action: Pause ads immediately on these {len(alerts['oos'])} listings")

    # ── Price Drops ───────────────────────────────────────────
    if alerts["price_drop"]:
        st.markdown("### 📉 Price Drops")
        drop_df = pd.DataFrame(alerts["price_drop"])
        drop_df["change_pct"] = drop_df["change_pct"].apply(lambda x: f"{x}%")
        drop_df.columns = [c.replace("_", " ").title() for c in drop_df.columns]
        st.dataframe(drop_df, hide_index=True, use_container_width=True)
        st.caption("💡 Consider matching price on competing channels or investigating cause")

    # ── Price Spikes ──────────────────────────────────────────
    if alerts["price_spike"]:
        st.markdown("### 📈 Price Spikes")
        spike_df = pd.DataFrame(alerts["price_spike"])
        spike_df["change_pct"] = spike_df["change_pct"].apply(lambda x: f"+{x}%")
        spike_df.columns = [c.replace("_", " ").title() for c in spike_df.columns]
        st.dataframe(spike_df, hide_index=True, use_container_width=True)
        st.caption("⚠️ Price above MSRP may reduce conversion — review urgently")

    # ── MAP Violations ────────────────────────────────────────
    if alerts["map"]:
        st.markdown("### ⚠️ MAP / MSRP Violations")
        map_df = pd.DataFrame(alerts["map"])
        map_df["below_pct"] = map_df["below_pct"].apply(lambda x: f"{x}% below MSRP")
        map_df.columns = [c.replace("_", " ").title() for c in map_df.columns]
        st.dataframe(map_df, hide_index=True, use_container_width=True)
        st.caption("🚨 MAP violations may damage brand equity — escalate to channel manager")

    # ── High Opportunity ──────────────────────────────────────
    if alerts["high_opp"]:
        st.markdown("### 🏆 High Opportunity Listings")
        opp_df = pd.DataFrame(alerts["high_opp"])
        opp_df.columns = [c.replace("_", " ").title() for c in opp_df.columns]
        st.dataframe(opp_df, hide_index=True, use_container_width=True)
        st.caption("🚀 These listings are primed for ad investment — increase budget now")

    # ── Alert history log ─────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📋 Alert Summary Log")
    log_rows = []
    for alert_type, items in alerts.items():
        for item in items:
            label = {
                "oos":         "🔴 Out of Stock",
                "price_drop":  "📉 Price Drop",
                "price_spike": "📈 Price Spike",
                "map":         "⚠️ MAP Violation",
                "high_opp":    "🏆 High Opportunity",
            }[alert_type]
            log_rows.append({
                "Type":    label,
                "Product": item.get("product", ""),
                "Channel": item.get("channel", ""),
                "Detail":  (
                    f"${item['new_price']} (was ${item['old_price']}, {item['change_pct']}%)"
                    if "new_price" in item else
                    f"Score: {item['score']}" if "score" in item else
                    f"${item.get('price', '')} vs MSRP ${item.get('msrp', '')}"
                    if "msrp" in item else
                    f"Last price: ${item.get('last_price', 'N/A')}"
                ),
            })

    if log_rows:
        log_df = pd.DataFrame(log_rows)
        st.dataframe(log_df, hide_index=True, use_container_width=True, height=300)
        st.download_button(
            "⬇️ Download Alert Log CSV",
            log_df.to_csv(index=False).encode(),
            f"alerts_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv",
        )