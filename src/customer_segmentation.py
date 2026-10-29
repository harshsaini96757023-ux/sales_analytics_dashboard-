
"""RFM customer segmentation for the Sales Analytics Dashboard."""

import numpy as np
import pandas as pd


RFM_COLUMNS = [
    "customer_id",
    "Recency",
    "Frequency",
    "Monetary",
    "R_Score",
    "F_Score",
    "M_Score",
    "RFM_Score",
    "Segment",
]


def calculate_rfm(
    sales_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Calculate RFM metrics for each customer.

    Required columns:
        customer_id, order_id, order_date, sales

    Recency is calculated relative to one day after the
    latest valid order date in the supplied dataset.
    """

    required = {
        "customer_id",
        "order_id",
        "order_date",
        "sales",
    }

    missing = required.difference(sales_df.columns)

    if missing:
        raise ValueError(
            "Missing required columns: "
            + ", ".join(sorted(missing))
        )

    if sales_df.empty:
        return pd.DataFrame(columns=RFM_COLUMNS)

    df = sales_df[
        ["customer_id", "order_id", "order_date", "sales"]
    ].copy()

    # Clean and validate fields.
    df["customer_id"] = df["customer_id"].astype("string").str.strip()
    df["order_id"] = df["order_id"].astype("string").str.strip()
    df["order_date"] = pd.to_datetime(
        df["order_date"], errors="coerce"
    )
    df["sales"] = pd.to_numeric(
        df["sales"], errors="coerce"
    )

    df = df.dropna(
        subset=["customer_id", "order_id", "order_date", "sales"]
    )

    df = df[
        df["customer_id"].ne("")
        & df["order_id"].ne("")
        & np.isfinite(df["sales"])
    ]

    if df.empty:
        return pd.DataFrame(columns=RFM_COLUMNS)

    # Use the calendar date, rather than the time of day.
    df["order_date"] = df["order_date"].dt.normalize()

    # Latest date + 1 day makes a purchase on the latest
    # date have Recency = 1 day.
    snapshot_date = df["order_date"].max() + pd.Timedelta(days=1)

    rfm = (
        df.groupby("customer_id", as_index=False)
        .agg(
            Last_Order=("order_date", "max"),
            Frequency=("order_id", "nunique"),
            Monetary=("sales", "sum"),
        )
    )

    rfm["Recency"] = (
        snapshot_date - rfm["Last_Order"]
    ).dt.days

    rfm = rfm.drop(columns=["Last_Order"])

    # A percentile-based score works even when there are
    # fewer than five customers or many duplicate values.
    # R: lower Recency is better.
    # F and M: higher values are better.
    rfm["R_Score"] = np.ceil(
        rfm["Recency"].rank(
            method="average", ascending=False, pct=True
        ) * 5
    ).clip(1, 5).astype(int)

    rfm["F_Score"] = np.ceil(
        rfm["Frequency"].rank(
            method="average", ascending=True, pct=True
        ) * 5
    ).clip(1, 5).astype(int)

    rfm["M_Score"] = np.ceil(
        rfm["Monetary"].rank(
            method="average", ascending=True, pct=True
        ) * 5
    ).clip(1, 5).astype(int)

    rfm["RFM_Score"] = (
        rfm["R_Score"].astype(str)
        + rfm["F_Score"].astype(str)
        + rfm["M_Score"].astype(str)
    )

    rfm["Segment"] = rfm.apply(
        classify_customer, axis=1
    )

    rfm = rfm.sort_values(
        ["R_Score", "F_Score", "M_Score"],
        ascending=False,
    ).reset_index(drop=True)

    # Keep the same output column order.
    return rfm[RFM_COLUMNS]


def classify_customer(row: pd.Series) -> str:
    """Assign a descriptive segment using RFM scores."""

    r = int(row["R_Score"])
    f = int(row["F_Score"])
    m = int(row["M_Score"])

    if r >= 4 and f >= 4 and m >= 4:
        return "Champions"

    if f >= 4 and r >= 3:
        return "Loyal Customers"

    if r >= 4 and f <= 2:
        return "New / Recent Customers"

    if r <= 2 and f >= 3:
        return "At Risk"

    if r <= 2 and f <= 2:
        return "Lost / Hibernating"

    if m >= 4:
        return "High Value Customers"

    return "Regular Customers"


def segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    """Summarize customer counts and value by segment."""

    columns = [
        "Segment",
        "Customers",
        "Total Revenue",
        "Average Revenue",
        "Average Orders",
        "Average Recency (days)",
    ]

    if rfm.empty:
        return pd.DataFrame(columns=columns)

    summary = (
        rfm.groupby("Segment", as_index=False)
        .agg(
            Customers=("customer_id", "nunique"),
            **{
                "Total Revenue": ("Monetary", "sum"),
                "Average Revenue": ("Monetary", "mean"),
                "Average Orders": ("Frequency", "mean"),
                "Average Recency (days)": ("Recency", "mean"),
            },
        )
        .sort_values("Total Revenue", ascending=False)
        .reset_index(drop=True)
    )

    return summary[columns]
