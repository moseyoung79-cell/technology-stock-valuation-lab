
from __future__ import annotations

from typing import Any

import pandas as pd


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def _empty_frame(df: Any) -> bool:
    """Return True when a metric DataFrame is missing or empty."""
    return not isinstance(df, pd.DataFrame) or df.empty


def _as_number(value: Any) -> float | None:
    """Convert a value to float, preserving missing values as None."""
    if value is None or pd.isna(value):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _sort_records(df: pd.DataFrame) -> pd.DataFrame:
    """Sort records by period end and filing date."""
    if _empty_frame(df):
        return pd.DataFrame()

    result = df.copy()

    if "end" in result.columns:
        result["end"] = pd.to_datetime(result["end"], errors="coerce")

    if "filed" in result.columns:
        result["filed"] = pd.to_datetime(result["filed"], errors="coerce")

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
    """
    Return the latest available record.

    If end is provided, only records with that period-end date are eligible.
    """
    if _empty_frame(df):
        return None

    result = _sort_records(df)

    if end is not None and "end" in result.columns:
        target_end = pd.to_datetime(end, errors="coerce")
        result = result[result["end"] == target_end]

    if result.empty:
        return None

    row = result.iloc[-1]
    return row.to_dict()


def _latest_annual(
    df: pd.DataFrame | None,
    end: str | pd.Timestamp | None = None,
) -> dict[str, Any] | None:
    """Return the latest annual record for a flow metric."""
    if _empty_frame(df):
        return None

    result = _sort_records(df)

    if "form" in result.columns:
        result = result[result["form"].astype(str).str.upper() == "10-K"]

    if "start" in result.columns and "end" in result.columns:
        starts = pd.to_datetime(result["start"], errors="coerce")
        ends = pd.to_datetime(result["end"], errors="coerce")
        duration_days = (ends - starts).dt.days

        # Annual income/cash-flow records should generally cover
        # approximately one fiscal year.
        result = result[
            duration_days.between(300, 380, inclusive="both")
        ]

    if end is not None and "end" in result.columns:
        target_end = pd.to_datetime(end, errors="coerce")
        result = result[result["end"] == target_end]

    if result.empty:
        return None

    return result.iloc[-1].to_dict()


def _record_value(record: dict[str, Any] | None) -> float | None:
    if record is None:
        return None

    return _as_number(record.get("value"))


def _record_date(record: dict[str, Any] | None) -> str | None:
    if record is None:
        return None

    value = record.get("end")
    if value is None or pd.isna(value):
        return None

    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _record_info(
    record: dict[str, Any] | None,
    definition: str,
    *,
    status: str | None = None,
) -> dict[str, Any]:
    """Return a consistent result structure for a metric."""
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

    def format_date(field: str) -> str | None:
        raw = record.get(field)
        if raw is None or pd.isna(raw):
            return None
        return pd.to_datetime(raw).strftime("%Y-%m-%d")

    return {
        "value": value,
        "end": format_date("end"),
        "start": format_date("start"),
        "filed": format_date("filed"),
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
    *,
    start: str | None = None,
) -> dict[str, Any]:
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
    """
    Select the latest available point-in-time balance-sheet record.

    Unlike annual flow metrics, balance-sheet values represent a date,
    not a duration.
    """
    record = _latest_record(metrics.get(metric_name))
    return _record_info(record, definition)


def _balance_items_at_date(
    metrics: dict[str, pd.DataFrame],
    metric_names: list[str],
) -> tuple[str | None, dict[str, dict[str, Any] | None]]:
    """
    Find the most recent date shared by the requested balance-sheet metrics.

    This helper is for calculations that genuinely require a common date.
    Individual values are still returned separately elsewhere.
    """
    available_dates: dict[str, set[str]] = {}

    for name in metric_names:
        df = metrics.get(name)

        if _empty_frame(df) or "end" not in df.columns:
            available_dates[name] = set()
            continue

        ends = pd.to_datetime(df["end"], errors="coerce")
        available_dates[name] = {
            date.strftime("%Y-%m-%d")
            for date in ends.dropna().unique()
        }

    if not available_dates:
        return None, {}

    common_dates = set.intersection(*available_dates.values())

    if not common_dates:
        return None, {}

    common_end = max(common_dates)

    records = {
        name: _latest_record(metrics.get(name), end=common_end)
        for name in metric_names
    }

    return common_end, records


def _same_period(
    first: dict[str, Any] | None,
    second: dict[str, Any] | None,
) -> bool:
    """Check whether two records have the same start and end dates."""
    if first is None or second is None:
        return False

    first_end = _record_date(first)
    second_end = _record_date(second)

    if not first_end or first_end != second_end:
        return False

    first_start = first.get("start")
    second_start = second.get("start")

    if first_start is None or second_start is None:
        return False

    first_start = pd.to_datetime(first_start, errors="coerce")
    second_start = pd.to_datetime(second_start, errors="coerce")

    if pd.isna(first_start) or pd.isna(second_start):
        return False

    return first_start == second_start


# ---------------------------------------------------------------------
# Main financial summary
# ---------------------------------------------------------------------

def summarize(metrics: dict[str, pd.DataFrame]) -> dict[str, dict[str, Any]]:
    """
    Summarize SEC company facts for financial analysis.

    Flow metrics are taken from annual 10-K periods.
    Balance-sheet metrics are selected independently by their latest date.

    Missing values remain None. They are never silently replaced with zero.
    """
    metrics = metrics or {}

    revenue_record = _latest_annual(metrics.get("revenue"))
    operating_income_record = _latest_annual(
        metrics.get("operating_income")
    )
    net_income_record = _latest_annual(metrics.get("net_income"))
    operating_cash_flow_record = _latest_annual(
        metrics.get("operating_cash_flow")
    )
    capex_record = _latest_annual(metrics.get("capex"))
    equity_record = _latest_record(metrics.get("equity"))

    revenue = _record_value(revenue_record)
    operating_income = _record_value(operating_income_record)
    net_income = _record_value(net_income_record)
    operating_cash_flow = _record_value(operating_cash_flow_record)
    capex = _record_value(capex_record)
    equity = _record_value(equity_record)

    revenue_end = _record_date(revenue_record)
    operating_income_end = _record_date(operating_income_record)
    net_income_end = _record_date(net_income_record)
    ocf_end = _record_date(operating_cash_flow_record)
    capex_end = _record_date(capex_record)

    # -------------------------------------------------------------
    # Revenue and profitability
    # -------------------------------------------------------------

    revenue_info = _record_info(
        revenue_record,
        "Latest annual revenue reported in SEC Company Facts.",
    )

    operating_income_info = _record_info(
        operating_income_record,
        "Latest annual operating income reported in SEC Company Facts.",
    )

    net_income_info = _record_info(
        net_income_record,
        "Latest annual net income reported in SEC Company Facts.",
    )

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

    # -------------------------------------------------------------
    # Return on equity
    # -------------------------------------------------------------

    roe = None
    roe_status = "unavailable: required annual data not found"
    roe_end = None

    if (
        net_income_record is not None
        and equity_record is not None
        and net_income is not None
        and equity is not None
        and net_income_end is not None
        and equity_end_matches = False
    ):
        # This branch is intentionally not used; period matching is
        # performed below using explicit date comparisons.
        pass

    if net_income_record is not None and equity_record is not None:
        annual_equity_end = _record_date(equity_record)

        if net_income_end and annual_equity_end == net_income_end:
            equity_history = _sort_records(metrics.get("equity"))

            if (
                not equity_history.empty
                and "end" in equity_history.columns
            ):
                equity_history = equity_history[
                    equity_history["end"] < pd.to_datetime(net_income_end)
                ]

                if not equity_history.empty:
                    previous_equity_record = equity_history.iloc[-1].to_dict()
                    previous_equity = _record_value(previous_equity_record)

                    if (
                        previous_equity is not None
                        and equity is not None
                    ):
                        average_equity = (previous_equity + equity) / 2

                        if average_equity != 0 and net_income is not None:
                            roe = net_income / average_equity
                            roe_status = "available"
                            roe_end = net_income_end
                        else:
                            roe_status = (
                                "unavailable: average equity is zero "
                                "or net income is missing"
                            )
                else:
                    roe_status = (
                        "unavailable: prior-period equity not found"
                    )
            else:
                roe_status = "unavailable: equity history not found"
        else:
            roe_status = (
                "unavailable: net income and ending equity dates do not match"
            )

    # -------------------------------------------------------------
    # Free cash flow proxy
    # -------------------------------------------------------------

    if (
        operating_cash_flow_record is not None
        and capex_record is not None
        and _same_period(
            operating_cash_flow_record,
            capex_record,
        )
        and operating_cash_flow is not None
        and capex is not None
    ):
        # SEC capex is commonly reported as a positive cash outflow.
        # Subtract its absolute value to avoid sign inconsistencies.
        fcf_proxy = operating_cash_flow - abs(capex)
        fcf_status = "available"
        fcf_end = ocf_end
        fcf_start = (
            pd.to_datetime(
                operating_cash_flow_record["start"]
            ).strftime("%Y-%m-%d")
        )
    else:
        fcf_proxy = None
        fcf_status = (
            "unavailable: operating cash flow and capex must cover "
            "the same annual reporting period"
        )
        fcf_end = None
        fcf_start = None

    # -------------------------------------------------------------
    # Balance-sheet items: select independently
    # -------------------------------------------------------------

    cash_info = _latest_balance_item(
        metrics,
        "cash",
        "Latest reported cash and cash equivalents. "
        "May not include all short-term investments.",
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
        "Latest reported point-in-time common shares outstanding. "
        "This is not necessarily diluted weighted-average shares.",
    )

    # Debt is only calculated when both debt categories are available
    # and their reporting dates match. An absent category is not
    # silently interpreted as zero.
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
            "Short-term debt plus long-term debt, only when both "
            "categories are available for the same reporting date."
        ),
        "status": debt_status,
    }

    # Common date is provided for diagnostics only. It does not prevent
    # individual balance-sheet values from being returned.
    balance_sheet_as_of = None
    dates = [
        cash_info.get("end"),
        debt_end,
        shares_info.get("end"),
    ]
    valid_dates = [date for date in dates if date is not None]

    if valid_dates and len(set(valid_dates)) == 1:
        balance_sheet_as_of = valid_dates[0]

    # -------------------------------------------------------------
    # Return a consistent structure for the app
    # -------------------------------------------------------------

    return {
        "revenue": revenue_info,
        "operating_income": operating_income_info,
        "net_income": net_income_info,
        "equity": _record_info(
            equity_record,
            "Latest reported stockholders' equity.",
        ),
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
            revenue_end if revenue_end == operating_income_end else None,
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
            "Common reporting date for cash, total debt, and shares, "
            "when all three are available for the same date.",
            (
                "available"
                if balance_sheet_as_of is not None
                else "different reporting dates or incomplete data"
            ),
        ),
    }


# ---------------------------------------------------------------------
# Data quality checks
# ---------------------------------------------------------------------

def quality_checks(
    metrics: dict[str, pd.DataFrame],
    summary: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    """
    Produce readable data-quality warnings for the app.

    This function does not alter financial values or assume missing
    values are zero.
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

    # Check whether the principal SEC metrics were found.
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

    # Derived profitability ratios.
    for key, label in (
        ("ros", "Return on sales"),
        ("operating_margin", "Operating margin"),
        ("roe", "ROE"),
        ("fcf_proxy", "FCF proxy"),
    ):
        item = summary.get(key, {})
        if item.get("value") is None:
            add(
                "Warning",
                label,
                str(item.get("status") or "Metric is unavailable."),
            )

    # Balance-sheet fields are checked independently.
    for key, label in (
        ("cash_value", "Cash and cash equivalents"),
        ("short_debt_value", "Short-term debt"),
        ("long_debt_value", "Long-term debt"),
        ("shares_value", "Shares outstanding"),
    ):
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

    # Compare available balance-sheet dates.
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

    distinct_dates = {date for _, date in available_dates}

    if len(distinct_dates) > 1:
        date_details = "; ".join(
            f"{label}: {date}"
            for label, date in available_dates
        )
        add(
            "Info",
            "Balance-sheet dates",
            (
                "Available balance-sheet items do not all share the same "
                f"reporting date. Verify before using them together. {date_details}"
            ),
        )

    # Shares are point-in-time shares outstanding, not necessarily
    # the diluted weighted-average shares used for EPS.
    shares_info = summary.get("shares_value", {})
    if shares_info.get("value") is not None:
        add(
            "Info",
            "Shares outstanding",
            (
                "SEC shares outstanding is a point-in-time figure. "
                "Verify the share-count definition and date before using "
                "it in per-share valuation."
            ),
        )

    if not checks:
        add(
            "Pass",
            "Data quality",
            "No missing core metrics or obvious period-matching issues detected.",
        )

    return checks
