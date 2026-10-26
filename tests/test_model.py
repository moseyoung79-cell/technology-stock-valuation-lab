
import pytest

from valuation_lab.dcf import scenarios


def test_dcf_returns_three_scenarios():
    result = scenarios(
        fcf=10_000_000_000,
        shares=1_000_000_000,
        cash=5_000_000_000,
        debt=2_000_000_000,
        price=10.0,
        growth={"Bear": 0.05, "Base": 0.10, "Bull": 0.15},
        wacc={"Bear": 0.12, "Base": 0.10, "Bull": 0.09},
        terminal_growth=0.03,
    )

    assert set(result.keys()) == {"Bear", "Base", "Bull"}
    assert all("intrinsic_per_share" in v for v in result.values())


def test_dcf_rejects_invalid_wacc():
    result = scenarios(
        fcf=10_000_000_000,
        shares=1_000_000_000,
        cash=5_000_000_000,
        debt=2_000_000_000,
        price=10.0,
        growth={"Bear": 0.05, "Base": 0.10, "Bull": 0.15},
        wacc={"Bear": 0.02, "Base": 0.10, "Bull": 0.09},
        terminal_growth=0.03,
    )

    assert "error" in result or result["Bear"]["wacc"] > 0.03


def test_dcf_rejects_missing_fcf():
    result = scenarios(
        fcf=None,
        shares=1_000_000_000,
        cash=5_000_000_000,
        debt=2_000_000_000,
        price=10.0,
        growth={"Bear": 0.05, "Base": 0.10, "Bull": 0.15},
        wacc={"Bear": 0.12, "Base": 0.10, "Bull": 0.09},
        terminal_growth=0.03,
    )

    assert "error" in result
