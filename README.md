# Technology Stock Valuation Lab — v1.1 validation-first prototype

Streamlit app for SEC-sourced financial data and an illustrative valuation model.

## Validation status
This app does **not** label all retrieved data as "verified". SEC Company Facts values are marked **SEC-sourced — filing/period review required** until checked against the relevant filing. Ratios and DCF results are **derived / illustrative**, not verified facts. Successful deployment does not prove the model is correct.

## Files
- `app.py`: interface
- `valuation_lab/sec_data.py`: ticker lookup and SEC Company Facts extraction
- `valuation_lab/metrics.py`: annual-period selection, aligned ratios and quality checks
- `valuation_lab/dcf.py`: DCF scenario model with guardrails
- `tests/test_model.py`: unit tests
- `requirements.txt`: cloud dependencies

## Deploy after review
1. Upload the **contents** of this folder to a GitHub repository, not the ZIP itself.
2. Visit https://share.streamlit.io and connect the repository.
3. Main file path: `app.py`.
4. In Streamlit app secrets, add `SEC_USER_AGENT = "TechnologyStockValuationLab contact your-real-email@example.com"` and replace the example with a real contact address.
5. Deploy. SEC requests may be rate-limited.

## Data handling
- Uses the SEC official ticker list and Company Facts endpoint.
- Supports common US-GAAP tags; missing facts remain missing.
- Annual income/cash-flow facts are filtered to FY/10-K and approximately full-year duration.
- Ratios require aligned periods. ROE requires current and previous annual equity.
- Operating cash flow minus capex is labelled an **FCF proxy**, not normalized FCFF.
- DCF is blocked if positive, aligned FCF proxy or shares are unavailable.
- Share count, cash and debt may require issuer-specific review. Price is manually entered; no live quote feed is configured.

## Known limitations
Tag mappings are incomplete for every issuer. Confirm facts in source filings. Fiscal-year boundaries, amended filings, units, debt definitions, restricted cash, leases, minority interests, marketable securities, dilution and stock-based compensation may require issuer-specific review. No backtest, live quote API, scheduler or notification system is included. Not financial advice.

## Optional local run
Python 3.10+ is only needed for local use; it is not required on your Mac if you use Streamlit Community Cloud.
```bash
pip install -r requirements.txt
streamlit run app.py
```
