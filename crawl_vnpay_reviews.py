"""
crawl_vnpay_reviews.py
----------------------
Crawl up to 5000 reviews for the VNPAY app (vnpay.smartacccount) from
Google Play Store using the local google-play-scraper library.

Strategy
--------
- Use `reviews()` with continuation_token for manual pagination so we can
  inject random sleep between batches and control progress precisely.
- Sort: NEWEST first (Sort.NEWEST).
- Each batch fetches up to 200 reviews (safe, well below the 4500 cap).
- Random delay [2, 6] seconds between batches to avoid IP throttling.
- Stops when we reach TARGET_COUNT reviews OR no more continuation token.
- Saves results to a UTF-8 CSV file.

Usage
-----
    python crawl_vnpay_reviews.py

Output
------
    vnpay_reviews_<timestamp>.csv
"""

import csv
import logging
import random
import sys
import time
from datetime import datetime
from pathlib import Path

# ── library lives in the same repo ──────────────────────────────────────────
# Make sure we import from the local source, not a globally installed package.
sys.path.insert(0, str(Path(__file__).parent))

from google_play_scraper import Sort, reviews

# ── Configuration ────────────────────────────────────────────────────────────
APP_ID = "vnpay.smartacccount"
LANG = "vi"          # Vietnamese reviews
COUNTRY = "vn"       # Vietnam store
TARGET_COUNT = 5000  # Maximum reviews to collect
BATCH_SIZE = 200     # Reviews per request (keep <= 200 for stability)
DELAY_MIN = 2.0      # Minimum sleep between batches (seconds)
DELAY_MAX = 6.0      # Maximum sleep between batches (seconds)

OUTPUT_DIR = Path(__file__).parent
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUTPUT_FILE = OUTPUT_DIR / f"vnpay_reviews_gstore_{TIMESTAMP}.csv"

# CSV columns (matches fields returned by the library)
CSV_FIELDS = [
    "reviewId",
    "userName",
    "userImage",
    "content",
    "score",
    "thumbsUpCount",
    "reviewCreatedVersion",
    "at",
    "replyContent",
    "repliedAt",
    "appVersion",
]

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(OUTPUT_DIR / f"crawl_{TIMESTAMP}.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def random_delay(min_s: float = DELAY_MIN, max_s: float = DELAY_MAX) -> None:
    """Sleep for a random duration to mimic human pacing."""
    delay = round(random.uniform(min_s, max_s), 2)
    log.info(f"  [sleep] {delay}s before next batch...")
    time.sleep(delay)


def safe_str(value) -> str:
    """Convert any value to a clean string for CSV."""
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def flatten_review(review: dict) -> dict:
    """Return a flat dict with only the columns we want."""
    return {field: safe_str(review.get(field)) for field in CSV_FIELDS}


# ── Main crawl logic ──────────────────────────────────────────────────────────

def crawl() -> None:
    log.info("=" * 60)
    log.info(f"  VNPAY Review Crawler")
    log.info(f"  App ID   : {APP_ID}")
    log.info(f"  Target   : {TARGET_COUNT} reviews")
    log.info(f"  Batch    : {BATCH_SIZE} / request")
    log.info(f"  Language : {LANG}  |  Country : {COUNTRY}")
    log.info(f"  Output   : {OUTPUT_FILE.name}")
    log.info("=" * 60)

    all_reviews: list[dict] = []
    continuation_token = None
    batch_num = 0
    consecutive_errors = 0
    MAX_CONSECUTIVE_ERRORS = 5

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=CSV_FIELDS)
        writer.writeheader()

        while len(all_reviews) < TARGET_COUNT:
            remaining = TARGET_COUNT - len(all_reviews)
            fetch_size = min(BATCH_SIZE, remaining)
            batch_num += 1

            log.info(
                f"Batch #{batch_num:03d}  |  collected={len(all_reviews)}  "
                f"|  fetching={fetch_size}  |  remaining={remaining}"
            )

            try:
                batch_reviews, continuation_token = reviews(
                    APP_ID,
                    lang=LANG,
                    country=COUNTRY,
                    sort=Sort.NEWEST,
                    count=fetch_size,
                    continuation_token=continuation_token,
                )
                consecutive_errors = 0  # reset on success
            except Exception as exc:
                consecutive_errors += 1
                log.warning(
                    f"  [WARN] Error on batch #{batch_num}: {exc}  "
                    f"(consecutive={consecutive_errors})"
                )
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    log.error(
                        "  [ERROR] Too many consecutive errors. Stopping crawl early."
                    )
                    break
                random_delay(DELAY_MAX, DELAY_MAX * 1.5)  # longer back-off
                continue

            if not batch_reviews:
                log.info("  [INFO] No reviews returned. The store may have no more data.")
                break

            # Write batch to CSV immediately (streaming — safe if interrupted)
            rows = [flatten_review(r) for r in batch_reviews]
            writer.writerows(rows)
            csv_file.flush()

            all_reviews.extend(batch_reviews)
            log.info(
                f"  [OK] Got {len(batch_reviews)} reviews  |  "
                f"total so far = {len(all_reviews)}"
            )

            # Stop conditions
            if continuation_token is None or continuation_token.token is None:
                log.info("  [END] No continuation token - reached end of available reviews.")
                break

            if len(all_reviews) >= TARGET_COUNT:
                log.info(f"  [DONE] Reached target of {TARGET_COUNT} reviews.")
                break

            # Polite random delay before next batch
            random_delay()

    # ── Summary ───────────────────────────────────────────────────────────────
    log.info("=" * 60)
    log.info(f"  Crawl complete!")
    log.info(f"  Total reviews saved : {len(all_reviews)}")
    log.info(f"  Batches executed    : {batch_num}")
    log.info(f"  Output file         : {OUTPUT_FILE.name}")
    log.info("=" * 60)

    if len(all_reviews) == 0:
        log.warning(
            "  [WARN] Zero reviews collected. Possible causes:\n"
            "      - The app ID is incorrect\n"
            "      - The country/language combo has no reviews\n"
            "      - Google Play blocked the requests\n"
            "      - The library's request format has changed"
        )


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    try:
        crawl()
    except KeyboardInterrupt:
        log.info("\n  [STOP] Crawl interrupted by user (Ctrl+C). Partial data saved.")
        sys.exit(0)
