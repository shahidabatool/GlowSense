"""Text analysis helpers for GlowSense.

Version 2 keeps the logic simple and explainable. It avoids heavy ML dependencies
so the app runs easily on a Mac and can be explained in a portfolio interview.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Iterable, Mapping, Any, Optional

POSITIVE_WORDS = {
    "amazing", "best", "better", "bright", "calm", "clean", "clear", "cleared",
    "comfort", "comfortable", "cooling", "dewy", "effective", "fresh", "gentle",
    "glow", "glowing", "good", "great", "happy", "healed", "helped", "hydrated",
    "hydrating", "hydration", "improved", "love", "loved", "lovely", "moisturizing",
    "nice", "perfect", "plump", "recommend", "reduced", "refreshing", "repair",
    "smooth", "soothing", "soft", "worked", "works", "lightweight", "affordable",
}

NEGATIVE_WORDS = {
    "acne", "bad", "breakout", "breakouts", "burn", "burned", "burning", "clogged",
    "dry", "drying", "expensive", "fragrance", "greasy", "heavy", "irritated",
    "irritating", "irritation", "itchy", "oily", "peeling", "pills", "rash", "red",
    "redness", "sensitive", "sticky", "strong", "waste", "worse", "worst", "reaction",
}

TOPIC_WORDS = {
    "Hydration": {"dry", "hydrated", "hydrating", "hydration", "moisture", "moisturizing", "soft"},
    "Acne / breakouts": {"acne", "breakout", "breakouts", "pimples", "clogged"},
    "Sensitivity": {"burn", "burning", "irritation", "irritated", "redness", "sensitive", "rash", "itchy", "reaction"},
    "Texture": {"sticky", "greasy", "heavy", "lightweight", "smooth", "pills", "oily"},
    "Fragrance": {"fragrance", "scent", "smell", "perfume", "strong"},
    "Glow / brightness": {"glow", "glowing", "bright", "dewy", "clear"},
    "Price / value": {"expensive", "affordable", "price", "worth", "waste"},
}

SKIN_TYPE_WORDS = {
    "Dry skin": {"dry", "flaky", "tight", "dehydrated"},
    "Oily skin": {"oily", "greasy", "shine", "shiny"},
    "Sensitive skin": {"sensitive", "redness", "irritated", "irritation", "burning", "rash"},
    "Acne-prone skin": {"acne", "breakout", "breakouts", "pimples", "clogged"},
    "Combination skin": {"combination", "t-zone", "tzone"},
}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from", "had",
    "has", "have", "he", "her", "i", "in", "is", "it", "its", "me", "my", "of", "on",
    "or", "our", "she", "so", "that", "the", "their", "this", "to", "was", "we", "were",
    "with", "you", "your", "very", "really", "product", "skin", "face", "use", "used",
    "using", "after", "before", "one", "two", "week", "weeks", "day", "days",
}


@dataclass(frozen=True)
class AnalysisResult:
    review_count: int
    word_count: int
    positive_count: int
    negative_count: int
    sentiment_label: str
    score: float
    glow_score: int
    positive_words: list[tuple[str, int]]
    negative_words: list[tuple[str, int]]
    common_words: list[tuple[str, int]]
    topics: list[tuple[str, int]]
    skin_types: list[tuple[str, int]]
    recommendation: str
    summary: str


def tokenize(text: str) -> list[str]:
    """Return lowercase words from text."""
    return re.findall(r"[a-zA-Z']+", text.lower())


def split_reviews(text: str) -> list[str]:
    """Split reviews by line. Empty lines are ignored."""
    reviews = [line.strip() for line in text.splitlines() if line.strip()]
    if not reviews and text.strip():
        return [text.strip()]
    return reviews


def _top_matches(words: Iterable[str], dictionary: set[str], limit: int = 8) -> list[tuple[str, int]]:
    counts = Counter(w for w in words if w in dictionary)
    return counts.most_common(limit)


def _topic_counts(words: list[str]) -> list[tuple[str, int]]:
    return _dictionary_counts(words, TOPIC_WORDS)


def _skin_type_counts(words: list[str]) -> list[tuple[str, int]]:
    return _dictionary_counts(words, SKIN_TYPE_WORDS)


def _dictionary_counts(words: list[str], dictionary: Mapping[str, set[str]]) -> list[tuple[str, int]]:
    counts = Counter(words)
    results = []
    for label, label_words in dictionary.items():
        count = sum(counts[w] for w in label_words)
        if count:
            results.append((label, count))
    return sorted(results, key=lambda x: x[1], reverse=True)


def _make_recommendation(score: float, topics: list[tuple[str, int]]) -> str:
    topic_names = {topic for topic, _ in topics[:3]}
    if "Sensitivity" in topic_names or "Acne / breakouts" in topic_names:
        return "Use caution: reviews mention sensitivity, irritation, or breakouts. Patch-test first."
    if score >= 0.45:
        return "Looks promising: reviews are mostly positive. Good candidate for comparison or recommendation."
    if score <= -0.25:
        return "Not ideal: concern words are strong. Check the negative reviews before buying."
    return "Mixed signal: compare with another product before deciding."


def fetch_product_metadata(
    product_id: Optional[str] = None,
    product_name: Optional[str] = None,
    brand_name: Optional[str] = None,
) -> tuple[Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Return (price_usd, avg_cat_price, brand_avg_rating, product_avg_rating)."""
    from pathlib import Path
    import sqlite3
    db_path = Path(__file__).parent / "glowsense.db"
    if not db_path.exists():
        return None, None, None, None

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        price_usd = None
        category = None
        brand = brand_name
        product_avg_rating = None
        
        # 1. Look up the product details
        row = None
        if product_id:
            row = conn.execute(
                "SELECT price_usd, avg_rating, category, brand_name FROM products WHERE product_id = ?",
                (product_id,)
            ).fetchone()
        elif product_name:
            row = conn.execute(
                "SELECT price_usd, avg_rating, category, brand_name FROM products WHERE product_name = ? LIMIT 1",
                (product_name,)
            ).fetchone()
            
        if row:
            price_usd = row["price_usd"]
            product_avg_rating = row["avg_rating"]
            category = row["category"]
            if not brand:
                brand = row["brand_name"]
                
        # 2. If product_avg_rating is None, check product reviews average rating
        if product_avg_rating is None:
            val = None
            if product_id:
                val = conn.execute(
                    "SELECT AVG(rating) FROM reviews WHERE product_id = ?",
                    (product_id,)
                ).fetchone()
            elif product_name:
                val = conn.execute(
                    "SELECT AVG(rating) FROM reviews WHERE product_name = ?",
                    (product_name,)
                ).fetchone()
            if val and val[0] is not None:
                product_avg_rating = float(val[0])
                
        # 3. Find average price of products in the same category
        avg_cat_price = None
        if category:
            val = conn.execute(
                "SELECT AVG(price_usd) FROM products WHERE category = ? AND price_usd IS NOT NULL",
                (category,)
            ).fetchone()
            if val and val[0] is not None:
                avg_cat_price = float(val[0])
                
        # 4. Find brand average rating
        brand_avg_rating = None
        if brand:
            # Try from products table first
            val = conn.execute(
                "SELECT AVG(avg_rating) FROM products WHERE brand_name = ? AND avg_rating IS NOT NULL",
                (brand,)
            ).fetchone()
            if val and val[0] is not None:
                brand_avg_rating = float(val[0])
            else:
                # Try from reviews table
                val = conn.execute(
                    "SELECT AVG(rating) FROM reviews WHERE brand_name = ? AND rating IS NOT NULL",
                    (brand,)
                ).fetchone()
                if val and val[0] is not None:
                    brand_avg_rating = float(val[0])
                    
        conn.close()
        return price_usd, avg_cat_price, brand_avg_rating, product_avg_rating
    except Exception:
        return None, None, None, None


def analyze_reviews(
    text: str,
    product_id: Optional[str] = None,
    product_name: Optional[str] = None,
    brand_name: Optional[str] = None,
    custom_metadata: Optional[dict] = None,
) -> AnalysisResult:
    """Analyze pasted skincare/beauty reviews with simple explainable logic."""
    reviews = split_reviews(text)
    words = tokenize(text)
    positive = _top_matches(words, POSITIVE_WORDS)
    negative = _top_matches(words, NEGATIVE_WORDS)
    positive_count = sum(count for _, count in positive)
    negative_count = sum(count for _, count in negative)
    total_signal = positive_count + negative_count
    score = round((positive_count - negative_count) / total_signal, 2) if total_signal else 0.0

    # ── Multi-factor Glow Score ──
    # Component 1: Sentiment Score (0-100)
    S = None
    if total_signal:
        S = ((score + 1) / 2) * 100

    # Retrieve metadata from database or custom metadata dict
    price_usd, avg_cat_price, brand_avg_rating, product_avg_rating = None, None, None, None
    if custom_metadata:
        price_usd = custom_metadata.get("price_usd")
        avg_cat_price = custom_metadata.get("avg_cat_price")
        brand_avg_rating = custom_metadata.get("brand_avg_rating")
        product_avg_rating = custom_metadata.get("product_avg_rating")
    elif product_id or product_name or brand_name:
        price_usd, avg_cat_price, brand_avg_rating, product_avg_rating = fetch_product_metadata(
            product_id=product_id,
            product_name=product_name,
            brand_name=brand_name
        )

    # Component 2: Stars Score (0-100)
    R = None
    if product_avg_rating is not None:
        R = product_avg_rating * 20.0

    # Component 3: Price Score (0-100)
    P = None
    if price_usd is not None and avg_cat_price is not None and avg_cat_price > 0:
        ratio = price_usd / avg_cat_price
        if ratio <= 1.0:
            P = 100.0 - 50.0 * ratio
        else:
            P = max(0.0, 50.0 / ratio)

    # Component 4: Brand Score (0-100)
    B = None
    if brand_avg_rating is not None:
        B = brand_avg_rating * 20.0

    # Dynamic Weighting
    components = {}
    if S is not None:
        components["sentiment"] = (S, 0.40)
    if R is not None:
        components["stars"] = (R, 0.30)
    if P is not None:
        components["price"] = (P, 0.15)
    if B is not None:
        components["brand"] = (B, 0.15)

    if not components:
        glow_score = 50
    else:
        tot_w = sum(w for _, w in components.values())
        w_sum = sum(val * w for val, w in components.values())
        glow_score = int(round(w_sum / tot_w))

    if total_signal == 0:
        sentiment = "Not enough clear sentiment words"
    elif score >= 0.25:
        sentiment = "Mostly positive"
    elif score <= -0.25:
        sentiment = "Mostly negative / concerns found"
    else:
        sentiment = "Mixed"

    topics = _topic_counts(words)
    skin_types = _skin_type_counts(words)
    common_words = Counter(w for w in words if w not in STOPWORDS and len(w) > 2).most_common(10)
    recommendation = _make_recommendation(score, topics)

    if sentiment == "Mostly positive":
        summary = "Most review signals look positive. People may be liking the product overall."
    elif sentiment == "Mostly negative / concerns found":
        summary = "There are several concern words. Check issues like irritation, acne, fragrance, or texture."
    elif sentiment == "Mixed":
        summary = "Reviews look mixed. Some people may like it, but there are also concerns."
    else:
        summary = "Add more review text to get a clearer analysis."

    if topics:
        summary += f" Main topic: {topics[0][0]}."

    return AnalysisResult(
        review_count=len(reviews),
        word_count=len(words),
        positive_count=positive_count,
        negative_count=negative_count,
        sentiment_label=sentiment,
        score=score,
        glow_score=glow_score,
        positive_words=positive,
        negative_words=negative,
        common_words=common_words,
        topics=topics,
        skin_types=skin_types,
        recommendation=recommendation,
        summary=summary,
    )


def review_vote(review_text: str) -> str:
    """Classify one review as recommend, not recommend, or mixed."""
    result = analyze_reviews(review_text)
    if result.score >= 0.25:
        return "Recommend"
    if result.score <= -0.25:
        return "Do not recommend"
    return "Mixed / unsure"


def product_recommendation_breakdown(
    text: str,
    product_id: Optional[str] = None,
    product_name: Optional[str] = None,
    brand_name: Optional[str] = None,
) -> dict[str, Any]:
    """Return user-friendly recommendation percentages for a product."""
    reviews = split_reviews(text)
    if not reviews:
        return {
            "Recommend %": 0,
            "Do not recommend %": 0,
            "Mixed %": 0,
            "Recommend count": 0,
            "Do not recommend count": 0,
            "Mixed count": 0,
            "Total reviews": 0,
            "Reasons people like it": [],
            "Reasons people dislike it": [],
        }

    votes = Counter(review_vote(review) for review in reviews)
    total = len(reviews)
    overall = analyze_reviews(text, product_id=product_id, product_name=product_name, brand_name=brand_name)
    return {
        "Recommend %": round((votes["Recommend"] / total) * 100, 1),
        "Do not recommend %": round((votes["Do not recommend"] / total) * 100, 1),
        "Mixed %": round((votes["Mixed / unsure"] / total) * 100, 1),
        "Recommend count": votes["Recommend"],
        "Do not recommend count": votes["Do not recommend"],
        "Mixed count": votes["Mixed / unsure"],
        "Total reviews": total,
        "Reasons people like it": overall.positive_words[:5],
        "Reasons people dislike it": overall.negative_words[:5],
    }


def analyze_products(
    product_reviews: Mapping[str, str],
    products_metadata: Optional[Mapping[str, dict]] = None,
) -> list[dict[str, object]]:
    """Analyze multiple products and return a table-friendly list."""
    rows = []
    for product, text in product_reviews.items():
        meta = products_metadata.get(product) if products_metadata else None
        result = analyze_reviews(text, product_name=product, custom_metadata=meta)
        breakdown = product_recommendation_breakdown(text, product_name=product)
        rows.append(
            {
                "Product": product,
                "Reviews": result.review_count,
                "Words": result.word_count,
                "Glow score": result.glow_score,
                "Recommend %": breakdown["Recommend %"],
                "Do not recommend %": breakdown["Do not recommend %"],
                "Mixed %": breakdown["Mixed %"],
                "Sentiment": result.sentiment_label,
                "Positive signals": result.positive_count,
                "Concern signals": result.negative_count,
                "Top topic": result.topics[0][0] if result.topics else "No clear topic",
                "Skin type mentioned": result.skin_types[0][0] if result.skin_types else "Not clear",
                "Recommendation": result.recommendation,
            }
        )
    return sorted(rows, key=lambda row: (float(row["Recommend %"]), int(row["Glow score"])), reverse=True)


def reviews_to_text(reviews: Iterable[object]) -> str:
    """Convert review values from a CSV column into newline-separated text."""
    return "\n".join(str(review).strip() for review in reviews if str(review).strip() and str(review) != "nan")
