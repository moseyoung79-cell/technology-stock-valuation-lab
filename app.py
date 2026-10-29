
import streamlit as st
import pandas as pd

from valuation_lab.sec_data import get_tickers, get_facts, extract_all
from valuation_lab.metrics import summarize, quality_checks
from valuation_lab.dcf import scenarios


# ============================================================
# Page configuration
# ============================================================

st.set_page_config(
    page_title="Technology Stock Valuation Lab",
    page_icon="📊",
    layout="wide",
)

st.title("Technology Stock Valuation Lab")
st.caption(
    "v1.5 · Reverse DCF · Growth/WACC sensitivity · "
    "SEC-sourced data · Not investment advice"
)

st.warning(
    "VALIDATION NOTICE: SEC data and valuation assumptions require "
    "independent verification against official company filings. "
    "This tool is an educational prototype, not investment advice."
)


# ============================================================
# Helpers
# ============================================================

def format_percentage(item):
    value = item.get("value")

    if value is None:
        return "N/A"

    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "N/A"


def safe_number(value):
    """Return a numeric value or None; never
