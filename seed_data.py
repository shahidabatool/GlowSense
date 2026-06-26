"""GlowSense seed_data.py — Load raw data into glowsense.db.

Sources:
  1. Sephora CSVs — archive (8)/ folder  (no login needed)
  2. HuggingFace   — jhan21/amazon-beauty-reviews-dataset  (needs HF token)

Usage (CLI):
    python seed_data.py --source sephora --limit 5000
    python seed_data.py --source huggingface --limit 2000

Usage (from Streamlit): import and call seed_sephora() / seed_huggingface().
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sqlite3
import sys
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

# ── Auto-load .env token ──────────────────────────────────────────────────
_ENV_FILE = Path(__file__).parent / ".env"
if _ENV_FILE.exists() and not os.environ.get("HF_TOKEN"):
    for _line in _ENV_FILE.read_text().splitlines():
        if _line.startswith("HF_TOKEN="):
            os.environ["HF_TOKEN"] = _line.split("=", 1)[1].strip()
            break

from database import init_db, insert_products_bulk, insert_reviews_bulk, bulk_update_amazon_products


ARCHIVE_DIR = Path(__file__).parent / "archive (8)"
PRODUCT_INFO_CSV = ARCHIVE_DIR / "product_info.csv"
ULTA_REVIEWS_CSV = Path(__file__).parent / "Ulta Skincare Reviews.csv"
REVIEW_CSV_PATTERNS = ["reviews_0-250.csv", "reviews_250-500.csv",
                       "reviews_500-750.csv", "reviews_750-1250.csv",
                       "reviews_1250-end.csv"]


# ── Sephora ───────────────────────────────────────────────────────────────

def seed_sephora(
    row_limit: int = 5000,
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> dict:
    """Seed from local Sephora CSV files.

    Args:
        row_limit: max number of REVIEW rows to insert (products are always fully loaded).
        progress_cb: optional callback(message, fraction 0-1) for Streamlit progress.

    Returns:
        dict with keys 'products_inserted', 'reviews_inserted'.
    """
    init_db()
    results = {"products_inserted": 0, "reviews_inserted": 0}

    # ── 1. Products ──────────────────────────────────────────────────────
    if progress_cb:
        progress_cb("Loading product catalogue …", 0.05)

    if PRODUCT_INFO_CSV.exists():
        prod_df = pd.read_csv(PRODUCT_INFO_CSV, low_memory=False)
        product_rows = []
        for _, row in prod_df.iterrows():
            product_rows.append({
                "product_id":   str(row.get("product_id", "")).strip() or None,
                "product_name": str(row.get("product_name", "")).strip(),
                "brand_name":   str(row.get("brand_name",  "")).strip() or None,
                "category":     str(row.get("primary_category", "")).strip() or None,
                "price_usd":    _float(row.get("price_usd")),
                "avg_rating":   _float(row.get("rating")),
                "review_count": _int(row.get("reviews")),
                "ingredients":  _clean_text(row.get("ingredients")),
                "highlights":   _clean_text(row.get("highlights")),
                "details_text": _clean_text(row.get("size")),
                "image_url":    None,
            })
        # Filter out rows missing product_id or product_name, or having fewer than 10 reviews
        product_rows = [
            r for r in product_rows 
            if r["product_id"] and r["product_name"] and r["review_count"] is not None and r["review_count"] >= 10
        ]
        n = insert_products_bulk(product_rows, source="sephora_csv")
        results["products_inserted"] = n
        if progress_cb:
            progress_cb(f"Inserted {n:,} products with 10+ reviews.", 0.25)
    else:
        if progress_cb:
            progress_cb("product_info.csv not found — skipping products.", 0.25)

    valid_product_ids = {r["product_id"] for r in product_rows} if PRODUCT_INFO_CSV.exists() else set()

    total_inserted = 0
    existing_files = [f for f in REVIEW_CSV_PATTERNS if (ARCHIVE_DIR / f).exists()]
    n_files = len(existing_files)

    if n_files == 0:
        if progress_cb:
            progress_cb("No review CSV files found in archive folder.", 1.0)
        return results

    # Divide limit evenly across all files so each brand range gets coverage
    per_file_limit = max(1, row_limit // n_files)
    if progress_cb:
        progress_cb(
            f"Reading ~{per_file_limit:,} rows from each of {n_files} review files …", 0.28
        )

    for file_idx, fname in enumerate(existing_files):
        fpath = ARCHIVE_DIR / fname
        try:
            df = pd.read_csv(fpath, low_memory=False, nrows=per_file_limit)
        except Exception as exc:
            if progress_cb:
                progress_cb(f"Could not read {fname}: {exc}", None)
            continue

        review_rows = []
        for _, row in df.iterrows():
            text = str(row.get("review_text", "")).strip()
            if not text or text == "nan":
                continue
            pid = str(row.get("product_id", "")).strip() or None
            # Only keep review if product is valid (has 10+ reviews)
            if pid not in valid_product_ids:
                continue
            review_rows.append({
                "product_id":     pid,
                "product_name":   str(row.get("product_name", "")).strip(),
                "brand_name":     str(row.get("brand_name", "")).strip() or None,
                "rating":         _float(row.get("rating")),
                "review_text":    text,
                "review_title":   str(row.get("review_title", "")).strip() or None,
                "skin_type":      str(row.get("skin_type", "")).strip() or None,
                "is_recommended": _int(row.get("is_recommended")),
            })

        n = insert_reviews_bulk(review_rows, source="sephora_csv")
        total_inserted += n

        frac = 0.28 + 0.68 * ((file_idx + 1) / n_files)
        if progress_cb:
            progress_cb(
                f"Reviews from {fname}: +{n:,} inserted (total so far: {total_inserted:,})",
                frac,
            )

    results["reviews_inserted"] = total_inserted
    if progress_cb:
        progress_cb("✅ Sephora seeding complete.", 1.0)
    return results


# ── Amazon Enrichment ─────────────────────────────────────────────────────

def enrich_amazon_products(
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> dict:
    """Fetch product names from McAuley-Lab/Amazon-Reviews-2023 metadata
    and update all Amazon ASIN stubs in the products table.

    Requires: huggingface_hub, pandas  (already installed).
    Returns: dict with 'enriched' count.
    """
    try:
        from huggingface_hub import hf_hub_download  # type: ignore
    except ImportError:
        msg = "huggingface_hub not installed. Run: pip install huggingface_hub"
        if progress_cb:
            progress_cb(f"❌ {msg}", None)
        return {"error": msg, "enriched": 0}

    init_db()
    hf_token = os.environ.get("HF_TOKEN")

    if progress_cb:
        progress_cb("Downloading Amazon product metadata from HuggingFace …", 0.05)

    # ── Step 1: download the All Beauty metadata parquet (~small) ────────
    try:
        path = hf_hub_download(
            repo_id="McAuley-Lab/Amazon-Reviews-2023",
            filename="raw_meta_All_Beauty/full-00000-of-00001.parquet",
            repo_type="dataset",
            token=hf_token,
        )
    except Exception as exc:
        msg = f"Could not download metadata: {exc}"
        if progress_cb:
            progress_cb(f"❌ {msg}", None)
        return {"error": msg, "enriched": 0}

    if progress_cb:
        progress_cb("Parsing metadata …", 0.25)

    import pandas as pd
    meta = pd.read_parquet(path)
    wanted_cols = [
        "parent_asin", "title", "store", "price", "average_rating", "rating_number",
        "main_category", "features", "description", "categories", "details", "images",
    ]
    meta = meta[[c for c in wanted_cols if c in meta.columns]]
    meta = meta.dropna(subset=["parent_asin", "title"])
    meta = meta.drop_duplicates(subset=["parent_asin"])

    if progress_cb:
        progress_cb(f"Loaded {len(meta):,} product records. Matching to DB …", 0.35)

    # ── Step 2: build updates list ────────────────────────────────────────
    def _safe_float(val):
        try:
            f = float(val)
            return None if f != f else f  # NaN guard
        except (TypeError, ValueError):
            return None

    def _safe_int(val):
        try:
            return int(float(val))
        except (TypeError, ValueError):
            return None

    def _clean(val):
        if val is None:
            return None
        try:
            if pd.isna(val):
                return None
        except (TypeError, ValueError):
            pass
        text = str(val).strip()
        return None if not text or text == "nan" else text

    def _list_text(val, max_items: int = 8):
        if val is None:
            return None
        try:
            items = list(val)
        except TypeError:
            return _clean(val)
        cleaned = [str(item).strip() for item in items if str(item).strip() and str(item).strip() != "nan"]
        return " | ".join(cleaned[:max_items]) or None

    def _details_text(val):
        if val is None:
            return None
        if hasattr(val, "items"):
            parts = []
            for key, item in list(val.items())[:12]:
                cleaned = _clean(item)
                if cleaned:
                    parts.append(f"{key}: {cleaned}")
            return " | ".join(parts) or None
        return _clean(val)

    def _first_image(val):
        try:
            for key in ("hi_res", "large", "thumb"):
                for item in list(val.get(key) or []):
                    url = _clean(item)
                    if url:
                        return url
        except Exception:
            return None
        return None

    updates = []
    for _, row in meta.iterrows():
        asin  = str(row["parent_asin"]).strip()
        title = str(row["title"]).strip()
        if not asin or not title:
            continue
        features = _list_text(row.get("features"))
        description = _list_text(row.get("description"))
        categories = _list_text(row.get("categories"))
        highlights = " | ".join(x for x in (features, description, categories) if x) or None
        updates.append({
            "product_id":   asin,
            "product_name": title,
            "brand_name":   str(row.get("store", "") or "").strip() or None,
            "category":     str(row.get("main_category", "") or "").strip() or None,
            "price_usd":    _safe_float(row.get("price")),
            "avg_rating":   _safe_float(row.get("average_rating")),
            "review_count": _safe_int(row.get("rating_number")),
            "ingredients":  None,
            "highlights":   highlights,
            "details_text": _details_text(row.get("details")),
            "image_url":    _first_image(row.get("images")),
        })

    if progress_cb:
        progress_cb(f"Updating {len(updates):,} products in database …", 0.55)

    # ── Step 3: batch update in chunks of 2000 ───────────────────────────
    total_enriched = 0
    chunk_size = 2000
    n_chunks = max(1, len(updates) // chunk_size + 1)

    for i in range(0, len(updates), chunk_size):
        chunk = updates[i : i + chunk_size]
        n = bulk_update_amazon_products(chunk)
        total_enriched += n
        frac = 0.55 + 0.40 * min(1.0, (i + chunk_size) / len(updates))
        if progress_cb:
            progress_cb(f"Enriched {total_enriched:,} products so far …", frac)

    if progress_cb:
        progress_cb(f"✅ Enrichment complete. {total_enriched:,} products updated.", 1.0)

    return {"enriched": total_enriched}


# ── Ulta ──────────────────────────────────────────────────────────────────

def _ulta_product_id(brand: str, product: str) -> str:
    key = f"{brand.lower().strip()}::{product.lower().strip()}"
    digest = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
    return f"ulta_{digest}"


def seed_ulta(
    row_limit: Optional[int] = None,
    progress_cb: Optional[Callable[[str, float], None]] = None,
    replace_existing: bool = True,
) -> dict:
    """Seed Ulta Skincare Reviews.csv into GlowSense.

    The Ulta file has review text, product, brand, verification and location, but
    no numeric star rating. We still store reviews so GlowSense can analyze the
    wording and compare products/brands.
    """
    init_db()
    if not ULTA_REVIEWS_CSV.exists():
        msg = f"Ulta file not found: {ULTA_REVIEWS_CSV}"
        if progress_cb:
            progress_cb(f"❌ {msg}", None)
        return {"error": msg, "products_inserted": 0, "reviews_inserted": 0}

    if progress_cb:
        progress_cb("Reading Ulta Skincare Reviews.csv …", 0.05)

    df = pd.read_csv(ULTA_REVIEWS_CSV, low_memory=False)
    if row_limit:
        df = df.head(row_limit)

    # Make import idempotent so running it twice does not double the reviews.
    if replace_existing:
        db_path = Path(__file__).parent / "glowsense.db"
        with sqlite3.connect(db_path) as conn:
            conn.execute("DELETE FROM reviews WHERE source = 'ulta_csv'")
            conn.execute("DELETE FROM products WHERE source = 'ulta_csv'")

    # Pre-calculate review counts per product to filter to 10+ reviews
    pid_list = []
    for _, row in df.iterrows():
        product = _clean_text(row.get("Product"))
        if not product:
            continue
        brand = _clean_text(row.get("Brand")) or "Unknown brand"
        pid = _ulta_product_id(brand, product)
        pid_list.append(pid)

    from collections import Counter
    pid_counts = Counter(pid_list)

    product_rows: dict[str, dict] = {}
    review_rows: list[dict] = []

    for _, row in df.iterrows():
        product = _clean_text(row.get("Product"))
        brand = _clean_text(row.get("Brand"))
        text = _clean_text(row.get("Review_Text"))
        if not product or not text:
            continue
        brand = brand or "Unknown brand"
        pid = _ulta_product_id(brand, product)

        # Skip products with fewer than 10 reviews
        if pid_counts[pid] < 10:
            continue

        if pid not in product_rows:
            product_rows[pid] = {
                "product_id": pid,
                "product_name": product,
                "brand_name": brand,
                "category": "Skincare",
                "price_usd": None,
                "avg_rating": None,
                "review_count": pid_counts[pid],
                "ingredients": None,
                "highlights": "Ulta skincare review dataset",
                "details_text": "Source: Ulta Skincare Reviews.csv",
                "image_url": None,
            }

        title = _clean_text(row.get("Review_Title"))
        location = _clean_text(row.get("Review_Location"))
        review_date = _clean_text(row.get("Review_Date"))
        verified = _clean_text(row.get("Verified_Buyer"))
        meta_parts = []
        if title:
            meta_parts.append(title)
        if verified:
            meta_parts.append(f"Verified buyer: {verified}")
        if location:
            meta_parts.append(f"Location: {location}")
        if review_date:
            meta_parts.append(f"Review date: {review_date}")

        review_rows.append({
            "product_id": pid,
            "product_name": product,
            "brand_name": brand,
            "rating": None,
            "review_text": text,
            "review_title": " | ".join(meta_parts) or title,
            "skin_type": None,
            "is_recommended": None,
        })

    if progress_cb:
        progress_cb(f"Prepared {len(product_rows):,} Ulta products and {len(review_rows):,} reviews with 10+ reviews …", 0.45)

    products_inserted = insert_products_bulk(list(product_rows.values()), source="ulta_csv")
    reviews_inserted = insert_reviews_bulk(review_rows, source="ulta_csv")

    if progress_cb:
        progress_cb(f"✅ Ulta import complete: {products_inserted:,} products, {reviews_inserted:,} reviews.", 1.0)

    return {"products_inserted": products_inserted, "reviews_inserted": reviews_inserted}


# ── HuggingFace ───────────────────────────────────────────────────────────

def seed_huggingface(
    row_limit: int = 2000,
    progress_cb: Optional[Callable[[str, float], None]] = None,
) -> dict:
    """Seed from HuggingFace jhan21/amazon-beauty-reviews-dataset.

    Requires:
        pip install datasets
        huggingface-cli login   (or set HF_TOKEN env var)
    """
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        msg = "datasets package not installed. Run: pip install datasets"
        if progress_cb:
            progress_cb(f"❌ {msg}", None)
        return {"error": msg, "reviews_inserted": 0}

    init_db()
    results = {"reviews_inserted": 0}
    hf_token = os.environ.get("HF_TOKEN")

    if progress_cb:
        progress_cb("Connecting to HuggingFace Hub …", 0.05)

    try:
        ds = load_dataset(
            "jhan21/amazon-beauty-reviews-dataset",
            split="train",
            streaming=True,
            token=hf_token,
        )
    except Exception as exc:
        msg = f"Could not load HuggingFace dataset: {exc}"
        if progress_cb:
            progress_cb(f"❌ {msg}", None)
        return {"error": msg, "reviews_inserted": 0}

    if progress_cb:
        progress_cb("Streaming rows from HuggingFace …", 0.15)

    candidates = []
    for row in ds:
        text = str(row.get("text", "")).strip()
        if not text:
            continue

        asin = str(row.get("asin", "")).strip() or None
        product_name = asin or "Unknown Amazon Product"
        rating_raw = row.get("rating")

        candidates.append({
            "product_id":     asin,
            "product_name":   product_name,
            "brand_name":     None,
            "rating":         _float(rating_raw),
            "review_text":    text,
            "review_title":   str(row.get("title", "") or "").strip() or None,
            "skin_type":      None,
            "is_recommended": None,
        })
        # Stream a larger pool (e.g. 3x row_limit) to find products with 10+ reviews
        if len(candidates) >= row_limit * 3:
            break

    from collections import Counter
    asin_counts = Counter(r["product_id"] for r in candidates if r["product_id"])
    valid_asins = {asin for asin, count in asin_counts.items() if count >= 10}

    filtered_candidates = [r for r in candidates if r["product_id"] in valid_asins][:row_limit]

    # Batch insert in chunks
    batch = []
    total = 0

    for r in filtered_candidates:
        batch.append(r)
        if len(batch) >= 500:
            product_stubs = []
            seen = set()
            for br in batch:
                pid = br["product_id"]
                if pid and pid not in seen:
                    seen.add(pid)
                    product_stubs.append({
                        "product_id":   pid,
                        "product_name": pid,
                        "brand_name":   None,
                        "category":     "Beauty",
                        "price_usd":    None,
                        "avg_rating":   None,
                        "review_count": asin_counts[pid],
                    })
            if product_stubs:
                insert_products_bulk(product_stubs, source="amazon_hf")
            n = insert_reviews_bulk(batch, source="amazon_hf")
            total += n
            batch = []
            frac = min(0.15 + 0.80 * (total / row_limit), 0.95)
            if progress_cb:
                progress_cb(f"Amazon HF reviews inserted: {total:,}", frac)

    if batch:
        product_stubs = []
        seen = set()
        for br in batch:
            pid = br["product_id"]
            if pid and pid not in seen:
                seen.add(pid)
                product_stubs.append({
                    "product_id":   pid,
                    "product_name": pid,
                    "brand_name":   None,
                    "category":     "Beauty",
                    "price_usd":    None,
                    "avg_rating":   None,
                    "review_count": asin_counts[pid],
                })
        if product_stubs:
            insert_products_bulk(product_stubs, source="amazon_hf")
        n = insert_reviews_bulk(batch, source="amazon_hf")
        total += n

    results["reviews_inserted"] = total
    if progress_cb:
        progress_cb(f"✅ HuggingFace seeding complete. {total:,} reviews added.", 1.0)
    return results


# ── Helpers ───────────────────────────────────────────────────────────────

def _clean_text(val) -> Optional[str]:
    if val is None:
        return None
    text = str(val).strip()
    return None if not text or text == "nan" else text


def _float(val) -> Optional[float]:
    try:
        f = float(val)
        return None if (f != f) else f  # NaN guard
    except (TypeError, ValueError):
        return None


def _int(val) -> Optional[int]:
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return None


# ── CLI ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed GlowSense database")
    parser.add_argument("--source", choices=["sephora", "huggingface", "ulta", "both", "enrich"],
                        default="sephora")
    parser.add_argument("--limit", type=int, default=5000,
                        help="Max review rows to insert")
    args = parser.parse_args()

    def cli_progress(msg: str, frac):
        pct = f"[{int(frac*100):3d}%]" if frac is not None else "[    ]"
        print(f"{pct} {msg}", flush=True)

    if args.source in ("sephora", "both"):
        print(f"\n── Seeding from Sephora CSVs (limit={args.limit:,}) ──")
        r = seed_sephora(row_limit=args.limit, progress_cb=cli_progress)
        print(f"   products: {r['products_inserted']:,}  reviews: {r['reviews_inserted']:,}")

    if args.source in ("huggingface", "both"):
        print(f"\n── Seeding from HuggingFace (limit={args.limit:,}) ──")
        r = seed_huggingface(row_limit=args.limit, progress_cb=cli_progress)
        if "error" in r:
            print(f"   ERROR: {r['error']}", file=sys.stderr)
        else:
            print(f"   reviews: {r['reviews_inserted']:,}")

    if args.source in ("ulta", "both"):
        print("\n── Seeding from Ulta Skincare Reviews.csv ──")
        r = seed_ulta(row_limit=args.limit if args.limit else None, progress_cb=cli_progress)
        if "error" in r:
            print(f"   ERROR: {r['error']}", file=sys.stderr)
        else:
            print(f"   products: {r['products_inserted']:,}  reviews: {r['reviews_inserted']:,}")

    if args.source == "enrich":
        print("\n── Enriching Amazon product names from McAuley-Lab metadata ──")
        r = enrich_amazon_products(progress_cb=cli_progress)
        if "error" in r:
            print(f"   ERROR: {r['error']}", file=sys.stderr)
        else:
            print(f"   enriched: {r['enriched']:,} products updated")

