
import pandas as pd


def _latest_annual(df, end=None):
    """Return the latest annual record, optionally for a given end date."""
    if df is None or df.empty:
        return None

    data = df.copy()

    if end is not None:
        data = data[data["end"].astype(str) == str(end)]

    if data.empty:
        return None

    data = data.sort_values(["end", "filed"])
    return data.iloc[-1].to_dict()


def _previous_year_end(df, end):
    """Return the latest equity record before the requested year end."""
    if df is None or df.empty:
        return None

    data = df[df["end"].astype(str) < str(end)].copy()

    if data.empty:
        return None

    data = data.sort_values(["end", "filed"])
    return data.iloc[-1].to_dict()


def _derived(value, end, definition, status):
    return {
        "value": value,
        "end": end,
        "definition": definition,
        "status": status,
    }


def summarize(metrics):
    """
    Calculate ratios only when source periods align.
    All calculated values remain derived, not independently verified.
    """
    out = {
        key: _latest_annual(value)
        for key, value in metrics.items()
    }

    revenue_df = metrics.get("revenue", pd.DataFrame())
    income_df = metrics.get("net_income", pd.DataFrame())
    operating_df = metrics.get("operating_income", pd.DataFrame())
    equity_df = metrics.get("equity", pd.DataFrame())
    ocf_df = metrics.get("operating_cash_flow", pd.DataFrame())
    capex_df = metrics.get("capex", pd.DataFrame())

    revenue = out.get("revenue")
    net_income = out.get("net_income")
    operating_income = out.get("operating_income")

    # ROS: net income / revenue, matched on the same period end.
    if (
        revenue
        and net_income
        and revenue["end"] == net_income["end"]
        and float(revenue["value"]) != 0
    ):
        ros = float(net_income["value"]) / float(revenue["value"])
        out["ros"] = _derived(
            ros, revenue["end"], "Net income / revenue",
            "Derived; annual period ends match; source review required",
        )
    else:
        out["ros"] = _derived(
            None, None, "Net income / revenue",
            "Unavailable: annual periods do not match",
        )

    # Operating margin is separate from ROS.
    if (
        revenue
        and operating_income
        and revenue["end"] == operating_income["end"]
        and float(revenue["value"]) != 0
    ):
        margin = (
            float(operating_income["value"])
            / float(revenue["value"])
        )
        out["operating_margin"] = _derived(
            margin, revenue["end"], "Operating income / revenue",
            "Derived; annual period ends match; source review required",
        )
    else:
        out["operating_margin"] = _derived(
            None, None, "Operating income / revenue",
            "Unavailable: annual periods do not match",
        )

    # ROE: annual net income / average beginning and ending equity.
    roe = None
    roe_end = None

    if net_income and equity_df is not None and not equity_df.empty:
        end = str(net_income["end"])
        ending_equity = _latest_annual(equity_df, end=end)
        beginning_equity = _previous_year_end(equity_df, end=end)

        if (
            ending_equity
            and beginning_equity
            and float(ending_equity["value"]) > 0
            and float(beginning_equity["value"]) > 0
        ):
            average_equity = (
                float(ending_equity["value"])
                + float(beginning_equity["value"])
            ) / 2

            if average_equity > 0:
                roe = float(net_income["value"]) / average_equity
                roe_end = end

    out["roe"] = _derived(
        roe, roe_end,
        "Annual net income / average beginning and ending equity",
        (
            "Derived; verify fiscal-year alignment and equity definition"
            if roe is not None
            else "Unavailable: matching year-end equity records required"
        ),
    )

    # FCF proxy: annual operating cash flow minus absolute capex.
    fcf = None
    fcf_end = None

    if not ocf_df.empty and not capex_df.empty:
        ocf = _latest_annual(ocf_df)
        capex = _latest_annual(capex_df)

        if (
            ocf
            and capex
            and ocf["end"] == capex["end"]
            and ocf.get("start") == capex.get("start")
        ):
            fcf = (
                float(ocf["value"])
                - abs(float(capex["value"]))
            )
            fcf_end = ocf["end"]

    out["fcf_proxy"] = _derived(
        fcf, fcf_end,
        "Operating cash flow - absolute capital expenditures",
        (
            "Derived proxy; not normalized FCFF; source review required"
            if fcf is not None
            else "Unavailable: aligned annual cash flow periods required"
        ),
    )

    return out


def quality_checks(metrics, summary):
    checks = []

    for name, df in metrics.items():
        if df is None or df.empty:
            checks.append({
                "check": f"{name}: data availability",
                "status": "MISSING",
                "detail": "No matching fact extracted from SEC Company Facts.",
            })
            continue

        row = _latest_annual(df)

        checks.append({
            "check": f"{name}: SEC fact retrieved",
            "status": "REVIEW REQUIRED",
            "detail": (
                f"Tag={row.get('tag')}; unit={row.get('unit')}; "
                f"period end={row.get('end')}; filed={row.get('filed')}. "
                "Confirm against the original filing."
            ),
        })

    for name in ("ros", "operating_margin", "roe", "fcf_proxy"):
        item = summary.get(name, {})
        checks.append({
            "check": name,
            "status": (
                "DERIVED - REVIEW REQUIRED"
                if item.get("value") is not None
                else "UNAVAILABLE"
            ),
            "detail": item.get("status", ""),
        })

    return pd.DataFrame(checks)
