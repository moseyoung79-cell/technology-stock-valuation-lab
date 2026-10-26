
import pandas as pd


def latest(df):
    if df is None or df.empty:
        return None

    row = df.sort_values(["end", "filed"]).iloc[-1]
    return row.to_dict()


def summarize(metrics):
    out = {key: latest(value) for key, value in metrics.items()}

    revenue = out.get("revenue")
    net_income = out.get("net_income")
    operating_income = out.get("operating_income")

    # ROS: net profit margin. Periods must match.
    if (
        revenue and net_income
        and revenue["end"] == net_income["end"]
        and float(revenue["value"]) != 0
    ):
        out["ros"] = {
            "value": float(net_income["value"]) / float(revenue["value"]),
            "end": revenue["end"],
            "status": "Derived; matching annual periods",
            "definition": "Net income / revenue",
        }
    else:
        out["ros"] = {
            "value": None,
            "status": "Unavailable: periods do not match",
            "definition": "Net income / revenue",
        }

    # Operating margin is reported separately from ROS.
    if (
        revenue and operating_income
        and revenue["end"] == operating_income["end"]
        and float(revenue["value"]) != 0
    ):
        out["operating_margin"] = {
            "value": float(operating_income["value"]) / float(revenue["value"]),
            "end": revenue["end"],
            "status": "Derived; matching annual periods",
            "definition": "Operating income / revenue",
        }
    else:
        out["operating_margin"] = {
            "value": None,
            "status": "Unavailable: periods do not match",
            "definition": "Operating income / revenue",
        }

    # ROE requires net income and current/prior year-end equity.
    roe = None
    equity = metrics.get("equity", pd.DataFrame())

    if (
        net_income
        and out.get("equity")
        and net_income["end"] == out["equity"]["end"]
        and equity is not None
        and not equity.empty
    ):
        previous = equity[
            equity["end"].astype(str) < str(out["equity"]["end"])
        ].sort_values("end")

        if not previous.empty:
            average_equity = (
                float(previous.iloc[-1]["value"])
                + float(out["equity"]["value"])
            ) / 2

            if average_equity != 0:
                roe = float(net_income["value"]) / average_equity

    out["roe"] = {
        "value": roe,
        "status": (
            "Derived; review source periods"
            if roe is not None
            else "Unavailable: aligned net income and two year-end equity values required"
        ),
        "definition": "Net income / average shareholders' equity",
    }

    # FCF proxy: annual operating cash flow less absolute capex.
    ocf = out.get("operating_cash_flow")
    capex = out.get("capex")

    fcf = None
    if ocf and capex and ocf["end"] == capex["end"]:
        fcf = float(ocf["value"]) - abs(float(capex["value"]))

    out["fcf_proxy"] = {
        "value": fcf,
        "end": ocf["end"] if fcf is not None else None,
        "status": (
            "Derived proxy; not normalized FCFF"
            if fcf is not None
            else "Unavailable: aligned annual cash flow and capex required"
        ),
    }

    return out


def quality_checks(metrics, summary):
    checks = []

    for name, df in metrics.items():
        if df is None or df.empty:
            checks.append({
                "check": f"{name}: data availability",
                "status": "MISSING",
                "detail": "No matching annual fact found.",
            })
        else:
            row = latest(df)
            checks.append({
                "check": f"{name}: SEC fact retrieved",
                "status": "REVIEW REQUIRED",
                "detail": (
                    f"Tag {row.get('tag')}; unit {row.get('unit')}; "
                    f"period end {row.get('end')}; filed {row.get('filed')}. "
                    "Verify in the source filing."
                ),
            })

    for name in ("ros", "operating_margin", "roe", "fcf_proxy"):
        item = summary[name]
        checks.append({
            "check": name,
            "status": "DERIVED" if item.get("value") is not None else "UNAVAILABLE",
            "detail": item.get("status", ""),
        })

    return pd.DataFrame(checks)
