# Sales Intelligence Dashboard

Advanced beginner-to-intermediate portfolio project using Python, Pandas, NumPy, SQLite, Streamlit, Plotly and pytest. The bundled generator creates **synthetic practice data**, not real customer or company data.

## Features

- KPI cards: net revenue, profit, order count, unique customers, units, average order value and profit margin.
- Date, region, category and customer-segment filters.
- Monthly revenue/profit trend, category mix, regional performance and top-product charts.
- CSV upload, basic validation/cleaning, SQLite persistence and filtered CSV export.
- Reusable analytics functions and automated tests.

## Folder structure

```text
sales_analytics_dashboard/
├── app.py
├── requirements.txt
├── README.md
├── .gitignore
├── data/
├── exports/
├── src/
│   ├── __init__.py
│   ├── analytics.py
│   ├── config.py
│   ├── data_pipeline.py
│   └── generate_sample_data.py
└── tests/
    └── test_analytics.py
```

## Windows PowerShell setup

Install Python 3.12 or newer, then open PowerShell in this project directory:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

If PowerShell blocks activation, run this for the current terminal only, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

If `py -3.12` is unavailable, use `python -m venv .venv` with an installed supported Python version.

## Generate sample data and launch

```powershell
python -m src.generate_sample_data --rows 1500
streamlit run app.py
```

A browser tab should open at the local Streamlit address shown in the terminal. Use the sidebar's **Load sample dataset** button once to import the generated CSV into SQLite.

## Use your own CSV

Required columns (exact spelling):

```text
order_id,order_date,customer_id,customer_segment,region,category,product,quantity,unit_price,unit_cost,discount
```

- `order_date`: date such as `2025-04-25`.
- `quantity`: positive whole number.
- `unit_price`, `unit_cost`: non-negative numbers in the same currency.
- `discount`: decimal between 0 and 1 (for example, `0.10` means 10%).
- Each `(order_id, product)` pair should identify one order line. Duplicate pairs are deduplicated by keeping the last row.

The app imports a validated CSV into a local SQLite database. Import replaces the current dataset, so export or back up data before importing another file. Do not upload confidential customer data to a hosted app without appropriate authorization and privacy controls.

## Tests

```powershell
pytest -q
```

## Business metric definitions

- **Net revenue** = quantity × unit price × (1 − discount).
- **Cost** = quantity × unit cost.
- **Profit** = net revenue − cost.
- **Profit margin** = total profit ÷ total revenue × 100.
- **Average order value (AOV)** = net revenue ÷ distinct orders.

These definitions are simplified. Production analytics may need returns, shipping, tax, currency conversion, order status and accounting-specific cost rules.

## Suggested next improvements

1. Add a proper star schema (orders, customers, products, date dimension) and migrations.
2. Add role-based authentication, secrets management and audit logging before deployment.
3. Add date-over-date comparisons and confidence checks for incomplete periods.
4. Add CI workflow to run tests on every GitHub push.
5. Deploy to a trusted host only after reviewing data privacy, authentication and database persistence.
