import streamlit as st
import pandas as pd
from valuation_lab.sec_data import get_tickers, get_facts, extract_all
from valuation_lab.metrics import summarize, quality_checks
from valuation_lab.dcf import scenarios

st.set_page_config(page_title="Technology Stock Valuation Lab", page_icon="📊", layout="wide")
st.title("Technology Stock Valuation Lab")
st.caption("v1.1 · Validation-first prototype · SEC-sourced data · Not investment advice")
st.warning("VALIDATION NOTICE: SEC-sourced does not automatically mean verified. Review each fact in its source 10-K before relying on it. Derived metrics and DCF scenarios are not verified facts.")
with st.sidebar:
    st.header("Company")
    ticker=st.text_input("US ticker", "NVDA").strip().upper()
    price=st.number_input("Current share price (USD; manually verified)", min_value=0.0, value=0.0, step=1.0)
    st.caption("No live quote API is configured.")
    st.header("Optional balance-sheet overrides")
    cash_b=st.number_input("Cash ($ billions; manually verify)", min_value=0.0, value=0.0, step=1.0)
    debt_b=st.number_input("Debt ($ billions; manually verify)", min_value=0.0, value=0.0, step=1.0)
    shares_b=st.number_input("Shares outstanding (billions; manually verify)", min_value=0.0, value=0.0, step=0.1)
    st.header("Illustrative assumptions")
    bg=st.number_input("Bear FCF growth", value=0.05, step=0.01, format="%.2f")
    bw=st.number_input("Bear WACC", value=0.12, step=0.01, format="%.2f")
    mg=st.number_input("Base FCF growth", value=0.12, step=0.01, format="%.2f")
    mw=st.number_input("Base WACC", value=0.10, step=0.01, format="%.2f")
    ug=st.number_input("Bull FCF growth", value=0.20, step=0.01, format="%.2f")
    uw=st.number_input("Bull WACC", value=0.09, step=0.01, format="%.2f")
    tg=st.number_input("Terminal growth", value=0.03, step=0.005, format="%.3f")
if st.button("Fetch SEC data & analyze", type="primary"):
    try:
        with st.spinner("Retrieving SEC ticker list and Company Facts..."):
            tickers=get_tickers()
            if ticker not in tickers:
                st.error(f"{ticker} not found in SEC ticker list."); st.stop()
            issuer=tickers[ticker]
            facts,url=get_facts(issuer["cik"])
            metrics=extract_all(facts)
            summary=summarize(metrics)
            st.session_state["result"]={"ticker":ticker,"issuer":issuer,"url":url,
                "metrics":{k:v.to_dict("records") for k,v in metrics.items()},
                "summary":summary,"checks":quality_checks(metrics,summary).to_dict("records")}
    except Exception as e:
        st.error(f"SEC retrieval failed: {e}")
        st.info("For Streamlit Cloud, set SEC_USER_AGENT in app Secrets. Use a descriptive app name and a real contact email. Some issuers may use unsupported tags.")
if "result" in st.session_state:
    r=st.session_state["result"]; summary=r["summary"]
    st.subheader(f'{r["issuer"]["name"]} ({r["ticker"]})')
    st.write(f'CIK: {r["issuer"]["cik"]} · SEC Company Facts: {r["url"]}')
    st.info("Source status: SEC-sourced; filing-level verification still required. The source URL and period are shown for review.")
    cols=st.columns(4)
    def pct(item):
        val=item.get("value")
        return "N/A" if val is None else f"{val:.1%}"
    cols[0].metric("ROS · net profit margin",pct(summary["ros"]))
    cols[1].metric("Operating margin",pct(summary["operating_margin"]))
    cols[2].metric("ROE",pct(summary["roe"]))
    fcf=summary["fcf_proxy"].get("value")
    cols[3].metric("FCF proxy (annual, USD B)","N/A" if fcf is None else f"${fcf/1e9:,.2f}")
    st.caption("Ratios are derived only when their periods align. FCF proxy = operating cash flow minus absolute capex; it is not normalized FCFF.")
    st.subheader("Data-quality and validation checklist")
    st.dataframe(pd.DataFrame(r["checks"]),use_container_width=True,hide_index=True)
    st.subheader("Retrieved annual facts")
    metrics={k:pd.DataFrame(v) for k,v in r["metrics"].items()}
    tabs=st.tabs(list(metrics.keys()))
    for tab,(name,df) in zip(tabs,metrics.items()):
        with tab:
            if df.empty: st.warning("No matching common US-GAAP annual fact found. No value has been imputed.")
            else: st.dataframe(df.sort_values("end",ascending=False),use_container_width=True,hide_index=True)
    st.subheader("Illustrative DCF scenarios")
   
    shares_record = summary.get("shares") or {}
    cash_record = summary.get("cash") or {}
    short_debt_record = summary.get("short_debt") or {}
    long_debt_record = summary.get("long_debt") or {}

    # Require manually verified inputs for the initial DCF.
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
        st.warning("DCF blocked: annual FCF proxy is unavailable.")
    elif price <= 0:
        st.warning(
            "DCF blocked: enter a manually verified current share price."
        )
    else:
        result = scenarios(
            fcf,
            shares,
            cash,
            debt,
            price,
            {"Bear": bg, "Base": mg, "Bull": ug},
            {"Bear": bw, "Base": mw, "Bull": uw},
            tg,
        )

    if isinstance(result, dict) and "error" in result:
    st.warning(f"DCF blocked: {result['error']}")
elif isinstance(result, dict):
    rows = [
        {"Scenario": scenario, **values}
        for scenario, values in result.items()
    ]
    df = pd.DataFrame(rows)

    st.dataframe(
        df,
        use_container_width=True,
        hide_index=True,
    )

    st.warning(
        "DCF is illustrative and uses a simplified FCF proxy. "
        "Verify all inputs and assumptions before relying on results."
    )
else:
    st.error("Unexpected DCF result format. Please review the app logs.")
annual = []
for metric, df in metrics.items():
for _, row in df.iterrows():
annual.append({"metric": metric, **row.to_dict()})

st.download_button(
"Download SEC facts CSV",
pd.DataFrame(annual).to_csv(index=False),
f'{r["ticker"]}_sec_facts.csv',
"text/csv",
)
st.divider()
st.caption("Next milestones: independently reconcile NVDA facts to official filings, add filing-specific validation records, then configure live price data and quarterly checks.")
