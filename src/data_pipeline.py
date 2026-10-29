"""Load, validate, clean and persist sales data."""
from __future__ import annotations

import sqlite3
from pathlib import Path
import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "order_id", "order_date", "customer_id", "customer_segment", "region",
    "category", "product", "quantity", "unit_price", "unit_cost", "discount"
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS sales (
    order_id TEXT NOT NULL,
    order_date TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    customer_segment TEXT NOT NULL,
    region TEXT NOT NULL,
    category TEXT NOT NULL,
    product TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK(quantity > 0),
    unit_price REAL NOT NULL CHECK(unit_price >= 0),
    unit_cost REAL NOT NULL CHECK(unit_cost >= 0),
    discount REAL NOT NULL CHECK(discount >= 0 AND discount <= 1),
    sales REAL NOT NULL,
    cost REAL NOT NULL,
    profit REAL NOT NULL,
    PRIMARY KEY (order_id, product)
);
CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(order_date);
CREATE INDEX IF NOT EXISTS idx_sales_region ON sales(region);
CREATE INDEX IF NOT EXISTS idx_sales_category ON sales(category);
"""


def clean_sales_data(raw: pd.DataFrame) -> pd.DataFrame:
    """Validate required fields and calculate trusted sales metrics."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(raw.columns))
    if missing:
        raise ValueError(f"CSV is missing required columns: {', '.join(missing)}")
    df = raw[REQUIRED_COLUMNS].copy()
    df = df.drop_duplicates(subset=["order_id", "product"], keep="last")

    for col in ["order_id", "customer_id", "customer_segment", "region", "category", "product"]:
        df[col] = df[col].astype("string").str.strip()
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    for col in ["quantity", "unit_price", "unit_cost", "discount"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=REQUIRED_COLUMNS)
    df = df[(df["order_id"] != "") & (df["product"] != "") & (df["customer_id"] != "")]
    df = df[(df["quantity"] > 0) & (df["unit_price"] >= 0) & (df["unit_cost"] >= 0)]
    df = df[(df["discount"] >= 0) & (df["discount"] <= 1)]
    if df.empty:
        raise ValueError("No valid rows remain after cleaning. Check your input CSV.")

    df["quantity"] = df["quantity"].astype(int)
    df["sales"] = (df["quantity"] * df["unit_price"] * (1 - df["discount"])).round(2)
    df["cost"] = (df["quantity"] * df["unit_cost"]).round(2)
    df["profit"] = (df["sales"] - df["cost"]).round(2)
    df["order_date"] = df["order_date"].dt.strftime("%Y-%m-%d")
    return df.reset_index(drop=True)


def initialize_database(db_path: str | Path) -> None:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.executescript(SCHEMA)


def import_csv_to_database(csv_path: str | Path, db_path: str | Path) -> dict:
    raw = pd.read_csv(csv_path)
    cleaned = clean_sales_data(raw)
    initialize_database(db_path)
    with sqlite3.connect(db_path) as conn:
        # Replace the current dataset only after validation succeeds.
        cleaned.to_sql("sales", conn, if_exists="replace", index=False)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(order_date)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_region ON sales(region)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sales_category ON sales(category)")
    return {"input_rows": len(raw), "imported_rows": len(cleaned), "dropped_rows": len(raw) - len(cleaned)}


def read_sales(db_path: str | Path) -> pd.DataFrame:
    if not Path(db_path).exists():
        return pd.DataFrame()
    with sqlite3.connect(db_path) as conn:
        try:
            df = pd.read_sql_query("SELECT * FROM sales", conn, parse_dates=["order_date"])
        except pd.errors.DatabaseError:
            return pd.DataFrame()
    return df
