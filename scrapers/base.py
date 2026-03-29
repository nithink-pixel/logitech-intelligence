"""
Logitech Brand Intelligence Platform — Base Scraper
Shared infrastructure: sessions, retries, rate-limiting, storage helpers
"""

import re
import time
import uuid
import random
import logging
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


def build_session(retries=3, backoff=1.5):
    session = requests.Session()
    retry_cfg = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_cfg, pool_connections=10, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def random_delay(min_s=1.5, max_s=4.0):
    time.sleep(random.uniform(min_s, max_s))


def clean_price(text):
    if not text:
        return None
    text = str(text).replace(",", "")
    matches = re.findall(r"\d+\.?\d*", text)
    for m in matches:
        try:
            val = float(m)
            if 0.5 < val < 10000:
                return round(val, 2)
        except ValueError:
            continue
    return None


def clean_rating(text):
    if not text:
        return None
    text = str(text)
    m = re.search(r"(\d+\.?\d*)\s*(?:out of|/)\s*5", text, re.I)
    if m:
        return round(float(m.group(1)), 1)
    m = re.search(r"(\d+\.?\d*)", text)
    if m:
        val = float(m.group(1))
        return round(val, 1) if val <= 5 else None
    return None


def clean_review_count(text):
    if not text:
        return None
    text = str(text).replace(",", "").replace(".", "")
    m = re.search(r"(\d+\.?\d*)\s*[Kk]", text)
    if m:
        return int(float(m.group(1)) * 1000)
    m = re.search(r"(\d+)", text)
    return int(m.group(1)) if m else None


class BaseScraper(ABC):
    CHANNEL_ID = ""

    def __init__(self, conn, run_id=None):
        self.conn = conn
        self.run_id = run_id or str(uuid.uuid4())
        self.session = build_session()
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Connection": "keep-alive",
        })
        self._rotate_ua()

    def _rotate_ua(self):
        self.session.headers["User-Agent"] = random.choice(USER_AGENTS)

    def fetch(self, url, timeout=20):
        self._rotate_ua()
        try:
            resp = self.session.get(url, timeout=timeout)
            if resp.status_code == 200:
                return resp
            logger.warning(f"[{self.CHANNEL_ID}] HTTP {resp.status_code} → {url}")
            return resp
        except requests.RequestException as e:
            logger.error(f"[{self.CHANNEL_ID}] Request error: {e}")
            return None

    @abstractmethod
    def scrape_product(self, product_id, url):
        ...

    def save_result(self, data):
        data.setdefault("channel_id", self.CHANNEL_ID)
        data.setdefault("scraped_at", datetime.now(timezone.utc).isoformat())
        cols = [
            "product_id", "channel_id", "scraped_at",
            "price", "original_price", "discount_pct", "currency",
            "rating", "review_count", "rating_histogram",
            "in_stock", "stock_level", "bsr_rank", "category_rank",
            "sold_by", "fulfilled_by", "is_prime",
            "has_coupon", "coupon_value", "deal_badge", "is_sponsored",
            "scrape_status", "scrape_error", "raw_url",
        ]
        vals = [data.get(c) for c in cols]
        placeholders = ",".join(["?"] * len(cols))
        sql = (
            f"INSERT OR REPLACE INTO product_intelligence ({','.join(cols)}) "
            f"VALUES ({placeholders})"
        )
        self.conn.execute(sql, vals)
        self.conn.commit()

    def run(self, product_map):
        results = []
        for product_id, url in product_map.items():
            logger.info(f"[{self.CHANNEL_ID}] Scraping {product_id} → {url}")
            try:
                data = self.scrape_product(product_id, url)
                data["product_id"] = product_id
                data.setdefault("raw_url", url)
                self.save_result(data)
                results.append(data)
            except Exception as e:
                logger.error(f"[{self.CHANNEL_ID}] Failed {product_id}: {e}")
                err = {
                    "product_id": product_id,
                    "channel_id": self.CHANNEL_ID,
                    "raw_url": url,
                    "scrape_status": "error",
                    "scrape_error": str(e),
                }
                self.save_result(err)
                results.append(err)
            random_delay(1.5, 3.5)
        return results