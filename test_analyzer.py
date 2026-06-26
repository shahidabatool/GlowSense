from analyzer import (
    analyze_products,
    analyze_reviews,
    product_recommendation_breakdown,
    reviews_to_text,
    split_reviews,
    tokenize,
)


def test_tokenize_lowercase_words():
    assert tokenize("Great, GREAT skin!") == ["great", "great", "skin"]


def test_split_reviews_ignores_empty_lines():
    text = "Good product\n\nBad fragrance\n"
    assert split_reviews(text) == ["Good product", "Bad fragrance"]


def test_analyze_positive_reviews():
    result = analyze_reviews("I love this. It is gentle, hydrating, soft and smooth.")
    assert result.sentiment_label == "Mostly positive"
    assert result.positive_count > result.negative_count
    assert result.glow_score > 50


def test_analyze_concern_reviews():
    result = analyze_reviews("This caused acne, breakouts, redness and irritation.")
    assert result.sentiment_label == "Mostly negative / concerns found"
    assert result.negative_count > result.positive_count
    assert result.glow_score < 50


def test_analyze_topics():
    result = analyze_reviews("Very hydrating but strong fragrance and some irritation on sensitive skin.")
    topic_names = [name for name, count in result.topics]
    skin_type_names = [name for name, count in result.skin_types]
    assert "Hydration" in topic_names
    assert "Fragrance" in topic_names
    assert "Sensitive skin" in skin_type_names


def test_reviews_to_text_ignores_empty_values():
    text = reviews_to_text(["Good", "", "  ", "Bad"])
    assert text == "Good\nBad"


def test_analyze_products_orders_by_glow_score():
    rows = analyze_products(
        {
            "Good Cream": "love gentle hydrating smooth",
            "Risky Serum": "acne irritation redness burning",
        }
    )
    assert rows[0]["Product"] == "Good Cream"
    assert rows[0]["Glow score"] > rows[1]["Glow score"]
    assert rows[0]["Recommend %"] > rows[1]["Recommend %"]


def test_product_recommendation_breakdown_percentages():
    text = "love gentle hydrating\nacne irritation redness\nokay normal"
    breakdown = product_recommendation_breakdown(text)
    assert breakdown["Total reviews"] == 3
    assert breakdown["Recommend count"] == 1
    assert breakdown["Do not recommend count"] == 1
    assert breakdown["Mixed count"] == 1
    assert breakdown["Recommend %"] == 33.3


def test_multi_factor_glow_score():
    res = analyze_reviews("love gentle hydrating", product_name="Dummy Product", brand_name="Dummy Brand")
    assert res.glow_score >= 50

