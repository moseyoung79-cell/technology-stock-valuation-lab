
import pandas as pd


def _latest_record(df, end=None):
    """Return the latest record, optionally for an exact period end."""
    if df is None or df.empty:
        return None

    data = df.copy()

    if end is not None:
        data = data[data["end"].astype(str) == str(end)]

    if data.empty:
        return None

    sort_cols = [
        col for col in ("end", "filed")
        if col in data.columns
    ]

    if sort_cols:
        data = data.sort_values(sort_cols)

    return data.iloc[-1].to_dict()


def _latest_annual(df, end=None):
    """Return the latest annual flow record."""
    if df is None or df.empty:
        return None

    data = df.copy()

    if "form" in data.columns:
        data = data[data["form"].astype(str) == "10-K"]

    if "start" in data.columns:
        data = data[data["start"].notna()]

    if end is not None:
        data = data[data["end"].astype(str) == str(end)]

    if data.empty:
        return None

    data = data.sort_values(["end", "filed"])
    return data.iloc[-1].to_dict()


def _previous_year_end(df, end):
    """Return the latest point-in-time record before the requested end."""
    if df is None or df.empty:
        return None

    data = df[df["end"].astype(str) < str(end)].copy()

    if data.empty:
        return None

    data = data.sort_values(["end", "filed"])
    return data.iloc[-1].to_dict()


def _derived(value, end, definition, status, unit=None):
    return {
        "value": value,
        "end": end,
        "definition": definition,
        "status": status,
        "unit": unit,
    }


def _same_unit(records):
    """Check whether all nonempty records use the same unit."""
    units = {
        str(record.get("unit"))
        for record in records
        if record and record.get("unit") is not None
    }
    return len(units) <= 1


def _latest_common_end(metrics, keys):
    """
    Find the latest period end shared by all specified balance-sheet
    dataframes. Returns None if no common period exists.
    """
    end_sets = []

    for key in keys:
        df = metrics.get(key, pd.DataFrame())

        if df is None or df.empty or "end" not in df.columns:
            return None

        end_sets.append(set(df["end"].dropna().astype(str)))

    if not end_sets:
        return None

    common_ends = set.intersection(*end_sets)

    if not common_ends:
        return None

    return max(common_ends)


def _sum_balance_items(metrics, keys, end, definition):
    """Sum balance-sheet values only when all items share an end date."""
    records = []

    for key in keys:
        df = metrics.get(key, pd.DataFrame())
        record = _latest_record(df, end=end)

        if record is None:
            return _derived(
                None,
                end,
                definition,
                f"Unavailable: missing {key} for the common reporting date",
            )

        records.append(record)

    if not _same_unit(records):
        return _derived(
            None,
            end,
            definition,
            "Unavailable: source units do not match",
        )

    value = sum(float(record["value"]) for record in records)

    return _derived(
        value,
        end,
        definition,
        "Derived from SEC facts; verify tags, units and original filing",
        records[0].get("unit"),
    )


def summarize(metrics):
    """
    Summarize annual flows and point-in-time balance-sheet items.

    All derived values require verification against the original SEC filing.
    Missing data is kept unavailable; it is never silently replaced by zero.
    """
    out = {}

    flow_keys = (
        "revenue",
        "operating_income",
        "net_income",
        "operating_cash_flow",
        "capex",
    )

    for key in flow_keys:
        out[key] = _latest_annual(
            metrics.get(key, pd.DataFrame())
        )

    # Preserve the latest extracted record for other metrics.
    for key, df in metrics.items():
        if key not in out:
            out[key] = _latest_record(df)

    revenue = out.get("revenue")
    net_income = out.get("net_income")
    operating_income = out.get("operating_income")

    # ROS: net income / revenue, with matching annual period ends.
    if (
        revenue
        and net_income
        and revenue["end"] == net_income["end"]
        and float(revenue["value"]) != 0
    ):
        out["ros"] = _derived(
            float(net_income["value"]) / float(revenue["value"]),
            revenue["end"],
            "Net income / revenue",
            "Derived; annual period ends match; verify source facts",
        )
    else:
        out["ros"] = _derived(
            None,
            None,
            "Net income / revenue",
            "Unavailable: matching annual periods required",
        )

    # Operating margin.
    if (
        revenue
        and operating_income
        and revenue["end"] == operating_income["end"]
        and float(revenue["value"]) != 0
    ):
        out["operating_margin"] = _derived(
            float(operating_income["value"])
            / float(revenue["value"]),
            revenue["end"],
            "Operating income / revenue",
            "Derived; annual period ends match; verify source facts",
        )
    else:
        out["operating_margin"] = _derived(
            None,
            None,
            "Operating income / revenue",
            "Unavailable: matching annual periods required",
        )

    # ROE: annual net income / average beginning and ending equity.
    equity_df = metrics.get("equity", pd.DataFrame())
    roe = None
    roe_end = None

    if net_income and equity_df is not None and not equity_df.empty:
        end = str(net_income["end"])
        ending_equity = _latest_record(equity_df, end=end)
        beginning_equity = _previous_year_end(equity_df, end=end)

        if (
            ending_equity
            and beginning_equity
            and float(ending_equity["value"]) > 0
            and float(beginning_equity["value"]) > 0
            and _same_unit([ending_equity, beginning_equity])
        ):
            average_equity = (
                float(ending_equity["value"])
                + float(beginning_equity["value"])
            ) / 2

            if average_equity > 0:
                roe = float(net_income["value"]) / average_equity
                roe_end = end

    out["roe"] = _derived(
        roe,
        roe_end,
        "Annual net income / average beginning and ending equity",
        (
            "Derived; verify fiscal-year alignment and equity definition"
            if roe is not None
            else "Unavailable: matching year-end equity records required"
        ),
    )

    # FCF proxy: annual operating cash flow minus absolute capex.
    ocf_df = metrics.get("operating_cash_flow", pd.DataFrame())
    capex_df = metrics.get("capex", pd.DataFrame())

    ocf = _latest_annual(ocf_df)
    capex = _latest_annual(
        capex_df,
        end=ocf["end"] if ocf else None,
    )

    fcf = None
    fcf_end = None

    if (
        ocf
        and capex
        and ocf["end"] == capex["end"]
        and ocf.get("start") == capex.get("start")
        and _same_unit([ocf, capex])
    ):
        fcf = float(ocf["value"]) - abs(float(capex["value"]))
        fcf_end = ocf["end"]

    out["fcf_proxy"] = _derived(
        fcf,
        fcf_end,
        "Operating cash flow - absolute capital expenditures",
        (
            "Derived annual proxy; not normalized FCFF; verify original filings"
            if fcf is not None
            else "Unavailable: matching annual cash flow periods and units required"
        ),
        ocf.get("unit") if ocf else None,
    )

    # Balance sheet: use one common period end where possible.
    balance_keys = [
        "cash",
        "short_debt",
        "long_debt",
        "shares",
    ]
    balance_end = _latest_common_end(metrics, balance_keys)

    out["balance_sheet_as_of"] = _derived(
        balance_end,
        balance_end,
        "Latest common end date across cash, short debt, long debt and shares",
        (
            "Common reporting date found; verify each fact against the filing"
            if balance_end
            else "Unavailable: no common reporting date across all required facts"
        ),
    )

    if balance_end:
        out["cash_value"] = _sum_balance_items(
            metrics,
            ["cash"],
            balance_end,
            "Cash and cash equivalents",
        )

        out["debt_value"] = _sum_balance_items(
            metrics,
            ["short_debt", "long_debt"],
            balance_end,
            "Short-term debt + long-term debt",
        )

        out["shares_value"] = _sum_balance_items(
            metrics,
            ["shares"],
            balance_end,
            "Shares outstanding from SEC Company Facts",
        )
    else:
        out["cash_value"] = _derived(
            None,
            None,
            "Cash and cash equivalents",
            "Unavailable: common balance-sheet reporting date not found",
        )

        out["debt_value"] = _derived(
            None,
            None,
            "Short-term debt + long-term debt",
            "Unavailable: common balance-sheet reporting date not found",
        )

        out["shares_value"] = _derived(
            None,
            None,
            "Shares outstanding from SEC Company Facts",
            "Unavailable: common balance-sheet reporting date not found",
        )

    return out


def quality_checks(metrics, summary):
    checks = []

    for name, df in metrics.items():
        if df is None or df.empty:
            checks.append({
                "check": f"{name}: data availability",
                "status": "MISSING",
                "detail": (
                    "No matching fact extracted from SEC Company Facts."
                ),
            })
            continue

        row = _latest_record(df)

        checks.append({
            "check": f"{name}: SEC fact retrieved",
            "status": "REVIEW REQUIRED",
            "detail": (
                f"Tag={row.get('tag')}; unit={row.get('unit')}; "
                f"period end={row.get('end')}; filed={row.get('filed')}. "
                "Confirm against the original filing."
            ),
        })

    for name in (
        "ros",
        "operating_margin",
        "roe",
        "fcf_proxy",
        "cash_value",
        "debt_value",
        "shares_value",
        "balance_sheet_as_of",
    ):
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
