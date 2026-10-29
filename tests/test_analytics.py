import pandas as pd
import pytest
from src.analytics import kpis, monthly_trend, growth_rate
from src.data_pipeline import clean_sales_data


def sample_raw():
    return pd.DataFrame([{
        "order_id":"A1", "order_date":"2025-01-05", "customer_id":"C1",
        "customer_segment":"Consumer", "region":"North", "category":"Technology",
        "product":"Mouse", "quantity":2, "unit_price":100, "unit_cost":60, "discount":0.1
    }])


def test_clean_calculates_sales_cost_profit():
    df = clean_sales_data(sample_raw())
    assert df.iloc[0]["sales"] == pytest.approx(180)
    assert df.iloc[0]["cost"] == pytest.approx(120)
    assert df.iloc[0]["profit"] == pytest.approx(60)


def test_kpis():
    df = clean_sales_data(sample_raw())
    result = kpis(df)
    assert result["orders"] == 1
    assert result["revenue"] == pytest.approx(180)
    assert result["margin_pct"] == pytest.approx(100 / 3)


def test_invalid_discount_rows_removed():
    raw = sample_raw()
    raw.loc[0, "discount"] = 1.5
    with pytest.raises(ValueError):
        clean_sales_data(raw)


def test_monthly_trend():
    df = clean_sales_data(sample_raw())
    result = monthly_trend(df)
    assert result.iloc[0]["month"] == "2025-01"


def test_growth_rate_zero_baseline():
    assert growth_rate(100, 0) is None
    assert growth_rate(120, 100) == pytest.approx(20)
