
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
    "v1.2 · Validation-first prototype · SEC-sourced data · Not investment advice"
)

st.warning(
    "VALIDATION NOTICE: SEC-sourced does not automatically mean verified. "
    "Review each fact in its source 10-K before relying on it. "
    "Derived metrics and DCF scenarios are not verified facts."
)


# --------------------------------------------------
# Sidebar inputs
# --------------------------------------------------

with st.sidebar:
    st.header("Company")

    ticker = st.text_input("US ticker", "NVDA").strip().upper()

    price = st.number_input(
        "Current share price (USD; manually verified)",
        min_value=0.0,
        value=0.0,
        step=1.0,
    )

    st.caption("No live quote API is configured.")

    st.header("Optional balance-sheet overrides")

    cash_b = st.number_input(
        "Cash ($ billions; manually verify)",
        min_value=0.0,
        value=0.0,
        step=1.0,
    )

    debt_b = st.number_input(
        "Debt ($ billions; manually verify)",
        min_value=0.0,
        value=0.0,
        step=1.0,
    )

    shares_b = st.number_input(
        "Shares outstanding (billions; manually verify)",
        min_value=0.0,
        value=0.0,
        step=0.1,
    )

    st.header("Illustrative assumptions")

    bg = st.number_input(
        "Bear FCF growth",
        value=0.05,
        step=0.01,
        format="%.2f",
    )

    bw = st.number_input(
        "Bear WACC",
        value=0.12,
        step=0.01,
        format="%.2f",
    )

    mg = st.number_input(
        "Base FCF growth",
        value=0.12,
        step=0.01,
        format="%.2f",
    )

    mw = st.number_input(
        "Base WACC",
        value=0.10,
        step=0.01,
        format="%.2f",
    )

    ug = st.number_input(
        "Bull FCF growth",
        value=0.20,
        step=0.01,
        format="%.2f",
    )

    uw = st.number_input(
        "Bull WACC",
        value=0.09,
        step=0.01,
        format="%.2f",
    )

    tg = st.number_input(
        "Terminal growth",
        value=0.03,
        step=0.005,
        format="%.3f",
    )


# --------------------------------------------------
# Retrieve and analyze SEC data
# --------------------------------------------------

if st.button("Fetch SEC data & analyze", type="primary"):
    try:
        with st.spinner("Retrieving SEC ticker list and Company Facts..."):
            tickers = get_tickers()

            if ticker not in tickers:
                st.error(
                    f"{ticker} was not found in the SEC ticker list."
                )
                st.stop()

            issuer = tickers[ticker]
            facts, url = get_facts(issuer["cik"])
            metrics = extract_all(facts)
            summary = summarize(metrics)
            checks = quality_checks(metrics, summary)

            # Save plain records in session state so the results
            # remain available after Streamlit reruns the script.
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
            "For Streamlit Cloud, check App settings > Secrets and "
            "configure SEC_USER_AGENT with a descriptive app name "
            "and a real contact email. Some issuers may use unsupported tags."
        )


# --------------------------------------------------
# Display results only when analysis has completed
# --------------------------------------------------

if "result" in st.session_state:
    result_data = st.session_state["result"]

    ticker_result = result_data["ticker"]
    issuer = result_data["issuer"]
    summary = result_data["summary"]

    # Reconstruct DataFrames from saved records.
    metrics = {
        name: pd.DataFrame(records)
        for name, records in result_data["metrics"].items()
    }

    st.subheader(f'{issuer["name"]} ({ticker_result})')

    st.write(
        f'CIK: {issuer["cik"]} · '
        f'SEC Company Facts: {result_data["url"]}'
    )

    st.info(
        "Source status: SEC-sourced; filing-level verification is still "
        "required. Review the source URL, reporting period, and official "
        "filing before relying on any value."
    )

    # --------------------------------------------------
    # Key metrics
    # --------------------------------------------------

    def format_percentage(item):
        value = item.get("value")

        if value is None:
            return "N/A"

        try:
            if pd.isna(value):
                return "N/A"
        except (TypeError, ValueError):
            pass

        return f"{value:.1%}"

    columns = st.columns(4)

    columns[0].metric(
        "ROS · Net profit margin",
        format_percentage(summary["ros"]),
    )

    columns[1].metric(
        "Operating margin",
        format_percentage(summary["operating_margin"]),
    )

    columns[2].metric(
        "ROE",
        format_percentage(summary["roe"]),
    )

    fcf_proxy = summary["fcf_proxy"].get("value")

    if fcf_proxy is None:
        fcf_display = "N/A"
    else:
        fcf_display = f"${fcf_proxy / 1e9:,.2f}"

    columns[3].metric(
        "FCF proxy (annual, USD B)",
        fcf_display,
    )

    st.caption(
        "Ratios are derived only when their periods align. "
        "FCF proxy = operating cash flow minus absolute capital expenditure. "
        "It is not normalized free cash flow to the firm (FCFF)."
    )

    # --------------------------------------------------
    # Data-quality checklist
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
    # Annual SEC facts
    # --------------------------------------------------

    st.subheader("Retrieved annual facts")

    if not metrics:
        st.info("No annual metric tables were returned.")
    else:
        tabs = st.tabs(list(metrics.keys()))

        for tab, (metric_name, metric_df) in zip(
            tabs,
            metrics.items(),
        ):
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
    # Illustrative DCF
    # --------------------------------------------------

    st.subheader("Illustrative DCF scenarios")

    shares = shares_b * 1e9 if shares_b > 0 else None
    cash = cash_b * 1e9 if cash_b > 0 else None
    debt = debt_b * 1e9 if debt_b > 0 else None
    fcf = summary["fcf_proxy"].get("value")

    if shares is None:
        st.warning(
            "DCF blocked: enter manually verified shares outstanding "
            "in billions. Confirm the date and diluted-share basis."
        )

    elif cash is None or debt is None:
        st.warning(
            "DCF blocked: enter manually verified cash and debt "
            "in USD billions, reconciled to the same filing."
        )

    elif fcf is None:
        st.warning(
            "DCF blocked: the annual FCF proxy is unavailable."
        )

    elif price <= 0:
        st.warning(
            "DCF blocked: enter a manually verified current share price."
        )

    elif tg < 0:
        st.warning(
            "DCF blocked: terminal growth cannot be negative in this prototype."
        )

    elif any(wacc <= tg for wacc in (bw, mw, uw)):
        st.warning(
            "DCF blocked: each scenario's WACC must be greater than "
            "terminal growth."
        )

    else:
        try:
            dcf_result = scenarios(
                fcf,
                shares,
                cash,
                debt,
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

            if isinstance(dcf_result, dict) and "error" in dcf_result:
                st.warning(
                    f"DCF blocked: {dcf_result['error']}"
                )

            elif isinstance(dcf_result, dict) and dcf_result:
                dcf_rows = [
                    {
                        "Scenario": scenario_name,
                        **scenario_values,
                    }
                    for scenario_name, scenario_values
                    in dcf_result.items()
                    if isinstance(scenario_values, dict)
                ]

                if dcf_rows:
                    dcf_df = pd.DataFrame(dcf_rows)

                    st.dataframe(
                        dcf_df,
                        use_container_width=True,
                        hide_index=True,
                    )

                    st.warning(
                        "DCF is illustrative and uses a simplified FCF proxy. "
                        "Verify all inputs and assumptions before relying "
                        "on the results."
                    )
                else:
                    st.error(
                        "The DCF returned no usable scenario rows. "
                        "Review valuation_lab/dcf.py."
                    )

            else:
                st.error(
                    "Unexpected DCF result format. "
                    "Review valuation_lab/dcf.py."
                )

        except Exception as exc:
            st.error(f"DCF calculation failed: {exc}")

    # --------------------------------------------------
    # Download SEC facts
    # --------------------------------------------------

    annual_rows = []

    for metric_name, metric_df in metrics.items():
        for _, row in metric_df.iterrows():
            annual_rows.append(
                {
                    "metric": metric_name,
                    **row.to_dict(),
                }
            )

    annual_df = pd.DataFrame(annual_rows)

    st.download_button(
        label="Download SEC facts CSV",
        data=annual_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{ticker_result}_sec_facts.csv",
        mime="text/csv",
    )


# --------------------------------------------------
# Footer
# --------------------------------------------------

st.divider()

st.caption(
    "Next milestones: independently reconcile NVDA facts to official filings, "
    "add filing-specific validation records, then configure live price data "
    "and quarterly checks."
)
