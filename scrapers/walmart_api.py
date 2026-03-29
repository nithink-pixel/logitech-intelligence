"""
Walmart API Scraper — uses Walmart's internal search API
No authentication required for basic product search.
"""

import json
import logging
import re
from urllib.parse import quote_plus
from .base import BaseScraper, clean_price, clean_rating, clean_review_count, random_delay

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


class WalmartAPIScraper(BaseScraper):
    CHANNEL_ID = "walmart"

    # Walmart's internal search API — no auth needed
    SEARCH_API = "https://www.walmart.com/search/api/preso?q={query}&cat_id=0"

    def __init__(self, conn, run_id=None):
        super().__init__(conn, run_id)
        # Walmart-specific headers
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.walmart.com/",
            "Origin": "https://www.walmart.com",
        })

    def scrape_product(self, product_id, url):
        term = PRODUCT_SEARCH_TERMS.get(product_id, "")
        api_url = self.SEARCH_API.format(query=quote_plus(term))

        resp = self.fetch(api_url)
        if not resp or resp.status_code != 200:
            # Fallback to HTML search
            return self._html_fallback(product_id, term)

        try:
            data = resp.json()
        except Exception:
            return self._html_fallback(product_id, term)

        # Parse Walmart search API response
        items = (
            data.get("props", {})
                .get("pageProps", {})
                .get("initialData", {})
                .get("searchResult", {})
                .get("itemStacks", [{}])[0]
                .get("items", [])
        )

        # Try direct items array
        if not items:
            items = data.get("items", data.get("searchResults", {}).get("items", []))

        for item in items[:5]:
            price_info = item.get("priceInfo", item.get("price", {}))
            price = None

            if isinstance(price_info, dict):
                price = (price_info.get("currentPrice", {}).get("price") or
                         price_info.get("priceDisplay") or
                         price_info.get("price"))
            elif isinstance(price_info, (int, float)):
                price = float(price_info)

            if price:
                try:
                    price = float(str(price).replace("$", "").replace(",", ""))
                except (ValueError, TypeError):
                    price = clean_price(str(price))

            if not price:
                continue

            avail = item.get("availabilityStatus", item.get("availability", ""))
            rating = item.get("averageRating", item.get("rating"))
            reviews = item.get("numberOfReviews", item.get("reviewCount"))
            seller = item.get("sellerDisplayName", item.get("sellerName", "Walmart"))

            return {
                "scrape_status": "success",
                "currency": "USD",
                "price": float(price),
                "rating": float(rating) if rating else None,
                "review_count": int(reviews) if reviews else None,
                "in_stock": 1 if "IN_STOCK" in str(avail).upper() or avail == "" else 0,
                "stock_level": str(avail) or "In Stock",
                "sold_by": str(seller),
                "fulfilled_by": "Walmart",
                "raw_url": api_url,
            }

        return self._html_fallback(product_id, term)

    def _html_fallback(self, product_id, term):
        """Fall back to HTML search page."""
        html_url = f"https://www.walmart.com/search?q={quote_plus(term)}"
        random_delay(2, 4)
        resp = self.fetch(html_url)
        if not resp or resp.status_code != 200:
            return {
                "scrape_status": "blocked",
                "scrape_error": f"Both API and HTML failed — HTTP {resp.status_code if resp else 'None'}",
                "raw_url": html_url,
            }

        # Try __NEXT_DATA__
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        script = soup.find("script", {"id": "__NEXT_DATA__"})
        if script:
            try:
                data = json.loads(script.string)
                items = (
                    data.get("props", {})
                        .get("pageProps", {})
                        .get("initialData", {})
                        .get("searchResult", {})
                        .get("itemStacks", [{}])[0]
                        .get("items", [])
                )
                for item in items:
                    price = item.get("priceInfo", {}).get("currentPrice", {}).get("price")
                    if price:
                        return {
                            "scrape_status": "success",
                            "currency": "USD",
                            "price": float(price),
                            "rating": item.get("averageRating"),
                            "review_count": item.get("numberOfReviews"),
                            "in_stock": 1,
                            "stock_level": "In Stock",
                            "sold_by": item.get("sellerDisplayName", "Walmart"),
                            "raw_url": html_url,
                        }
            except Exception:
                pass

        return {
            "scrape_status": "not_found",
            "scrape_error": "No price found on Walmart",
            "raw_url": html_url,
        }