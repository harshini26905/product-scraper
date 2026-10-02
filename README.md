# Product Web Scraper

Extracts **name, price, rating and product URL** from a public, paginated e-commerce category and writes a structured CSV.

Default target: [Books to Scrape](https://books.toscrape.com/), a public site built for scraping practice.

## Extraction record

Filled in automatically by `scraper.py` at the end of each run (also saved to `extraction_metadata.json`).

<!-- EXTRACTION:START -->
- **Extraction timestamp (UTC):** 2026-10-02T08:30:53Z
- **Starting URL:** https://books.toscrape.com/catalogue/category/books_1/index.html
- **Records:** 1000 (1000 with all fields)
- **Pages fetched (50):**
  - https://books.toscrape.com/catalogue/category/books_1/index.html
  - https://books.toscrape.com/catalogue/category/books_1/page-2.html
  - https://books.toscrape.com/catalogue/category/books_1/page-3.html
  - https://books.toscrape.com/catalogue/category/books_1/page-4.html
  - https://books.toscrape.com/catalogue/category/books_1/page-5.html
  - https://books.toscrape.com/catalogue/category/books_1/page-6.html
  - https://books.toscrape.com/catalogue/category/books_1/page-7.html
  - https://books.toscrape.com/catalogue/category/books_1/page-8.html
  - https://books.toscrape.com/catalogue/category/books_1/page-9.html
  - https://books.toscrape.com/catalogue/category/books_1/page-10.html
  - https://books.toscrape.com/catalogue/category/books_1/page-11.html
  - https://books.toscrape.com/catalogue/category/books_1/page-12.html
  - https://books.toscrape.com/catalogue/category/books_1/page-13.html
  - https://books.toscrape.com/catalogue/category/books_1/page-14.html
  - https://books.toscrape.com/catalogue/category/books_1/page-15.html
  - https://books.toscrape.com/catalogue/category/books_1/page-16.html
  - https://books.toscrape.com/catalogue/category/books_1/page-17.html
  - https://books.toscrape.com/catalogue/category/books_1/page-18.html
  - https://books.toscrape.com/catalogue/category/books_1/page-19.html
  - https://books.toscrape.com/catalogue/category/books_1/page-20.html
  - https://books.toscrape.com/catalogue/category/books_1/page-21.html
  - https://books.toscrape.com/catalogue/category/books_1/page-22.html
  - https://books.toscrape.com/catalogue/category/books_1/page-23.html
  - https://books.toscrape.com/catalogue/category/books_1/page-24.html
  - https://books.toscrape.com/catalogue/category/books_1/page-25.html
  - https://books.toscrape.com/catalogue/category/books_1/page-26.html
  - https://books.toscrape.com/catalogue/category/books_1/page-27.html
  - https://books.toscrape.com/catalogue/category/books_1/page-28.html
  - https://books.toscrape.com/catalogue/category/books_1/page-29.html
  - https://books.toscrape.com/catalogue/category/books_1/page-30.html
  - https://books.toscrape.com/catalogue/category/books_1/page-31.html
  - https://books.toscrape.com/catalogue/category/books_1/page-32.html
  - https://books.toscrape.com/catalogue/category/books_1/page-33.html
  - https://books.toscrape.com/catalogue/category/books_1/page-34.html
  - https://books.toscrape.com/catalogue/category/books_1/page-35.html
  - https://books.toscrape.com/catalogue/category/books_1/page-36.html
  - https://books.toscrape.com/catalogue/category/books_1/page-37.html
  - https://books.toscrape.com/catalogue/category/books_1/page-38.html
  - https://books.toscrape.com/catalogue/category/books_1/page-39.html
  - https://books.toscrape.com/catalogue/category/books_1/page-40.html
  - https://books.toscrape.com/catalogue/category/books_1/page-41.html
  - https://books.toscrape.com/catalogue/category/books_1/page-42.html
  - https://books.toscrape.com/catalogue/category/books_1/page-43.html
  - https://books.toscrape.com/catalogue/category/books_1/page-44.html
  - https://books.toscrape.com/catalogue/category/books_1/page-45.html
  - https://books.toscrape.com/catalogue/category/books_1/page-46.html
  - https://books.toscrape.com/catalogue/category/books_1/page-47.html
  - https://books.toscrape.com/catalogue/category/books_1/page-48.html
  - https://books.toscrape.com/catalogue/category/books_1/page-49.html
  - https://books.toscrape.com/catalogue/category/books_1/page-50.html
<!-- EXTRACTION:END -->

## Usage

```bash
pip install -r requirements.txt
python scraper.py                      # default category, writes products.csv
python scraper.py --url <category-url> --output out.csv --min-records 50 --verbose
```

Outputs: `products.csv` (header row + one row per product), `sample_output.md` (first 10 rows), `extraction_metadata.json`.

CSV columns: `name, price, rating, product_url`
- `price`: numeric string, currency symbol stripped
- `rating`: 1–5 where the site provides one, otherwise empty

## How it meets the requirements

| Requirement | Implementation |
|---|---|
| Name, price, rating, URL | `parse_card()` |
| CSV with header, 50+ records | `write_csv()`; the default category has 1,000 products across 50 pages; exit code 2 and a warning if fewer than `--min-records` are found |
| Source URLs + timestamp | `update_readme()` and `extraction_metadata.json` (UTC, ISO 8601) |
| Pagination | Follows the "next" link until none remains; `--max-pages` cap and loop guard |
| Layout variations | Ordered fallback selector lists in `PROFILE` (e.g. `article.product_pod`, `li.product`, schema.org `itemprop`); rating read from word classes, numeric text or data attributes |
| Request failures | Timeouts; automatic retries with backoff on 429/5xx and connection errors; a failed page is logged and records already collected are kept |
| Missing fields | A missing field becomes an empty cell and is logged; a malformed card is skipped without aborting; duplicates removed by product URL |

## Notes

- Polite by default: custom User-Agent and 0.5 s delay between requests (`--delay`).
- Check a site's terms of service and `robots.txt` before pointing this at a different target.
- Tested against a local mock site (3 pages, a transient 503, a card missing price, a card missing rating, a dead host). The mock site is not included, and none of its data is in the deliverable CSV.
