
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
    "v1.5 | SEC Financial Data | DCF | Reverse DCF | "
    "Growth/WACC Sensitivity | Educational Prototype"
)

st.warning(
    "SEC data and model assumptions require independent verification. "
    "This tool is for educational purposes and is not investment advice."
)


# ============================================================
# Session state initialization
# ============================================================

DEFAULTS = {
    "ticker_input": "NVDA",
    "price_input": 0.0,
    "cash_input": 0.0,
    "debt_input": 0.0,
    "shares_input": 0.0,
    "fcf_input": 0.0,
    "result": None,
    "fetch_error": None,
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# Utility functions
# ============================================================

def number_or_none(value):
    """Return a float or None; never convert missing data into zero."""
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def billions(value):
    """Convert a raw USD or share count to billions."""
    value = number_or_none(value)
    if value is None:
        return None
    return value / 1e9


def summary_value(summary, key):
    """Safely read a value from the financial summary."""
    item = summary.get(key, {})
    if not isinstance(item, dict):
        return None
    return number_or_none(item.get("value"))


def format_percentage(item):
    value = number_or_none(item.get("value"))
    return f"{value:.1%}" if value is not None else "N/A"


def format_billions(value):
    value = number_or_none(value)
    return f"${value:,.3f}B" if value is not None else "N/A"


def record_to_dataframe(records):
    if not records:
        return pd.DataFrame()
    return pd.DataFrame(records)


# ============================================================
# SEC retrieval callback
# ============================================================

def fetch_company_data():
    """
    Fetch SEC facts for the selected ticker.

    This callback runs before Streamlit recreates the widgets, allowing
    successful SEC values to populate the input widgets safely.
    """
    ticker = str(
        st.session_state.get("ticker_input", "")
    ).strip().upper()

    st.session_state["fetch_error"] = None

    if not ticker:
        st.session_state["fetch_error"] = "Enter a stock ticker."
        return

    previous_result = st.session_state.get("result")
    previous_ticker = (
        previous_result.get("ticker")
        if isinstance(previous_result, dict)
        else None
    )

    try:
        ticker_map = get_tickers()

        if ticker not in ticker_map:
            st.session_state["fetch_error"] = (
                f"{ticker} was not found in the SEC ticker list."
            )
            return

        issuer = ticker_map[ticker]
        facts, url = get_facts(issuer["cik"])
        metrics = extract_all(facts)
        summary = summarize(metrics)
        checks = quality_checks(metrics, summary)

        # Store serializable data in session state.
        st.session_state["result"] = {
            "ticker": ticker,
            "issuer": issuer,
            "url": url,
            "metrics": {
                name: frame.to_dict("records")
                for name, frame in metrics.items()
            },
            "summary": summary,
            "checks": checks,
        }

        # When switching companies, clear the previous company's
        # manual price and all old company-specific financial inputs.
        if previous_ticker != ticker:
            st.session_state["price_input"] = 0.0
            st.session_state["cash_input"] = 0.0
            st.session_state["debt_input"] = 0.0
            st.session_state["shares_input"] = 0.0
            st.session_state["fcf_input"] = 0.0

        # Auto-fill cash when available.
        cash_value = billions(
            summary_value(summary, "cash_value")
        )
        if cash_value is not None and cash_value >= 0:
            st.session_state["cash_input"] = cash_value

        # Auto-fill debt only when the metrics module calculated
        # a reliable total. Missing debt remains unavailable.
        debt_value = billions(
            summary_value(summary, "debt_value")
        )
        if debt_value is not None and debt_value >= 0:
            st.session_state["debt_input"] = debt_value

        # Shares are point-in-time shares outstanding, not necessarily
        # diluted weighted-average shares. The app labels this explicitly.
        shares_value = billions(
            summary_value(summary, "shares_value")
        )
        if shares_value is not None and shares_value > 0:
            st.session_state["shares_input"] = shares_value

        # FCF proxy is reported in raw USD by the metrics module.
        fcf_value = billions(
            summary_value(summary, "fcf_proxy")
        )
        if fcf_value is not None and fcf_value > 0:
            st.session_state["fcf_input"] = fcf_value

    except Exception as exc:
        st.session_state["fetch_error"] = (
            f"SEC retrieval or analysis failed: {exc}"
        )


# ============================================================
# Sidebar inputs
# ============================================================

with st.sidebar:
    st.header("Company")

    st.text_input(
        "US ticker",
        key="ticker_input",
        help="Examples: NVDA, GOOGL, MSFT, AMZN, TSM.",
    )

    st.button(
        "Fetch SEC data & analyze",
        type="primary",
        use_container_width=True,
        on_click=fetch_company_data,
    )

    st.caption(
        "Click the button after changing the ticker. "
        "SEC does not provide a live stock quote here."
    )

    st.divider()
    st.header("Valuation inputs")

    st.number_input(
        "Current share price (USD; manual)",
        min_value=0.0,
        step=1.0,
        format="%.2f",
        key="price_input",
        help="Enter a verified current market price.",
    )

    st.number_input(
        "Cash and cash equivalents ($ billions)",
        min_value=0.0,
        step=0.5,
        format="%.3f",
        key="cash_input",
        help=(
            "Auto-filled from SEC when available. Verify the filing date. "
            "This field may not include all short-term investments."
        ),
    )

    st.number_input(
        "Total debt ($ billions)",
        min_value=0.0,
        step=0.5,
        format="%.3f",
        key="debt_input",
        help=(
            "Auto-filled only when short-term and long-term debt "
            "are both available for the same reporting date."
        ),
    )

    st.number_input(
        "Shares outstanding (billions)",
        min_value=0.0,
        step=0.1,
        format="%.3f",
        key="shares_input",
        help=(
            "SEC point-in-time shares outstanding, not necessarily "
            "diluted weighted-average shares. Verify before valuation."
        ),
    )

    st.number_input(
        "Annual FCF proxy ($ billions)",
        min_value=0.0,
        step=1.0,
        format="%.3f",
        key="fcf_input",
        help=(
            "Auto-filled from SEC when available. You can manually "
            "override it after verifying annual FCF."
        ),
    )

    st.divider()
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

    st.divider()
    st.header("Sensitivity settings")

    sensitivity_wacc_min = st.number_input(
        "Sensitivity WACC minimum",
        min_value=0.01,
        max_value=0.50,
        value=0.08,
        step=0.01,
        format="%.3f",
    )
    sensitivity_wacc_max = st.number_input(
        "Sensitivity WACC maximum",
        min_value=0.02,
        max_value=0.60,
        value=0.14,
        step=0.01,
        format="%.3f",
    )
    sensitivity_growth_min = st.number_input(
        "Sensitivity FCF growth minimum",
        min_value=-0.50,
        max_value=1.00,
        value=0.05,
        step=0.05,
        format="%.3f",
    )
    sensitivity_growth_max = st.number_input(
        "Sensitivity FCF growth maximum",
        min_value=-0.50,
        max_value=2.00,
        value=0.30,
        step=0.05,
        format="%.3f",
    )


# ============================================================
# Retrieval errors and result state
# ============================================================

if st.session_state.get("fetch_error"):
    st.error(st.session_state["fetch_error"])
    st.info(
        "If SEC retrieval fails, check Streamlit Secrets for "
        "SEC_USER_AGENT and verify that the ticker is supported."
    )

result_data = st.session_state.get("result")

if not isinstance(result_data, dict):
    st.info(
        "Enter a ticker in the sidebar and click "
        "'Fetch SEC data & analyze' to begin."
    )
    st.stop()

ticker = str(
    st.session_state.get("ticker_input", "")
).strip().upper()

if ticker != result_data.get("ticker"):
    st.warning(
        f"The loaded data is for {result_data.get('ticker')}, "
        f"but the selected ticker is {ticker}. "
        "Click 'Fetch SEC data & analyze' to load the new company."
    )
    st.stop()


# ============================================================
# Reconstruct retrieved data
# ============================================================

issuer = result_data["issuer"]
summary = result_data["summary"]

metrics = {
    name: record_to_dataframe(records)
    for name, records in result_data["metrics"].items()
}

st.subheader(
    f"{issuer['name']} ({result_data['ticker']})"
)
st.write(
    f"CIK: {issuer['cik']} | "
    f"SEC Company Facts: {result_data['url']}"
)

st.info(
    "SEC-derived values are starting points. Verify each value, unit, "
    "filing date and share-count definition against official filings."
)


# ============================================================
# Financial metrics
# ============================================================

st.subheader("Financial overview")

fcf_proxy = summary_value(summary, "fcf_proxy")

cols = st.columns(4)
cols[0].metric(
    "ROS / Net profit margin",
    format_percentage(summary.get("ros", {})),
)
cols[1].metric(
    "Operating margin",
    format_percentage(summary.get("operating_margin", {})),
)
cols[2].metric(
    "ROE",
    format_percentage(summary.get("roe", {})),
)
cols[3].metric(
    "SEC-derived FCF proxy",
    format_billions(billions(fcf_proxy)),
)

st.caption(
    "FCF proxy = annual operating cash flow minus absolute capital "
    "expenditure. It is a simplified measure, not normalized FCFF."
)


# ============================================================
# Data quality checks
# ============================================================

st.subheader("Data-quality and validation checklist")

checks = result_data.get("checks", [])
checks_df = pd.DataFrame(checks)

if checks_df.empty:
    st.info("No validation checks were returned.")
else:
    st.dataframe(
        checks_df,
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# Data dates and auto-filled inputs
# ============================================================

st.subheader("Auto-filled SEC inputs")

auto_rows = []

for key, label in (
    ("cash_value", "Cash and cash equivalents"),
    ("short_debt_value", "Short-term debt"),
    ("long_debt_value", "Long-term debt"),
    ("debt_value", "Calculated total debt"),
    ("shares_value", "Shares outstanding"),
    ("fcf_proxy", "Annual FCF proxy"),
):
    item = summary.get(key, {})

    if not isinstance(item, dict):
        item = {}

    value = number_or_none(item.get("value"))

    auto_rows.append({
        "Metric": label,
        "Value (raw SEC units)": value,
        "Period end": item.get("end"),
        "Filed": item.get("filed"),
        "Unit": item.get("unit"),
        "Status": item.get("status"),
    })

st.dataframe(
    pd.DataFrame(auto_rows),
    use_container_width=True,
    hide_index=True,
)

st.caption(
    "Shares outstanding is a point-in-time figure. The DCF model uses "
    "the shares value entered in the sidebar; confirm whether diluted "
    "shares are more appropriate for your valuation."
)


# ============================================================
# DCF valuation
# ============================================================

st.subheader("DCF valuation")

price = float(st.session_state["price_input"])
cash_b = float(st.session_state["cash_input"])
debt_b = float(st.session_state["debt_input"])
shares_b = float(st.session_state["shares_input"])
fcf_b = float(st.session_state["fcf_input"])

fcf = fcf_b * 1e9

st.write("**FCF input source:** Sidebar annual FCF proxy (USD billions)")

if fcf_b <= 0:
    st.warning(
        "Enter a positive, verified annual FCF proxy. "
        "A missing SEC value is not assumed to be zero."
    )
elif shares_b <= 0:
    st.warning(
        "Enter a positive share count and verify the share-count definition."
    )
elif price <= 0:
    st.warning(
        "Enter a manually verified current share price to calculate "
        "price comparison and Reverse DCF."
    )
elif any(w <= tg for w in (bw, mw, uw)):
    st.warning(
        "Each scenario's WACC must be greater than terminal growth."
    )
elif tg < 0:
    st.warning("Terminal growth cannot be negative in this prototype.")
elif any(g <= -1 for g in (bg, mg, ug)):
    st.warning("FCF growth must be greater than -100%.")
elif sensitivity_wacc_max <= sensitivity_wacc_min:
    st.warning(
        "Sensitivity WACC maximum must be greater than its minimum."
    )
elif sensitivity_growth_max <= sensitivity_growth_min:
    st.warning(
        "Sensitivity growth maximum must be greater than its minimum."
    )
else:
    cash = cash_b * 1e9
    debt = debt_b * 1e9
    shares = shares_b * 1e9

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

        if "error" in dcf_result:
            st.warning(dcf_result["error"])
        else:
            order = ["Bear", "Base", "Bull"]

            st.markdown("### Intrinsic value per share")

            cards = st.columns(3)

            for card, name in zip(cards, order):
                data = dcf_result[name]
                intrinsic = data["intrinsic_per_share"]
                mos = data["margin_of_safety"]

                card.metric(
                    f"{name} case",
                    f"${intrinsic:,.2f}",
                )

                if mos is not None:
                    label = (
                        "Discount to value (MOS)"
                        if mos >= 0
                        else "Premium to value"
                    )
                    card.caption(f"{label}: {mos:.1%}")
                else:
                    card.caption("Margin of safety unavailable")

            base_value = dcf_result["Base"]["intrinsic_per_share"]
            upside = base_value / price - 1

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
                f"{upside:+.1%}",
            )

            if base_value > price:
                st.success(
                    "The model's Base-case estimated value is above the "
                    "entered price. This is not a buy recommendation."
                )
            else:
                st.warning(
                    "The model's Base-case estimated value is at or below "
                    "the entered price. This is not a sell recommendation."
                )

            st.markdown("### Scenario details")

            rows = []

            for name in order:
                data = dcf_result[name]

                rows.append({
                    "Scenario": name,
                    "FCF growth": data["growth"],
                    "WACC": data["wacc"],
                    "Terminal growth": data["terminal_growth"],
                    "Enterprise value ($B)": (
                        data["enterprise_value"] / 1e9
                    ),
                    "Equity value ($B)": (
                        data["equity_value"] / 1e9
                    ),
                    "Intrinsic value / share ($)": (
                        data["intrinsic_per_share"]
                    ),
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

            # ----------------------------------------------------
            # Reverse DCF
            # ----------------------------------------------------

            st.markdown(
                "### Reverse DCF | What growth is priced in?"
            )

            st.write(
                "Estimates the constant annual FCF growth rate over "
                "five years required for model value to equal the entered "
                "market price, holding WACC and terminal growth constant."
            )

            reverse_wacc = st.selectbox(
                "WACC for Reverse DCF",
                options=[bw, mw, uw],
                index=1,
                format_func=lambda value: f"{value:.1%}",
            )

            target_equity_value = price * shares
            target_enterprise_value = (
                target_equity_value - cash + debt
            )

            def dcf_ev_for_growth(
                growth,
                discount_rate,
                terminal_rate,
            ):
                forecast = [
                    fcf * ((1 + growth) ** year)
                    for year in range(1, 6)
                ]

                pv_forecast = sum(
                    cf / ((1 + discount_rate) ** year)
                    for year, cf in enumerate(forecast, start=1)
                )

                terminal_value = (
                    forecast[-1]
                    * (1 + terminal_rate)
                    / (discount_rate - terminal_rate)
                )

                pv_terminal = terminal_value / (
                    (1 + discount_rate) ** 5
                )

                return pv_forecast + pv_terminal

            if reverse_wacc <= tg:
                st.warning(
                    "Reverse DCF WACC must be greater than terminal growth."
                )
            else:
                low, high = -0.95, 5.0

                low_ev = dcf_ev_for_growth(low, reverse_wacc, tg)
                high_ev = dcf_ev_for_growth(high, reverse_wacc, tg)

                if (
                    target_enterprise_value < low_ev
                    or target_enterprise_value > high_ev
                ):
                    st.warning(
                        "The target price is outside the supported growth "
                        "search range (-95% to 500%). No reliable solution "
                        "was found with these inputs."
                    )
                else:
                    for _ in range(150):
                        mid = (low + high) / 2

                        model_ev = dcf_ev_for_growth(
                            mid,
                            reverse_wacc,
                            tg,
                        )

                        if model_ev < target_enterprise_value:
                            low = mid
                        else:
                            high = mid

                    implied_growth = (low + high) / 2

                    rc1, rc2, rc3 = st.columns(3)

                    rc1.metric(
                        "Market price entered",
                        f"${price:,.2f}",
                    )
                    rc2.metric(
                        "Reverse DCF WACC",
                        f"{reverse_wacc:.1%}",
                    )
                    rc3.metric(
                        "Implied 5-year FCF growth",
                        f"{implied_growth:.1%}",
                    )

                    difference = implied_growth - mg

                    st.caption(
                        f"Implied growth is {difference:+.1%} points "
                        f"versus your Base-case growth assumption of {mg:.1%}."
                    )

                    if implied_growth > mg + 0.10:
                        st.warning(
                            "The entered price requires materially stronger "
                            "five-year FCF growth than the Base case."
                        )
                    elif implied_growth < mg - 0.05:
                        st.info(
                            "The entered price can be supported by a lower "
                            "growth rate than the Base case under these "
                            "assumptions. Verify all inputs."
                        )
                    else:
                        st.info(
                            "The implied growth rate is relatively close "
                            "to the Base-case assumption."
                        )

            # ----------------------------------------------------
            # Sensitivity table
            # ----------------------------------------------------

            st.markdown("### Growth-rate / WACC sensitivity")

            st.write(
                "Each cell is estimated intrinsic value per share. "
                "Terminal growth, cash, debt and shares remain constant."
            )

            growth_values = [
                sensitivity_growth_min
                + i * (
                    sensitivity_growth_max
                    - sensitivity_growth_min
                ) / 5
                for i in range(6)
            ]

            wacc_values = [
                sensitivity_wacc_min
                + i * (
                    sensitivity_wacc_max
                    - sensitivity_wacc_min
                ) / 4
                for i in range(5)
            ]

            valid_wacc_values = [
                value for value in wacc_values if value > tg
            ]

            if not valid_wacc_values:
                st.warning(
                    "All sensitivity WACC values must exceed terminal growth."
                )
            else:
                sensitivity_rows = []

                for growth in growth_values:
                    row = {"FCF growth": f"{growth:.1%}"}

                    for wacc in valid_wacc_values:
                        enterprise_value = dcf_ev_for_growth(
                            growth,
                            wacc,
                            tg,
                        )

                        equity_value = (
                            enterprise_value + cash - debt
                        )

                        row[f"WACC {wacc:.1%}"] = (
                            equity_value / shares
                        )

                    sensitivity_rows.append(row)

                sensitivity_df = pd.DataFrame(sensitivity_rows)

                value_columns = [
                    column
                    for column in sensitivity_df.columns
                    if column != "FCF growth"
                ]

                st.dataframe(
                    sensitivity_df.style.format({
                        column: "${:,.2f}"
                        for column in value_columns
                    }),
                    use_container_width=True,
                    hide_index=True,
                )

                st.caption(
                    "Sensitivity results are illustrative, not price targets. "
                    "The model assumes constant FCF growth for five years, "
                    "followed by perpetual terminal growth."
                )

    except Exception as exc:
        st.error(f"DCF calculation failed: {exc}")


# ============================================================
# Retrieved SEC facts
# ============================================================

st.subheader("Retrieved SEC facts")

if not metrics:
    st.info("No metric tables were returned.")
else:
    tabs = st.tabs(list(metrics.keys()))

    for tab, (metric_name, metric_df) in zip(
        tabs,
        metrics.items(),
    ):
        with tab:
            if metric_df.empty:
                st.warning(
                    "No matching SEC fact was found. "
                    "No value has been imputed."
                )
            else:
                display_df = metric_df.copy()

                if "end" in display_df.columns:
                    display_df = display_df.sort_values(
                        "end",
                        ascending=False,
                    )

                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                )


# ============================================================
# CSV download
# ============================================================

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
    file_name=f"{result_data['ticker']}_sec_facts.csv",
    mime="text/csv",
)

st.divider()
st.caption(
    "Technology Stock Valuation Lab | Educational prototype | Not investment advice"
)
