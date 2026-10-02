#!/usr/bin/env python3
"""Product data scraper.

Extracts name, price, rating and product URL from a paginated e-commerce
category page and writes a CSV. Default target is books.toscrape.com, a
public site built for scraping practice.

Usage:
    python scraper.py
    python scraper.py --url https://books.toscrape.com/catalogue/category/books/travel_2/index.html
    python scraper.py --min-records 50 --output products.csv
"""
import argparse
import csv
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_URL = "https://books.toscrape.com/catalogue/category/books_1/index.html"
FIELDS = ["name", "price", "rating", "product_url"]
USER_AGENT = "Mozilla/5.0 (compatible; ProductScraperDemo/1.0; educational use)"
WORDS = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5}

log = logging.getLogger("scraper")

# Layout variations: each profile lists candidate CSS selectors tried in order.
# The first selector that matches wins, so alternative page layouts are handled
# without code changes.
PROFILE = {
    "card": ["article.product_pod", "li.product", "div.product", "div.product-card",
             "[itemtype*='schema.org/Product']", "div.thumbnail"],
    "name": ["h3 a[title]", "h3 a", "h2 a", "a.title", "[itemprop='name']", ".product-title"],
    "price": [".price_color", ".price", "[itemprop='price']", "span.amount", ".product-price"],
    "rating": ["p.star-rating", ".rating", "[itemprop='ratingValue']", "[data-rating]"],
    "link": ["h3 a", "h2 a", "a.title", "a[href]"],
    "next": ["li.next a", "a[rel='next']", "a.next", "a.next-page"],
}


def make_session(retries=3, backoff=1.0):
    """Session with automatic retry on transient HTTP errors and connection failures."""
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(total=retries, backoff_factor=backoff,
                  status_forcelist=(429, 500, 502, 503, 504),
                  allowed_methods=("GET",), respect_retry_after_header=True)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    return s


def fetch(session, url, timeout=15):
    """Return page HTML, or None if the request failed (error is logged)."""
    try:
        resp = session.get(url, timeout=timeout)
        resp.raise_for_status()
        # Site may omit charset; trust detected encoding to avoid mojibake.
        resp.encoding = resp.apparent_encoding if resp.encoding in (None, "ISO-8859-1") else resp.encoding
        return resp.text
    except requests.exceptions.RequestException as exc:
        log.error("Request failed for %s: %s", url, exc)
        return None


def first(node, selectors):
    """First element matching any selector, else None."""
    for sel in selectors:
        found = node.select_one(sel)
        if found is not None:
            return found
    return None


def parse_price(text):
    """'£51.77' -> '51.77'. Returns '' if no number is found."""
    m = re.search(r"\d[\d,]*\.?\d*", text or "")
    return m.group(0).replace(",", "") if m else ""


def parse_rating(el):
    """Handle word classes ('star-rating Three'), numeric text, or data attributes."""
    if el is None:
        return ""
    for cls in el.get("class", []):
        if cls.lower() in WORDS:
            return str(WORDS[cls.lower()])
    for raw in (el.get("data-rating"), el.get("content"), el.get_text(strip=True)):
        m = re.search(r"\d+(\.\d+)?", raw or "")
        if m:
            return m.group(0)
    return ""


def parse_card(card, base_url):
    """Extract one record. Missing fields become '' rather than raising."""
    name_el = first(card, PROFILE["name"])
    name = (name_el.get("title") or name_el.get_text(strip=True)) if name_el else ""
    price_el = first(card, PROFILE["price"])
    price = parse_price(price_el.get("content") if price_el and price_el.get("content")
                        else price_el.get_text() if price_el else "")
    link_el = first(card, PROFILE["link"])
    href = link_el.get("href") if link_el else ""
    return {
        "name": name.strip(),
        "price": price,
        "rating": parse_rating(first(card, PROFILE["rating"])),
        "product_url": urljoin(base_url, href) if href else "",
    }


def parse_page(html, base_url):
    """Return (records, next_page_url_or_None)."""
    soup = BeautifulSoup(html, "html.parser")
    cards = []
    for sel in PROFILE["card"]:
        cards = soup.select(sel)
        if cards:
            break
    if not cards:
        log.warning("No product cards found on %s (unrecognised layout?)", base_url)
    records = []
    for i, card in enumerate(cards, 1):
        try:
            rec = parse_card(card, base_url)
        except Exception as exc:  # one bad card must not abort the run
            log.warning("Skipping card %d on %s: %s", i, base_url, exc)
            continue
        if not rec["name"] and not rec["product_url"]:
            log.warning("Skipping empty card %d on %s", i, base_url)
            continue
        missing = [k for k in FIELDS if not rec[k]]
        if missing:
            log.info("Record %r missing fields: %s", rec["name"] or rec["product_url"], missing)
        records.append(rec)
    nxt = first(soup, PROFILE["next"])
    next_url = urljoin(base_url, nxt["href"]) if nxt and nxt.get("href") else None
    return records, next_url


def scrape(start_url, max_pages=50, delay=0.5, session=None):
    """Follow pagination from start_url. Returns (records, pages_fetched, urls_visited)."""
    session = session or make_session()
    url, seen, records, visited = start_url, set(), [], []
    while url and url not in seen and len(visited) < max_pages:
        seen.add(url)  # guards against pagination loops
        log.info("Fetching %s", url)
        html = fetch(session, url)
        if html is None:
            break  # retries already exhausted; keep what we have
        visited.append(url)
        page_records, url = parse_page(html, visited[-1])
        records.extend(page_records)
        time.sleep(delay)
    # De-duplicate on product URL (fall back to name)
    unique, keys = [], set()
    for r in records:
        k = r["product_url"] or r["name"]
        if k not in keys:
            keys.add(k)
            unique.append(r)
    return unique, len(visited), visited


def write_csv(records, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(records)


def write_preview(records, path, n=10):
    lines = ["| " + " | ".join(FIELDS) + " |", "|" + "---|" * len(FIELDS)]
    for r in records[:n]:
        lines.append("| " + " | ".join(str(r[k]).replace("|", "\\|") for k in FIELDS) + " |")
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"# Sample output (first {min(n, len(records))} of {len(records)} records)\n\n")
        f.write("\n".join(lines) + "\n")


def update_readme(meta, path="README.md"):
    """Fill the extraction-record block in README.md between the markers."""
    try:
        text = open(path, encoding="utf-8").read()
    except OSError:
        return
    block = (
        "<!-- EXTRACTION:START -->\n"
        f"- **Extraction timestamp (UTC):** {meta['extraction_timestamp_utc']}\n"
        f"- **Starting URL:** {meta['source_url']}\n"
        f"- **Records:** {meta['records']} ({meta['complete_records']} with all fields)\n"
        f"- **Pages fetched ({meta['pages_fetched']}):**\n"
        + "".join(f"  - {u}\n" for u in meta["page_urls"])
        + "<!-- EXTRACTION:END -->"
    )
    new = re.sub(r"<!-- EXTRACTION:START -->.*?<!-- EXTRACTION:END -->", lambda _: block, text, flags=re.S)
    with open(path, "w", encoding="utf-8") as f:
        f.write(new)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", default=DEFAULT_URL, help="category/listing URL to start from")
    ap.add_argument("--output", default="products.csv")
    ap.add_argument("--max-pages", type=int, default=50)
    ap.add_argument("--min-records", type=int, default=50)
    ap.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(message)s")

    started = datetime.now(timezone.utc)
    records, pages, urls = scrape(args.url, args.max_pages, args.delay)
    if not records:
        log.error("No records extracted; nothing written.")
        return 1

    write_csv(records, args.output)
    write_preview(records, "sample_output.md")
    complete = sum(all(r[k] for k in FIELDS) for r in records)
    meta = {
        "source_url": args.url,
        "pages_fetched": pages,
        "page_urls": urls,
        "extraction_timestamp_utc": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "records": len(records),
        "complete_records": complete,
    }
    with open("extraction_metadata.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    update_readme(meta)
    print(json.dumps({k: v for k, v in meta.items() if k != "page_urls"}, indent=2))
    if len(records) < args.min_records:
        log.warning("Only %d records (< %d requested)", len(records), args.min_records)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
