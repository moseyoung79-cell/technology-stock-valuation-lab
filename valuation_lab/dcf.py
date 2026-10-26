
def scenarios(fcf, shares, cash, debt, price, growths, waccs, terminal_growth):
    """Illustrative five-year DCF using an annual FCF proxy."""

    if fcf is None or fcf <= 0:
        return {"error": "No positive, period-aligned FCF proxy. DCF blocked."}

    if shares is None or shares <= 0:
        return {"error": "Shares outstanding unavailable. DCF blocked."}

    if any(w <= terminal_growth for w in waccs.values()):
        return {"error": "Terminal growth must be below WACC in every scenario."}

    results = {}

    for scenario in ("Bear", "Base", "Bull"):
        growth = growths[scenario]
        wacc = waccs[scenario]

        cashflows = []
        pv_forecast = 0.0
        current_fcf = fcf

        for year in range(1, 6):
            current_fcf *= 1 + growth
            cashflows.append(current_fcf)
            pv_forecast += current_fcf / ((1 + wacc) ** year)

        terminal_value = (
            cashflows[-1] * (1 + terminal_growth)
            / (wacc - terminal_growth)
        )
        pv_terminal = terminal_value / ((1 + wacc) ** 5)

        enterprise_value = pv_forecast + pv_terminal
        equity_value = enterprise_value + (cash or 0) - (debt or 0)
        intrinsic_per_share = equity_value / shares

        margin_of_safety = None
        if price is not None and price > 0 and intrinsic_per_share > 0:
            margin_of_safety = 1 - price / intrinsic_per_share

        results[scenario] = {
            "growth": growth,
            "wacc": wacc,
            "terminal_growth": terminal_growth,
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "intrinsic_per_share": intrinsic_per_share,
            "margin_of_safety": margin_of_safety,
            "pv_forecast": pv_forecast,
            "pv_terminal": pv_terminal,
            "status": "Illustrative DCF; FCF proxy and assumptions require verification",
        }

    return results
