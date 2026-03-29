"""
Logitech Brand Intelligence Platform — All 31 Channel Scrapers
- Amazon (12 marketplaces): direct ASIN URLs
- All other 19 channels: search-query based (reliable across any site change)
"""

import json
import logging
import re
from urllib.parse import quote_plus
from bs4 import BeautifulSoup
from .base import BaseScraper, clean_price, clean_rating, clean_review_count, random_delay

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Verified product search terms (used by all non-Amazon channels)
# ─────────────────────────────────────────────
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

# Amazon marketplace domains
AMAZON_DOMAINS = {
    "amazon_us": "www.amazon.com",
    "amazon_uk": "www.amazon.co.uk",
    "amazon_de": "www.amazon.de",
    "amazon_ca": "www.amazon.ca",
    "amazon_jp": "www.amazon.co.jp",
    "amazon_fr": "www.amazon.fr",
    "amazon_it": "www.amazon.it",
    "amazon_es": "www.amazon.es",
    "amazon_mx": "www.amazon.com.mx",
    "amazon_au": "www.amazon.com.au",
    "amazon_in": "www.amazon.in",
    "amazon_sg": "www.amazon.sg",
}


def amazon_urls_for(channel_id):
    domain = AMAZON_DOMAINS[channel_id]
    return {pid: f"https://{domain}/dp/{pid}" for pid in PRODUCT_SEARCH_TERMS}


def search_map():
    return {pid: term for pid, term in PRODUCT_SEARCH_TERMS.items()}


# ══════════════════════════════════════════════════════════════
# AMAZON SCRAPER — handles all 12 Amazon marketplaces
# ══════════════════════════════════════════════════════════════
class AmazonScraper(BaseScraper):
    def __init__(self, conn, channel_id, run_id=None):
        self.CHANNEL_ID = channel_id
        super().__init__(conn, run_id)

    def scrape_product(self, product_id, url):
        resp = self.fetch(url)
        if not resp or resp.status_code != 200:
            return {
                "scrape_status": "blocked" if resp and resp.status_code in (503, 429) else "error",
                "scrape_error": f"HTTP {resp.status_code if resp else 'None'}",
            }
        if "api-services-support@amazon.com" in resp.text or \
           ("robot" in resp.text[:2000].lower() and len(resp.text) < 5000):
            return {"scrape_status": "blocked", "scrape_error": "CAPTCHA detected"}

        soup = BeautifulSoup(resp.text, "html.parser")
        result = {"scrape_status": "success", "currency": "USD"}

        result["price"] = self._price(soup)
        result["original_price"] = self._orig_price(soup)
        if result["price"] and result["original_price"] and result["original_price"] > result["price"]:
            result["discount_pct"] = round(
                (result["original_price"] - result["price"]) / result["original_price"] * 100, 1
            )

        result["rating"] = self._rating(soup)
        result["review_count"] = self._reviews(soup)
        result.update(self._stock(soup))
        result.update(self._bsr(soup))
        result.update(self._seller(soup))
        result.update(self._promos(soup))
        return result

    def _price(self, soup):
        for sel in [
            "#priceblock_ourprice", "#priceblock_dealprice",
            ".a-price .a-offscreen", "#price_inside_buybox",
            "#corePrice_feature_div .a-price .a-offscreen", "#newBuyBoxPrice",
            "#apex_desktop .a-price .a-offscreen",
        ]:
            el = soup.select_one(sel)
            if el:
                p = clean_price(el.get_text())
                if p:
                    return p
        return None

    def _orig_price(self, soup):
        for sel in [".priceBlockStrikePriceString", ".a-text-price .a-offscreen", "#listPrice"]:
            el = soup.select_one(sel)
            if el:
                p = clean_price(el.get_text())
                if p:
                    return p
        return None

    def _rating(self, soup):
        el = soup.select_one("#acrPopover, [data-hook='rating-out-of-text']")
        if el:
            return clean_rating(el.get("title", "") or el.get_text())
        el = soup.select_one(".a-icon-star .a-icon-alt")
        if el:
            return clean_rating(el.get_text())
        return None

    def _reviews(self, soup):
        el = soup.select_one("#acrCustomerReviewText, [data-hook='total-review-count']")
        return clean_review_count(el.get_text()) if el else None

    def _stock(self, soup):
        el = soup.select_one("#availability, #outOfStock")
        if not el:
            return {"in_stock": 1, "stock_level": "In Stock"}
        text = el.get_text(strip=True)
        if re.search(r"out of stock|unavailable|currently unavailable", text, re.I):
            return {"in_stock": 0, "stock_level": text}
        if re.search(r"only \d+ left|low in stock", text, re.I):
            return {"in_stock": 1, "stock_level": text}
        return {"in_stock": 1, "stock_level": text or "In Stock"}

    def _bsr(self, soup):
        for row in soup.select(
            "#detailBulletsWrapper_feature_div li, #productDetails_detailBullets_sections1 tr"
        ):
            text = row.get_text(" ", strip=True)
            if "Best Sellers Rank" in text or "Amazon Best Sellers Rank" in text:
                m = re.search(r"#([\d,]+)\s+in\s+([^(#]+)", text)
                if m:
                    return {
                        "bsr_rank": int(m.group(1).replace(",", "")),
                        "category_rank": m.group(2).strip(),
                    }
        return {}

    def _seller(self, soup):
        r = {}
        el = soup.select_one("#sellerProfileTriggerId, #merchant-info a")
        if el:
            r["sold_by"] = el.get_text(strip=True)
        mi = soup.select_one("#merchant-info")
        if mi:
            t = mi.get_text(" ", strip=True)
            r["fulfilled_by"] = "Amazon" if "Amazon" in t else "Merchant"
        r["is_prime"] = 1 if soup.select_one("[aria-label*='Prime'], .a-icon-prime") else 0
        return r

    def _promos(self, soup):
        r = {"has_coupon": 0, "is_sponsored": 0}
        c = soup.select_one(".coupon-badge, #coupon-badge-id, [data-feature-name='couponBadge']")
        if c:
            r["has_coupon"] = 1
            r["coupon_value"] = c.get_text(strip=True)
        d = soup.select_one(".deal-badge, #dealBadge, [data-hook='deal-badge']")
        if d:
            r["deal_badge"] = d.get_text(strip=True)
        return r


# ══════════════════════════════════════════════════════════════
# GENERIC SEARCH SCRAPER — base for all non-Amazon channels
# ══════════════════════════════════════════════════════════════
class GenericSearchScraper(BaseScraper):
    CHANNEL_ID = ""

    def search_url(self, term):
        raise NotImplementedError

    def scrape_product(self, product_id, url):
        term = PRODUCT_SEARCH_TERMS.get(product_id, product_id)
        surl = self.search_url(term)
        resp = self.fetch(surl)
        if not resp or resp.status_code != 200:
            return {
                "scrape_status": "error",
                "scrape_error": f"HTTP {resp.status_code if resp else 'None'}",
                "raw_url": surl,
            }
        soup = BeautifulSoup(resp.text, "html.parser")
        result = self.parse_result(soup, term)
        result["raw_url"] = surl
        return result

    def parse_result(self, soup, term):
        result = {"scrape_status": "success", "currency": "USD"}

        # Try JSON-LD first
        for script in soup.find_all("script", {"type": "application/ld+json"}):
            try:
                ld = json.loads(script.string or "")
                items = ld if isinstance(ld, list) else [ld]
                for item in items:
                    if item.get("@type") in ("Product", "ItemList"):
                        offers = item.get("offers", item.get("Offers", {}))
                        if isinstance(offers, list):
                            offers = offers[0] if offers else {}
                        price = clean_price(str(offers.get("price", "")))
                        if price:
                            result["price"] = price
                            avail = offers.get("availability", "")
                            result["in_stock"] = 1 if "InStock" in avail else 0
                            result["stock_level"] = avail.split("/")[-1] if "/" in avail else avail or "Unknown"
                            result["rating"] = item.get("aggregateRating", {}).get("ratingValue")
                            result["review_count"] = item.get("aggregateRating", {}).get("reviewCount")
                            return result
            except Exception:
                continue

        # HTML fallback — generic price selectors
        for sel in [
            "[data-price]", "[itemprop='price']",
            "[class*='product-price']", "[class*='ProductPrice']",
            "span.price", "div.price", "[class*='price']",
        ]:
            el = soup.select_one(sel)
            if el:
                p = clean_price(
                    el.get("content", "") or el.get("data-price", "") or el.get_text()
                )
                if p:
                    result["price"] = p
                    break

        # Rating
        for sel in [
            "[itemprop='ratingValue']",
            "[class*='rating'][aria-label]",
            "[class*='stars'][aria-label]",
            "[class*='review-average']",
        ]:
            el = soup.select_one(sel)
            if el:
                r = clean_rating(
                    el.get("content", "") or el.get("aria-label", "") or el.get_text()
                )
                if r:
                    result["rating"] = r
                    break

        # Review count
        for sel in [
            "[itemprop='reviewCount']",
            "[class*='review-count']",
            "[class*='num-reviews']",
            "[class*='rating-count']",
        ]:
            el = soup.select_one(sel)
            if el:
                rc = clean_review_count(el.get("content", "") or el.get_text())
                if rc:
                    result["review_count"] = rc
                    break

        # Stock
        oos = soup.select_one(
            "[class*='out-of-stock'], [class*='sold-out'], [class*='unavailable']"
        )
        result["in_stock"] = 0 if oos else 1
        result["stock_level"] = oos.get_text(strip=True) if oos else "In Stock"

        if not result.get("price"):
            result["scrape_status"] = "not_found"
            result["scrape_error"] = f"No price found on {self.CHANNEL_ID}"

        return result


# ══════════════════════════════════════════════════════════════
# TIER A — 5 major US retailers + Logitech.com
# ══════════════════════════════════════════════════════════════

class WalmartScraper(GenericSearchScraper):
    CHANNEL_ID = "walmart"

    def search_url(self, term):
        return f"https://www.walmart.com/search?q={quote_plus(term)}"

    def parse_result(self, soup, term):
        result = {"scrape_status": "success", "currency": "USD"}
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
                        result["price"] = float(price)
                        result["rating"] = item.get("averageRating")
                        result["review_count"] = item.get("numberOfReviews")
                        avail = item.get("availabilityStatus", "")
                        result["in_stock"] = 1 if "STOCK" in avail.upper() else 0
                        result["stock_level"] = avail
                        result["sold_by"] = item.get("sellerDisplayName", "")
                        return result
            except Exception:
                pass
        return super().parse_result(soup, term)


class TargetScraper(GenericSearchScraper):
    CHANNEL_ID = "target"

    def search_url(self, term):
        return f"https://www.target.com/s?searchTerm={quote_plus(term)}"

    def parse_result(self, soup, term):
        result = {"scrape_status": "success", "currency": "USD"}
        el = soup.select_one('[data-test="product-price"]')
        if el:
            result["price"] = clean_price(el.get_text())
        el = soup.select_one('[data-test="ratings"] span[aria-label]')
        if el:
            result["rating"] = clean_rating(el.get("aria-label", ""))
        el = soup.select_one('[data-test="rating-count"]')
        if el:
            result["review_count"] = clean_review_count(el.get_text())
        oos = soup.select_one('[data-test="outOfStockMessage"]')
        result["in_stock"] = 0 if oos else 1
        result["stock_level"] = oos.get_text(strip=True) if oos else "In Stock"
        if not result.get("price"):
            return super().parse_result(soup, term)
        return result


class BestBuyScraper(GenericSearchScraper):
    CHANNEL_ID = "bestbuy"

    def search_url(self, term):
        return f"https://www.bestbuy.com/site/searchpage.jsp?st={quote_plus(term)}"

    def parse_result(self, soup, term):
        result = {"scrape_status": "success", "currency": "USD"}
        jld = soup.find("script", {"type": "application/ld+json"})
        if jld:
            try:
                ld = json.loads(jld.string)
                if isinstance(ld, list):
                    ld = ld[0]
                if ld.get("@type") == "Product":
                    offers = ld.get("offers", {})
                    result["price"] = clean_price(str(offers.get("price", "")))
                    result["rating"] = ld.get("aggregateRating", {}).get("ratingValue")
                    result["review_count"] = ld.get("aggregateRating", {}).get("reviewCount")
                    avail = offers.get("availability", "")
                    result["in_stock"] = 1 if "InStock" in avail else 0
                    result["stock_level"] = avail.split("/")[-1] if "/" in avail else avail
                    if result["price"]:
                        return result
            except Exception:
                pass
        el = soup.select_one('[class*="priceView-customer-price"] span, .priceView-hero-price span')
        if el:
            result["price"] = clean_price(el.get_text())
        if not result.get("price"):
            return super().parse_result(soup, term)
        return result


class EbayScraper(GenericSearchScraper):
    CHANNEL_ID = "ebay"

    def search_url(self, term):
        return f"https://www.ebay.com/sch/i.html?_nkw={quote_plus(term)}&_sop=12&LH_ItemCondition=1000"

    def parse_result(self, soup, term):
        result = {"scrape_status": "success", "currency": "USD"}
        for item in soup.select(".s-item")[:10]:
            if item.select_one(".s-item__badge--PROMOTED"):
                continue
            price_el = item.select_one(".s-item__price")
            if not price_el:
                continue
            price = clean_price(price_el.get_text())
            if price and 5 < price < 5000:
                result["price"] = price
                result["in_stock"] = 1
                result["stock_level"] = "Available"
                seller_el = item.select_one(".s-item__seller-info-text")
                if seller_el:
                    result["sold_by"] = seller_el.get_text(strip=True)
                return result
        result["scrape_status"] = "not_found"
        result["scrape_error"] = "No eBay listings found"
        return result


class LogitechDirectScraper(GenericSearchScraper):
    CHANNEL_ID = "logitech"

    def search_url(self, term):
        return f"https://www.logitech.com/en-us/search?q={quote_plus(term)}"


# ══════════════════════════════════════════════════════════════
# TIER B — 14 additional US channels
# ══════════════════════════════════════════════════════════════

class NeweggScraper(GenericSearchScraper):
    CHANNEL_ID = "newegg"
    def search_url(self, term):
        return f"https://www.newegg.com/p/pl?d={quote_plus(term)}"


class KohlsScraper(GenericSearchScraper):
    CHANNEL_ID = "kohls"
    def search_url(self, term):
        return f"https://www.kohls.com/search/results.jsp?keyword={quote_plus(term)}"


class CostcoScraper(GenericSearchScraper):
    CHANNEL_ID = "costco"
    def search_url(self, term):
        return f"https://www.costco.com/CatalogSearch?keyword={quote_plus(term)}"


class SamsClubScraper(GenericSearchScraper):
    CHANNEL_ID = "samsclub"
    def search_url(self, term):
        return f"https://www.samsclub.com/s/{quote_plus(term)}"


class BHPhotoScraper(GenericSearchScraper):
    CHANNEL_ID = "bhphotovideo"
    def search_url(self, term):
        return f"https://www.bhphotovideo.com/c/search?Ntt={quote_plus(term)}"


class AdoramaScraper(GenericSearchScraper):
    CHANNEL_ID = "adorama"
    def search_url(self, term):
        return f"https://www.adorama.com/l/?searchinfo={quote_plus(term)}"


class StaplesScraper(GenericSearchScraper):
    CHANNEL_ID = "staples"
    def search_url(self, term):
        return f"https://www.staples.com/search?query={quote_plus(term)}"


class OfficeDepotScraper(GenericSearchScraper):
    CHANNEL_ID = "officedepot"
    def search_url(self, term):
        return f"https://www.officedepot.com/catalog/search.do?Ntt={quote_plus(term)}"


class MicroCenterScraper(GenericSearchScraper):
    CHANNEL_ID = "microcenter"
    def search_url(self, term):
        return f"https://www.microcenter.com/search/search_results.aspx?Ntk=all&N=4294967288&myStore=false&DisplayCount=24&Ntt={quote_plus(term)}"


class RakutenScraper(GenericSearchScraper):
    CHANNEL_ID = "rakuten"
    def search_url(self, term):
        return f"https://www.rakuten.com/search/{quote_plus(term)}/"


class OverstockScraper(GenericSearchScraper):
    CHANNEL_ID = "overstock"
    def search_url(self, term):
        return f"https://www.overstock.com/search?keywords={quote_plus(term)}"


class WayfairScraper(GenericSearchScraper):
    CHANNEL_ID = "wayfair"
    def search_url(self, term):
        return f"https://www.wayfair.com/keyword.php?keyword={quote_plus(term)}"


class HomeDepotScraper(GenericSearchScraper):
    CHANNEL_ID = "homedepot"
    def search_url(self, term):
        return f"https://www.homedepot.com/s/{quote_plus(term)}"


class MacysScraper(GenericSearchScraper):
    CHANNEL_ID = "macys"
    def search_url(self, term):
        return f"https://www.macys.com/shop/featured/{quote_plus(term)}"


# ══════════════════════════════════════════════════════════════
# REGISTRY — maps every channel_id → (scraper, url_map)
# ══════════════════════════════════════════════════════════════
def build_scraper_registry(conn, run_id=None):
    registry = {}

    # All 12 Amazon marketplaces — direct ASIN URLs
    for ch in AMAZON_DOMAINS:
        scraper = AmazonScraper(conn, channel_id=ch, run_id=run_id)
        registry[ch] = (scraper, amazon_urls_for(ch))

    # All non-Amazon channels — search-based URL maps
    non_amazon_classes = [
        WalmartScraper, TargetScraper, BestBuyScraper, EbayScraper, LogitechDirectScraper,
        NeweggScraper, KohlsScraper, CostcoScraper, SamsClubScraper, BHPhotoScraper,
        AdoramaScraper, StaplesScraper, OfficeDepotScraper, MicroCenterScraper,
        RakutenScraper, OverstockScraper, WayfairScraper, HomeDepotScraper, MacysScraper,
    ]
    for ScraperClass in non_amazon_classes:
        s = ScraperClass(conn, run_id=run_id)
        registry[s.CHANNEL_ID] = (s, search_map())

    return registry