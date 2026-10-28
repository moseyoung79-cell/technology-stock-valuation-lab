
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
    "v1.4 · Reverse DCF · Growth/WACC sensitivity · "
    "SEC-sourced data · Not investment advice"
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
        "Cash and liquid investments ($ billions; manually verify)",
        min_value=0.0,
        value=0.0,
        step=0.5,
        format="%.3f",
        help=(
            "You may include cash plus marketable securities. "
            "Keep the reporting date consistent with debt and shares."
        ),
    )

    debt_b = st.number_input(
        "Debt ($ billions; manually verify)",
        min_value=0.0,
        value=0.0,
        step=0.5,
        format="%.3f",
    )

    shares_b = st.number_input(
        "Diluted shares outstanding (billions; manually verify)",
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
        "FCF proxy. Enter USD billions."
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
        with st.spinner(
            "Retrieving SEC ticker list and Company Facts..."
        ):
            ticker_map = get_tickers()

            if ticker not in ticker_map:
                st.error(
                    f"{ticker} was not found in the SEC ticker list."
                )
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
            "Check Streamlit Secrets for SEC_USER_AGENT and verify "
            "that the ticker and SEC data are accessible."
        )


# --------------------------------------------------
# Display results
# --------------------------------------------------

if "result" not in st.session_state:
    st.info(
        "Enter the ticker and assumptions in the sidebar, then click "
        "'Fetch SEC data & analyze' once. After data is loaded, changing "
        "assumptions recalculates the valuation automatically."
    )
    st.stop()

result_data = st.session_state["result"]

if ticker != result_data["ticker"]:
    st.warning(
        f"Loaded data is for {result_data['ticker']}, but the sidebar "
        f"now contains {ticker}. Click 'Fetch SEC data & analyze' "
        "to load the new company."
    )
    st.stop()

issuer = result_data["issuer"]
summary = result_data["summary"]

metrics = {
    name: pd.DataFrame(records)
    for name, records in result_data["metrics"].items()
}

st.subheader(f'{issuer["name"]} ({result_data["ticker"]})')

st.write(
    f'CIK: {issuer["cik"]} · '
    f'SEC Company Facts: {result_data["url"]}'
)

st.info(
    "SEC-sourced data still requires filing-level verification. "
    "Review reporting period, units and official filings before relying on values."
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

cols = st.columns(4)

cols[0].metric(
    "ROS · Net profit margin",
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
    f"${fcf_proxy / 1e9:,.2f}B"
    if fcf_proxy is not None
    else "N/A",
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
# DCF valuation
# --------------------------------------------------

st.subheader("DCF valuation")

if manual_fcf_b > 0:
    fcf = manual_fcf_b * 1e9
    fcf_source = "Manual annual FCF proxy"
else:
    fcf = fcf_proxy
    fcf_source = "SEC-derived annual FCF proxy"

st.write(f"**FCF input source:** {fcf_source}")


# --------------------------------------------------
# DCF helper function
# --------------------------------------------------

def dcf_ev_for_growth(fcf_value, growth, discount_rate, terminal_rate):
    """
    Five-year DCF enterprise value.

    FCF grows at a constant annual rate for five years.
    Terminal value uses the Gordon Growth formula.
    All monetary values use USD.
    """

    if fcf_value <= 0:
        raise ValueError("FCF must be positive.")

    if discount_rate <= terminal_rate:
        raise ValueError("WACC must be greater than terminal growth.")

    if growth <= -1:
        raise ValueError("FCF growth must be greater than -100%.")

    forecast = [
        fcf_value * ((1 + growth) ** year)
        for year in range(1, 6)
    ]

    pv_forecast = sum(
        cashflow / ((1 + discount_rate) ** year)
        for year, cashflow in enumerate(forecast, start=1)
    )

    terminal_value = (
        forecast[-1] * (1 + terminal_rate)
        / (discount_rate - terminal_rate)
    )

    pv_terminal = terminal_value / ((1 + discount_rate) ** 5)

    return pv_forecast + pv_terminal


# --------------------------------------------------
# Input validation and main DCF calculation
# --------------------------------------------------

if fcf is None:
    st.warning(
        "DCF cannot calculate because the SEC-derived annual FCF proxy "
        "is unavailable. Enter a manually verified annual FCF proxy. "
        "Do not use quarterly FCF as a full-year value."
    )

elif fcf <= 0:
    st.warning(
        "DCF cannot calculate because starting FCF must be positive."
    )

elif shares_b <= 0:
    st.warning(
        "Enter manually verified diluted shares outstanding in billions, "
        "and confirm the reporting date."
    )

elif price <= 0:
    st.warning(
        "Enter a manually verified current share price in USD "
        "to calculate price comparison and reverse DCF."
    )

elif any(w <= tg for w in (bw, mw, uw)):
    st.warning(
        "Each scenario's WACC must be greater than terminal growth."
    )

elif tg < 0:
    st.warning(
        "Terminal growth cannot be negative in this prototype."
    )

elif any(g <= -1 for g in (bg, mg, ug)):
    st.warning(
        "FCF growth must be greater than -100%."
    )

elif sensitivity_wacc_max <= sensitivity_wacc_min:
    st.warning(
        "Sensitivity WACC maximum must be greater than its minimum."
    )

elif sensitivity_growth_max <= sensitivity_growth_min:
    st.warning(
        "Sensitivity growth maximum must be greater than its minimum."
    )

else:
    try:
        cash = cash_b * 1e9
        debt = debt_b * 1e9
        shares = shares_b * 1e9

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

            # ------------------------------------------
            # Intrinsic value cards
            # ------------------------------------------

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
                    if mos > 0:
                        card.caption(
                            f"Discount to value (MOS): {mos:.1%}"
                        )
                    elif mos < 0:
                        card.caption(
                            f"Premium to estimated value: {-mos:.1%}"
                        )
                    else:
                        card.caption(
                            "Market price equals estimated value"
                        )
                else:
                    card.caption(
                        "Margin of safety unavailable"
                    )

            # ------------------------------------------
            # Base-case interpretation
            # ------------------------------------------

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
                    "The base-case estimated value is above the current "
                    "price. This is a model result, not a buy recommendation."
                )
            else:
                st.warning(
                    "The base-case estimated value is at or below the current "
                    "price. This is a model result, not a sell recommendation."
                )

            # ------------------------------------------
            # Scenario details
            # ------------------------------------------

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
                    "PV terminal value ($B)": (
                        data["pv_terminal"] / 1e9
                    ),
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

            # ------------------------------------------
            # Reverse DCF
            # ------------------------------------------

            st.markdown(
                "### Reverse DCF · What growth is priced in?"
            )

            st.write(
                "This estimates the constant annual FCF growth rate over "
                "the next five years needed for the model value to equal "
                "the current share price, holding WACC and terminal growth "
                "constant. It is a model-implied assumption, not a forecast."
            )

            reverse_wacc = st.selectbox(
                "WACC for reverse DCF",
                options=[bw, mw, uw],
                index=1,
                format_func=lambda value: f"{value:.1%}",
            )

            target_equity_value = price * shares

            target_enterprise_value = (
                target_equity_value - cash + debt
            )

            if reverse_wacc <= tg:
                st.warning(
                    "Reverse DCF WACC must be greater than terminal growth."
                )

            elif target_enterprise_value <= 0:
                st.warning(
                    "The implied target enterprise value is not positive. "
                    "Verify price, shares, cash and debt inputs."
                )

            else:
                low = -0.95
                high = 5.0

                low_ev = dcf_ev_for_growth(
                    fcf, low, reverse_wacc, tg
                )

                high_ev = dcf_ev_for_growth(
                    fcf, high, reverse_wacc, tg
                )

                if (
                    target_enterprise_value < low_ev
                    or target_enterprise_value > high_ev
                ):
                    st.warning(
                        "The target price is outside the model's supported "
                        "growth search range (-95% to 500%). Reverse DCF "
                        "cannot find a solution with these inputs."
                    )

                else:
                    for _ in range(150):
                        mid = (low + high) / 2

                        mid_ev = dcf_ev_for_growth(
                            fcf, mid, reverse_wacc, tg
                        )

                        if mid_ev < target_enterprise_value:
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

                    diff = implied_growth - mg

                    st.caption(
                        f"Implied growth is {diff:+.1%} points versus "
                        f"your Base-case FCF growth assumption of {mg:.1%}."
                    )

                    if implied_growth > mg + 0.10:
                        st.warning(
                            "The current price requires materially stronger "
                            "five-year FCF growth than your Base case under "
                            "these assumptions."
                        )

                    elif implied_growth < mg - 0.05:
                        st.info(
                            "The current price can be supported by a lower "
                            "growth rate than your Base case under these "
                            "assumptions. Verify WACC, FCF, cash, debt and "
                            "shares before drawing conclusions."
                        )

                    else:
                        st.info(
                            "The implied growth rate is relatively close "
                            "to your Base-case assumption. Small changes "
                            "in assumptions can still materially change "
                            "the valuation."
                        )

            # ------------------------------------------
            # Growth-rate / WACC sensitivity
            # ------------------------------------------

            st.markdown(
                "### Growth-rate / WACC sensitivity"
            )

            st.write(
                "Each cell is estimated intrinsic value per share. "
                "Terminal growth, cash, debt and shares are held constant; "
                "only five-year FCF growth and WACC change."
            )

            growth_values = [
                round(
                    sensitivity_growth_min
                    + i * (
                        sensitivity_growth_max
                        - sensitivity_growth_min
                    ) / 5,
                    4,
                )
                for i in range(6)
            ]

            wacc_values = [
                round(
                    sensitivity_wacc_min
                    + i * (
                        sensitivity_wacc_max
                        - sensitivity_wacc_min
                    ) / 4,
                    4,
                )
                for i in range(5)
            ]

            valid_wacc_values = [
                wacc for wacc in wacc_values if wacc > tg
            ]

            if not valid_wacc_values:
                st.warning(
                    "All sensitivity WACC values must be greater "
                    "than terminal growth."
                )

            else:
                sensitivity_rows = []

                for growth in growth_values:
                    row = {
                        "FCF growth": f"{growth:.1%}"
                    }

                    for wacc in valid_wacc_values:
                        enterprise_value = dcf_ev_for_growth(
                            fcf,
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

                sensitivity_df = pd.DataFrame(
                    sensitivity_rows
                )

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
                    "The model assumes a constant FCF growth rate for five "
                    "years followed by perpetual terminal growth."
                )

            st.caption(
                "All assumptions and balance-sheet inputs require independent "
                "verification. A DCF should not be tuned merely to match "
                "the market price."
            )

    except Exception as exc:
        st.error(f"DCF calculation failed: {exc}")


# --------------------------------------------------
# Retrieved annual SEC facts
# --------------------------------------------------

st.subheader("Retrieved annual SEC facts")

if not metrics:
    st.info("No annual metric tables were returned.")

else:
    tabs = st.tabs(list(metrics.keys()))

    for tab, (metric_name, metric_df) in zip(
        tabs, metrics.items()
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
    file_name=f'{result_data["ticker"]}_sec_facts.csv',
    mime="text/csv",
)

st.divider()

st.caption(
    "Technology Stock Valuation Lab · Educational prototype · "
    "Not investment advice"
)
