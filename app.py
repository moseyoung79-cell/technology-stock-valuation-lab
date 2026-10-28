
import streamlit as st
import pandas as pd

from valuation_lab.sec_data import get_tickers, get_facts, extract_all
from valuation_lab.metrics import summarize, quality_checks
from valuation_lab.dcf import scenarios


# --------------------------------------------------
# Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="Technology Stock Valuation Lab",
    page_icon="📊",
    layout="wide",
)

st.title("Technology Stock Valuation Lab")
st.caption(
    "v1.3 · Automatic DCF scenarios · SEC-sourced data · Not investment advice"
)

st.warning(
    "VALIDATION NOTICE: SEC-sourced data is not automatically verified. "
    "Verify financial facts against official filings. DCF results depend "
    "on the quality of the FCF input and your assumptions."
)


# --------------------------------------------------
# Sidebar inputs
# --------------------------------------------------

with st.sidebar:
    st.header("Company")

    ticker = st.text_input("US ticker", "NVDA").strip().upper()

    price = st.number_input(
        "Current share price (USD; manually verify)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        format="%.2f",
    )

    st.caption("No live quote API is configured.")

    st.header("Balance-sheet inputs")

    cash_b = st.number_input(
        "Cash ($ billions; manually verify)",
        min_value=0.0,
        value=0.0,
        step=0.5,
        format="%.3f",
    )

    debt_b = st.number_input(
        "Debt ($ billions; manually verify)",
        min_value=0.0,
        value=0.0,
        step=0.5,
        format="%.3f",
    )

    shares_b = st.number_input(
        "Shares outstanding (billions; manually verify)",
        min_value=0.0,
        value=0.0,
        step=0.1,
        format="%.3f",
    )

    st.header("FCF input")

    manual_fcf_b = st.number_input(
        "Manual annual FCF proxy ($ billions)",
        min_value=0.0,
        value=0.0,
        step=1.0,
        format="%.3f",
        help=(
            "Optional fallback when the SEC-derived annual FCF proxy "
            "is unavailable. Enter a verified annual value, not quarterly FCF."
        ),
    )

    st.caption(
        "If manual FCF is greater than zero, it overrides the SEC-derived "
        "FCF proxy. Enter values in USD billions."
    )

    st.header("DCF assumptions")

    st.caption("Bear scenario")

    bg = st.number_input(
        "Bear FCF growth",
        value=0.05,
        step=0.01,
        format="%.3f",
    )

    bw = st.number_input(
        "Bear WACC",
        value=0.12,
        step=0.01,
        format="%.3f",
    )

    st.caption("Base scenario")

    mg = st.number_input(
        "Base FCF growth",
        value=0.12,
        step=0.01,
        format="%.3f",
    )

    mw = st.number_input(
        "Base WACC",
        value=0.10,
        step=0.01,
        format="%.3f",
    )

    st.caption("Bull scenario")

    ug = st.number_input(
        "Bull FCF growth",
        value=0.20,
        step=0.01,
        format="%.3f",
    )

    uw = st.number_input(
        "Bull WACC",
        value=0.09,
        step=0.01,
        format="%.3f",
    )

    tg = st.number_input(
        "Terminal growth",
        value=0.03,
        step=0.005,
        format="%.3f",
    )

    fetch_clicked = st.button(
        "Fetch SEC data & analyze",
        type="primary",
        use_container_width=True,
    )


# --------------------------------------------------
# Retrieve SEC data when requested
# --------------------------------------------------

if fetch_clicked:
    try:
        with st.spinner("Retrieving SEC ticker list and Company Facts..."):
            tickers = get_tickers()

            if ticker not in tickers:
                st.error(f"{ticker} was not found in the SEC ticker list.")
                st.stop()

            issuer = tickers[ticker]
            facts, url = get_facts(issuer["cik"])
            metrics = extract_all(facts)
            summary = summarize(metrics)
            checks = quality_checks(metrics, summary)

            st.session_state["result"] = {
                "ticker": ticker,
                "issuer": issuer,
                "url": url,
                "metrics": {
                    name: frame.to_dict("records")
                    for name, frame in metrics.items()
                },
                "summary": summary,
                "checks": checks.to_dict("records"),
            }

    except Exception as exc:
        st.error(f"SEC retrieval or analysis failed: {exc}")
        st.info(
            "Check Streamlit Secrets for SEC_USER_AGENT and verify that "
            "the ticker and SEC data are accessible."
        )


# --------------------------------------------------
# Display results
# --------------------------------------------------

if "result" not in st.session_state:
    st.info(
        "Enter the ticker and assumptions in the sidebar, then click "
        "'Fetch SEC data & analyze' once. After data is loaded, changing "
        "the assumptions automatically recalculates the DCF."
    )
    st.stop()

result_data = st.session_state["result"]

# If the ticker changes after a previous fetch, require fresh SEC data.
if ticker != result_data["ticker"]:
    st.warning(
        f"Loaded data is for {result_data['ticker']}, but the sidebar "
        f"now contains {ticker}. Click 'Fetch SEC data & analyze' to load "
        "the new company before using its valuation."
    )
    st.stop()

ticker_result = result_data["ticker"]
issuer = result_data["issuer"]
summary = result_data["summary"]

metrics = {
    name: pd.DataFrame(records)
    for name, records in result_data["metrics"].items()
}

st.subheader(f'{issuer["name"]} ({ticker_result})')

st.write(
    f'CIK: {issuer["cik"]} · SEC Company Facts: {result_data["url"]}'
)

st.info(
    "SEC-sourced data still requires filing-level verification. "
    "Review the reporting period, units and official filing before "
    "relying on the values."
)


# --------------------------------------------------
# Key financial metrics
# --------------------------------------------------

def format_percentage(item):
    value = item.get("value")

    if value is None:
        return "N/A"

    try:
        if pd.isna(value):
            return "N/A"
        return f"{value:.1%}"
    except (TypeError, ValueError):
        return "N/A"


fcf_proxy = summary.get("fcf_proxy", {}).get("value")

if fcf_proxy is not None:
    try:
        if pd.isna(fcf_proxy):
            fcf_proxy = None
    except (TypeError, ValueError):
        fcf_proxy = None

columns = st.columns(4)

columns[0].metric(
    "ROS · Net profit margin",
    format_percentage(summary.get("ros", {})),
)

columns[1].metric(
    "Operating margin",
    format_percentage(summary.get("operating_margin", {})),
)

columns[2].metric(
    "ROE",
    format_percentage(summary.get("roe", {})),
)

columns[3].metric(
    "SEC-derived FCF proxy",
    f"${fcf_proxy / 1e9:,.2f}B" if fcf_proxy is not None else "N/A",
)

st.caption(
    "FCF proxy = operating cash flow minus absolute capital expenditure. "
    "It is a simplified measure, not normalized FCFF."
)


# --------------------------------------------------
# Data quality checklist
# --------------------------------------------------

st.subheader("Data-quality and validation checklist")

checks_df = pd.DataFrame(result_data["checks"])

if checks_df.empty:
    st.info("No validation checks were returned.")
else:
    st.dataframe(
        checks_df,
        use_container_width=True,
        hide_index=True,
    )


# --------------------------------------------------
# Automatic DCF calculation
# --------------------------------------------------

st.subheader("DCF valuation")

# Manual FCF is expressed in USD billions; internal model uses USD.
if manual_fcf_b > 0:
    fcf = manual_fcf_b * 1e9
    fcf_source = "Manual annual FCF proxy"
else:
    fcf = fcf_proxy
    fcf_source = "SEC-derived annual FCF proxy"

st.write(f"**FCF input source:** {fcf_source}")

if fcf is None:
    st.warning(
        "DCF cannot calculate because the SEC-derived annual FCF proxy "
        "is unavailable. Enter a manually verified annual FCF proxy in "
        "the sidebar. Do not use quarterly FCF as a full-year value."
    )

elif fcf <= 0:
    st.warning(
        "DCF cannot calculate because the starting FCF must be positive."
    )

elif shares_b <= 0:
    st.warning(
        "Enter manually verified shares outstanding in billions. "
        "Confirm whether the figure is diluted shares and note its date."
    )

elif cash_b <= 0 or debt_b <= 0:
    st.warning(
        "Enter verified cash and debt values in USD billions. "
        "Use a consistent reporting date. A zero input is treated as "
        "missing in this prototype."
    )

elif price <= 0:
    st.warning(
        "Enter a manually verified current share price in USD to calculate "
        "margin of safety and price comparison."
    )

elif tg < 0:
    st.warning("Terminal growth cannot be negative in this prototype.")

elif any(wacc <= tg for wacc in (bw, mw, uw)):
    st.warning(
        "Each scenario's WACC must be greater than terminal growth."
    )

elif any(growth <= -1 for growth in (bg, mg, ug)):
    st.warning("FCF growth must be greater than -100%.")

else:
    try:
        dcf_result = scenarios(
            fcf,
            shares_b * 1e9,
            cash_b * 1e9,
            debt_b * 1e9,
            price,
            {
                "Bear": bg,
                "Base": mg,
                "Bull": ug,
            },
            {
                "Bear": bw,
                "Base": mw,
                "Bull": uw,
            },
            tg,
        )

        if "error" in dcf_result:
            st.warning(dcf_result["error"])

        else:
            # Summary cards
            st.markdown("### Intrinsic value per share")

            scenario_order = ["Bear", "Base", "Bull"]
            cards = st.columns(3)

            for card, scenario_name in zip(cards, scenario_order):
                data = dcf_result[scenario_name]
                intrinsic = data["intrinsic_per_share"]
                mos = data["margin_of_safety"]

                card.metric(
                    f"{scenario_name} case",
                    f"${intrinsic:,.2f}",
                    (
                        f"Margin of safety: {mos:.1%}"
                        if mos is not None
                        else "Margin of safety unavailable"
                    ),
                )

            base_value = dcf_result["Base"]["intrinsic_per_share"]
            price_difference = price - base_value
            upside = (base_value / price - 1) if price > 0 else None

            st.markdown("### Base-case interpretation")

            summary_cols = st.columns(3)

            summary_cols[0].metric(
                "Current share price",
                f"${price:,.2f}",
            )

            summary_cols[1].metric(
                "Base-case intrinsic value",
                f"${base_value:,.2f}",
            )

            summary_cols[2].metric(
                "Implied upside / downside",
                f"{upside:.1%}" if upside is not None else "N/A",
            )

            if base_value > price:
                st.success(
                    "The base-case estimated value is above the current price. "
                    "This is a model result, not a buy recommendation."
                )
            else:
                st.warning(
                    "The base-case estimated value is at or below the current "
                    "price. This is a model result, not a sell recommendation."
                )

            st.markdown("### Scenario details")

            rows = []

            for scenario_name in scenario_order:
                data = dcf_result[scenario_name]
                rows.append({
                    "Scenario": scenario_name,
                    "FCF growth": data["growth"],
                    "WACC": data["wacc"],
                    "Terminal growth": data["terminal_growth"],
                    "Enterprise value ($B)": data["enterprise_value"] / 1e9,
                    "Equity value ($B)": data["equity_value"] / 1e9,
                    "Intrinsic value / share ($)": data["intrinsic_per_share"],
                    "Current price ($)": price,
                    "Margin of safety": data["margin_of_safety"],
                    "PV forecast ($B)": data["pv_forecast"] / 1e9,
                    "PV terminal value ($B)": data["pv_terminal"] / 1e9,
                })

            dcf_df = pd.DataFrame(rows)

            st.dataframe(
                dcf_df.style.format({
                    "FCF growth": "{:.1%}",
                    "WACC": "{:.1%}",
                    "Terminal growth": "{:.1%}",
                    "Enterprise value ($B)": "${:,.2f}",
                    "Equity value ($B)": "${:,.2f}",
                    "Intrinsic value / share ($)": "${:,.2f}",
                    "Current price ($)": "${:,.2f}",
                    "Margin of safety": "{:.1%}",
                    "PV forecast ($B)": "${:,.2f}",
                    "PV terminal value ($B)": "${:,.2f}",
                }),
                use_container_width=True,
                hide_index=True,
            )

            st.caption(
                "The model updates automatically when sidebar inputs change. "
                "The DCF is illustrative and uses a simplified FCF proxy. "
                "Growth rates, WACC, terminal growth, cash, debt, shares and "
                "price all require independent verification."
            )

    except Exception as exc:
        st.error(f"DCF calculation failed: {exc}")


# --------------------------------------------------
# Retrieved annual SEC facts
# --------------------------------------------------

st.subheader("Retrieved annual facts")

if not metrics:
    st.info("No annual metric tables were returned.")
else:
    tabs = st.tabs(list(metrics.keys()))

    for tab, (metric_name, metric_df) in zip(tabs, metrics.items()):
        with tab:
            if metric_df.empty:
                st.warning(
                    "No matching annual fact was found. "
                    "No value has been imputed."
                )
            else:
                if "end" in metric_df.columns:
                    display_df = metric_df.sort_values(
                        "end",
                        ascending=False,
                    )
                else:
                    display_df = metric_df

                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                )


# --------------------------------------------------
# Download SEC facts
# --------------------------------------------------

annual_rows = []

for metric_name, metric_df in metrics.items():
    for _, row in metric_df.iterrows():
        annual_rows.append({
            "metric": metric_name,
            **row.to_dict(),
        })

annual_df = pd.DataFrame(annual_rows)

st.download_button(
    label="Download SEC facts CSV",
    data=annual_df.to_csv(index=False).encode("utf-8"),
    file_name=f"{ticker_result}_sec_facts.csv",
    mime="text/csv",
)

st.divider()

st.caption(
    "Technology Stock Valuation Lab · Educational prototype · "
    "Not investment advice"
)
