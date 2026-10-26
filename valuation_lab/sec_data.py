
import os
import requests
import pandas as pd

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

# Flow metrics cover a reporting period; balance-sheet metrics
# represent a point in time. Keep those rules separate.
FLOW_METRICS = {
    "revenue",
    "operating_income",
    "net_income",
    "operating_cash_flow",
    "capex",
}

TAGS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "Revenues",
    ],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "equity": ["StockholdersEquity"],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "short_debt": [
        "ShortTermBorrowings",
        "ShortTermDebtCurrent",
        "LongTermDebtCurrent",
    ],
    "long_debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
    ],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities"
    ],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment"
    ],
    "shares": ["EntityCommonStockSharesOutstanding"],
}

VALID_FORMS = {"10-K", "10-Q"}


def headers():
    user_agent = os.getenv("SEC_USER_AGENT", "").strip()

    if not user_agent:
        try:
            import streamlit as st
            user_agent = str(
                st.secrets.get("SEC_USER_AGENT", "")
            ).strip()
        except Exception:
            user_agent = ""

    if not user_agent or "@" not in user_agent:
        raise RuntimeError(
            "Configure SEC_USER_AGENT with an app name "
            "and a real contact email in Streamlit Secrets."
        )

    return {
        "User-Agent": user_agent,
        "Accept-Encoding": "gzip, deflate",
    }


def get_tickers():
    response = requests.get(
        TICKERS_URL, headers=headers(), timeout=30
    )
    response.raise_for_status()

    return {
        str(item["ticker"]).upper(): {
            "cik": str(item["cik_str"]).zfill(10),
            "name": item["title"],
        }
        for item in response.json().values()
        if item.get("ticker")
    }


def get_facts(cik):
    url = FACTS_URL.format(cik=str(cik).zfill(10))
    response = requests.get(
        url, headers=headers(), timeout=45
    )
    response.raise_for_status()
    return response.json(), url


def _tag_records(facts, metric):
    """
    Extract SEC facts without silently mixing alternate tags.

    Flow metrics: annual 10-K periods only, approximately one year.
    Instant metrics: 10-K/10-Q point-in-time facts.
    Raw value, unit, tag, period and filing date are retained.

    This is a preliminary extraction rule, not filing-level
    verification. Company-specific tag mapping may be necessary.
    """
    us_gaap = facts.get("facts", {}).get("us-gaap", {})
    records = []
    seen_periods = set()

    for tag in TAGS[metric]:
        fact = us_gaap.get(tag)
        if not fact:
            continue

        for unit, entries in fact.get("units", {}).items():
            for entry in entries:
                form = entry.get("form")
                end = entry.get("end")
                filed = entry.get("filed")
                start = entry.get("start")

                if (
                    form not in VALID_FORMS
                    or not end
                    or not filed
                ):
                    continue

                if metric in FLOW_METRICS:
                    if form != "10-K" or not start:
                        continue

                    days = (
                        pd.Timestamp(end) - pd.Timestamp(start)
                    ).days

                    if not 300 <= days <= 380:
                        continue

                # Use the first available tag in the declared
                # priority list for each period end.
                period_key = (end, unit)
                if period_key in seen_periods:
                    continue

                records.append({
                    "end": end,
                    "start": start,
                    "value": float(entry["val"]),
                    "filed": filed,
                    "fy": entry.get("fy"),
                    "fp": entry.get("fp"),
                    "form": form,
                    "tag": tag,
                    "unit": unit,
                    "accn": entry.get("accn"),
                    "frame": entry.get("frame"),
                    "status": "SEC-sourced; filing verification required",
                })
                seen_periods.add(period_key)

    columns = [
        "end", "start", "value", "filed", "fy", "fp",
        "form", "tag", "unit", "accn", "frame", "status",
    ]

    if not records:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(records)
    return df.sort_values(
        ["end", "filed"]
    ).reset_index(drop=True)


def extract_all(facts):
    return {
        metric: _tag_records(facts, metric)
        for metric in TAGS
    }
