
import pandas as pd

from src.customer_segmentation import (
    calculate_rfm,
    segment_summary,
)


def sample_sales():
    return pd.DataFrame({
        "customer_id": [
            "C001", "C001", "C002", "C003", "C003"
        ],
        "order_id": [
            "O001", "O002", "O003", "O004", "O005"
        ],
        "order_date": [
            "2026-01-01",
            "2026-01-10",
            "2026-01-08",
            "2026-01-02",
            "2026-01-12",
        ],
        "sales": [1000, 1500, 500, 800, 1200],
    })


def test_rfm_returns_one_row_per_customer():
    result = calculate_rfm(sample_sales())

    assert len(result) == 3
    assert result["customer_id"].nunique() == 3


def test_rfm_scores_are_between_one_and_five():
    result = calculate_rfm(sample_sales())

    for column in ["R_Score", "F_Score", "M_Score"]:
        assert result[column].between(1, 5).all()


def test_rfm_frequency_counts_unique_orders():
    result = calculate_rfm(sample_sales())

    customer = result[result["customer_id"] == "C001"].iloc[0]

    assert customer["Frequency"] == 2
    assert customer["Monetary"] == 2500


def test_empty_input_returns_empty_result():
    empty = pd.DataFrame(columns=[
        "customer_id", "order_id", "order_date", "sales"
    ])

    result = calculate_rfm(empty)

    assert result.empty


def test_segment_summary_counts_customers():
    result = calculate_rfm(sample_sales())
    summary = segment_summary(result)

    assert summary["Customers"].sum() == 3
