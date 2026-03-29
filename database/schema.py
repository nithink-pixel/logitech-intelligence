"""
Logitech Brand Intelligence Platform — SQLite Schema
10 verified products x 31 retail channels
"""

import sqlite3
import os

DB_PATH = os.environ.get("LOGITECH_DB_PATH", "logitech_intelligence.db")

BRAND_PRODUCTS = {
    "B0BS9VVQPD": {"name": "Logitech MX Master 3S Mouse (Black)",          "category": "Productivity Mouse",    "msrp": 99.99},
    "B09HM94VDS": {"name": "Logitech MX Master 3S Mouse (Graphite/Bolt)",  "category": "Productivity Mouse",    "msrp": 99.99},
    "B0BKW3LB2B": {"name": "Logitech MX Keys S Wireless Keyboard",         "category": "Productivity Keyboard", "msrp": 109.99},
    "B07XD3VS62": {"name": "Logitech MX Keys Wireless Keyboard",           "category": "Productivity Keyboard", "msrp": 109.99},
    "B08KTW2188": {"name": "Logitech C920x HD Pro Webcam 1080p",           "category": "Webcam",                "msrp": 69.99},
    "B09NBWWP79": {"name": "Logitech Brio 4K Webcam",                      "category": "Webcam",                "msrp": 149.99},
    "B0B3F8V4JG": {"name": "Logitech G PRO X 2 Lightspeed Headset",       "category": "Gaming Headset",        "msrp": 199.99},
    "B07W5JKB8Z": {"name": "Logitech G PRO X Wireless Headset",           "category": "Gaming Headset",        "msrp": 129.99},
    "B09NBWQDKX": {"name": "Logitech G PRO X Superlight 2 Mouse (White)", "category": "Gaming Mouse",          "msrp": 159.99},
    "B07GBZ4Q68": {"name": "Logitech G502 Hero Wired Gaming Mouse",       "category": "Gaming Mouse",          "msrp": 49.99},
}

RETAIL_CHANNELS = [
    ("amazon_us",    "Amazon US",    "https://www.amazon.com",      1, "US"),
    ("walmart",      "Walmart",      "https://www.walmart.com",      1, "US"),
    ("target",       "Target",       "https://www.target.com",       1, "US"),
    ("bestbuy",      "Best Buy",     "https://www.bestbuy.com",      1, "US"),
    ("ebay",         "eBay",         "https://www.ebay.com",         1, "US"),
    ("logitech",     "Logitech.com", "https://www.logitech.com",     1, "US"),
    ("newegg",       "Newegg",       "https://www.newegg.com",       2, "US"),
    ("kohls",        "Kohl's",       "https://www.kohls.com",        2, "US"),
    ("costco",       "Costco",       "https://www.costco.com",       2, "US"),
    ("samsclub",     "Sam's Club",   "https://www.samsclub.com",     2, "US"),
    ("bhphotovideo", "B&H Photo",    "https://www.bhphotovideo.com", 2, "US"),
    ("adorama",      "Adorama",      "https://www.adorama.com",      2, "US"),
    ("staples",      "Staples",      "https://www.staples.com",      2, "US"),
    ("officedepot",  "Office Depot", "https://www.officedepot.com",  2, "US"),
    ("microcenter",  "Micro Center", "https://www.microcenter.com",  2, "US"),
    ("rakuten",      "Rakuten",      "https://www.rakuten.com",      2, "US"),
    ("overstock",    "Overstock",    "https://www.overstock.com",    2, "US"),
    ("wayfair",      "Wayfair",      "https://www.wayfair.com",      2, "US"),
    ("homedepot",    "Home Depot",   "https://www.homedepot.com",    2, "US"),
    ("macys",        "Macy's",       "https://www.macys.com",        2, "US"),
    ("amazon_uk",    "Amazon UK",    "https://www.amazon.co.uk",     3, "GB"),
    ("amazon_de",    "Amazon DE",    "https://www.amazon.de",        3, "DE"),
    ("amazon_ca",    "Amazon CA",    "https://www.amazon.ca",        3, "CA"),
    ("amazon_jp",    "Amazon JP",    "https://www.amazon.co.jp",     3, "JP"),
    ("amazon_fr",    "Amazon FR",    "https://www.amazon.fr",        3, "FR"),
    ("amazon_it",    "Amazon IT",    "https://www.amazon.it",        3, "IT"),
    ("amazon_es",    "Amazon ES",    "https://www.amazon.es",        3, "ES"),
    ("amazon_mx",    "Amazon MX",    "https://www.amazon.com.mx",    3, "MX"),
    ("amazon_au",    "Amazon AU",    "https://www.amazon.com.au",    3, "AU"),
    ("amazon_in",    "Amazon IN",    "https://www.amazon.in",        3, "IN"),
    ("amazon_sg",    "Amazon SG",    "https://www.amazon.sg",        3, "SG"),
]

DDL = """
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    category   TEXT NOT NULL,
    msrp       REAL NOT NULL,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS retail_channels (
    channel_id   TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    base_url     TEXT,
    tier         INTEGER NOT NULL DEFAULT 1,
    region       TEXT DEFAULT 'US',
    active       INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS product_intelligence (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id      TEXT NOT NULL REFERENCES products(product_id),
    channel_id      TEXT NOT NULL REFERENCES retail_channels(channel_id),
    scraped_at      TEXT NOT NULL DEFAULT (datetime('now')),
    price           REAL,
    original_price  REAL,
    discount_pct    REAL,
    currency        TEXT DEFAULT 'USD',
    rating          REAL,
    review_count    INTEGER,
    rating_histogram TEXT,
    in_stock        INTEGER DEFAULT 1,
    stock_level     TEXT,
    bsr_rank        INTEGER,
    category_rank   TEXT,
    sold_by         TEXT,
    fulfilled_by    TEXT,
    is_prime        INTEGER DEFAULT 0,
    has_coupon      INTEGER DEFAULT 0,
    coupon_value    TEXT,
    deal_badge      TEXT,
    is_sponsored    INTEGER DEFAULT 0,
    scrape_status   TEXT DEFAULT 'success',
    scrape_error    TEXT,
    raw_url         TEXT,
    UNIQUE(product_id, channel_id, scraped_at)
);

CREATE TABLE IF NOT EXISTS opportunity_scores (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id            TEXT NOT NULL REFERENCES products(product_id),
    channel_id            TEXT NOT NULL REFERENCES retail_channels(channel_id),
    computed_at           TEXT NOT NULL DEFAULT (datetime('now')),
    velocity_score        REAL,
    price_competitiveness REAL,
    distribution_gap      REAL,
    content_quality       REAL,
    opportunity_score     REAL,
    opportunity_tier      TEXT,
    ad_recommendation     TEXT,
    action_notes          TEXT,
    price_trend_7d        REAL,
    review_velocity_7d    REAL,
    stock_risk            TEXT,
    UNIQUE(product_id, channel_id, computed_at)
);

CREATE TABLE IF NOT EXISTS scrape_runs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id        TEXT NOT NULL UNIQUE,
    started_at    TEXT NOT NULL,
    finished_at   TEXT,
    channels      TEXT,
    total_scraped INTEGER DEFAULT 0,
    total_success INTEGER DEFAULT 0,
    total_errors  INTEGER DEFAULT 0,
    notes         TEXT
);

CREATE INDEX IF NOT EXISTS idx_pi_product_channel ON product_intelligence(product_id, channel_id);
CREATE INDEX IF NOT EXISTS idx_pi_scraped_at      ON product_intelligence(scraped_at DESC);
CREATE INDEX IF NOT EXISTS idx_os_opportunity     ON opportunity_scores(opportunity_score DESC);

CREATE VIEW IF NOT EXISTS v_latest_intelligence AS
SELECT pi.*,
       p.name        AS product_name,
       p.category    AS product_category,
       p.msrp        AS product_msrp,
       rc.display_name AS channel_name,
       rc.tier       AS channel_tier,
       rc.region     AS channel_region
FROM product_intelligence pi
JOIN products p         ON pi.product_id = p.product_id
JOIN retail_channels rc ON pi.channel_id = rc.channel_id
WHERE pi.id IN (
    SELECT MAX(id) FROM product_intelligence GROUP BY product_id, channel_id
);

CREATE VIEW IF NOT EXISTS v_latest_scores AS
SELECT os.*,
       p.name        AS product_name,
       p.category    AS product_category,
       rc.display_name AS channel_name,
       rc.tier       AS channel_tier
FROM opportunity_scores os
JOIN products p         ON os.product_id = p.product_id
JOIN retail_channels rc ON os.channel_id = rc.channel_id
WHERE os.id IN (
    SELECT MAX(id) FROM opportunity_scores GROUP BY product_id, channel_id
);
"""


def init_db(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(DDL)
    conn.executemany(
        "INSERT OR IGNORE INTO products (product_id, name, category, msrp) VALUES (?,?,?,?)",
        [(pid, d["name"], d["category"], d["msrp"]) for pid, d in BRAND_PRODUCTS.items()]
    )
    conn.executemany(
        "INSERT OR IGNORE INTO retail_channels (channel_id, display_name, base_url, tier, region) VALUES (?,?,?,?,?)",
        RETAIL_CHANNELS
    )
    conn.commit()
    print(f"[DB] Initialized → {db_path}")
    print(f"[DB] Products: {len(BRAND_PRODUCTS)} | Channels: {len(RETAIL_CHANNELS)}")
    return conn


def get_connection(db_path=DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


if __name__ == "__main__":
    init_db()