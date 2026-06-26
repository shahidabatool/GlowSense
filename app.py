import ast
from urllib.parse import quote_plus

import altair as alt
import pandas as pd
import streamlit as st

from analyzer import analyze_products, analyze_reviews, product_recommendation_breakdown, reviews_to_text
from database import (
    init_db, get_db_stats, search_products, search_products_by_name_only, search_brands,
    get_reviews_for_product, get_reviews_by_brand, get_products_by_brand,
    get_all_products, get_distinct_brands, get_distinct_categories,
    insert_products_bulk, insert_reviews_bulk, sync_product_stats,
)

# ── Page config ────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="GlowSense Review Analyzer",
    page_icon="✨",
    layout="wide",
)

init_db()  # ensure DB tables exist on every startup

# ── Design tokens ──────────────────────────────────────────────────────────
PRIMARY   = "#6B3A2A"  # Deep espresso brown
PRIMARY_L = "#A0522D"  # Sienna brown
SOFT      = "#FAF6F2"  # Warm parchment
ACCENT    = "#C8A882"  # Caramel tan
DARK_TEXT = "#2C1810"  # Deep cocoa

st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;900&family=Inter:wght@400;500;600;700;900&display=swap');
    * {{ font-family: 'Inter', sans-serif; }}

    /* ── Warm parchment background ─────────────────────────────── */
    .stApp {{
        background: #FAF6F2 !important;
        background-image:
            radial-gradient(ellipse 70% 45% at 15% 8%, rgba(107,58,42,0.06) 0%, transparent 60%),
            radial-gradient(ellipse 55% 38% at 85% 82%, rgba(160,82,45,0.05) 0%, transparent 55%);
    }}

    /* ── Glassmorphism cards ───────────────────────────────────── */
    .glass-card {{
        padding: 1.4rem 1.6rem;
        border-radius: 14px;
        background: rgba(255,252,248,0.75);
        backdrop-filter: blur(18px) saturate(160%);
        -webkit-backdrop-filter: blur(18px) saturate(160%);
        border: 1px solid rgba(200,168,130,0.4);
        box-shadow: 0 8px 32px rgba(107,58,42,0.08), inset 0 1px 0 rgba(255,255,255,0.7);
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }}
    .glass-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 16px 44px rgba(107,58,42,0.13), inset 0 1px 0 rgba(255,255,255,0.8);
    }}

    /* ── Hero section ─────────────────────────────────────────── */
    .hero {{
        position: relative;
        padding: 3.2rem 2.6rem 2.8rem;
        background:
            linear-gradient(90deg, rgba(255,252,248,0.98) 0%, rgba(250,246,242,0.9) 45%, rgba(245,235,220,0.4) 100%),
            radial-gradient(circle at 88% 30%, rgba(160,82,45,0.12), transparent 30%),
            radial-gradient(circle at 74% 78%, rgba(107,58,42,0.08), transparent 32%),
            linear-gradient(135deg, #FAF6F2 0%, #F0E8DC 55%, #E8D8C4 100%);
        border-top: 4px solid #6B3A2A;
        border-bottom: 1px solid #D4C4B0;
        border-left: 0; border-right: 0;
        box-shadow: 0 18px 48px rgba(44,24,16,0.07);
        overflow: hidden;
        animation: fadeSlideIn 0.7s ease-out;
    }}
    .hero::before {{
        content: '';
        position: absolute;
        top: -50px; right: -50px;
        width: 220px; height: 220px;
        background: radial-gradient(circle, rgba(200,168,130,0.18) 0%, transparent 65%);
        border-radius: 50%;
        animation: floatBlob 10s ease-in-out infinite;
        pointer-events: none;
    }}
    .hero::after {{
        content: '';
        position: absolute;
        bottom: -30px; left: 80px;
        width: 140px; height: 140px;
        background: radial-gradient(circle, rgba(107,58,42,0.1) 0%, transparent 65%);
        border-radius: 50%;
        animation: floatBlob 13s ease-in-out infinite reverse;
        pointer-events: none;
    }}

    @keyframes floatBlob {{
        0%, 100% {{ transform: translateY(0) scale(1); }}
        50%      {{ transform: translateY(-18px) scale(1.08); }}
    }}
    @keyframes fadeSlideIn {{
        from {{ opacity: 0; transform: translateY(14px); }}
        to   {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes shimmerBrown {{
        0%, 100% {{ background-position: 0% center; }}
        50%      {{ background-position: 100% center; }}
    }}

    .main-title {{
        font-family: 'Playfair Display', 'Inter', serif !important;
        font-size: clamp(3rem, 5.8vw, 5.4rem);
        font-weight: 900;
        letter-spacing: -1px;
        margin: .8rem 0;
        background: linear-gradient(135deg, #6B3A2A 0%, #2C1810 45%, #A0522D 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        background-size: 200% auto;
        animation: shimmerBrown 5s ease-in-out infinite;
        text-transform: uppercase;
    }}

    .subtitle {{
        font-size: 1.08rem;
        color: #5C3D2E;
        margin-top: .5rem;
        max-width: 820px;
        line-height: 1.7;
        position: relative;
        z-index: 2;
    }}

    .version-pill {{
        display: inline-block;
        padding: .3rem .9rem;
        border-radius: 999px;
        background: linear-gradient(135deg, #6B3A2A, #A0522D);
        color: #FAF6F2;
        font-weight: 700;
        font-size: .75rem;
        letter-spacing: .4px;
        box-shadow: 0 3px 12px rgba(107,58,42,0.28);
        position: relative;
        z-index: 2;
        margin-bottom: .35rem;
    }}

    .hero-badges {{
        display: flex;
        gap: .55rem;
        margin-top: 1rem;
        flex-wrap: wrap;
    }}
    .hero-badge {{
        display: inline-flex;
        align-items: center;
        gap: .35rem;
        padding: .38rem .85rem;
        border-radius: 999px;
        background: rgba(255,252,248,0.85);
        backdrop-filter: blur(8px);
        border: 1px solid rgba(200,168,130,0.55);
        font-size: .78rem;
        font-weight: 700;
        color: #2C1810;
        box-shadow: 3px 3px 0 rgba(107,58,42,0.15);
        transition: all 0.2s ease;
    }}
    .hero-badge:hover {{
        transform: translate(-1px, -1px);
        box-shadow: 4px 4px 0 rgba(107,58,42,0.25);
    }}

    /* ── Stat boxes ────────────────────────────────────────────── */
    .stat-box {{
        padding: 1.2rem 1.5rem;
        border-radius: 12px;
        background: rgba(255,252,248,0.8);
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        border: 1px solid rgba(200,168,130,0.4);
        box-shadow: 0 6px 24px rgba(107,58,42,0.07);
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        animation: fadeSlideIn 0.6s ease-out both;
    }}
    .stat-box:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 32px rgba(107,58,42,0.13);
    }}
    .stat-num {{
        font-size: 2.2rem;
        font-weight: 900;
        background: linear-gradient(135deg, {PRIMARY}, {PRIMARY_L});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}
    .stat-lbl {{
        font-size: .78rem;
        color: #7A5C3E;
        margin-top: .25rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: .5px;
    }}
    .stat-icon {{ font-size: 1.4rem; margin-bottom: .3rem; }}

    /* ── Result / product cards ────────────────────────────────── */
    .result-card {{
        padding: 1.4rem 1.6rem;
        border-radius: 12px;
        background: rgba(255,252,248,0.85);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(200,168,130,0.4);
        box-shadow: 0 8px 28px rgba(107,58,42,0.07);
        margin-bottom: .85rem;
        animation: fadeSlideIn 0.5s ease-out both;
        transition: box-shadow 0.2s ease;
    }}
    .result-card:hover {{
        box-shadow: 0 12px 36px rgba(107,58,42,0.12);
    }}
    .copilot-card {{
        padding: 1.1rem 1.3rem;
        border-radius: 12px;
        background: linear-gradient(135deg, rgba(255,252,248,0.97), rgba(245,235,220,0.9));
        border: 1px solid rgba(160,82,45,0.2);
        border-top: 4px solid #6B3A2A;
        box-shadow: 0 10px 30px rgba(44,24,16,0.06);
        margin: .8rem 0 1rem;
    }}
    .copilot-title {{
        font-size: 1rem;
        font-weight: 800;
        color: #2C1810;
        margin-bottom: .35rem;
        text-transform: uppercase;
        letter-spacing: .5px;
    }}
    .copilot-chip {{
        display: inline-block;
        padding: .22rem .65rem;
        margin: .15rem .2rem .15rem 0;
        border-radius: 999px;
        background: #EDE0D0;
        color: #4A2C1A;
        font-size: .76rem;
        font-weight: 700;
    }}

    /* ── Glow gauge ────────────────────────────────────────────── */
    .glow-gauge {{
        position: relative;
        width: 140px; height: 140px;
        margin: 0 auto;
    }}
    .glow-gauge svg {{ transform: rotate(-90deg); }}
    .glow-gauge-label {{
        position: absolute;
        top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        text-align: center;
    }}
    .glow-gauge-num {{
        font-size: 2rem;
        font-weight: 900;
        color: {PRIMARY};
        line-height: 1;
    }}
    .glow-gauge-sub {{
        font-size: .62rem;
        color: #7A5C3E;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: .8px;
    }}

    /* ── Price & rating pills ─────────────────────────────────── */
    .price-pill {{
        display: inline-block;
        padding: .25rem .75rem;
        border-radius: 999px;
        background: linear-gradient(135deg, #EDE0D0, #D4C4B0);
        color: #4A2C1A;
        font-weight: 700;
        font-size: .9rem;
        border: 1px solid rgba(107,58,42,0.2);
    }}
    .source-pill {{
        display: inline-block;
        padding: .2rem .6rem;
        border-radius: 999px;
        background: rgba(200,168,130,0.25);
        color: #2C1810;
        font-weight: 600;
        font-size: .75rem;
    }}
    .star-rating {{
        color: #C8860A;
        font-size: 1.1rem;
        letter-spacing: 1px;
    }}

    /* ── Sentiment pills ──────────────────────────────────────── */
    .pill-positive {{
        display: inline-block;
        padding: .25rem .7rem;
        border-radius: 999px;
        background: #EAF2E8;
        color: #2D5A27;
        font-weight: 700;
        font-size: .82rem;
        border: 1px solid rgba(45,90,39,0.2);
    }}
    .pill-negative {{
        display: inline-block;
        padding: .25rem .7rem;
        border-radius: 999px;
        background: #F5EDE8;
        color: #7B2D00;
        font-weight: 700;
        font-size: .82rem;
        border: 1px solid rgba(123,45,0,0.2);
    }}
    .pill-mixed {{
        display: inline-block;
        padding: .25rem .7rem;
        border-radius: 999px;
        background: #F5EDD8;
        color: #7B4F2E;
        font-weight: 700;
        font-size: .82rem;
        border: 1px solid rgba(123,79,46,0.25);
    }}

    /* ── Tab styling ───────────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {{
        gap: 0;
        background: #FAF6F2;
        padding: 0;
        border-radius: 0;
        border-bottom: 2px solid #2C1810;
    }}
    .stTabs [data-baseweb="tab"] {{
        border-radius: 0;
        background: transparent;
        padding: .72rem 1.1rem;
        font-weight: 700;
        font-size: .78rem;
        letter-spacing: .8px;
        text-transform: uppercase;
        color: #7A5C3E;
        border-right: 1px solid #D4C4B0;
        transition: all 0.2s ease;
    }}
    .stTabs [data-baseweb="tab"]:hover {{
        background: rgba(200,168,130,0.15);
        color: #2C1810;
    }}
    .stTabs [aria-selected="true"] {{
        background: #2C1810 !important;
        color: #FFFFFF !important;
        box-shadow: none;
    }}
    .stTabs [aria-selected="true"] * {{
        color: #FFFFFF !important;
    }}

    /* ── Metric overrides ─────────────────────────────────────── */
    [data-testid="stMetric"] {{
        background: rgba(255,252,248,0.9) !important;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        border: 1px solid rgba(200,168,130,0.4) !important;
        border-radius: 12px !important;
        padding: .9rem 1rem;
        box-shadow: 0 4px 16px rgba(107,58,42,0.06);
        transition: transform 0.2s ease;
    }}
    [data-testid="stMetric"]:hover {{ transform: translateY(-2px); }}
    [data-testid="stMetricLabel"] {{
        font-weight: 700 !important;
        color: #7A5C3E !important;
        font-size: .74rem !important;
        text-transform: uppercase;
        letter-spacing: .5px;
    }}
    [data-testid="stMetricValue"] {{
        font-weight: 900 !important;
        color: {PRIMARY} !important;
    }}

    /* ── Dividers ──────────────────────────────────────────────── */
    hr {{
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent, {ACCENT}, rgba(160,82,45,0.3), transparent);
        margin: 1.5rem 0;
    }}

    /* ── Sidebar ───────────────────────────────────────────────── */
    section[data-testid="stSidebar"] {{
        background: #F0EBE3 !important;
        border-right: 1px solid #D4C4B0;
    }}
    section[data-testid="stSidebar"] [data-testid="stMetric"] {{
        background: rgba(255,252,248,0.8) !important;
    }}
    .sidebar-feature {{
        display: flex;
        align-items: center;
        gap: .55rem;
        padding: .4rem .75rem;
        margin: .25rem 0;
        border-radius: 8px;
        background: rgba(255,252,248,0.7);
        border: 1px solid rgba(200,168,130,0.3);
        transition: all 0.2s ease;
        font-size: .86rem;
        font-weight: 500;
        color: #2C1810;
    }}
    .sidebar-feature:hover {{
        background: rgba(255,252,248,0.95);
        border-color: rgba(107,58,42,0.3);
    }}
    .sidebar-icon {{
        width: 22px; height: 22px;
        border-radius: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: .75rem;
        flex-shrink: 0;
    }}
    .sidebar-icon.green  {{ background: #E8F0E4; }}
    .sidebar-icon.pink   {{ background: #F5EDE4; }}
    .sidebar-icon.purple {{ background: #EDE4F0; }}
    .sidebar-icon.blue   {{ background: #E4ECF5; }}

    /* ── Section titles ────────────────────────────────────────── */
    .section-title {{
        font-size: 1.45rem;
        font-weight: 800;
        color: #2C1810;
        margin-bottom: .5rem;
        display: flex;
        align-items: center;
        gap: .5rem;
    }}
    .section-title .icon-circle {{
        width: 34px; height: 34px;
        border-radius: 10px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1rem;
        background: linear-gradient(135deg, {ACCENT}, rgba(160,82,45,0.25));
    }}

    /* ── Custom scrollbar ──────────────────────────────────────── */
    ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
    ::-webkit-scrollbar-track {{ background: #F0EBE3; }}
    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(180deg, #C8A882, #A0522D);
        border-radius: 999px;
    }}

    /* ── Timeline ──────────────────────────────────────────────── */
    .timeline-item {{
        position: relative;
        padding: .8rem 1rem .8rem 2.2rem;
        margin: .5rem 0;
        border-radius: 8px;
        background: rgba(255,252,248,0.7);
        border: 1px solid rgba(200,168,130,0.35);
    }}
    .timeline-item::before {{
        content: '';
        position: absolute;
        left: .8rem; top: 50%;
        transform: translateY(-50%);
        width: 8px; height: 8px;
        border-radius: 50%;
        background: linear-gradient(135deg, {PRIMARY}, {PRIMARY_L});
    }}

    /* ── Feature grid ──────────────────────────────────────────── */
    .feature-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: .8rem;
        margin: 1rem 0;
    }}
    .feature-card {{
        padding: 1rem;
        border-radius: 12px;
        background: rgba(255,252,248,0.75);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(200,168,130,0.35);
        text-align: center;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }}
    .feature-card:hover {{
        transform: translateY(-3px);
        box-shadow: 0 10px 28px rgba(107,58,42,0.1);
    }}
    .feature-card-icon {{ font-size: 1.8rem; margin-bottom: .4rem; }}
    .feature-card-title {{ font-weight: 700; color: #2C1810; font-size: .88rem; }}
    .feature-card-desc {{ font-size: .76rem; color: #7A5C3E; margin-top: .2rem; }}

    /* ── Stagger delays ────────────────────────────────────────── */
    .anim-delay-1 {{ animation-delay: 0.1s; }}
    .anim-delay-2 {{ animation-delay: 0.2s; }}
    .anim-delay-3 {{ animation-delay: 0.3s; }}
    .anim-delay-4 {{ animation-delay: 0.4s; }}

    /* ── Global / layout ───────────────────────────────────────── */
    .stApp {{ background: #FAF6F2 !important; }}
    .block-container {{ padding-top: 1.2rem; max-width: 1280px; }}

    .luxury-top-strip {{
        margin: 0 0 1rem;
        padding: .7rem 1rem;
        min-height: 40px;
        background: #2C1810;
        color: #FFFFFF;
        font-size: .78rem;
        font-weight: 800;
        letter-spacing: .1em;
        text-transform: uppercase;
        text-align: center;
    }}

    /* ── Editorial grid ────────────────────────────────────────── */
    .luxury-editorial-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 1rem;
        margin: 1rem 0 1.2rem;
    }}
    .luxury-editorial-card {{
        min-height: 130px;
        padding: 1.3rem;
        background: #2C1810;
        color: #FFFFFF;
        border-radius: 8px;
        position: relative;
        overflow: hidden;
        transition: transform 0.2s ease;
    }}
    .luxury-editorial-card:hover {{ transform: translateY(-2px); }}
    .luxury-editorial-card.red {{
        background: linear-gradient(135deg, #6B3A2A, #A0522D);
        color: #FFFFFF;
    }}
    .luxury-editorial-card.light {{
        background: #F0EBE3;
        color: #2C1810;
        border: 1px solid #D4C4B0;
    }}
    .luxury-editorial-kicker {{
        font-size: .68rem;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
        opacity: .7;
    }}
    .luxury-editorial-title {{
        font-size: 1.2rem;
        font-weight: 900;
        line-height: 1.1;
        margin-top: .55rem;
        text-transform: uppercase;
    }}

    .luxury-product-kicker {{
        margin: 1rem 0 .5rem;
        padding: .45rem .8rem;
        background: #2C1810;
        color: #FFFFFF;
        display: inline-block;
        font-size: .72rem;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
        border-radius: 4px;
    }}
    .luxury-buyer-action {{
        margin: .8rem 0 1rem;
        padding: 1rem;
        background: #F5EDE8;
        border-left: 5px solid #6B3A2A;
        color: #2C1810;
        font-weight: 700;
        border-radius: 0 8px 8px 0;
    }}

    /* card/metric/stat overrides */
    .result-card, [data-testid="stMetric"], .stat-box, .copilot-card {{
        border-radius: 12px !important;
        background: rgba(255,252,248,0.9) !important;
        border: 1px solid rgba(200,168,130,0.4) !important;
        box-shadow: 0 6px 20px rgba(107,58,42,0.06) !important;
    }}
    .copilot-card {{ border-top: 4px solid #6B3A2A !important; }}
    .copilot-chip, .source-pill, .price-pill {{
        border-radius: 999px !important;
        background: #EDE0D0 !important;
        color: #4A2C1A !important;
        border: 0 !important;
        font-weight: 700;
    }}
    .price-pill {{
        background: linear-gradient(135deg, #6B3A2A, #A0522D) !important;
        color: #FAF6F2 !important;
    }}
    .pill-positive {{ background: #EAF2E8; color: #2D5A27; border: 1px solid rgba(45,90,39,0.2); border-radius: 999px; }}
    .pill-negative {{ background: #F5EDE8; color: #7B2D00; border: 1px solid rgba(123,45,0,0.2);  border-radius: 999px; }}
    .pill-mixed    {{ background: #F5EDD8; color: #7B4F2E; border: 1px solid rgba(123,79,46,0.2);  border-radius: 999px; }}

    /* widget overrides */
    .stTextArea textarea, .stTextInput input {{
        background: rgba(255,252,248,0.95) !important;
        border: 1px solid rgba(200,168,130,0.5) !important;
        color: #2C1810 !important;
        border-radius: 8px !important;
    }}
    .stTextArea textarea:focus, .stTextInput input:focus {{
        border-color: #6B3A2A !important;
        box-shadow: 0 0 0 2px rgba(107,58,42,0.12) !important;
    }}
    .stButton button {{
        background: #2C1810 !important;
        border: 0 !important;
        color: #FFFFFF !important;
        border-radius: 6px !important;
        font-weight: 700 !important;
        letter-spacing: .5px !important;
        transition: all 0.2s ease !important;
    }}
    .stButton button * {{
        color: inherit !important;
    }}
    .stButton button:hover {{
        background: #6B3A2A !important;
        color: #FFFFFF !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 14px rgba(107,58,42,0.3) !important;
    }}
    /* Secondary/outline-style buttons (light bg) */
    .stButton button[kind="secondary"] {{
        background: #F0EBE3 !important;
        color: #2C1810 !important;
        border: 1px solid rgba(107,58,42,0.3) !important;
    }}
    .stButton button[kind="secondary"]:hover {{
        background: #E8D8C4 !important;
        color: #2C1810 !important;
    }}
    h1, h2, h3, h4 {{ color: #2C1810; font-weight: 800; }}
    p {{ color: #4A3728; }}

    @media (max-width: 820px) {{
        .luxury-editorial-grid {{ grid-template-columns: 1fr; }}
        .hero {{ padding: 2rem 1.2rem; }}
    }}

    /* ── Footer ────────────────────────────────────────────────── */
    .app-footer {{
        text-align: center;
        padding: 1.2rem 0 .6rem;
        color: #7A5C3E;
        font-size: .8rem;
    }}
    .app-footer .footer-brand {{
        font-weight: 800;
        background: linear-gradient(135deg, {PRIMARY}, {PRIMARY_L});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)




stats = get_db_stats()  # load once for hero + sidebar

# ── Hero ───────────────────────────────────────────────────────────────────
st.markdown(
    f"""
    <div class="hero">
      <span class="version-pill">GlowSense Buyer Intelligence</span>
      <p class="main-title">GlowSense</p>
      <p class="subtitle">
        Sephora-inspired product intelligence for skincare shoppers: review signals,
        buyer copilot, deal links, video-review search, and clean product lookup.
      </p>
      <div class="hero-badges">
        <span class="hero-badge">💬 Ask GlowSense</span>
        <span class="hero-badge">🛍️ Deal Finder</span>
        <span class="hero-badge">💬 {stats['reviews']:,}+ Reviews</span>
        <span class="hero-badge">🧴 Reviewed Products</span>
      </div>
    </div>
    <div class="luxury-editorial-grid">
      <div class="luxury-editorial-card">
        <div class="luxury-editorial-kicker">Shop with confidence</div>
        <div class="luxury-editorial-title">See what buyers actually loved</div>
      </div>
      <div class="luxury-editorial-card red">
        <div class="luxury-editorial-kicker">Before checkout</div>
        <div class="luxury-editorial-title">Check concerns, sensitivity, and breakouts</div>
      </div>
      <div class="luxury-editorial-card light">
        <div class="luxury-editorial-kicker">Smart shopping</div>
        <div class="luxury-editorial-title">Find video reviews and current deal links</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.warning("GlowSense is for review analysis and shopping research only. It is not medical or dermatology advice.")

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        f"""
        <div style="text-align:center; margin-bottom:.6rem;">
            <span style="font-size:2.4rem;">✨</span>
            <p style="font-size:1.3rem; font-weight:900; margin:.2rem 0 0;
               background:linear-gradient(135deg,{PRIMARY},{PRIMARY_L});
               -webkit-background-clip:text; -webkit-text-fill-color:transparent;
               background-clip:text;">GlowSense</p>
            <p style="font-size:.78rem; color:#7A5C3E; margin-top:.1rem;">
                Beauty & skincare review intelligence
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    # Live DB stats (uses stats loaded above)
    st.markdown("**📦 Database Overview**")
    s1, s2 = st.columns(2)
    s1.metric("Products", f"{stats['products']:,}")
    s2.metric("Reviews",  f"{stats['reviews']:,}")
    st.caption(f"🏷️ Brands in DB: **{stats['brands']:,}**")
    if stats["sources"]:
        for src, n in stats["sources"].items():
            src_label = {"sephora_csv": "Sephora CSV", "amazon_hf": "Amazon HF", "ulta_csv": "Ulta CSV"}.get(src, src)
            st.caption(f"  • {src_label}: {n:,} reviews")

    st.divider()
    st.markdown("**✨ Capabilities**")
    features = [
        ("📝", "green",  "Paste Review Analysis"),
        ("📊", "purple", "CSV Upload & Compare"),
        ("🔍", "pink",   "Product Lookup (DB)"),
        ("🗄️", "blue",   "Database Explorer"),
        ("📥", "purple", "Seed Data (Sephora + Amazon + Ulta)"),
        ("💬", "purple", "GlowSense Assistant"),
        ("💡", "green",  "Glow Score & Skin-type"),
        ("⬇️", "blue",   "Download Results"),
    ]
    features_html = ""
    for icon, color, label in features:
        features_html += f"""
        <div class="sidebar-feature">
            <span class="sidebar-icon {color}">{icon}</span>
            {label}
        </div>"""
    st.markdown(features_html, unsafe_allow_html=True)

    st.divider()
    st.caption("📋 Suggested CSV columns: `product`, `review`")
    st.markdown(
        f"""
        <div style="text-align:center; margin-top:1rem; padding:.5rem; opacity:.6;">
            <span style="font-size:.7rem; color:#8a6b7c;">
                Powered by <span style="font-weight:700;">GlowSense</span> v2.0
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ── Tabs ───────────────────────────────────────────────────────────────────
analyze_tab, compare_tab, lookup_tab, explorer_tab, seed_tab, about_tab = st.tabs([
    "📝 Analyze Reviews",
    "📊 Compare Products",
    "🔍 Product Lookup",
    "🗄️ Database Explorer",
    "📥 Seed Data",
    "💬 Ask / About",
])

# ══════════════════════════════════════════════════════════════════════════
# TAB 1 — Analyze pasted reviews  (unchanged)
# ══════════════════════════════════════════════════════════════════════════
sample_reviews = """I love this moisturizer. It is gentle and very hydrating. My dry skin feels soft and smooth.
The serum gave me a nice glow but the fragrance is strong.
This product made my sensitive skin red and irritated. I got small breakouts.
It works well under makeup and feels lightweight."""


def _pretty_source(src: str | None) -> str:
    if src == "sephora_csv":
        return "Sephora"
    if src == "amazon_hf":
        return "Amazon Beauty"
    if src == "ulta_csv":
        return "Ulta Beauty"
    return src or "Unknown source"


def _clip_text(text: object, max_chars: int = 850) -> str:
    if text is None:
        return ""
    value = str(text).strip()
    if not value or value == "nan":
        return ""
    if value.startswith("{") and value.endswith("}"):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, dict):
                parts = [f"{k}: {v}" for k, v in parsed.items() if v not in (None, "", "nan")]
                value = " | ".join(parts) or value
        except Exception:
            pass
    return value if len(value) <= max_chars else value[:max_chars].rstrip() + "…"


def _render_stars(rating: float) -> str:
    """Return HTML star string for a 0-5 rating."""
    try:
        rating = float(rating)
    except Exception:
        return ""
    full = int(rating)
    half = 1 if (rating - full) >= 0.3 else 0
    empty = 5 - full - half
    return (
        '<span class="star-rating">'
        + "★" * full
        + ("★" if half else "")
        + "☆" * empty
        + f"</span> <span style='font-weight:700;color:#20223a;'>{rating:.1f}</span>"
    )


def render_soft_bar_chart(data, x: str, y: str, color: str | None = None, height: int = 280) -> None:
    """Render calmer, portfolio-friendly charts instead of default Streamlit colors."""
    df = pd.DataFrame(data).copy()
    if df.empty or x not in df.columns or y not in df.columns:
        return
    df[y] = pd.to_numeric(df[y], errors="coerce")
    df = df.dropna(subset=[y]).sort_values(y, ascending=False)
    if df.empty:
        return
    color_scale = alt.Scale(
        range=["#6B3A2A", "#A0522D", "#C8A882", "#8B5A2B", "#D4A76A", "#7B4F2E"]
    )
    color_field = color or x
    encode_kwargs = {
        "x": alt.X(f"{x}:N", sort="-y", title=None, axis=alt.Axis(labelAngle=-30)),
        "y": alt.Y(f"{y}:Q", title=None),
        "color": alt.Color(f"{color_field}:N", scale=color_scale, legend=None if color_field == x else alt.Legend(title=None)),
        "tooltip": [alt.Tooltip(f"{x}:N"), alt.Tooltip(f"{y}:Q")],
    }
    if color and color != x:
        encode_kwargs["xOffset"] = alt.XOffset(f"{color}:N")
        encode_kwargs["tooltip"] = [alt.Tooltip(f"{x}:N"), alt.Tooltip(f"{color}:N"), alt.Tooltip(f"{y}:Q")]
    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8, opacity=0.88)
        .encode(**encode_kwargs)
        .properties(height=height)
    )
    st.altair_chart(chart, width="stretch")


def render_rating_distribution(ratings: list) -> None:
    clean = pd.Series(ratings).dropna()
    if clean.empty:
        return
    df = clean.round().astype(int).value_counts().sort_index().reset_index()
    df.columns = ["Rating", "Count"]
    df["Stars"] = df["Rating"].astype(str) + "★"
    render_soft_bar_chart(df, "Stars", "Count", height=220)


def render_glowsense_chatbot() -> None:
    """Rule-based Q&A assistant that answers questions about the GlowSense project."""
    stats = get_db_stats()
    products   = stats.get("products", 0)
    reviews    = stats.get("reviews", 0)
    brands     = stats.get("brands", 0)
    sources    = stats.get("sources", {})

    # ── Session state for chat history ──────────────────────────────────
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    st.markdown(
        """
        <div class="copilot-card" style="margin-bottom:1rem;">
          <div class="copilot-title">💬 GlowSense Assistant</div>
          <p style="margin:.3rem 0 0; font-size:.88rem; color:#5C3D2E;">
            Ask me anything about this project — products, brands, scoring, features, and more.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Quick-question chips ─────────────────────────────────────────────
    st.markdown("**Quick questions:**")
    quick_qs = [
        "How many products do you have?",
        "How many brands are covered?",
        "How does the Glow Score work?",
        "What data sources are used?",
        "What features does GlowSense have?",
        "How many reviews are in the database?",
    ]
    cols = st.columns(3)
    for i, q in enumerate(quick_qs):
        if cols[i % 3].button(q, key=f"quick_q_{i}", use_container_width=True):
            st.session_state.chat_history.append({"role": "user", "text": q})

    # ── Free-text input ─────────────────────────────────────────────────
    user_input = st.chat_input("Ask a question about GlowSense…")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "text": user_input})

    # ── Rule-based answering engine ──────────────────────────────────────
    def answer(q: str) -> str:
        q = q.lower().strip()

        # product count
        if any(k in q for k in ["how many product", "number of product", "products do you", "total product"]):
            return (f"GlowSense currently has **{products:,} products** in its database, "
                    f"covering **{brands:,} brands** across {len(sources)} data source(s).")

        # review count
        elif any(k in q for k in ["how many review", "number of review", "total review", "reviews do you"]):
            src_lines = ""
            for src, n in sources.items():
                label = {"sephora_csv": "Sephora", "amazon_hf": "Amazon", "ulta_csv": "Ulta"}.get(src, src)
                src_lines += f"\n- {label}: {n:,} reviews"
            return (f"The database contains **{reviews:,} reviews** in total.{src_lines}")

        # brand count
        elif any(k in q for k in ["how many brand", "number of brand", "brands covered", "brands do you"]):
            return (f"GlowSense covers **{brands:,} unique brands** sourced from Sephora, Amazon, and Ulta datasets.")

        # glow score
        elif any(k in q for k in ["glow score", "score work", "how is the score", "scoring", "how scored"]):
            return ("The **Glow Score** (0–100) is calculated from four factors:\n"
                    "- 🧠 **Sentiment analysis** of review text (positive vs negative language)\n"
                    "- ⭐ **Star rating** of the product\n"
                    "- 💰 **Price value** (compared to similar products in the same category)\n"
                    "- 🏷️ **Brand reputation** score\n\n"
                    "Only products with 10+ reviews are scored to ensure statistical reliability.")

        # data sources
        elif any(k in q for k in ["data source", "where does", "where do the", "what source", "dataset"]):
            src_detail = ", ".join(
                {"sephora_csv": "Sephora CSV", "amazon_hf": "Amazon HuggingFace", "ulta_csv": "Ulta CSV"}.get(s, s)
                for s in sources
            )
            return (f"GlowSense pulls data from: **{src_detail or 'Sephora, Amazon & Ulta'}**. "
                    f"Reviews are filtered to products with **10+ reviews** so the Glow Score is meaningful.")

        # features
        elif any(k in q for k in ["feature", "what can", "what does glowsense do", "capabilities", "what do you do"]):
            return ("GlowSense offers:\n"
                    "- 📝 **Paste & analyze** any skincare review text instantly\n"
                    "- 📊 **Compare products** side-by-side with Glow Score charts\n"
                    "- 🔍 **Product Lookup** — search the full database by name or brand\n"
                    "- 🗄️ **Database Explorer** — browse all {products:,} products and {reviews:,} reviews\n"
                    "- 📥 **Seed Data** — import Sephora, Amazon & Ulta datasets\n"
                    "- 💬 **This assistant** — ask questions about the project").format(
                        products=products, reviews=reviews)

        # what is glowsense
        elif any(k in q for k in ["what is glowsense", "about glowsense", "tell me about", "what are you"]):
            return ("**GlowSense** is a skincare review intelligence platform. "
                    f"It analyzes {reviews:,} real reviews from {products:,} products across {brands:,} brands "
                    "to compute a **Glow Score** — a composite rating based on sentiment, stars, price value, "
                    "and brand quality — so you can make smarter skincare decisions.")

        # sentiment analysis
        elif any(k in q for k in ["sentiment", "nlp", "natural language", "text analysis"]):
            return ("GlowSense uses **rule-based NLP sentiment analysis** (no external API needed). "
                    "It classifies review sentences as Positive, Negative, or Mixed, "
                    "identifies the most common positive and concern words, "
                    "and feeds those signals into the Glow Score calculation.")

        # categories / skin types
        elif any(k in q for k in ["category", "skin type", "skin concern", "moisturizer", "serum", "sunscreen"]):
            return ("GlowSense covers all major skincare categories including moisturizers, serums, "
                    "sunscreens, cleansers, toners, eye creams, and more. "
                    "Reviews are tagged with relevant skin types and concerns automatically.")

        # who made it
        elif any(k in q for k in ["who made", "who built", "who created", "who developed", "creator", "author"]):
            return ("GlowSense was designed as a skincare product intelligence platform "
                    "combining data engineering, NLP, and modern UI design. "
                    "It's built with **Python**, **Streamlit**, **SQLite**, and **Altair** for visualizations.")

        # tech stack
        elif any(k in q for k in ["tech", "built with", "technology", "stack", "python", "streamlit", "sqlite"]):
            return ("**Tech Stack:**\n"
                    "- 🐍 Python 3.12\n"
                    "- 🌐 Streamlit (UI)\n"
                    "- 🗄️ SQLite (database)\n"
                    "- 📊 Altair + Pandas (charts & data)\n"
                    "- 🧠 Custom NLP sentiment engine (no API key needed)")

        # hello / hi / hey
        elif any(k in q for k in ["hello", "hi ", "hey", "good morning", "good afternoon", "howdy"]):
            return (f"👋 Hello! I'm the **GlowSense Assistant**. "
                    f"I can tell you about our {products:,} products, {reviews:,} reviews, "
                    "how the Glow Score works, and much more. What would you like to know?")

        # thank you
        elif any(k in q for k in ["thank", "thanks", "great", "awesome", "perfect"]):
            return "You're welcome! Feel free to ask anything else about GlowSense. 😊"

        # fallback
        else:
            return (f"I can answer questions about GlowSense! Try asking:\n"
                    f"- *How many products do you have?* ({products:,} products)\n"
                    f"- *How does the Glow Score work?*\n"
                    f"- *What data sources are used?*\n"
                    f"- *What features does GlowSense have?*")

    # ── Process and display messages ─────────────────────────────────────
    if st.session_state.chat_history:
        # Answer the latest user message if not yet answered
        history = st.session_state.chat_history
        if history and history[-1]["role"] == "user":
            reply = answer(history[-1]["text"])
            st.session_state.chat_history.append({"role": "assistant", "text": reply})

        # Render full conversation
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.write(msg["text"])
            else:
                with st.chat_message("assistant", avatar="✨"):
                    st.markdown(msg["text"])

        # Clear button
        if st.button("🗑️ Clear conversation", key="clear_chat"):
            st.session_state.chat_history = []
            st.rerun()
    else:
        st.info("👆 Click a quick question above or type your own below to get started.")



def render_product_beauty_card(product: dict) -> None:
    """Show product metadata in a premium beauty-style card."""
    st.markdown('<div class="luxury-product-kicker">Product detail page</div>', unsafe_allow_html=True)
    left, right = st.columns([1, 2.2])
    with left:
        image_url = product.get("image_url")
        if image_url:
            st.markdown(
                f'<div style="border-radius:1.2rem; overflow:hidden; '
                f'box-shadow:0 8px 28px rgba(95,90,246,0.12); '
                f'transition:transform 0.3s ease;">'
                f'<img src="{image_url}" style="width:100%; display:block;" />'
                f'</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                """
                <div class="result-card" style="text-align:center; padding:3rem 1rem;">
                    <div style="font-size:3.5rem;">🧴</div>
                    <p style="color:#8a6b7c; font-weight:600; margin-top:.5rem;">No product image</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
    with right:
        st.markdown(f"### {product.get('product_name') or 'Unknown product'}")

        # Build rich meta HTML
        meta_html = '<div style="display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; margin:.4rem 0 .8rem;">'
        if product.get("brand_name"):
            meta_html += f'<span class="source-pill">🏷️ {product["brand_name"]}</span>'
        if product.get("category"):
            meta_html += f'<span class="source-pill">📁 {product["category"]}</span>'
        if product.get("price_usd"):
            meta_html += f'<span class="price-pill">${float(product["price_usd"]):.2f}</span>'
        meta_html += f'<span class="source-pill">{_pretty_source(product.get("source"))}</span>'
        meta_html += '</div>'

        if product.get("avg_rating"):
            meta_html += _render_stars(float(product["avg_rating"]))

        st.markdown(meta_html, unsafe_allow_html=True)

        detail_tabs = st.tabs(["📋 Details", "🧪 Ingredients", "✨ Highlights"])
        with detail_tabs[0]:
            details = _clip_text(product.get("details_text"), 1000)
            st.write(details if details else "No extra product details stored yet.")
        with detail_tabs[1]:
            ingredients = _clip_text(product.get("ingredients"), 1200)
            st.write(ingredients if ingredients else "No ingredients stored for this product yet.")
        with detail_tabs[2]:
            highlights = _clip_text(product.get("highlights"), 1200)
            st.write(highlights if highlights else "No highlights stored for this product yet.")


def render_buyer_links(product: dict) -> None:
    """Show helpful buyer links without needing paid shopping/YouTube APIs."""
    product_name = product.get("product_name") or ""
    brand = product.get("brand_name") or ""
    query = " ".join([brand, product_name]).strip()
    if not query:
        return

    q = quote_plus(query)
    yt_q = quote_plus(f"{query} review skincare beauty")
    deal_q = quote_plus(f"{query} deal sale coupon")

    st.markdown("### 🛍️ Buyer helper")
    st.caption(
        "These open live searches. For YouTube, check likes/views on the video page; GlowSense does not store YouTube likes yet."
    )
    st.markdown(
        '<div class="luxury-buyer-action">Buyer action center: watch reviews, compare stores, then decide.</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Video reviews**")
        st.markdown(
            f"""
            <div class="result-card">
              <a href="https://www.youtube.com/results?search_query={yt_q}" target="_blank">▶️ YouTube review search</a><br/>
              <a href="https://www.google.com/search?tbm=vid&q={yt_q}+1000+likes" target="_blank">⭐ Video reviews likely to have 1,000+ likes/views</a><br/>
              <a href="https://www.tiktok.com/search?q={yt_q}" target="_blank">🎥 TikTok product reviews</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown("**Find current deals**")
        st.markdown(
            f"""
            <div class="result-card">
              <a href="https://www.google.com/search?tbm=shop&q={deal_q}" target="_blank">🛒 Google Shopping deals</a><br/>
              <a href="https://www.amazon.com/s?k={q}" target="_blank">Amazon</a> ·
              <a href="https://www.sephora.com/search?keyword={q}" target="_blank">Sephora</a> ·
              <a href="https://www.ulta.com/search?search={q}" target="_blank">Ulta</a><br/>
              <a href="https://www.google.com/search?q={deal_q}+site%3Atarget.com+OR+site%3Awalmart.com" target="_blank">Target/Walmart deal search</a>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _glow_gauge_html(score: int) -> str:
    """Return an SVG radial gauge for the Glow score."""
    radius = 54
    circumference = 2 * 3.14159 * radius
    offset = circumference * (1 - score / 100)
    # Color gradient based on score
    if score >= 70:
        color = "#2e7d32"
    elif score >= 40:
        color = "#f9a825"
    else:
        color = "#c62828"
    return f"""
    <div class="glow-gauge">
        <svg width="140" height="140" viewBox="0 0 140 140">
            <circle cx="70" cy="70" r="{radius}" fill="none" stroke="rgba(244,207,226,0.3)" stroke-width="10"/>
            <circle cx="70" cy="70" r="{radius}" fill="none" stroke="{color}" stroke-width="10"
                    stroke-dasharray="{circumference}" stroke-dashoffset="{offset}"
                    stroke-linecap="round" style="transition: stroke-dashoffset 1s ease;"/>
        </svg>
        <div class="glow-gauge-label">
            <div class="glow-gauge-num">{score}</div>
            <div class="glow-gauge-sub">Glow Score</div>
        </div>
    </div>
    """


def render_review_analysis_panel(result, breakdown: dict, review_rows: list[dict] | None = None) -> None:
    """Reusable review-analysis panel with radial gauge and sentiment pills."""
    # ── Top metrics row ──
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Reviews analysed", f"{result.review_count:,}")
    m2.metric("Glow score", f"{result.glow_score}/100")
    m3.metric("Recommend", f"{breakdown['Recommend %']}%")
    m4.metric("Do not recommend", f"{breakdown['Do not recommend %']}%")
    m5.metric("Mixed", f"{breakdown['Mixed %']}%")

    # ── "What people are saying" card with sentiment pills ──
    rec_pct = breakdown['Recommend %']
    neg_pct = breakdown['Do not recommend %']
    mix_pct = breakdown['Mixed %']
    st.markdown(
        f"""
        <div class="result-card">
        <h3>💬 What people are saying</h3>
        <p>
            <span class="pill-positive">👍 {rec_pct}% Recommend</span>&nbsp;
            <span class="pill-negative">👎 {neg_pct}% Don't recommend</span>&nbsp;
            <span class="pill-mixed">🤷 {mix_pct}% Mixed</span>
        </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(2)
    with left:
        # Radial glow gauge
        st.markdown(_glow_gauge_html(result.glow_score), unsafe_allow_html=True)
        st.caption(
            "ℹ️ **Multi-factor Glow Score**: Calculated dynamically based on Review Sentiment (40%), "
            "Product Star Rating (30%), Price vs. Category Average (15%), and Brand Reputation (15%)."
        )
        st.markdown(f"**Sentiment:** {result.sentiment_label}")
        st.success(result.summary)
        st.info(result.recommendation)

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**👍 Why people like it:**")
            st.dataframe(pd.DataFrame(breakdown["Reasons people like it"], columns=["Word", "Count"]),
                         width="stretch", hide_index=True)
        with c2:
            st.markdown("**👎 Why people dislike it:**")
            st.dataframe(pd.DataFrame(breakdown["Reasons people dislike it"], columns=["Word", "Count"]),
                         width="stretch", hide_index=True)
    with right:
        if result.topics:
            st.markdown("**🏷️ Topic signals:**")
            render_soft_bar_chart(pd.DataFrame(result.topics, columns=["Topic", "Count"]), "Topic", "Count")
        if result.skin_types:
            st.markdown("**🧬 Skin-type clues:**")
            st.dataframe(pd.DataFrame(result.skin_types, columns=["Skin type", "Count"]),
                         width="stretch", hide_index=True)
        if review_rows:
            ratings = [r["rating"] for r in review_rows if r.get("rating") is not None]
            if ratings:
                st.markdown("**⭐ Rating distribution:**")
                render_rating_distribution(ratings)
            skin_meta = [r["skin_type"] for r in review_rows if r.get("skin_type")]
            if skin_meta:
                st.markdown("**👤 Reviewer skin types:**")
                skin_counts = pd.Series(skin_meta).value_counts().head(8).reset_index()
                skin_counts.columns = ["Skin type", "Count"]
                render_soft_bar_chart(skin_counts, "Skin type", "Count", height=220)

with analyze_tab:
    st.subheader("Analyze pasted reviews")
    reviews = st.text_area(
        "Paste skincare / beauty product reviews here",
        value=sample_reviews,
        height=230,
        help="Tip: put each review on a new line.",
    )

    result = analyze_reviews(reviews)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Reviews",    result.review_count)
    col2.metric("Words",      result.word_count)
    col3.metric("Glow score", f"{result.glow_score}/100")
    col4.metric("Positive",   result.positive_count)
    col5.metric("Concerns",   result.negative_count)

    left, right = st.columns([1, 1])
    with left:
        st.markdown("### Overall read")
        st.markdown(f"**{result.sentiment_label}**")
        st.progress(result.glow_score / 100)
        st.caption("Higher score means stronger positive review signals.")
        st.success(result.summary)
        st.info(result.recommendation)

    with right:
        st.markdown("### Topic signals")
        if result.topics:
            topic_df = pd.DataFrame(result.topics, columns=["Topic", "Count"])
            render_soft_bar_chart(topic_df, "Topic", "Count")
        else:
            st.write("No clear skincare topic found yet.")

        st.markdown("### Skin-type clues")
        if result.skin_types:
            skin_df = pd.DataFrame(result.skin_types, columns=["Skin type clue", "Count"])
            st.dataframe(skin_df, width="stretch", hide_index=True)
        else:
            st.write("No strong skin-type clue found yet.")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("### Positive words")
        st.dataframe(pd.DataFrame(result.positive_words, columns=["Word", "Count"]),
                     width="stretch", hide_index=True)
    with c2:
        st.markdown("### Concern words")
        st.dataframe(pd.DataFrame(result.negative_words, columns=["Word", "Count"]),
                     width="stretch", hide_index=True)
    with c3:
        st.markdown("### Common words")
        st.dataframe(pd.DataFrame(result.common_words, columns=["Word", "Count"]),
                     width="stretch", hide_index=True)

# ══════════════════════════════════════════════════════════════════════════
# TAB 2 — Compare products  (unchanged)
# ══════════════════════════════════════════════════════════════════════════
with compare_tab:
    st.subheader("Upload reviews and products metadata")
    
    upload_mode = st.radio(
        "Upload configuration",
        ["Single CSV File (Reviews + metadata)", "Two CSV Files (Reviews file + Products metadata file)"],
        horizontal=True
    )
    
    df = None
    is_demo = False
    
    if upload_mode == "Single CSV File (Reviews + metadata)":
        uploaded_file = st.file_uploader("Upload CSV file (Reviews & optional metadata)", type=["csv"], key="single_csv_uploader")
        if uploaded_file is not None:
            try:
                df = pd.read_csv(uploaded_file)
            except Exception as e:
                st.error(f"Error loading CSV file: {e}")
        else:
            is_demo = True
    else:
        col_u1, col_u2 = st.columns(2)
        with col_u1:
            uploaded_reviews = st.file_uploader("Upload Reviews CSV", type=["csv"], key="two_csv_reviews_uploader")
        with col_u2:
            uploaded_prods = st.file_uploader("Upload Products details/metadata CSV", type=["csv"], key="two_csv_products_uploader")
            
        if uploaded_reviews is not None and uploaded_prods is not None:
            try:
                df_revs = pd.read_csv(uploaded_reviews)
                df_prods = pd.read_csv(uploaded_prods)
                
                st.markdown("##### Link columns between files")
                col_join1, col_join2 = st.columns(2)
                with col_join1:
                    rev_join_col = st.selectbox(
                        "Product key in Reviews CSV", 
                        df_revs.columns, 
                        index=df_revs.columns.get_loc("product") if "product" in df_revs.columns else 0,
                        key="rev_join_col"
                    )
                with col_join2:
                    prod_join_col = st.selectbox(
                        "Product key in Products CSV", 
                        df_prods.columns, 
                        index=df_prods.columns.get_loc("product") if "product" in df_prods.columns else 0,
                        key="prod_join_col"
                    )
                
                df = pd.merge(df_revs, df_prods, left_on=rev_join_col, right_on=prod_join_col, how="left")
            except Exception as e:
                st.error(f"Error linking files: {e}")
        else:
            if uploaded_reviews is not None or uploaded_prods is not None:
                st.warning("Please upload BOTH files to link them. Using demo data in the meantime.")
            is_demo = True

    if is_demo:
        df = pd.DataFrame(
            {
                "product": ["Glow Cream", "Glow Cream", "Clear Serum", "Clear Serum", "Soft Gel", "Soft Gel"],
                "review": [
                    "Very hydrating and gentle. My dry skin feels soft.",
                    "Nice glow but the fragrance is strong.",
                    "Helped my acne and made my skin clear.",
                    "It caused redness and irritation on my sensitive skin.",
                    "Lightweight, smooth, affordable and refreshing.",
                    "Works well for oily skin and does not feel greasy.",
                ],
                "brand": ["PureGlow", "PureGlow", "ClearSkin", "ClearSkin", "DewSkin", "DewSkin"],
                "price": [32.0, 32.0, 45.0, 45.0, 22.0, 22.0],
                "category": ["Moisturizer", "Moisturizer", "Serum", "Serum", "Cleanser", "Cleanser"],
                "rating": [4.2, 4.2, 4.0, 4.0, 4.6, 4.6]
            }
        )

    if df is not None:
        st.markdown("### Data preview")
        st.dataframe(df.head(10), width="stretch")

        columns = list(df.columns)
        if len(columns) < 2:
            st.error("Your CSV needs at least two columns: product and review.")
        else:
            st.markdown("### Column Mapping & Settings")
            st.caption("Map the columns from your data so GlowSense can calculate sentiments and dynamic Glow Scores.")
            
            c_sel1, c_sel2 = st.columns(2)
            with c_sel1:
                product_col = st.selectbox(
                    "Product Identifier column *", 
                    columns,
                    index=columns.index("product") if "product" in columns else 0,
                    key="mapped_product_col"
                )
                brand_col = st.selectbox(
                    "Brand column (optional)", 
                    [None] + columns,
                    index=columns.index("brand") + 1 if "brand" in columns else 0,
                    key="mapped_brand_col"
                )
                category_col = st.selectbox(
                    "Category column (optional)", 
                    [None] + columns,
                    index=columns.index("category") + 1 if "category" in columns else 0,
                    key="mapped_category_col"
                )
            with c_sel2:
                review_col = st.selectbox(
                    "Review Text column *", 
                    columns,
                    index=columns.index("review") if "review" in columns else min(1, len(columns) - 1),
                    key="mapped_review_col"
                )
                price_col = st.selectbox(
                    "Price column (optional)", 
                    [None] + columns,
                    index=columns.index("price") + 1 if "price" in columns else 0,
                    key="mapped_price_col"
                )
                rating_col = st.selectbox(
                    "Rating/Stars column (optional)", 
                    [None] + columns,
                    index=columns.index("rating") + 1 if "rating" in columns else 0,
                    key="mapped_rating_col"
                )

            # Extract custom metadata from mapping
            products_metadata = {}
            prod_details = {}
            for prod_id, group in df.groupby(product_col):
                brand = None
                price = None
                cat = None
                rating = None
                
                if brand_col and brand_col in df.columns:
                    non_null = group[brand_col].dropna()
                    if not non_null.empty:
                        brand = str(non_null.iloc[0])
                        
                if price_col and price_col in df.columns:
                    non_null = pd.to_numeric(group[price_col], errors='coerce').dropna()
                    if not non_null.empty:
                        price = float(non_null.mean())
                        
                if category_col and category_col in df.columns:
                    non_null = group[category_col].dropna()
                    if not non_null.empty:
                        cat = str(non_null.iloc[0])
                        
                if rating_col and rating_col in df.columns:
                    non_null = pd.to_numeric(group[rating_col], errors='coerce').dropna()
                    if not non_null.empty:
                        rating = float(non_null.mean())
                        
                prod_details[str(prod_id)] = {
                    "brand": brand,
                    "price": price,
                    "category": cat,
                    "rating": rating
                }
            
            # Calculate category average price
            cat_prices = {}
            for p, details in prod_details.items():
                cat = details["category"]
                price = details["price"]
                if cat and price is not None:
                    if cat not in cat_prices:
                        cat_prices[cat] = []
                    cat_prices[cat].append(price)
                    
            cat_avg_price = {cat: sum(prices)/len(prices) for cat, prices in cat_prices.items() if prices}
            
            # Calculate brand average rating
            brand_ratings = {}
            for p, details in prod_details.items():
                brand = details["brand"]
                rating = details["rating"]
                if brand and rating is not None:
                    if brand not in brand_ratings:
                        brand_ratings[brand] = []
                    brand_ratings[brand].append(rating)
                    
            brand_avg_rating = {brand: sum(ratings)/len(ratings) for brand, ratings in brand_ratings.items() if ratings}
            
            # Build the final metadata dictionary
            for p, details in prod_details.items():
                products_metadata[p] = {
                    "price_usd": details["price"],
                    "avg_cat_price": cat_avg_price.get(details["category"]) if details["category"] else None,
                    "brand_avg_rating": brand_avg_rating.get(details["brand"]) if details["brand"] else None,
                    "product_avg_rating": details["rating"]
                }

            grouped_reviews = {
                str(product): reviews_to_text(group[review_col].dropna())
                for product, group in df.groupby(product_col)
            }

            # ── Action A: Save to database ──
            st.markdown("### 📥 Save to GlowSense Database")
            st.info(
                f"Saving will import all **{len(prod_details):,} products** and **{len(df):,} reviews** "
                f"from your uploaded files directly into the SQLite database. Once saved, you can search, lookup "
                f"or ask about these products across all tabs in the app."
            )
            
            col_save1, _ = st.columns([1.5, 2.5])
            with col_save1:
                if st.button("📥 Save all uploaded data to Database", key="save_to_db_btn", type="primary", use_container_width=True):
                    with st.spinner("Saving data to database..."):
                        prod_inserts = []
                        for prod, details in prod_details.items():
                            prod_inserts.append({
                                "product_id": prod,
                                "product_name": prod,
                                "brand_name": details["brand"] or "Uploaded Brand",
                                "category": details["category"] or "Skincare",
                                "price_usd": details["price"],
                                "avg_rating": details["rating"] or 4.0,
                                "review_count": 0,
                                "source": "user_upload",
                                "ingredients": None,
                                "highlights": None,
                                "details_text": None,
                                "image_url": None,
                            })
                        
                        rev_inserts = []
                        for idx, row in df.iterrows():
                            p_id = str(row[product_col])
                            r_text = str(row[review_col])
                            br = str(row[brand_col]) if brand_col and brand_col in df.columns and pd.notnull(row[brand_col]) else None
                            rt = float(row[rating_col]) if rating_col and rating_col in df.columns and pd.notnull(row[rating_col]) else 4.0
                            rev_inserts.append({
                                "product_id": p_id,
                                "product_name": p_id,
                                "brand_name": br,
                                "rating": rt,
                                "review_text": r_text,
                                "review_title": "Review",
                                "skin_type": None,
                                "is_recommended": 1 if rt >= 4.0 else (0 if rt <= 2.0 else None),
                                "source": "user_upload"
                            })
                        
                        inserted_prods = insert_products_bulk(prod_inserts, source="user_upload")
                        inserted_revs = insert_reviews_bulk(rev_inserts, source="user_upload")
                        sync_product_stats()
                        
                    st.success(f"🎉 Successfully imported {inserted_prods} products and {inserted_revs} reviews! Refreshing database stats...")
                    st.rerun()

            # ── Action B: Run Comparison Analysis on Selected Subset ──
            st.markdown("### 📊 Compare Selected Products")
            st.caption("Select specific products below to run sentiment analysis and compute comparison charts at runtime. This avoids performance issues on large files.")
            
            all_product_names = list(grouped_reviews.keys())
            selected_products = st.multiselect(
                "Select products to compare (max 10 recommended)",
                options=all_product_names,
                default=all_product_names[:3] if len(all_product_names) >= 3 else all_product_names,
                key="comparison_selected_prods"
            )

            if selected_products:
                sub_grouped_reviews = {p: grouped_reviews[p] for p in selected_products}
                sub_metadata = {p: products_metadata[p] for p in selected_products if p in products_metadata}
                
                with st.spinner("Analyzing selected products..."):
                    comparison_df = pd.DataFrame(analyze_products(sub_grouped_reviews, products_metadata=sub_metadata))

                st.markdown("#### Comparison results")
                st.dataframe(comparison_df, width="stretch", hide_index=True)

                if not comparison_df.empty:
                    chart_df = comparison_df[["Product", "Glow score", "Recommend %", "Do not recommend %"]].melt(
                        id_vars="Product", var_name="Metric", value_name="Score"
                    )
                    st.markdown("#### Comparison chart")
                    render_soft_bar_chart(chart_df, "Product", "Score", color="Metric")

                    best_product = comparison_df.iloc[0]
                    st.success(
                        f"Best current product by recommendation percentage: **{best_product['Product']}** "
                        f"({best_product['Recommend %']}% recommend, Glow score {best_product['Glow score']}/100)."
                    )

                    st.markdown("#### Understand one product")
                    selected_product  = st.selectbox("Which product do you want to understand?", selected_products, key="compare_understand_product")
                    selected_text     = sub_grouped_reviews[selected_product]
                    selected_meta     = sub_metadata.get(selected_product) if sub_metadata else None
                    selected_analysis = analyze_reviews(selected_text, product_name=selected_product, custom_metadata=selected_meta)
                    selected_breakdown = product_recommendation_breakdown(selected_text, product_name=selected_product)

                    p1, p2, p3, p4 = st.columns(4)
                    p1.metric("Recommend",       f"{selected_breakdown['Recommend %']}%",
                              f"{selected_breakdown['Recommend count']} reviews")
                    p2.metric("Do not recommend", f"{selected_breakdown['Do not recommend %']}%",
                              f"{selected_breakdown['Do not recommend count']} reviews")
                    p3.metric("Mixed",           f"{selected_breakdown['Mixed %']}%",
                              f"{selected_breakdown['Mixed count']} reviews")
                    p4.metric("Total reviews",   selected_breakdown["Total reviews"])

                    st.markdown(
                        f"**Simple answer:** For **{selected_product}**, about "
                        f"**{selected_breakdown['Recommend %']}%** of reviews look like they recommend it, "
                        f"while **{selected_breakdown['Do not recommend %']}%** look like they do not recommend it."
                    )
                    st.info(selected_analysis.recommendation)

                    reason_left, reason_right = st.columns(2)
                    with reason_left:
                        st.markdown("##### Why people like it")
                        st.dataframe(pd.DataFrame(selected_breakdown["Reasons people like it"],
                                     columns=["Reason word", "Count"]),
                                     width="stretch", hide_index=True)
                    with reason_right:
                        st.markdown("##### Why people may dislike it")
                        st.dataframe(pd.DataFrame(selected_breakdown["Reasons people dislike it"],
                                     columns=["Concern word", "Count"]),
                                     width="stretch", hide_index=True)

                    csv_download = comparison_df.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "Download comparison results",
                        data=csv_download,
                        file_name="glowsense_product_comparison.csv",
                        mime="text/csv",
                    )
            else:
                st.warning("⚠️ Please select at least one product above to analyze and display the comparison table.")

# ══════════════════════════════════════════════════════════════════════════
# TAB 3 — 🔍 Product Lookup  (Brand overview + per-product deep-dive)
# ══════════════════════════════════════════════════════════════════════════
with lookup_tab:
    st.subheader("🔍 Product Lookup")

    if stats["reviews"] == 0:
        st.info("📭 Your database is empty. Go to the **📥 Seed Data** tab first to load products and reviews.")
    else:
        st.write(
            "Search a **product name** to get a full buyer-style analysis: review summary, brand, price/details, YouTube review searches, and deal links. "
            "GlowSense now shows reviewed products first so the results feel cleaner. "
            "You can also search a **brand name** to compare reviewed products for that brand."
        )

        col_search, col_mode = st.columns([3, 1])
        with col_search:
            search_query = st.text_input(
                "Brand name, product name, or product ID",
                placeholder="e.g. LANEIGE   or   Lotus Balancing Oil   or   P379064",
            )
        with col_mode:
            lookup_mode = st.radio("Search mode", ["Single Product", "Brand Overview"], horizontal=False)

        if search_query and search_query.strip():
            q = search_query.strip()

            # ── BRAND OVERVIEW MODE ──────────────────────────────────────
            if lookup_mode == "Brand Overview":
                brand_options = search_brands(q, limit=12)
                if not brand_options:
                    st.warning(f"No brand found matching **{q}**. Try a different spelling.")
                else:
                    if len(brand_options) == 1:
                        selected_brand = brand_options[0]["brand_name"]
                    else:
                        st.caption("Choose the exact brand below. This avoids mixed results from similar brand names.")
                        selected_idx = st.selectbox(
                            "Brand match",
                            range(len(brand_options)),
                            format_func=lambda i: (
                                f"{brand_options[i]['brand_name']} "
                                f"({brand_options[i]['products']:,} products · {brand_options[i]['reviews']:,} reviews)"
                            ),
                            key="brand_match_select",
                        )
                        selected_brand = brand_options[selected_idx]["brand_name"]

                    with st.spinner(f"Loading all products for **{selected_brand}** …"):
                        brand_products = get_products_by_brand(selected_brand, limit=100)
                        brand_reviews  = get_reviews_by_brand(selected_brand, limit=10000)

                    total_brand_reviews = len(brand_reviews)
                    st.success(
                        f"Found **{len(brand_products)} products** for **{selected_brand}** "
                        f"with **{total_brand_reviews:,} reviews** in the database."
                    )

                    if total_brand_reviews == 0:
                        st.warning(
                            f"⚠️ No reviews are stored yet for **{selected_brand}** products. "
                            "Go to **📥 Seed Data** and increase the row limit to load more reviews."
                        )
                    else:
                        # ── Brand-level aggregate analysis ──────────────
                        st.markdown("---")
                        st.markdown(f"### 🏷️ {selected_brand} — Brand Overview")

                        all_brand_texts = "\n".join(
                            r["review_text"] for r in brand_reviews if r.get("review_text")
                        )
                        brand_result    = analyze_reviews(all_brand_texts, brand_name=selected_brand)
                        brand_breakdown = product_recommendation_breakdown(all_brand_texts, brand_name=selected_brand)

                        bm1, bm2, bm3, bm4, bm5 = st.columns(5)
                        bm1.metric("Total reviews", f"{brand_result.review_count:,}")
                        bm2.metric("Brand Glow score", f"{brand_result.glow_score}/100")
                        bm3.metric("Recommend %", f"{brand_breakdown['Recommend %']}%")
                        bm4.metric("Don't recommend", f"{brand_breakdown['Do not recommend %']}%")
                        bm5.metric("Mixed", f"{brand_breakdown['Mixed %']}%")

                        bl, br = st.columns(2)
                        with bl:
                            st.markdown(f"**Overall sentiment:** {brand_result.sentiment_label}")
                            st.progress(brand_result.glow_score / 100)
                            st.success(brand_result.summary)
                            st.info(brand_result.recommendation)
                        with br:
                            if brand_result.topics:
                                st.markdown("**Top topics across all products:**")
                                td = pd.DataFrame(brand_result.topics, columns=["Topic", "Count"])
                                render_soft_bar_chart(td, "Topic", "Count")

                        # ── Per-product analysis table ──────────────────
                        st.markdown("---")
                        st.markdown("### 📊 All Products — Analysis Table")
                        st.caption("Each row is computed live from stored reviews for that product.")

                        # Group brand_reviews by product_id / product_name
                        product_review_map: dict[str, list] = {}
                        for rev in brand_reviews:
                            key = rev.get("product_id") or rev.get("product_name") or "Unknown"
                            product_review_map.setdefault(key, []).append(rev)

                        table_rows = []
                        for prod in brand_products:
                            pid   = prod["product_id"]
                            pname = prod["product_name"]
                            # Match reviews by product_id
                            prod_reviews = product_review_map.get(pid, [])
                            if not prod_reviews and pname:
                                prod_reviews = product_review_map.get(pname, [])

                            if not prod_reviews:
                                table_rows.append({
                                    "Product": pname,
                                    "Category": prod.get("category") or "—",
                                    "Price ($)": prod.get("price_usd") or "—",
                                    "Reviews": 0,
                                    "Glow Score": "—",
                                    "Recommend %": "—",
                                    "Don't Rec %": "—",
                                    "Sentiment": "No reviews",
                                    "Top Concern": "—",
                                    "Top Positive": "—",
                                })
                                continue

                            rev_text = "\n".join(r["review_text"] for r in prod_reviews if r.get("review_text"))
                            res  = analyze_reviews(rev_text, product_id=prod.get("product_id"), product_name=pname)
                            brkd = product_recommendation_breakdown(rev_text, product_id=prod.get("product_id"), product_name=pname)
                            top_concern  = res.negative_words[0][0] if res.negative_words else "—"
                            top_positive = res.positive_words[0][0] if res.positive_words else "—"

                            table_rows.append({
                                "Product":       pname,
                                "Category":      prod.get("category") or "—",
                                "Price ($)":     prod.get("price_usd") or "—",
                                "Reviews":       res.review_count,
                                "Glow Score":    res.glow_score,
                                "Recommend %":   brkd["Recommend %"],
                                "Don't Rec %":   brkd["Do not recommend %"],
                                "Sentiment":     res.sentiment_label,
                                "Top Concern":   top_concern,
                                "Top Positive":  top_positive,
                            })

                        products_df = pd.DataFrame(table_rows)
                        # Sort: products with reviews first, then by Glow Score
                        has_reviews = products_df[products_df["Reviews"] > 0].sort_values(
                            "Glow Score", ascending=False
                        )
                        no_reviews = products_df[products_df["Reviews"] == 0]
                        products_df = pd.concat([has_reviews, no_reviews], ignore_index=True)

                        st.dataframe(products_df, width="stretch", hide_index=True)

                        # Glow score bar chart for products that have reviews
                        scored = has_reviews[has_reviews["Glow Score"] != "—"].copy()
                        if not scored.empty:
                            st.markdown("#### Glow Score comparison")
                            render_soft_bar_chart(scored[["Product", "Glow Score"]], "Product", "Glow Score", height=320)

                        # Download
                        csv_dl = products_df.to_csv(index=False).encode("utf-8")
                        st.download_button(
                            f"⬇️ Download {selected_brand} analysis table",
                            data=csv_dl,
                            file_name=f"glowsense_{selected_brand.lower().replace(' ','_')}_analysis.csv",
                            mime="text/csv",
                        )

                        # ── Click to drill into one product ────────────
                        st.markdown("---")
                        st.markdown("### 🔬 Deep-dive into one product")
                        prods_with_reviews = [r["Product"] for r in table_rows if r["Reviews"] > 0]
                        if prods_with_reviews:
                            drill_choice = st.selectbox(
                                "Select a product for full detailed analysis",
                                prods_with_reviews,
                                key="drill_brand"
                            )
                            # Find product_id for drill
                            drill_prod = next((p for p in brand_products if p["product_name"] == drill_choice), None)
                            drill_pid  = drill_prod["product_id"] if drill_prod else None
                            drill_revs = product_review_map.get(drill_pid, [])
                            if not drill_revs:
                                drill_revs = product_review_map.get(drill_choice, [])

                            if drill_revs:
                                drill_text     = "\n".join(r["review_text"] for r in drill_revs if r.get("review_text"))
                                drill_result   = analyze_reviews(drill_text, product_id=drill_pid, product_name=drill_choice)
                                drill_breakdown= product_recommendation_breakdown(drill_text, product_id=drill_pid, product_name=drill_choice)

                                d1, d2, d3, d4, d5 = st.columns(5)
                                d1.metric("Reviews", f"{drill_result.review_count:,}")
                                d2.metric("Glow score", f"{drill_result.glow_score}/100")
                                d3.metric("Recommend %", f"{drill_breakdown['Recommend %']}%")
                                d4.metric("Don't rec", f"{drill_breakdown['Do not recommend %']}%")
                                d5.metric("Mixed", f"{drill_breakdown['Mixed %']}%")



                                dl, dr = st.columns(2)
                                with dl:
                                    st.markdown(f"**Sentiment:** {drill_result.sentiment_label}")
                                    st.progress(drill_result.glow_score / 100)
                                    st.success(drill_result.summary)
                                    st.info(drill_result.recommendation)

                                    st.markdown("**Why people like it:**")
                                    if drill_breakdown["Reasons people like it"]:
                                        st.dataframe(
                                            pd.DataFrame(drill_breakdown["Reasons people like it"],
                                                         columns=["Word", "Count"]),
                                            width="stretch", hide_index=True
                                        )
                                    st.markdown("**Why people dislike it:**")
                                    if drill_breakdown["Reasons people dislike it"]:
                                        st.dataframe(
                                            pd.DataFrame(drill_breakdown["Reasons people dislike it"],
                                                         columns=["Word", "Count"]),
                                            width="stretch", hide_index=True
                                        )

                                with dr:
                                    if drill_result.topics:
                                        st.markdown("**Topic signals:**")
                                        td = pd.DataFrame(drill_result.topics, columns=["Topic", "Count"])
                                        render_soft_bar_chart(td, "Topic", "Count")
                                    if drill_result.skin_types:
                                        st.markdown("**Skin-type clues:**")
                                        sd = pd.DataFrame(drill_result.skin_types, columns=["Skin type", "Count"])
                                        st.dataframe(sd, width="stretch", hide_index=True)

                                    # Rating distribution
                                    ratings = [r["rating"] for r in drill_revs if r.get("rating") is not None]
                                    if ratings:
                                        st.markdown("**Rating distribution:**")
                                        render_rating_distribution(ratings)

                                    # Skin type metadata
                                    skin_meta = [r["skin_type"] for r in drill_revs if r.get("skin_type")]
                                    if skin_meta:
                                        st.markdown("**Reviewer skin types:**")
                                        sc_counts = pd.Series(skin_meta).value_counts().head(8).reset_index()
                                        sc_counts.columns = ["Skin type", "Count"]
                                        render_soft_bar_chart(sc_counts, "Skin type", "Count", height=220)

            # ── SINGLE PRODUCT MODE ──────────────────────────────────────
            else:
                with st.spinner("Searching database …"):
                    matches    = search_products(q, limit=20)
                    name_matches = search_products_by_name_only(q, limit=10)

                if not matches and not name_matches:
                    st.warning(f"No products found matching **{q}**.")
                else:
                    combined_names = {m["product_name"] for m in matches}
                    extra = [m for m in name_matches if m["product_name"] not in combined_names]
                    all_options = [
                        f"{m['product_name']}" + (f" — {m['brand_name']}" if m.get('brand_name') else "")
                        + f" ({m.get('stored_reviews', 0):,} reviews)"
                        for m in matches
                    ] + [
                        f"{m['product_name']} ({m.get('stored_reviews', 0):,} reviews)"
                        for m in extra
                    ]

                    if len(all_options) == 1:
                        choice_idx = 0
                    else:
                        st.success(f"Found {len(all_options)} match(es).")
                        choice_idx = st.selectbox(
                            "Select product", range(len(all_options)),
                            format_func=lambda i: all_options[i],
                            key="single_product_select"
                        )

                    chosen = matches[choice_idx] if choice_idx < len(matches) else extra[choice_idx - len(matches)]
                    pid    = chosen.get("product_id")
                    pname  = chosen.get("product_name")

                    with st.spinner("Loading reviews and generating analysis …"):
                        review_rows = get_reviews_for_product(product_id=pid, product_name=pname, limit=2000)

                    st.markdown("---")
                    render_product_beauty_card(chosen)
                    render_buyer_links(chosen)
                    st.markdown("---")

                    if not review_rows:
                        st.info(
                            f"📭 No reviews stored for **{pname}** yet — but the product details above are from the database. "
                            "Go to **📥 Seed Data** and load more rows to include reviews for this product."
                        )
                    else:
                        review_texts  = [r["review_text"] for r in review_rows if r.get("review_text")]
                        combined_text = "\n".join(review_texts)
                        result        = analyze_reviews(combined_text, product_id=pid, product_name=pname)
                        breakdown     = product_recommendation_breakdown(combined_text, product_id=pid, product_name=pname)

                        render_review_analysis_panel(result, breakdown, review_rows)



# ══════════════════════════════════════════════════════════════════════════
# TAB 4 — 🗄️ Database Explorer
# ══════════════════════════════════════════════════════════════════════════

with explorer_tab:
    st.subheader("🗄️ Database Explorer")

    if stats["reviews"] == 0:
        st.info("📭 Database is empty. Go to the **📥 Seed Data** tab to load data.")
    else:
        # Stats cards
        sc1, sc2, sc3 = st.columns(3)
        sc1.markdown(
            f'<div class="stat-box"><div class="stat-icon">🧴</div><div class="stat-num">{stats["products"]:,}</div>'
            f'<div class="stat-lbl">Products stored</div></div>',
            unsafe_allow_html=True,
        )
        sc2.markdown(
            f'<div class="stat-box"><div class="stat-icon">💬</div><div class="stat-num">{stats["reviews"]:,}</div>'
            f'<div class="stat-lbl">Reviews stored</div></div>',
            unsafe_allow_html=True,
        )
        sc3.markdown(
            f'<div class="stat-box"><div class="stat-icon">🏷️</div><div class="stat-num">{stats["brands"]:,}</div>'
            f'<div class="stat-lbl">Brands</div></div>',
            unsafe_allow_html=True,
        )

        st.markdown("---")
        st.markdown("### Browse products")

        fe1, fe2 = st.columns(2)
        with fe1:
            brands = ["All brands"] + get_distinct_brands()
            brand_sel = st.selectbox("Filter by brand", brands)
        with fe2:
            cats = ["All categories"] + get_distinct_categories()
            cat_sel = st.selectbox("Filter by category", cats)

        page_size = st.slider("Rows per page", 10, 100, 25, step=5)
        only_reviewed = st.checkbox("Show only products with reviews", value=True)
        page_num  = st.number_input("Page", min_value=1, value=1, step=1)
        offset    = (page_num - 1) * page_size

        products = get_all_products(
            limit=page_size,
            offset=offset,
            brand_filter=None if brand_sel == "All brands" else brand_sel,
            category_filter=None if cat_sel == "All categories" else cat_sel,
            only_with_reviews=only_reviewed,
        )

        if products:
            prod_df = pd.DataFrame(products)
            prod_df = prod_df.rename(columns={
                "product_id": "ID", "product_name": "Product",
                "brand_name": "Brand", "category": "Category",
                "price_usd": "Price ($)", "avg_rating": "Avg Rating",
                "stored_reviews": "Reviews in DB", "source": "Source",
            })
            st.dataframe(prod_df, width="stretch", hide_index=True)
        else:
            st.info("No products found with the selected filters.")

# ══════════════════════════════════════════════════════════════════════════
# TAB 5 — 📥 Seed Data  (NEW)
# ══════════════════════════════════════════════════════════════════════════
with seed_tab:
    st.subheader("📥 Seed Data into Database")
    st.write(
        "Load beauty product data and reviews into the local SQLite database. "
        "After seeding, use **Product Lookup** to search and analyse products."
    )

    seed_source = st.radio(
        "Data source",
        ["Sephora CSVs (local files — no login needed)",
         "Amazon Beauty Reviews — HuggingFace (requires HF login)",
         "Ulta Skincare Reviews.csv (local file)"],
        horizontal=True,
    )

    row_limit = st.slider(
        "Max review rows to import",
        min_value=500,
        max_value=50_000,
        value=5_000,
        step=500,
        help="Larger values take more time. Start with 5,000 to test.",
    )

    st.caption(f"Current DB: {stats['products']:,} products · {stats['reviews']:,} reviews")

    if st.button("🚀 Start seeding", type="primary"):
        progress_bar  = st.progress(0.0)
        status_text   = st.empty()

        def ui_progress(msg: str, frac):
            status_text.write(msg)
            if frac is not None:
                progress_bar.progress(min(float(frac), 1.0))

        if "Sephora" in seed_source:
            from seed_data import seed_sephora
            with st.spinner("Seeding from Sephora CSV files …"):
                result = seed_sephora(row_limit=row_limit, progress_cb=ui_progress)
            st.success(
                f"✅ Done! Inserted {result['products_inserted']:,} products "
                f"and {result['reviews_inserted']:,} reviews from Sephora."
            )
        elif "Ulta" in seed_source:
            from seed_data import seed_ulta
            with st.spinner("Importing Ulta skincare reviews …"):
                result = seed_ulta(row_limit=row_limit, progress_cb=ui_progress)
            if "error" in result:
                st.error(f"❌ {result['error']}")
            else:
                st.success(
                    f"✅ Done! Inserted {result['products_inserted']:,} Ulta products "
                    f"and {result['reviews_inserted']:,} Ulta reviews."
                )
        else:
            from seed_data import seed_huggingface
            st.info(
                "Make sure you have run `huggingface-cli login` in your terminal before seeding. "
                "Or set the `HF_TOKEN` environment variable."
            )
            with st.spinner("Streaming from HuggingFace (this may take a minute) …"):
                result = seed_huggingface(row_limit=row_limit, progress_cb=ui_progress)
            if "error" in result:
                st.error(f"❌ {result['error']}")
            else:
                st.success(
                    f"✅ Done! Inserted {result['reviews_inserted']:,} Amazon beauty reviews from HuggingFace."
                )

        # Refresh stats
        stats = get_db_stats()
        st.rerun()

# ══════════════════════════════════════════════════════════════════════════
# TAB 6 — Portfolio story  (redesigned)
# ══════════════════════════════════════════════════════════════════════════
with about_tab:
    # ── GlowSense Assistant Chatbot ────────────────────────────────────────────
    render_glowsense_chatbot()

    st.markdown("---")
    st.markdown(
        """
        <div class="section-title">
            <span class="icon-circle">💎</span>
            Portfolio Story
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Problem / Solution / Users — timeline
    st.markdown(
        """
        <div class="timeline-item">
            <strong>🎯 Problem</strong><br/>
            Beauty and skincare reviews are long, emotional, and hard to compare quickly.
        </div>
        <div class="timeline-item">
            <strong>💡 Solution</strong><br/>
            GlowSense summarizes review text into simple signals: sentiment, concern words,
            topics, skin-type clues, and product ranking.
        </div>
        <div class="timeline-item">
            <strong>👥 Target Users</strong><br/>
            Skincare shoppers, beauty creators, small e-commerce sellers, and data science portfolio reviewers.
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Data Science Concepts — feature grid
    st.markdown("### 🧠 Data Science Concepts Used")
    st.markdown(
        """
        <div class="feature-grid">
            <div class="feature-card">
                <div class="feature-card-icon">📝</div>
                <div class="feature-card-title">Text Cleaning</div>
                <div class="feature-card-desc">Tokenization & preprocessing</div>
            </div>
            <div class="feature-card">
                <div class="feature-card-icon">💬</div>
                <div class="feature-card-title">Sentiment Scoring</div>
                <div class="feature-card-desc">Keyword-based classification</div>
            </div>
            <div class="feature-card">
                <div class="feature-card-icon">🏷️</div>
                <div class="feature-card-title">Topic Extraction</div>
                <div class="feature-card-desc">Dictionary-driven topics</div>
            </div>
            <div class="feature-card">
                <div class="feature-card-icon">📊</div>
                <div class="feature-card-title">Aggregation</div>
                <div class="feature-card-desc">Product-level metrics</div>
            </div>
            <div class="feature-card">
                <div class="feature-card-icon">🏆</div>
                <div class="feature-card-title">Ranking Score</div>
                <div class="feature-card-desc">Glow score algorithm</div>
            </div>
            <div class="feature-card">
                <div class="feature-card-icon">🗄️</div>
                <div class="feature-card-title">SQLite Database</div>
                <div class="feature-card-desc">Persistent multi-source storage</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # Data sources and monetization in columns
    ds_col, money_col = st.columns(2)
    with ds_col:
        st.markdown("### 📦 Data Sources")
        st.markdown(
            """
            <div class="timeline-item">
                <strong>Sephora</strong> — Products & Reviews (local CSV, Kaggle)
            </div>
            <div class="timeline-item">
                <strong>Amazon Beauty</strong> — HuggingFace dataset
            </div>
            """,
            unsafe_allow_html=True,
        )
    with money_col:
        st.markdown("### 💰 Monetization Path")
        st.markdown(
            """
            <div class="timeline-item">Free demo website & portfolio showcase</div>
            <div class="timeline-item">Affiliate links on product pages</div>
            <div class="timeline-item">Product comparison reports</div>
            <div class="timeline-item">Newsletter / skincare shopping guide</div>
            <div class="timeline-item">Premium CSV analysis for sellers</div>
            """,
            unsafe_allow_html=True,
        )

# ── Footer ─────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    """
    <div class="app-footer">
        <span class="footer-brand">✨ GlowSense</span> v2.0 · Portfolio MVP by Shahida Batool<br/>
        <span style="font-size:.7rem; opacity:.6;">Built with Streamlit · Powered by data science 💜</span>
    </div>
    """,
    unsafe_allow_html=True,
)
