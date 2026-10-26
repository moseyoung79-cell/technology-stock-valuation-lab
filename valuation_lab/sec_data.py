
import os
import requests
import pandas as pd

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

TAGS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "Revenues",
    ],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "equity": ["StockholdersEquity"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "short_debt": [
        "ShortTermBorrowings",
        "ShortTermDebtCurrent",
        "LongTermDebtCurrent",
    ],
    "long_debt": ["LongTermDebtNoncurrent", "LongTermDebt"],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities"
    ],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "shares": ["EntityCommonStockSharesOutstanding"],
}


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

    if (
        not user_agent
        or "example.com" in user_agent
        or "your-real-email" in user_agent
    ):
        raise RuntimeError(
            "Please configure SEC_USER_AGENT with an app name "
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
    response = requests.get(url, headers=headers(), timeout=45)
    response.raise_for_status()
    return response.json(), url


def _tag_records(facts, metric):
    records = []

    for tag in TAGS[metric]:
        fact = (
            facts.get("facts", {})
            .get("us-gaap", {})
            .get(tag)
        )

        if not fact:
            continue

        for unit, entries in fact.get("units", {}).items():
            for entry in entries:
                if (
                    entry.get("form") != "10-K"
                    or not entry.get("end")
                    or not entry.get("filed")
                ):
                    continue

                start = entry.get("start")

                if metric in (
                    "revenue",
                    "operating_income",
                    "net_income",
                    "operating_cash_flow",
                    "capex",
                ):
                    if not start or entry.get("fp") != "FY":
                        continue

                    days = (
                        pd.Timestamp(entry["end"])
                        - pd.Timestamp(start)
                    ).days

                    if not 300 <= days <= 380:
                        continue

                records.append({
                    "end": entry["end"],
                    "start": start,
                    "value": float(entry["val"]),
                    "filed": entry["filed"],
                    "fy": entry.get("fy"),
                    "tag": tag,
                    "unit": unit,
                    "form": entry.get("form"),
                    "fp": entry.get("fp"),
                })

    columns = [
        "end", "start", "value", "filed", "fy",
        "tag", "unit", "form", "fp",
    ]

    if not records:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(records)
    df = df.sort_values(["end", "filed", "tag"])

    # Keep one fact per period end. This is a preliminary
    # extraction rule, not a substitute for filing review.
    df = df.drop_duplicates(
        subset=["end"], keep="last"
    )

    return df.sort_values("end").reset_index(drop=True)


def extract_all(facts):
    return {
        metric: _tag_records(facts, metric)
        for metric in TAGS
    }
