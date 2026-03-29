"""
Anker Brand Intelligence Platform — Opportunity Score Engine
Computes velocity, price competitiveness, distribution gap, and composite scores.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Score weights (must sum to 1.0)
WEIGHTS = {
    "velocity":             0.30,
    "price_competitiveness": 0.25,
    "distribution_gap":     0.25,
    "content_quality":      0.20,
}

AD_THRESHOLDS = {
    "SP_BOOST":  80,   # Sponsored Products aggressive push
    "SB_TEST":   60,   # Sponsored Brands test
    "HOLD":      40,   # Maintain current
    "REPRICE":    0,   # Price issue — fix before spending
}


def compute_all_scores(conn: sqlite3.Connection) -> int:
    """Compute opportunity scores for all product-channel combos. Returns rows written."""
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all product-channel combos that have data
    combos = cur.execute(
        "SELECT DISTINCT product_id, channel_id FROM product_intelligence "
        "WHERE scrape_status = 'success'"
    ).fetchall()

    written = 0
    for row in combos:
        pid, cid = row["product_id"], row["channel_id"]
        score_data = compute_score(conn, pid, cid)
        if score_data:
            _upsert_score(conn, score_data)
            written += 1

    conn.commit()
    logger.info(f"[Scorer] Computed {written} opportunity scores")
    return written


def compute_score(conn: sqlite3.Connection, product_id: str, channel_id: str) -> Optional[dict]:
    """Compute the full opportunity score for one product-channel combo."""
    cur = conn.cursor()

    # Latest snapshot
    latest = cur.execute(
        "SELECT * FROM product_intelligence "
        "WHERE product_id=? AND channel_id=? AND scrape_status='success' "
        "ORDER BY scraped_at DESC LIMIT 1",
        (product_id, channel_id)
    ).fetchone()

    if not latest:
        return None

    # Historical snapshots (last 30 days)
    history = cur.execute(
        "SELECT * FROM product_intelligence "
        "WHERE product_id=? AND channel_id=? AND scrape_status='success' "
        "  AND scraped_at >= datetime('now', '-30 days') "
        "ORDER BY scraped_at DESC",
        (product_id, channel_id)
    ).fetchall()

    # Cross-channel prices for this product (price context)
    channel_prices = cur.execute(
        "SELECT channel_id, price FROM product_intelligence "
        "WHERE product_id=? AND scrape_status='success' AND price IS NOT NULL "
        "  AND id IN (SELECT MAX(id) FROM product_intelligence "
        "             WHERE product_id=? AND scrape_status='success' GROUP BY channel_id)",
        (product_id, product_id)
    ).fetchall()

    # MSRP from products table
    product_row = cur.execute(
        "SELECT msrp FROM products WHERE product_id=?", (product_id,)
    ).fetchone()
    msrp = product_row["msrp"] if product_row else None

    # ── Compute component scores ───────────────────────────────
    velocity        = _velocity_score(latest, history)
    price_comp      = _price_competitiveness(latest, channel_prices, msrp)
    dist_gap        = _distribution_gap_score(latest, history)
    content_qual    = _content_quality_score(latest)

    # ── Composite ─────────────────────────────────────────────
    composite = round(
        velocity        * WEIGHTS["velocity"] +
        price_comp      * WEIGHTS["price_competitiveness"] +
        dist_gap        * WEIGHTS["distribution_gap"] +
        content_qual    * WEIGHTS["content_quality"],
        1
    )

    tier = _score_to_tier(composite)
    ad_rec = _ad_recommendation(composite, latest)
    price_trend = _price_trend(history)
    review_velocity = _review_velocity(history)
    stock_risk = _stock_risk(latest, history)

    return {
        "product_id":             product_id,
        "channel_id":             channel_id,
        "computed_at":            datetime.utcnow().isoformat(),
        "velocity_score":         velocity,
        "price_competitiveness":  price_comp,
        "distribution_gap":       dist_gap,
        "content_quality":        content_qual,
        "opportunity_score":      composite,
        "opportunity_tier":       tier,
        "ad_recommendation":      ad_rec,
        "action_notes":           _action_notes(composite, latest, price_comp, dist_gap),
        "price_trend_7d":         price_trend,
        "review_velocity_7d":     review_velocity,
        "stock_risk":             stock_risk,
    }


# ── Component calculators ────────────────────────────────────

def _velocity_score(latest, history) -> float:
    """
    Score based on review momentum and BSR trend.
    Higher review count + improving BSR → high velocity.
    """
    score = 50.0  # baseline

    review_count = latest["review_count"] or 0

    # Review count tiers
    if review_count >= 10000: score += 30
    elif review_count >= 5000: score += 20
    elif review_count >= 1000: score += 10
    elif review_count >= 100:  score += 5
    elif review_count == 0:    score -= 20

    # BSR bonus (lower rank = better)
    bsr = latest["bsr_rank"]
    if bsr:
        if bsr <= 100:    score += 20
        elif bsr <= 500:  score += 15
        elif bsr <= 1000: score += 10
        elif bsr <= 5000: score += 5
        elif bsr > 50000: score -= 10

    # Review velocity over last 7 days
    if len(history) >= 2:
        newest_reviews = history[0]["review_count"] or 0
        # Find snapshot ~7 days ago
        week_ago = datetime.utcnow() - timedelta(days=7)
        older = [h for h in history if h["scraped_at"] < week_ago.isoformat()]
        if older:
            old_reviews = older[0]["review_count"] or 0
            if old_reviews > 0 and newest_reviews > old_reviews:
                velocity_pct = (newest_reviews - old_reviews) / old_reviews * 100
                score += min(velocity_pct * 0.5, 15)  # cap bonus at 15

    return max(0, min(100, round(score, 1)))


def _price_competitiveness(latest, channel_prices, msrp: Optional[float]) -> float:
    """
    Score based on price positioning vs MAP/MSRP and channel average.
    Price at or near MSRP = good. Under MAP = risk. Far above = missed sales.
    """
    score = 50.0
    price = latest["price"]

    if not price:
        return 20.0  # missing price = bad signal

    prices = [row["price"] for row in channel_prices if row["price"] and row["price"] > 0]

    if prices and len(prices) > 1:
        avg_price = sum(prices) / len(prices)
        min_price = min(prices)

        # Is this channel competitive vs others?
        if price <= avg_price:
            score += 20
        elif price > avg_price * 1.1:
            score -= 15
        elif price > avg_price * 1.05:
            score -= 5

        # Is this channel the cheapest? (potential distribution signal)
        if price == min_price:
            score += 10

    if msrp:
        ratio = price / msrp
        if 0.90 <= ratio <= 1.05:   # at/near MSRP → healthy
            score += 15
        elif ratio < 0.80:           # deep discount → MAP risk
            score -= 25
        elif ratio < 0.90:           # mild discount
            score -= 5
        elif ratio > 1.15:           # above MSRP → overpriced
            score -= 20

    # Discount badge signal
    discount_pct = latest["discount_pct"] or 0
    if 5 <= discount_pct <= 20:
        score += 10  # healthy promo
    elif discount_pct > 30:
        score -= 15  # aggressive discounting

    return max(0, min(100, round(score, 1)))


def _distribution_gap_score(latest, history) -> float:
    """
    Score based on stock availability and out-of-stock frequency.
    High availability + low OOS history = good distribution.
    """
    score = 70.0  # assume good unless evidence otherwise

    # Current stock
    if not latest["in_stock"]:
        score -= 40

    # Historical OOS rate
    if history:
        oos_count = sum(1 for h in history if not h["in_stock"])
        oos_rate = oos_count / len(history)
        if oos_rate > 0.5:  score -= 30
        elif oos_rate > 0.2: score -= 15
        elif oos_rate > 0.1: score -= 5
        elif oos_rate == 0:  score += 15  # never OOS

    # Low-stock warning
    stock_text = (latest["stock_level"] or "").lower()
    if "only" in stock_text and "left" in stock_text:
        score -= 10

    return max(0, min(100, round(score, 1)))


def _content_quality_score(latest) -> float:
    """Score based on listing quality signals."""
    score = 40.0

    rating = latest["rating"] or 0
    if rating >= 4.5:   score += 30
    elif rating >= 4.0: score += 20
    elif rating >= 3.5: score += 10
    elif rating < 3.0 and rating > 0: score -= 20

    reviews = latest["review_count"] or 0
    if reviews >= 5000:  score += 25
    elif reviews >= 1000: score += 15
    elif reviews >= 100:  score += 5
    elif reviews == 0:    score -= 15

    # Deal badge = well-merchandised
    if latest["deal_badge"]:
        score += 5

    return max(0, min(100, round(score, 1)))


# ── Derived fields ───────────────────────────────────────────

def _score_to_tier(score: float) -> str:
    if score >= 75: return "A"
    if score >= 55: return "B"
    if score >= 35: return "C"
    return "D"


def _ad_recommendation(score: float, latest) -> str:
    if not latest["in_stock"]:
        return "PAUSE_ADS"
    if score >= AD_THRESHOLDS["SP_BOOST"]:
        return "SP_BOOST"
    if score >= AD_THRESHOLDS["SB_TEST"]:
        return "SB_TEST"
    if score >= AD_THRESHOLDS["HOLD"]:
        return "HOLD"
    return "REPRICE"


def _action_notes(score: float, latest, price_comp: float, dist_gap: float) -> str:
    notes = []
    if not latest["in_stock"]:
        notes.append("⚠️ Currently out of stock — pause ad spend immediately.")
    if price_comp < 30:
        notes.append("💲 Price is uncompetitive vs other channels or above MSRP — review pricing.")
    if dist_gap < 40:
        notes.append("📦 Frequent OOS detected — coordinate inventory replenishment.")
    if score >= 75:
        notes.append("🚀 High-opportunity listing — increase ad budget and optimize PDP.")
    elif score >= 55:
        notes.append("📈 Solid performer — test Sponsored Brands creative.")
    elif score < 35:
        notes.append("🔴 Low priority — resolve pricing/stock issues before ad investment.")
    return " | ".join(notes) if notes else "No immediate action required."


def _price_trend(history) -> Optional[float]:
    """% price change over last 7 days."""
    if len(history) < 2:
        return None
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent = [h for h in history if h["scraped_at"] >= week_ago.isoformat() and h["price"]]
    older = [h for h in history if h["scraped_at"] < week_ago.isoformat() and h["price"]]
    if not recent or not older:
        return None
    avg_recent = sum(h["price"] for h in recent) / len(recent)
    avg_older = sum(h["price"] for h in older) / len(older)
    if avg_older == 0:
        return None
    return round((avg_recent - avg_older) / avg_older * 100, 2)


def _review_velocity(history) -> Optional[float]:
    """Average new reviews per day over last 7 days."""
    if len(history) < 2:
        return None
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent = [h for h in history if h["scraped_at"] >= week_ago.isoformat() and h["review_count"]]
    if len(recent) < 2:
        return None
    newest = max(h["review_count"] for h in recent)
    oldest = min(h["review_count"] for h in recent)
    days = 7
    return round((newest - oldest) / days, 1) if newest > oldest else 0.0


def _stock_risk(latest, history) -> str:
    if not latest["in_stock"]:
        return "CRITICAL"
    oos_count = sum(1 for h in history if not h["in_stock"]) if history else 0
    oos_rate = oos_count / len(history) if history else 0
    stock_text = (latest["stock_level"] or "").lower()
    if oos_rate > 0.3 or "only" in stock_text:
        return "HIGH"
    if oos_rate > 0.1:
        return "MEDIUM"
    return "LOW"


def _upsert_score(conn: sqlite3.Connection, data: dict) -> None:
    cols = list(data.keys())
    vals = list(data.values())
    placeholders = ",".join(["?"] * len(cols))
    sql = (
        f"INSERT OR REPLACE INTO opportunity_scores ({','.join(cols)}) "
        f"VALUES ({placeholders})"
    )
    conn.execute(sql, vals)