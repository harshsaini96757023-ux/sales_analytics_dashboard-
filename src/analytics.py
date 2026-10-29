"""Reusable business metrics; functions accept already-filtered DataFrames."""
import numpy as np
import pandas as pd


def kpis(df: pd.DataFrame) -> dict:
    if df.empty:
        return {"revenue": 0.0, "profit": 0.0, "orders": 0, "customers": 0,
                "units": 0, "aov": 0.0, "margin_pct": 0.0}
    revenue = float(df["sales"].sum())
    profit = float(df["profit"].sum())
    orders = int(df["order_id"].nunique())
    return {
        "revenue": revenue,
        "profit": profit,
        "orders": orders,
        "customers": int(df["customer_id"].nunique()),
        "units": int(df["quantity"].sum()),
        "aov": revenue / orders if orders else 0.0,
        "margin_pct": profit / revenue * 100 if revenue else 0.0,
    }


def monthly_trend(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["month", "sales", "profit", "orders"])
    out = df.copy()
    out["month"] = pd.to_datetime(out["order_date"]).dt.to_period("M").astype(str)
    return out.groupby("month", as_index=False).agg(
        sales=("sales", "sum"), profit=("profit", "sum"), orders=("order_id", "nunique")
    ).sort_values("month")


def group_performance(df: pd.DataFrame, dimension: str) -> pd.DataFrame:
    if df.empty or dimension not in df.columns:
        return pd.DataFrame(columns=[dimension, "sales", "profit", "quantity"])
    return df.groupby(dimension, as_index=False).agg(
        sales=("sales", "sum"), profit=("profit", "sum"), quantity=("quantity", "sum")
    ).sort_values("sales", ascending=False)


def top_products(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    result = group_performance(df, "product")
    return result.head(limit)


def growth_rate(current: float, previous: float) -> float | None:
    """Percentage change; None when the comparison baseline is zero."""
    if previous == 0:
        return None
    return (current - previous) / abs(previous) * 100


def period_comparison(
    df: pd.DataFrame,
    start_date,
    end_date,
) -> dict:
    """Compare a selected date range with the previous equal-length period."""
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()

    if end < start:
        raise ValueError("end_date must be on or after start_date")

    days = (end - start).days + 1
    previous_start = start - pd.Timedelta(days=days)
    previous_end = start - pd.Timedelta(days=1)

    dates = pd.to_datetime(df["order_date"], errors="coerce").dt.normalize()

    current_df = df.loc[dates.between(start, end)]
    previous_df = df.loc[dates.between(previous_start, previous_end)]

    current = kpis(current_df)
    previous = kpis(previous_df)

    keys = [
        "revenue", "profit", "orders",
        "customers", "units", "aov",
    ]

    growth = {
        key: growth_rate(current[key], previous[key])
        for key in keys
    }

    return {
        "current": current,
        "previous": previous,
        "growth": growth,
        "previous_start": previous_start.date(),
        "previous_end": previous_end.date(),
    }
