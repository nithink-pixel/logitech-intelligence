"""
Target API Scraper — uses Target's RedSky API
No authentication required for product search.
"""

import json
import logging
from urllib.parse import quote_plus
from .base import BaseScraper, clean_price, clean_rating, clean_review_count

logger = logging.getLogger(__name__)

PRODUCT_SEARCH_TERMS = {
    "B0BS9VVQPD": "Logitech MX Master 3S Wireless Mouse Black",
    "B09HM94VDS": "Logitech MX Master 3S Wireless Mouse Graphite",
    "B0BKW3LB2B": "Logitech MX Keys S Wireless Keyboard",
    "B07XD3VS62": "Logitech MX Keys Wireless Keyboard",
    "B08KTW2188": "Logitech C920x HD Pro Webcam 1080p",
    "B09NBWWP79": "Logitech Brio 4K Webcam",
    "B0B3F8V4JG": "Logitech G PRO X 2 Lightspeed Wireless Gaming Headset",
    "B07W5JKB8Z": "Logitech G PRO X Wireless Gaming Headset",
    "B09NBWQDKX": "Logitech G PRO X Superlight 2 Wireless Gaming Mouse",
    "B07GBZ4Q68": "Logitech G502 Hero Wired Gaming Mouse",
}

# Target RedSky search API
TARGET_SEARCH_API = (
    "https://redsky.target.com/redsky_aggregations/v1/web/plp_search_v2"
    "?key=9f36aeafbe60771e321a7cc95a78140772ab3e96"
    "&channel=WEB&count=5&default_purchasability_filter=false"
    "&include_sponsored=true&keyword={query}&offset=0"
    "&platform=desktop&pricing_store_id=3991&scheduled_delivery_store_id=3991"
    "&store_ids=3991&useragent=Mozilla%2F5.0&visitor_id=test123"
    "&zip=10001"
)


class TargetAPIScraper(BaseScraper):
    CHANNEL_ID = "target"

    def __init__(self, conn, run_id=None):
        super().__init__(conn, run_id)
        self.session.headers.update({
            "Accept": "application/json",
            "Referer": "https://www.target.com/",
            "Origin": "https://www.target.com",
        })

    def scrape_product(self, product_id, url):
        term = PRODUCT_SEARCH_TERMS.get(product_id, "")
        api_url = TARGET_SEARCH_API.format(query=quote_plus(term))

        resp = self.fetch(api_url)
        if not resp or resp.status_code != 200:
            return self._html_fallback(product_id, term)

        try:
            data = resp.json()
        except Exception:
            return self._html_fallback(product_id, term)

        # Parse Target RedSky response
        products = (
            data.get("data", {})
                .get("search", {})
                .get("products", [])
        )

        for product in products[:3]:
            item = product.get("item", {})
            price_info = item.get("price", {})

            price = (price_info.get("current_retail") or
                     price_info.get("reg_retail") or
                     price_info.get("formatted_current_price_type"))

            if not price:
                continue

            try:
                price = float(str(price).replace("$","").replace(",",""))
            except (ValueError, TypeError):
                price = clean_price(str(price))

            if not price:
                continue

            ratings = item.get("ratings_and_reviews", {})
            avail = item.get("fulfillment", {}).get("is_out_of_stock", False)
            tcin = item.get("tcin", "")
            pdp_url = f"https://www.target.com/p/-/A-{tcin}" if tcin else api_url

            return {
                "scrape_status": "success",
                "currency": "USD",
                "price": float(price),
                "original_price": price_info.get("reg_retail"),
                "rating": ratings.get("statistics", {}).get("rating", {}).get("average"),
                "review_count": ratings.get("statistics", {}).get("review_count"),
                "in_stock": 0 if avail else 1,
                "stock_level": "Out of Stock" if avail else "In Stock",
                "sold_by": "Target",
                "fulfilled_by": "Target",
                "raw_url": pdp_url,
            }

        return self._html_fallback(product_id, term)

    def _html_fallback(self, product_id, term):
        """HTML fallback for Target."""
        from bs4 import BeautifulSoup
        html_url = f"https://www.target.com/s?searchTerm={quote_plus(term)}"
        resp = self.fetch(html_url)
        if not resp or resp.status_code != 200:
            return {
                "scrape_status": "blocked",
                "scrape_error": f"HTTP {resp.status_code if resp else 'None'}",
                "raw_url": html_url,
            }
        soup = BeautifulSoup(resp.text, "html.parser")
        el = soup.select_one('[data-test="product-price"]')
        if el:
            price = clean_price(el.get_text())
            if price:
                return {
                    "scrape_status": "success",
                    "currency": "USD",
                    "price": price,
                    "in_stock": 1,
                    "stock_level": "In Stock",
                    "raw_url": html_url,
                }
        return {
            "scrape_status": "not_found",
            "scrape_error": "No price found on Target",
            "raw_url": html_url,
        }