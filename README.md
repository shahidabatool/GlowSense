# GlowSense ✨ — Beauty & Skincare Product Intelligence

GlowSense is a premium, portfolio-ready product intelligence dashboard designed for beauty and skincare shoppers. It aggregates real-world customer reviews from Sephora, Ulta, and Amazon, runs custom lexical sentiment analysis, and calculates an explainable multi-factor **Glow Score** to rank products.

Users can paste reviews, search the pre-seeded SQLite database, chat with the GlowSense Q&A Assistant, or upload custom review CSVs to analyze and compare their own datasets.

---

## 🚀 Key Features

*   **📝 Paste Review Analysis:** Paste raw skincare/beauty reviews directly to extract sentiment scores, top skincare topics, skin-type clues (e.g., dry, oily, sensitive), and keyword frequency counts.
*   **🔍 Product Lookup:** Search by brand, name, or product ID to pull a comprehensive detail sheet: review summaries, YouTube review search links, Amazon/Sephora/Ulta deal finders, ingredients list, and highlights.
*   **💬 GlowSense Q&A Assistant:** Ask questions about the database and the project (e.g., *"How many reviews are in the database?"*, *"Explain how the Glow Score is computed"*, or *"Tell me about the tech stack"*).
*   **📊 Compare Products (Custom CSV uploads):** Link and analyze custom customer reviews and product details from uploaded files. Includes:
    *   **Single CSV** (Reviews + details combined).
    *   **Double CSV** (Reviews CSV linked to a Products CSV via a product identifier key).
    *   **📥 Save to Database:** Bulk-import uploaded files directly into the local SQLite database.
    *   **Targeted Comparison:** Select specific products from a dropdown to run sentiment analysis and render interactive comparison charts on a subset of data (preventing page crashes on large uploads).
*   **📥 Seed Data Manager:** Seed the database with high-quality reviews from Sephora, Ulta, and Amazon Hugging Face datasets.

---

## 🧠 Data Science & Sentiment Analysis Logic

### 1. Lexical Keyword-Based Sentiment Engine
To maintain high explainability and avoid heavy ML dependencies, GlowSense uses a custom lexical tokenization engine:
*   **Tokenization & Cleaning:** Normalizes review text by converting to lowercase, removing punctuation, and filtering out common English stopwords.
*   **Keyword Matching:** Scores text against curated lists of beauty-specific sentiment words:
    *   *Positive signals (e.g., dewy, hydrating, calm, glowing, smooth, soft).*
    *   *Concern signals (e.g., breakout, acne, burn, irritation, redness, peeling, dry).*
*   **Sentiment Labeling:**
    *   `Mostly positive` (score >= 0.25)
    *   `Mostly negative / concerns found` (score <= -0.25)
    *   `Mixed` (between -0.25 and 0.25)

### 2. Explainable Multi-Factor Glow Score
The **Glow Score (0–100)** is computed using a dynamically weighted formula that aggregates four dimensions of a product:
1.  🧠 **Sentiment Score (40%):** Calculated from tokenized customer reviews.
2.  ⭐ **Product Rating (30%):** Average star rating of the product normalized to a 100-point scale.
3.  💰 **Price Value (15%):** Dynamically compares the product's price against the average price of all products within the same category (e.g., moisturizers). Products cheaper than the category average get a bonus; expensive items scale down.
4.  🏷️ **Brand Reputation (15%):** Average star rating of all products sold under the same brand in the database.

*Note: To ensure statistical reliability, GlowScore scoring only applies to products with **10 or more reviews**.*

---

## 📥 Hugging Face & Seeding Pipeline

GlowSense supports seeding reviews from Sephora (CSV), Ulta (CSV), and Amazon (Hugging Face Hub):
*   **Amazon Dataset:** Utilizes the `amazon_us_reviews` dataset (under the `Personal_Care_Appliances_v1_00` or `Beauty` category).
*   **Data Streaming:** Streams reviews from Hugging Face using the `datasets` library to avoid downloading massive multi-gigabyte files to local disk.
*   **10+ Reviews Filter:** Counts product review frequencies dynamically during ingestion. It discards products with fewer than 10 reviews, ensuring only products with significant data are stored in the database.
*   **Bulk Database Insertion:** Writes batches in bulk to the SQLite database via `insert_products_bulk()` and `insert_reviews_bulk()` for maximum speed and efficiency.

---

## 🛠️ Installation & Setup

### Prerequisites
*   Python 3.8 to 3.12 (Python 3.10+ recommended)
*   SQLite3

### 1. Clone & Navigate
```bash
git clone https://github.com/shahidabatool/GlowSense.git
cd GlowSense
```

### 2. Install Packages
```bash
pip install -r requirements.txt
```

### 3. Run the App
```bash
streamlit run app.py
```
*The app will launch and open in your default browser at `http://localhost:8502`.*

---

## 📂 Project Structure

*   `app.py`: Main Streamlit app containing all tabs, page styling, and UI controllers.
*   `analyzer.py`: Contains the sentiment scoring, topic tagging, recommendation generator, and multi-factor Glow Score calculations.
*   `database.py`: Handles SQLite database initialization, table indices, bulk insertion, query helpers, and stats calculation.
*   `seed_data.py`: Script and UI logic to read and import Sephora, Ulta, and Amazon Hugging Face reviews.
*   `test_analyzer.py`: Assert-based test suite verifying tokenization, sentiment calculations, and Glow Score logic.
*   `requirements.txt`: Python package list (`streamlit`, `pandas`, `altair`, `datasets`, etc.).
