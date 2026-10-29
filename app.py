
    # -------------------------------------------------------------
    # Return on equity
    # -------------------------------------------------------------

    roe = None
    roe_status = "unavailable: required annual data not found"
    roe_end = None

    if net_income_record is not None and net_income is not None and net_income_end:
        equity_history = _sort_records(metrics.get("equity"))

        if not equity_history.empty and "end" in equity_history.columns:
            # Match ending equity to the net-income fiscal year-end.
            equity_history = equity_history[
                equity_history["end"] <= pd.to_datetime(net_income_end)
            ]

            ending_equity_record = _latest_record(
                equity_history,
                end=net_income_end,
            )

            prior_equity_record = None

            if ending_equity_record is not None:
                prior_records = equity_history[
                    equity_history["end"] < pd.to_datetime(net_income_end)
                ]

                if not prior_records.empty:
                    prior_equity_record = prior_records.iloc[-1].to_dict()

            ending_equity = _record_value(ending_equity_record)
            prior_equity = _record_value(prior_equity_record)

            if ending_equity is None or prior_equity is None:
                roe_status = (
                    "unavailable: beginning or ending equity is missing"
                )
            else:
                average_equity = (prior_equity + ending_equity) / 2

                if average_equity == 0:
                    roe_status = "unavailable: average equity is zero"
                else:
                    roe = net_income / average_equity
                    roe_status = "available"
                    roe_end = net_income_end
        else:
            roe_status = "unavailable: equity history not found"
