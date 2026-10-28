            for name in order:
                d = dcf_result[name]
                rows.append({
                    "Scenario": name, "FCF growth": d["growth"], "WACC": d["wacc"], "Terminal growth": d["terminal_growth"],
                    "Enterprise value ($B)": d["enterprise_value"] / 1e9, "Equity value ($B)": d["equity_value"] / 1e9,
                    "Intrinsic value / share ($)": d["intrinsic_per_share"], "Current price ($)": price,
                    "Margin of safety": d["margin_of_safety"], "PV forecast ($B)": d["pv_forecast"] / 1e9,
                    "PV terminal value ($B)": d["pv_terminal"] / 1e9,
                })
            dcf_df = pd.DataFrame(rows)
            st.dataframe(dcf_df.style.format({
                "FCF growth": "{:.1%}", "WACC": "{:.1%}", "Terminal growth": "{:.1%}",
                "Enterprise value ($B)": "${:,.2f}", "Equity value ($B)": "${:,.2f}",
                "Intrinsic value / share ($)": "${:,.2f}", "Current price ($)": "${:,.2f}",
                "Margin of safety": "{:.1%}", "PV forecast ($B)": "${:,.2f}", "PV terminal value ($B)": "${:,.2f}",
            }), use_container_width=True, hide_index=True)

            # Reverse DCF: solve for the constant annual five-year FCF growth rate
            # that makes model equity value per share equal to the entered market price.
            st.markdown("### Reverse DCF · What growth is priced in?")
            st.write("This estimates the constant annual FCF growth rate over the next five years needed for the model value to equal the current share price, holding WACC and terminal growth constant. It is a model-implied assumption, not a forecast.")
            reverse_wacc = st.selectbox("WACC for reverse DCF", options=[bw, mw, uw], index=1, format_func=lambda x: f"{x:.1%}")
            target_equity_value = price * shares
            target_enterprise_value = target_equity_value - cash + debt

            def dcf_ev_for_growth(growth, discount_rate, terminal_rate):
                forecast = [fcf * ((1 + growth) ** year) for year in range(1, 6)]
                pv_forecast = sum(cf / ((1 + discount_rate) ** year) for year, cf in enumerate(forecast, start=1))
                terminal = forecast[-1] * (1 + terminal_rate) / (discount_rate - terminal_rate)
                return pv_forecast + terminal / ((1 + discount_rate) ** 5)

            if reverse_wacc <= tg:
                st.warning("Reverse DCF WACC must be greater than terminal growth.")
            else:
                low, high = -0.95, 5.0
                low_ev = dcf_ev_for_growth(low, reverse_wacc, tg)
                high_ev = dcf_ev_for_growth(high, reverse_wacc, tg)
                if target_enterprise_value < low_ev or target_enterprise_value > high_ev:
                    st.warning("The target price is outside the model's supported growth search range (-95% to 500%). Reverse DCF cannot find a reliable solution with these inputs.")
                else:
                    for _ in range(150):
                        mid = (low + high) / 2
                        if dcf_ev_for_growth(mid, reverse_wacc, tg) < target_enterprise_value:
                            low = mid
                        else:
                            high = mid
                    implied_growth = (low + high) / 2
                    rc1, rc2, rc3 = st.columns(3)
                    rc1.metric("Market price entered", f"${price:,.2f}")
                    rc2.metric("Reverse DCF WACC", f"{reverse_wacc:.1%}")
                    rc3.metric("Implied 5-year FCF growth", f"{implied_growth:.1%}")
                    base_growth = mg
                    diff = implied_growth - base_growth
                    st.caption(f"Implied growth is {diff:+.1%} points versus your Base-case FCF growth assumption of {base_growth:.1%}.")
                    if implied_growth > base_growth + 0.10:
                        st.warning("The current price requires materially stronger five-year FCF growth than your Base case under these assumptions.")
                    elif implied_growth < base_growth - 0.05:
                        st.info("The current price can be supported by a lower growth rate than your Base case under these assumptions. Verify WACC, FCF, cash, debt and shares before drawing conclusions.")
                    else:
                        st.info("The implied growth rate is relatively close to your Base-case assumption. Small changes in assumptions can still materially change the valuation.")

            # Sensitivity grid, holding terminal growth and balance-sheet inputs constant.
            st.markdown("### Growth-rate / WACC sensitivity")
            st.write("Each cell is estimated intrinsic value per share. Terminal growth, cash, debt and shares are held constant; only five-year FCF growth and WACC change.")
            growth_values = [round(float(x), 4) for x in pd.Series([sensitivity_growth_min + i * (sensitivity_growth_max - sensitivity_growth_min) / 5 for i in range(6)]).tolist()]
            wacc_values = [round(float(x), 4) for x in pd.Series([sensitivity_wacc_min + i * (sensitivity_wacc_max - sensitivity_wacc_min) / 4 for i in range(5)]).tolist()]
            valid_wacc_values = [w for w in wacc_values if w > tg]
            if not valid_wacc_values:
                st.warning("All sensitivity WACC values must be greater than terminal growth.")
            else:
                sensitivity_rows = []
                for growth in growth_values:
                    row = {"FCF growth": f"{growth:.1%}"}
                    for wacc in valid_wacc_values:
                        ev = dcf_ev_for_growth(growth, wacc, tg)
                        equity = ev + cash - debt
                        row[f"WACC {wacc:.1%}"] = equity / shares
                    sensitivity_rows.append(row)
                sensitivity_df = pd.DataFrame(sensitivity_rows)
                value_columns = [c for c in sensitivity_df.columns if c != "FCF growth"]
                st.dataframe(sensitivity_df.style.format({c: "${:,.2f}" for c in value_columns}), use_container_width=True, hide_index=True)
                st.caption("Sensitivity results are illustrative, not price targets. The model assumes a constant FCF growth rate for five years followed by perpetual terminal growth.")

            st.caption("All assumptions and balance-sheet inputs require independent verification. A DCF should not be tuned merely to match the market price.")
    except Exception as exc:
        st.error(f"DCF calculation failed: {exc}")

st.subheader("Retrieved annual SEC facts")
if not metrics:
    st.info("No annual metric tables were returned.")
else:
    tabs = st.tabs(list(metrics.keys()))
    for tab, (metric_name, metric_df) in zip(tabs, metrics.items()):
        with tab:
            if metric_df.empty:
                st.warning("No matching annual fact was found. No value has been imputed.")
            else:
                display_df = metric_df.sort_values("end", ascending=False) if "end" in metric_df.columns else metric_df
                st.dataframe(display_df, use_container_width=True, hide_index=True)

annual_rows = []
for metric_name, metric_df in metrics.items():
    for _, row in metric_df.iterrows():
        annual_rows.append({"metric": metric_name, **row.to_dict()})
annual_df = pd.DataFrame(annual_rows)
st.download_button(label="Download SEC facts CSV", data=annual_df.to_csv(index=False).encode("utf-8"), file_name=f"{result_data['ticker']}_sec_facts.csv", mime="text/csv")
st.divider()
st.caption("Technology Stock Valuation Lab · Educational prototype · Not investment advice")
