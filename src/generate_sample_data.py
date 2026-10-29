"""Create reproducible synthetic sales data for local practice."""
import argparse
from pathlib import Path
import numpy as np
import pandas as pd


def generate_sales(rows: int = 1500, seed: int = 42) -> pd.DataFrame:
    if rows < 1:
        raise ValueError("rows must be at least 1")
    rng = np.random.default_rng(seed)
    products = {
        "Technology": [("Wireless Mouse", 850, 430), ("Keyboard", 1500, 800), ("Monitor", 12000, 8500), ("USB Hub", 1200, 620)],
        "Office Supplies": [("Notebook Pack", 350, 170), ("Desk Organizer", 700, 330), ("Pen Set", 220, 90)],
        "Furniture": [("Office Chair", 6500, 4200), ("Study Desk", 9000, 6100), ("Bookshelf", 7200, 4800)],
    }
    regions = np.array(["North", "South", "East", "West", "Central"])
    segments = np.array(["Consumer", "Corporate", "Small Business"])
    dates = pd.Timestamp("2024-01-01") + pd.to_timedelta(rng.integers(0, 730, rows), unit="D")
    records = []
    for i in range(rows):
        category = str(rng.choice(list(products)))
        product, price, cost = products[category][int(rng.integers(0, len(products[category])))]
        quantity = int(rng.integers(1, 8))
        records.append({
            "order_id": f"ORD-{i+1:06d}", "order_date": dates[i].strftime("%Y-%m-%d"),
            "customer_id": f"CUST-{int(rng.integers(1, max(20, rows//3))):05d}",
            "customer_segment": str(rng.choice(segments)), "region": str(rng.choice(regions)),
            "category": category, "product": product, "quantity": quantity,
            "unit_price": round(float(price) * float(rng.uniform(0.9, 1.1)), 2),
            "unit_cost": cost, "discount": float(rng.choice([0, 0.05, 0.1, 0.15], p=[0.45, 0.25, 0.2, 0.1]))
        })
    return pd.DataFrame(records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1500)
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "data" / "sales.csv")
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    generate_sales(args.rows).to_csv(args.output, index=False)
    print(f"Created {args.rows} synthetic sales rows: {args.output}")
