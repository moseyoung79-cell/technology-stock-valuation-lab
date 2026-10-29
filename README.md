# Technology Stock Valuation Lab

**An interactive financial analysis and valuation application built with Python and Streamlit.**

[**Live Demo**](https://technology-stock-valuation-lab-3snhk4jyatuueuexuvrappq.streamlit.app/) · [**GitHub Repository**](https://github.com/moseyoung79-cell/technology-stock-valuation-lab)

## Overview

Technology Stock Valuation Lab is a personal project that explores how financial data, valuation models, and interactive tools can support structured investment analysis.

The application retrieves financial data from the SEC Company Facts API and uses it as an input for financial metric analysis and illustrative valuation models.

The project focuses on three areas:

- **Financial data analysis:** Extracting and organizing company financial information.
- **Valuation modelling:** Exploring intrinsic value estimates under different assumptions.
- **Data quality and transparency:** Highlighting data limitations and distinguishing reported financial facts from model-derived estimates.

## Key Features

- **SEC financial data integration** — Retrieve company financial facts and organize relevant financial information.
- **DCF valuation** — Explore valuation outcomes using Bear, Base, and Bull scenarios.
- **Reverse DCF analysis** — Examine the assumptions implied by a market price.
- **Sensitivity analysis** — Understand how changes in key assumptions affect estimated value.
- **Data quality checks** — Highlight potential limitations in retrieved financial data.
- **Financial data export** — Support further analysis through downloadable tables, where available in the application.

## Technology Stack

- **Language:** Python
- **Application:** Streamlit
- **Data processing:** Pandas
- **Financial data source:** SEC Company Facts API
- **Testing:** Pytest

## How It Works

1. Select a publicly traded company.
2. Retrieve available financial data from SEC filings.
3. Review extracted financial metrics and data quality checks.
4. Explore valuation scenarios and sensitivity to key assumptions.
5. Compare model outputs with market-price assumptions.

Some inputs, including the current share price, may require manual entry. Data availability and reporting periods can vary by company.

## Project Structure

```text
.
├── app.py
├── valuation_lab/
│   ├── sec_data.py
│   ├── metrics.py
│   └── dcf.py
├── tests/
│   └── test_model.py
├── requirements.txt
└── README.md
```

- `app.py` — Streamlit user interface
- `sec_data.py` — SEC company lookup and financial data extraction
- `metrics.py` — Financial metric calculations, reporting-period selection, and quality checks
- `dcf.py` — DCF scenario modelling and related valuation calculations
- `test_model.py` — Unit tests for model logic

## Data Quality and Limitations

This application is an analytical prototype, not a source of verified investment advice.

- SEC-sourced figures should be checked against the relevant filing and reporting period before use.
- Financial ratios and valuation outputs are calculated estimates, not reported facts.
- DCF results depend on assumptions about future cash flows, growth, discount rates, and terminal value.
- A successful deployment or passing test suite does not, by itself, establish that every financial calculation is correct.
- The application should not be used as the sole basis for investment decisions.

## About This Project

This project combines financial analysis, Python-based application development, and AI-assisted problem-solving.

It is an ongoing learning project focused on making financial data and valuation assumptions more transparent, structured, and accessible through an interactive web application.
