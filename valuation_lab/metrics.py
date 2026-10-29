
from __future__ import annotations

from typing import Any

import pandas as pd


# ============================================================
# Helpers
# ============================================================

def _empty_frame(df: Any) -> bool:
    """Check whether a metric DataFrame is missing or empty."""
    return not isinstance(df, pd.DataFrame) or df.empty


def _as_number(value: Any) -> float | None:
    """Convert a value to float without converting missing data to zero."""
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _sort_records(df: pd.DataFrame | None) -> pd.DataFrame:
    """Sort records by period end and filing date."""
    if _empty_frame(df):
        return pd.DataFrame()

    result = df.copy()

    for column in ("end", "start", "filed"):
        if column in result.columns:
            result[column] = pd.to_datetime(
                result[column], errors="coerce"
            )

    sort_columns = [
        column for column in ("end", "filed")
        if column in result.columns
    ]

    if sort_columns:
        result = result.sort_values(sort_columns)

    return result


def _latest_record(
    df: pd.DataFrame | None,
    end: str | pd.Timestamp | None = None,
) -> dict[str, Any] | None:
    """Return the latest record, optionally restricted to one end date."""
    if _empty_frame(df):
        return None

    result = _sort_records(df)

    if end is not None and "end" in result.columns:
        target_end = pd.to_datetime(end, errors="coerce")
        result = result[result["end"] == target_end]

    if result.empty:
        return None

    return result.iloc[-1].to_dict()


def _latest_annual(
    df: pd.DataFrame | None,
    end: str | pd.Timestamp | None = None,
) -> dict[str, Any] | None:
    """
    Return the latest annual flow record.

    Prefer 10-K records covering approximately one fiscal year.
    """
    if _empty_frame(df):
        return None

    result = _sort_records(df)

    if "form" in result.columns:
        result = result[
            result["form"].astype(str).str.upper() == "10-K"
        ]

    if "start" in result.columns and "end" in result.columns:
        duration_days = (
            result["end"] - result["start"]
        ).dt.days

        result = result[
            duration_days.between(300, 380, inclusive="both")
        ]

    if end is not None and "end" in result.columns:
        target_end = pd.to_datetime(end, errors="coerce")
        result = result[result["end"] == target_end]

    if result.empty:
        return None

    return result.iloc[-1].to_dict()


def _record_value(
    record: dict[str, Any] | None,
) -> float | None:
    if record is None:
        return None

    return _as_number(record.get("value"))


def _format_date(value: Any) -> str | None:
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None

        parsed = pd.to_datetime(value, errors="coerce")

        if pd.isna(parsed):
            return None

        return parsed.strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return None


def _record_date(
    record: dict[str, Any] | None,
) -> str | None:
    if record is None:
        return None

    return _format_date(record.get("end"))


def _record_info(
    record: dict[str, Any] | None,
    definition: str,
    status: str | None = None,
) -> dict[str, Any]:
    """Return a consistent data structure for a reported metric."""
    if record is None:
        return {
            "value": None,
            "end": None,
            "start": None,
            "filed": None,
            "unit": None,
            "tag": None,
            "definition": definition,
            "status": status or "unavailable",
        }

    value = _record_value(record)

    return {
        "value": value,
        "end": _format_date(record.get("end")),
        "start": _format_date(record.get("start")),
        "filed": _format_date(record.get("filed")),
        "unit": record.get("unit"),
        "tag": record.get("tag"),
        "definition": definition,
        "status": status or (
            "available" if value is not None else "unavailable"
        ),
    }


def _derived(
    value: float | None,
    end: str | None,
    definition: str,
    status: str = "available",
    start: str | None = None,
) -> dict[str, Any]:
    """Return a consistent data structure for a calculated metric."""
    return {
        "value": value,
        "end": end,
        "start": start,
        "filed": None,
        "unit": None,
        "tag": None,
        "definition": definition,
        "status": status,
    }


def _latest_balance_item(
    metrics: dict[str, pd.DataFrame],
    metric_name: str,
    definition: str,
) -> dict[str, Any]:
    """Get the latest available point-in-time balance-sheet value."""
    record = _latest_record(metrics.get(metric_name))
    return _record_info(record, definition)


def _same_period(
    first: dict[str, Any] | None,
    second: dict[str, Any] | None,
) -> bool:
    """Check that two flow records cover the same start and end dates."""
    if first is None or second is None:
        return False

    first_end = _record_date(first)
    second_end = _record_date(second)

    first_start = _format_date(first.get("start"))
    second_start = _format_date(second.get("start"))

    return (
        first_end is not None
        and first_end == second_end
        and first_start is not None
        and first_start == second_start
    )


# ============================================================
# Main financial summary
# ============================================================

def summarize(
    metrics: dict[str, pd.DataFrame],
) -> dict[str, dict[str, Any]]:
    """
    Summarize SEC company facts.

    Flow metrics use annual 10-K records.
    Balance-sheet metrics are selected independently by reporting date.
    Missing data stays None; it is never silently converted to zero.
    """
    metrics = metrics or {}

    # --------------------------------------------------------
    # Latest annual flow records
    # --------------------------------------------------------

    revenue_record = _latest_annual(metrics.get("revenue"))
    operating_income_record = _latest_annual(
        metrics.get("operating_income")
    )
    net_income_record = _latest_annual(metrics.get("net_income"))
    ocf_record = _latest_annual(
        metrics.get("operating_cash_flow")
    )
    capex_record = _latest_annual(metrics.get("capex"))

    revenue = _record_value(revenue_record)
    operating_income = _record_value(operating_income_record)
    net_income = _record_value(net_income_record)
    operating_cash_flow = _record_value(ocf_record)
    capex = _record_value(capex_record)

    revenue_end = _record_date(revenue_record)
    operating_income_end = _record_date(operating_income_record)
    net_income_end = _record_date(net_income_record)
    ocf_end = _record_date(ocf_record)
    capex_end = _record_date(capex_record)

    revenue_info = _record_info(
        revenue_record,
        "Latest annual revenue reported by the SEC.",
    )

    operating_income_info = _record_info(
        operating_income_record,
        "Latest annual operating income reported by the SEC.",
    )

    net_income_info = _record_info(
        net_income_record,
        "Latest annual net income reported by the SEC.",
    )

    # --------------------------------------------------------
    # Return on sales
    # --------------------------------------------------------

    if (
        revenue is not None
        and revenue != 0
        and net_income is not None
        and revenue_end == net_income_end
    ):
        ros = net_income / revenue
        ros_status = "available"
    else:
        ros = None
        ros_status = (
            "unavailable: missing data, zero revenue, "
            "or reporting periods do not match"
        )

    # --------------------------------------------------------
    # Operating margin
    # --------------------------------------------------------

    if (
        revenue is not None
        and revenue != 0
        and operating_income is not None
        and revenue_end == operating_income_end
    ):
        operating_margin = operating_income / revenue
        operating_margin_status = "available"
    else:
        operating_margin = None
        operating_margin_status = (
            "unavailable: missing data, zero revenue, "
            "or reporting periods do not match"
        )

    # --------------------------------------------------------
    # Return on equity (ROE)
    # --------------------------------------------------------

    roe = None
    roe_status = "unavailable: required annual data not found"
    roe_end = None

    equity_history = _sort_records(metrics.get("equity"))

    if (
        net_income_record is not None
        and net_income is not None
        and net_income_end is not None
        and not equity_history.empty
        and "end" in equity_history.columns
    ):
        target_end = pd.to_datetime(net_income_end)

        ending_equity_record = _latest_record(
            equity_history,
            end=target_end,
        )

        prior_records = equity_history[
            equity_history["end"] < target_end
        ]

        if ending_equity_record is None:
            roe_status = (
                "unavailable: ending equity does not match "
                "the net income fiscal year-end"
            )
        elif prior_records.empty:
            roe_status = (
                "unavailable: prior-period equity not found"
            )
        else:
            ending_equity = _record_value(ending_equity_record)
            previous_equity_record = prior_records.iloc[-1].to_dict()
            previous_equity = _record_value(previous_equity_record)

            if ending_equity is None or previous_equity is None:
                roe_status = (
                    "unavailable: beginning or ending equity is missing"
                )
            else:
                average_equity = (
                    previous_equity + ending_equity
                ) / 2

                if average_equity == 0:
                    roe_status = "unavailable: average equity is zero"
                else:
                    roe = net_income / average_equity
                    roe_status = "available"
                    roe_end = net_income_end

    elif equity_history.empty:
        roe_status = "unavailable: equity history not found"

    # --------------------------------------------------------
    # Free cash flow proxy
    # --------------------------------------------------------

    if (
        ocf_record is not None
        and capex_record is not None
        and _same_period(ocf_record, capex_record)
        and operating_cash_flow is not None
        and capex is not None
    ):
        # SEC capex is usually a positive cash-outflow value.
        # Using abs() also protects against inconsistent signs.
        fcf_proxy = operating_cash_flow - abs(capex)
        fcf_status = "available"
        fcf_end = ocf_end
        fcf_start = _format_date(ocf_record.get("start"))
    else:
        fcf_proxy = None
        fcf_status = (
            "unavailable: operating cash flow and capex must cover "
            "the same annual reporting period"
        )
        fcf_end = None
        fcf_start = None

    # --------------------------------------------------------
    # Balance-sheet values
    # --------------------------------------------------------

    cash_info = _latest_balance_item(
        metrics,
        "cash",
        "Latest reported cash and cash equivalents. "
        "May exclude some short-term investments.",
    )

    short_debt_info = _latest_balance_item(
        metrics,
        "short_debt",
        "Latest reported short-term debt.",
    )

    long_debt_info = _latest_balance_item(
        metrics,
        "long_debt",
        "Latest reported long-term debt.",
    )

    shares_info = _latest_balance_item(
        metrics,
        "shares",
        "Latest point-in-time common shares outstanding. "
        "Not necessarily diluted weighted-average shares.",
    )

    # Do not assume missing debt categories equal zero.
    short_debt = short_debt_info["value"]
    long_debt = long_debt_info["value"]
    short_debt_end = short_debt_info["end"]
    long_debt_end = long_debt_info["end"]

    if (
        short_debt is not None
        and long_debt is not None
        and short_debt_end is not None
        and short_debt_end == long_debt_end
    ):
        debt_value = short_debt + long_debt
        debt_end = short_debt_end
        debt_status = "available"
    else:
        debt_value = None
        debt_end = None
        debt_status = (
            "unavailable: both short-term and long-term debt "
            "must be reported for the same date"
        )

    debt_info = {
        "value": debt_value,
        "end": debt_end,
        "start": None,
        "filed": None,
        "unit": "USD" if debt_value is not None else None,
        "tag": None,
        "definition": (
            "Short-term debt plus long-term debt, when both "
            "are available for the same reporting date."
        ),
        "status": debt_status,
    }

    # Report a common date only if cash, total debt and shares
    # all have the same date. Individual values remain available.
    balance_dates = [
        cash_info.get("end"),
        debt_info.get("end"),
        shares_info.get("end"),
    ]
    valid_dates = [
        date for date in balance_dates if date is not None
    ]

    if (
        len(valid_dates) == 3
        and len(set(valid_dates)) == 1
    ):
        balance_sheet_as_of = valid_dates[0]
        balance_date_status = "available"
    else:
        balance_sheet_as_of = None
        balance_date_status = (
            "different reporting dates or incomplete data"
        )

    # --------------------------------------------------------
    # Return summary
    # --------------------------------------------------------

    return {
        "revenue": revenue_info,
        "operating_income": operating_income_info,
        "net_income": net_income_info,
        "cash_value": cash_info,
        "short_debt_value": short_debt_info,
        "long_debt_value": long_debt_info,
        "debt_value": debt_info,
        "shares_value": shares_info,
        "ros": _derived(
            ros,
            revenue_end if revenue_end == net_income_end else None,
            "Return on sales = annual net income / annual revenue.",
            ros_status,
        ),
        "operating_margin": _derived(
            operating_margin,
            (
                revenue_end
                if revenue_end == operating_income_end
                else None
            ),
            "Operating margin = annual operating income / annual revenue.",
            operating_margin_status,
        ),
        "roe": _derived(
            roe,
            roe_end,
            "ROE = annual net income / average beginning and ending equity.",
            roe_status,
        ),
        "fcf_proxy": _derived(
            fcf_proxy,
            fcf_end,
            "FCF proxy = annual operating cash flow - absolute annual capex.",
            fcf_status,
            start=fcf_start,
        ),
        "balance_sheet_as_of": _derived(
            None,
            balance_sheet_as_of,
            "Common reporting date for cash, total debt and shares.",
            balance_date_status,
        ),
    }


# ============================================================
# Data quality checks
# ============================================================

def quality_checks(
    metrics: dict[str, pd.DataFrame],
    summary: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """
    Generate data-quality messages for the Streamlit interface.

    This function reports missing data but never changes missing values
    into zero.
    """
    metrics = metrics or {}
    summary = summary or {}

    checks: list[dict[str, str]] = []

    def add(level: str, item: str, message: str) -> None:
        checks.append({
            "level": level,
            "item": item,
            "message": message,
        })

    # Core SEC records.
    core_metrics = [
        ("revenue", "Revenue"),
        ("operating_income", "Operating income"),
        ("net_income", "Net income"),
        ("operating_cash_flow", "Operating cash flow"),
        ("capex", "Capital expenditure"),
    ]

    for key, label in core_metrics:
        if _empty_frame(metrics.get(key)):
            add(
                "Warning",
                label,
                "No usable SEC records were found for this metric.",
            )

    # Derived ratios and FCF.
    derived_metrics = [
        ("ros", "Return on sales"),
        ("operating_margin", "Operating margin"),
        ("roe", "ROE"),
        ("fcf_proxy", "FCF proxy"),
    ]

    for key, label in derived_metrics:
        item = summary.get(key, {})

        if item.get("value") is None:
            add(
                "Warning",
                label,
                str(
                    item.get("status")
                    or "Metric is unavailable."
                ),
            )

    # Balance-sheet values.
    balance_metrics = [
        ("cash_value", "Cash and cash equivalents"),
        ("short_debt_value", "Short-term debt"),
        ("long_debt_value", "Long-term debt"),
        ("shares_value", "Shares outstanding"),
    ]

    for key, label in balance_metrics:
        item = summary.get(key, {})

        if item.get("value") is None:
            add(
                "Warning",
                label,
                "No usable value was found. Do not treat this as zero.",
            )

    debt_info = summary.get("debt_value", {})

    if debt_info.get("value") is None:
        add(
            "Warning",
            "Total debt",
            str(
                debt_info.get("status")
                or "Total debt could not be reliably calculated."
            ),
        )

    # Check balance-sheet reporting dates.
    date_items = [
        ("Cash", summary.get("cash_value", {})),
        ("Short-term debt", summary.get("short_debt_value", {})),
        ("Long-term debt", summary.get("long_debt_value", {})),
        ("Shares", summary.get("shares_value", {})),
    ]

    available_dates = [
        (label, item.get("end"))
        for label, item in date_items
        if item and item.get("end")
    ]

    distinct_dates = {
        date for _, date in available_dates
    }

    if len(distinct_dates) > 1:
        date_details = "; ".join(
            f"{label}: {date}"
            for label, date in available_dates
        )

        add(
            "Info",
            "Balance-sheet dates",
            (
                "Available balance-sheet items do not all share the "
                "same reporting date. Verify before using them together. "
                f"{date_details}"
            ),
        )

    # Share-count definition warning.
    shares_info = summary.get("shares_value", {})

    if shares_info.get("value") is not None:
        add(
            "Info",
            "Shares outstanding",
            (
                "SEC shares outstanding is a point-in-time figure. "
                "Verify the share-count definition and date before "
                "using it for per-share valuation."
            ),
        )

    if not checks:
        add(
            "Pass",
            "Data quality",
            "No missing core metrics or obvious period-matching "
            "issues were detected.",
        )

    return checks
