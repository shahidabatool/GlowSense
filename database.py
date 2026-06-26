"""GlowSense database layer — SQLite backend.

Stores raw products and reviews. Analysis is always generated at runtime
so that improvements to analyzer.py automatically apply to all stored data.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "glowsense.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db() -> None:
    """Create tables if they don't already exist."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS products (
                product_id    TEXT PRIMARY KEY,
                product_name  TEXT NOT NULL,
                brand_name    TEXT,
                category      TEXT,
                price_usd     REAL,
                avg_rating    REAL,
                review_count  INTEGER DEFAULT 0,
                source        TEXT,
                ingredients   TEXT,
                highlights    TEXT,
                details_text  TEXT,
                image_url     TEXT
            );

            CREATE TABLE IF NOT EXISTS reviews (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id       TEXT,
                product_name     TEXT NOT NULL,
                brand_name       TEXT,
                rating           REAL,
                review_text      TEXT,
                review_title     TEXT,
                skin_type        TEXT,
                is_recommended   INTEGER,
                source           TEXT,
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            );

            CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON reviews(product_id);
            CREATE INDEX IF NOT EXISTS idx_reviews_product_name ON reviews(product_name);
            CREATE INDEX IF NOT EXISTS idx_products_name       ON products(product_name);
            CREATE INDEX IF NOT EXISTS idx_products_brand      ON products(brand_name);
            """
        )
        # Safe migration for older GlowSense databases created before product details.
        for column_sql in (
            "ingredients TEXT",
            "highlights TEXT",
            "details_text TEXT",
            "image_url TEXT",
        ):
            try:
                conn.execute(f"ALTER TABLE products ADD COLUMN {column_sql}")
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc):
                    raise


# ── Inserts ────────────────────────────────────────────────────────────────

def insert_products_bulk(rows: list[dict], source: str = "sephora_csv") -> int:
    """Insert products, skipping duplicates. Returns number of new rows inserted."""
    if not rows:
        return 0
    with _connect() as conn:
        result = conn.executemany(
            """
            INSERT OR IGNORE INTO products
                (product_id, product_name, brand_name, category, price_usd, avg_rating, review_count, source,
                 ingredients, highlights, details_text, image_url)
            VALUES
                (:product_id, :product_name, :brand_name, :category, :price_usd, :avg_rating, :review_count, :source,
                 :ingredients, :highlights, :details_text, :image_url)
            """,
            [
                {
                    **r,
                    "source": source,
                    "ingredients": r.get("ingredients"),
                    "highlights": r.get("highlights"),
                    "details_text": r.get("details_text"),
                    "image_url": r.get("image_url"),
                }
                for r in rows
            ],
        )
    return result.rowcount


def bulk_update_amazon_products(updates: list[dict]) -> int:
    """Update Amazon metadata: name, brand, price, image, and product details."""
    if not updates:
        return 0

    normalized = [
        {
            **u,
            "ingredients": u.get("ingredients"),
            "highlights": u.get("highlights"),
            "details_text": u.get("details_text"),
            "image_url": u.get("image_url"),
            "review_count": u.get("review_count"),
        }
        for u in updates
    ]
    with _connect() as conn:
        result = conn.executemany(
            """
            UPDATE products
            SET product_name = CASE
                    WHEN product_name = :product_id OR product_name IS NULL
                    THEN COALESCE(:product_name, product_name)
                    ELSE product_name
                END,
                brand_name   = COALESCE(:brand_name, brand_name),
                category     = COALESCE(:category, category),
                price_usd    = COALESCE(:price_usd, price_usd),
                avg_rating   = COALESCE(:avg_rating, avg_rating),
                review_count = COALESCE(:review_count, review_count),
                ingredients  = COALESCE(:ingredients, ingredients),
                highlights   = COALESCE(:highlights, highlights),
                details_text = COALESCE(:details_text, details_text),
                image_url    = COALESCE(:image_url, image_url)
            WHERE product_id = :product_id
            """,
            normalized,
        )
    return result.rowcount



def insert_reviews_bulk(rows: list[dict], source: str = "sephora_csv") -> int:
    """Insert reviews. Skips rows where review_text is empty."""
    if not rows:
        return 0
    clean = [r for r in rows if r.get("review_text") and str(r["review_text"]).strip()]
    if not clean:
        return 0
    with _connect() as conn:
        result = conn.executemany(
            """
            INSERT INTO reviews
                (product_id, product_name, brand_name, rating, review_text, review_title,
                 skin_type, is_recommended, source)
            VALUES
                (:product_id, :product_name, :brand_name, :rating, :review_text, :review_title,
                 :skin_type, :is_recommended, :source)
            """,
            [{**r, "source": source} for r in clean],
        )
    return result.rowcount


# ── Queries ────────────────────────────────────────────────────────────────

def search_products(query: str, limit: int = 20, only_with_reviews: bool = True) -> list[dict]:
    """Search products by name, brand, or product_id.

    Multi-word searches like "maybelline eyeliner" match products where all words
    appear across the product name/brand/id, not only as one exact phrase.
    """
    terms = [t.strip() for t in query.split() if t.strip()]
    if not terms:
        return []
    where = " AND ".join(
        ["(p.product_name LIKE ? OR p.brand_name LIKE ? OR p.product_id LIKE ?)"] * len(terms)
    )
    params = []
    for term in terms:
        q = f"%{term}%"
        params.extend([q, q, q])
    params.append(limit)
    having_sql = "HAVING COUNT(r.id) > 0" if only_with_reviews else ""
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT p.product_id, p.product_name, p.brand_name, p.category,
                   p.price_usd, p.avg_rating, p.review_count, p.source,
                   p.ingredients, p.highlights, p.details_text, p.image_url,
                   COUNT(r.id) AS stored_reviews
            FROM products p
            LEFT JOIN reviews r ON r.product_id = p.product_id
            WHERE {where}
            GROUP BY p.product_id
            {having_sql}
            ORDER BY stored_reviews DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def search_products_by_name_only(query: str, limit: int = 20) -> list[dict]:
    """Search only in reviews table by product_name/brand with multi-word matching."""
    terms = [t.strip() for t in query.split() if t.strip()]
    if not terms:
        return []
    where = " AND ".join(["(product_name LIKE ? OR brand_name LIKE ?)"] * len(terms))
    params = []
    for term in terms:
        q = f"%{term}%"
        params.extend([q, q])
    params.append(limit)
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT product_name, brand_name, COUNT(*) AS stored_reviews,
                   AVG(rating) AS avg_rating
            FROM reviews
            WHERE {where}
            GROUP BY product_name
            ORDER BY stored_reviews DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def get_reviews_for_product(product_id: Optional[str] = None,
                             product_name: Optional[str] = None,
                             limit: int = 2000) -> list[dict]:
    """Return stored reviews for a product, by ID or name."""
    with _connect() as conn:
        if product_id:
            rows = conn.execute(
                "SELECT * FROM reviews WHERE product_id = ? LIMIT ?",
                (product_id, limit),
            ).fetchall()
        elif product_name:
            rows = conn.execute(
                "SELECT * FROM reviews WHERE product_name = ? LIMIT ?",
                (product_name, limit),
            ).fetchall()
        else:
            return []
    return [dict(r) for r in rows]


def get_all_products(limit: int = 100, offset: int = 0,
                     brand_filter: Optional[str] = None,
                     category_filter: Optional[str] = None,
                     only_with_reviews: bool = True) -> list[dict]:
    """Paginated list of all products with live review counts."""
    conditions = []
    params: list = []
    if brand_filter:
        conditions.append("p.brand_name = ?")
        params.append(brand_filter)
    if category_filter:
        conditions.append("p.category = ?")
        params.append(category_filter)
    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    having_sql = "HAVING COUNT(r.id) > 0" if only_with_reviews else ""
    params += [limit, offset]
    with _connect() as conn:
        rows = conn.execute(
            f"""
            SELECT p.product_id, p.product_name, p.brand_name, p.category,
                   p.price_usd, p.avg_rating, p.source,
                   p.ingredients, p.highlights, p.details_text, p.image_url,
                   COUNT(r.id) AS stored_reviews
            FROM products p
            LEFT JOIN reviews r ON r.product_id = p.product_id
            {where}
            GROUP BY p.product_id
            {having_sql}
            ORDER BY stored_reviews DESC
            LIMIT ? OFFSET ?
            """,
            params,
        ).fetchall()
    return [dict(r) for r in rows]


def get_distinct_brands() -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT brand_name FROM products WHERE brand_name IS NOT NULL ORDER BY brand_name"
        ).fetchall()
    return [r["brand_name"] for r in rows]


def get_distinct_categories() -> list[str]:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT DISTINCT category FROM products WHERE category IS NOT NULL ORDER BY category"
        ).fetchall()
    return [r["category"] for r in rows]


def search_brands(query: str, limit: int = 12) -> list[dict]:
    """Return brand suggestions, ordered exact match → starts-with → contains."""
    q = query.strip()
    if not q:
        return []
    like = f"%{q}%"
    starts = f"{q}%"
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT p.brand_name,
                   COUNT(DISTINCT p.product_id) AS products,
                   COUNT(r.id) AS reviews
            FROM products p
            LEFT JOIN reviews r ON r.product_id = p.product_id
            WHERE p.brand_name IS NOT NULL
              AND p.brand_name != ''
              AND p.brand_name LIKE ?
            GROUP BY p.brand_name
            HAVING COUNT(r.id) > 0
            ORDER BY
              CASE
                WHEN lower(p.brand_name) = lower(?) THEN 0
                WHEN lower(p.brand_name) LIKE lower(?) THEN 1
                ELSE 2
              END,
              reviews DESC,
              products DESC,
              p.brand_name ASC
            LIMIT ?
            """,
            (like, q, starts, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_products_by_brand(brand_name: str, limit: int = 100, only_with_reviews: bool = True) -> list[dict]:
    """Return products for one brand, preferring exact brand match over fuzzy contains."""
    q = brand_name.strip()
    with _connect() as conn:
        exact_count = conn.execute(
            "SELECT COUNT(*) FROM products WHERE lower(brand_name) = lower(?)",
            (q,),
        ).fetchone()[0]
        where_sql = "lower(p.brand_name) = lower(?)" if exact_count else "p.brand_name LIKE ?"
        param = q if exact_count else f"%{q}%"
        having_sql = "HAVING COUNT(r.id) > 0" if only_with_reviews else ""
        rows = conn.execute(
            f"""
            SELECT p.product_id, p.product_name, p.brand_name, p.category,
                   p.price_usd, p.avg_rating, p.source,
                   p.ingredients, p.highlights, p.details_text, p.image_url,
                   COUNT(r.id) AS stored_reviews
            FROM products p
            LEFT JOIN reviews r ON r.product_id = p.product_id
            WHERE {where_sql}
            GROUP BY p.product_id
            {having_sql}
            ORDER BY stored_reviews DESC
            LIMIT ?
            """,
            (param, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_reviews_by_brand(brand_name: str, limit: int = 5000) -> list[dict]:
    """Return reviews for one brand, preferring exact brand match over fuzzy contains."""
    q = brand_name.strip()
    with _connect() as conn:
        exact_count = conn.execute(
            "SELECT COUNT(*) FROM products WHERE lower(brand_name) = lower(?)",
            (q,),
        ).fetchone()[0]
        op_sql = "lower(?)" if exact_count else "?"
        brand_condition = f"lower(r.brand_name) = {op_sql}" if exact_count else "r.brand_name LIKE ?"
        product_condition = f"lower(brand_name) = {op_sql}" if exact_count else "brand_name LIKE ?"
        param = q if exact_count else f"%{q}%"
        rows = conn.execute(
            f"""
            SELECT r.* FROM reviews r
            WHERE {brand_condition}
               OR r.product_id IN (
                    SELECT product_id FROM products WHERE {product_condition}
               )
            LIMIT ?
            """,
            (param, param, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def get_db_stats() -> dict:
    """Return high-level stats about the database."""
    with _connect() as conn:
        products_total = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        reviews_total  = conn.execute("SELECT COUNT(*) FROM reviews").fetchone()[0]
        brands_total   = conn.execute(
            "SELECT COUNT(DISTINCT brand_name) FROM products"
        ).fetchone()[0]
        sources = conn.execute(
            "SELECT source, COUNT(*) AS n FROM reviews GROUP BY source"
        ).fetchall()
    return {
        "products": products_total,
        "reviews":  reviews_total,
        "brands":   brands_total,
        "sources":  {r["source"]: r["n"] for r in sources},
    }


def sync_product_stats() -> None:
    """Sync review count and average rating for all products in the database."""
    with _connect() as conn:
        conn.execute(
            """
            UPDATE products
            SET review_count = (
                SELECT COUNT(*) FROM reviews 
                WHERE reviews.product_id = products.product_id OR reviews.product_name = products.product_name
            )
            """
        )
        conn.execute(
            """
            UPDATE products
            SET avg_rating = (
                SELECT AVG(rating) FROM reviews 
                WHERE (reviews.product_id = products.product_id OR reviews.product_name = products.product_name)
                  AND rating IS NOT NULL
            )
            WHERE EXISTS (
                SELECT 1 FROM reviews 
                WHERE (reviews.product_id = products.product_id OR reviews.product_name = products.product_name)
                  AND rating IS NOT NULL
            )
            """
        )


# ── CLI helper ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    stats = get_db_stats()
    print(f"DB initialised at {DB_PATH}")
    print(f"  products : {stats['products']}")
    print(f"  reviews  : {stats['reviews']}")
    print(f"  brands   : {stats['brands']}")
