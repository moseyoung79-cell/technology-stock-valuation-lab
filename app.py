import streamlit as st
import pandas as pd

from valuation_lab.sec_data import get_tickers, get_facts, extract_all
from valuation_lab.metrics import summarize, quality_checks
from valuation_lab.dcf import scenarios

st.set_page_config(page_title="Technology Stock Valuation Lab", page_icon="📊", layout="wide")
st.title("Technology Stock Valuation Lab")
st.caption("v1.4 · Reverse DCF · Growth/WACC sensitivity · SEC-sourced data · Not investment advice")
st.warning(
    "VALIDATION NOTICE: SEC-sourced data is not automatically verified. Verify financial facts against official filings. "
    "DCF results depend on the quality of the FCF input and your assumptions."
)

with st.sidebar:
    st.header("Company")
    ticker = st.text_input("US ticker", "NVDA").strip().upper()
    price = st.number_input("Current share price (USD; manually verify)", min_value=0.0, value=0.0, step=1.0, format="%.2f")
    st.caption("No live quote API is configured.")

    st.header("Balance-sheet inputs")
    cash_b = st.number_input("Cash and liquid investments ($ billions; manually verify)", min_value=0.0, value=0.0, step=0.5, format="%.3f",
        help="For a more complete equity bridge, you may include cash plus marketable securities. Keep the reporting date consistent with debt and shares.")
    debt_b = st.number_input("Debt ($ billions; manually verify)", min_value=0.0, value=0.0, step=0.5, format="%.3f")
    shares_b = st.number_input("Diluted shares outstanding (billions; manually verify)", min_value=0.0, value=0.0, step=0.1, format="%.3f")

    st.header("FCF input")
    manual_fcf_b = st.number_input("Manual annual FCF proxy ($ billions)", min_value=0.0, value=0.0, step=1.0, format="%.3f",
        help="Optional fallback when the SEC-derived annual FCF proxy is unavailable. Enter a verified annual value, not quarterly FCF.")
    st.caption("If manual FCF is greater than zero, it overrides the SEC-derived FCF proxy. Enter USD billions.")

    st.header("DCF assumptions")
    st.caption("Bear scenario")
    bg = st.number_input("Bear FCF growth", value=0.05, step=0.01, format="%.3f")
    bw = st.number_input("Bear WACC", value=0.12, step=0.01, format="%.3f")
    st.caption("Base scenario")
    mg = st.number_input("Base FCF growth", value=0.12, step=0.01, format="%.3f")
    mw = st.number_input("Base WACC", value=0.10, step=0.01, format="%.3f")
    st.caption("Bull scenario")
    ug = st.number_input("Bull FCF growth", value=0.20, step=0.01, format="%.3f")
    uw = st.number_input("Bull WACC", value=0.09, step=0.01, format="%.3f")
    tg = st.number_input("Terminal growth", value=0.03, step=0.005, format="%.3f")

    st.header("Sensitivity settings")
    sensitivity_wacc_min = st.number_input("Sensitivity WACC minimum", min_value=0.01, max_value=0.50, value=0.08, step=0.01, format="%.3f")
    sensitivity_wacc_max = st.number_input("Sensitivity WACC maximum", min_value=0.02, max_value=0.60, value=0.14, step=0.01, format="%.3f")
    sensitivity_growth_min = st.number_input("Sensitivity FCF growth minimum", min_value=-0.50, max_value=1.00, value=0.05, step=0.05, format="%.3f")
    sensitivity_growth_max = st.number_input("Sensitivity FCF growth maximum", min_value=-0.50, max_value=2.00, value=0.30, step=0.05, format="%.3f")
    fetch_clicked = st.button("Fetch SEC data & analyze", type="primary", use_container_width=True)

if fetch_clicked:
    try:
        with st.spinner("Retrieving SEC ticker list and Company Facts..."):
            ticker_map = get_tickers()
            if ticker not in ticker_map:
                st.error(f"{ticker} was not found in the SEC ticker list.")
                st.stop()
            issuer = ticker_map[ticker]
            facts, url = get_facts(issuer["cik"])
            metrics = extract_all(facts)
            summary = summarize(metrics)
            checks = quality_checks(metrics, summary)
            st.session_state["result"] = {
                "ticker": ticker,
                "issuer": issuer,
                "url": url,
                "metrics": {name: frame.to_dict("records") for name, frame in metrics.items()},
                "summary": summary,
                "checks": checks.to_dict("records"),
            }
    except Exception as exc:
        st.error(f"SEC retrieval or analysis failed: {exc}")
        st.info("Check Streamlit Secrets for SEC_USER_AGENT and verify that the ticker and SEC data are accessible.")

if "result" not in st.session_state:
    st.info("Enter the ticker and assumptions in the sidebar, then click 'Fetch SEC data & analyze' once. After data is loaded, changing assumptions recalculates the valuation automatically.")
    st.stop()

result_data = st.session_state["result"]
if ticker != result_data["ticker"]:
    st.warning(f"Loaded data is for {result_data['ticker']}, but the sidebar now contains {ticker}. Click 'Fetch SEC data & analyze' to load the new company.")
    st.stop()

issuer = result_data["issuer"]
summary = result_data["summary"]
metrics = {name: pd.DataFrame(records) for name, records in result_data["metrics"].items()}
st.subheader(f'{issuer["name"]} ({result_data["ticker"]})')
st.write(f'CIK: {issuer["cik"]} · SEC Company Facts: {result_data["url"]}')
st.info("SEC-sourced data still requires filing-level verification. Review reporting period, units and official filings before relying on values.")

def format_percentage(item):
    value = item.get("value")
    if value is None:
        return "N/A"
    try:
