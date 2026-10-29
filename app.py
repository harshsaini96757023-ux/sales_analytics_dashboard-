
from __future__ import annotations
import pandas as pd
import streamlit as st
from io import BytesIO
from src.customer_segmentation import calculate_rfm, segment_summary

import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.config import DB_PATH, SAMPLE_CSV
from src.data_pipeline import import_csv_to_database, read_sales
from src.analytics import (
    kpis,
    monthly_trend,
    group_performance,
    top_products,
)

# --------------------------------------------------
# PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="Sales Intelligence",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    [data-testid="stMetric"] {
        background: #111827;
        border: 1px solid #263449;
        padding: 16px;
        border-radius: 12px;
    }
    [data-testid="stMetricLabel"] {
        color: #cbd5e1;
    }
    .hero {
        padding: 1.4rem 1.5rem;
        border-radius: 16px;
        background: linear-gradient(120deg, #111827, #172554);
        border: 1px solid #334155;
        margin-bottom: 1rem;
    }
    .hero h1 {
        margin: 0;
        color: #f8fafc;
    }
    .hero p {
        color: #cbd5e1;
        margin-bottom: 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="hero">
        <h1>📊 Sales Intelligence Dashboard</h1>
        <p>
            Revenue analytics, profitability, customer insights
            and product performance.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# HELPER FUNCTIONS
# --------------------------------------------------

def calculate_growth(current: float, previous: float):
    """Return percentage growth, or None if no valid baseline exists."""
    if pd.isna(current) or pd.isna(previous) or previous == 0:
        return None

    return ((current - previous) / abs(previous)) * 100


def format_growth(value):
    if value is None:
        return None

    return f"{value:+.1f}%"


def get_comparison(
    df: pd.DataFrame,
    start_date,
    end_date,
) -> dict:
    """Compare the selected range with the previous equal-length range."""
    start = pd.Timestamp(start_date).normalize()
    end = pd.Timestamp(end_date).normalize()

    if end < start:
        raise ValueError("End date must not precede start date.")

    number_of_days = (end - start).days + 1
    previous_start = start - pd.Timedelta(days=number_of_days)
    previous_end = start - pd.Timedelta(days=1)

    dates = pd.to_datetime(df["order_date"], errors="coerce").dt.normalize()

    current_df = df.loc[dates.between(start, end)]
    previous_df = df.loc[dates.between(previous_start, previous_end)]

    current_metrics = kpis(current_df)
    previous_metrics = kpis(previous_df)

    metric_keys = [
        "revenue",
        "profit",
        "orders",
        "customers",
        "units",
        "aov",
    ]

    growth = {
        key: calculate_growth(
            current_metrics[key],
            previous_metrics[key],
        )
        for key in metric_keys
    }

    margin_change = None
    if previous_metrics["orders"] > 0:
        margin_change = (
            current_metrics["margin_pct"]
            - previous_metrics["margin_pct"]
        )

    return {
        "current": current_metrics,
        "previous": previous_metrics,
        "growth": growth,
        "margin_change": margin_change,
        "previous_start": previous_start.date(),
        "previous_end": previous_end.date(),
    }


def show_metric(
    column,
    label: str,
    value: str,
    growth=None,
    delta_description: str = "vs previous period",
):
    """Display a metric without inventing growth when no baseline exists."""
    if growth is None:
        column.metric(
            label,
            value,
            delta="No previous baseline",
            delta_color="off",
            help="Growth cannot be calculated when the previous value is zero or unavailable.",
        )
    else:
        column.metric(
            label,
            value,
            delta=f"{growth:+.1f}%",
            delta_color="normal",
            help=delta_description,
        )


# --------------------------------------------------
# SIDEBAR: DATA IMPORT
# --------------------------------------------------

with st.sidebar:
    st.header("📁 Data controls")

    uploaded = st.file_uploader(
        "Upload sales CSV",
        type=["csv"],
        help="Upload a CSV matching the columns documented in README.md.",
    )

    if st.button("Load sample dataset", use_container_width=True):
        if SAMPLE_CSV.exists():
            try:
                result = import_csv_to_database(SAMPLE_CSV, DB_PATH)

                st.session_state["load_message"] = (
                    f"Loaded {result['imported_rows']:,} rows; "
                    f"dropped {result['dropped_rows']:,}."
                )
                st.session_state.pop("load_error", None)
                st.rerun()

            except Exception as exc:
                st.session_state["load_error"] = str(exc)

        else:
            st.warning(
                "Sample CSV not found. Run the sample-data generator first."
            )

    if uploaded is not None:
        if st.button(
            "Validate and import upload",
            use_container_width=True,
        ):
            temp_path = ROOT / "data" / "uploaded_sales.csv"
            temp_path.parent.mkdir(parents=True, exist_ok=True)

            try:
                temp_path.write_bytes(uploaded.getvalue())

                result = import_csv_to_database(temp_path, DB_PATH)

                st.session_state["load_message"] = (
                    f"Imported {result['imported_rows']:,} rows; "
                    f"dropped {result['dropped_rows']:,}."
                )
                st.session_state.pop("load_error", None)
                st.rerun()

            except Exception as exc:
                st.session_state["load_error"] = str(exc)

    if st.session_state.get("load_message"):
        st.success(st.session_state["load_message"])

    if st.session_state.get("load_error"):
        st.error(
            f"Data import failed: {st.session_state['load_error']}"
        )

    st.caption(
        "Synthetic data is for practice. Verify business data before "
        "making decisions."
    )

# --------------------------------------------------
# LOAD DATA
# --------------------------------------------------

try:
    df = read_sales(DB_PATH)
except Exception as exc:
    st.error(f"Could not read the sales database: {exc}")
    st.stop()

if df.empty:
    st.info(
        "No sales data found. Use 'Load sample dataset' in the sidebar."
    )
    st.stop()

required_columns = {
    "order_date",
    "region",
    "category",
    "customer_segment",
    "product",
    "sales",
    "profit",
    "quantity",
    "order_id",
    "customer_id",
}

missing_columns = required_columns - set(df.columns)

if missing_columns:
    st.error(
        "The database is missing required columns: "
        + ", ".join(sorted(missing_columns))
    )
    st.stop()

# Keep raw date strings available for diagnostics, then normalize dates.
df = df.copy()
df["order_date"] = pd.to_datetime(
    df["order_date"],
    errors="coerce",
)

for column in ["sales", "profit", "quantity"]:
    df[column] = pd.to_numeric(df[column], errors="coerce")

invalid_dates = int(df["order_date"].isna().sum())

if invalid_dates:
    st.warning(
        f"{invalid_dates:,} rows have invalid dates and will be excluded "
        "from date-based analytics."
    )

valid_df = df.dropna(subset=["order_date"]).copy()

if valid_df.empty:
    st.error("No rows contain valid order dates.")
    st.stop()

# --------------------------------------------------
# SIDEBAR: FILTERS
# --------------------------------------------------

with st.sidebar:
    st.divider()
    st.subheader("🔎 Filters")

    min_date = valid_df["order_date"].min().date()
    max_date = valid_df["order_date"].max().date()

    date_range = st.date_input(
        "Order date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    regions_available = sorted(
        valid_df["region"].dropna().unique().tolist()
    )
    categories_available = sorted(
        valid_df["category"].dropna().unique().tolist()
    )
    segments_available = sorted(
        valid_df["customer_segment"].dropna().unique().tolist()
    )

    regions = st.multiselect(
        "Region",
        regions_available,
        default=regions_available,
    )

    categories = st.multiselect(
        "Category",
        categories_available,
        default=categories_available,
    )

    segments = st.multiselect(
        "Customer segment",
        segments_available,
        default=segments_available,
    )

# Streamlit date_input can return one date or a two-date tuple.
if isinstance(date_range, (tuple, list)):
    if len(date_range) == 2:
        start_date, end_date = date_range
    elif len(date_range) == 1:
        start_date = end_date = date_range[0]
    else:
        start_date, end_date = min_date, max_date
else:
    start_date = end_date = date_range

# Apply dimensions before comparing date periods.
base_filtered = valid_df[
    valid_df["region"].isin(regions)
    & valid_df["category"].isin(categories)
    & valid_df["customer_segment"].isin(segments)
].copy()

date_values = base_filtered["order_date"].dt.date

filtered = base_filtered.loc[
    date_values.between(start_date, end_date)
].copy()

# ==========================================================
# RFM CUSTOMER SEGMENTATION
# ==========================================================
import plotly.express as px
st.divider()
st.header("👥 RFM Customer Segmentation")
st.caption(
    "Understand customer recency, purchase frequency "
    "and total purchase value."
)

try:
    rfm_df = calculate_rfm(filtered)

    if rfm_df.empty:
        st.warning(
            "RFM analysis ke liye valid customer data nahi mila."
        )
    else:
        summary_df = segment_summary(rfm_df)

        # Customer KPIs
        total_customers = rfm_df["customer_id"].nunique()
        champions = int(
            (rfm_df["Segment"] == "Champions").sum()
        )
        at_risk = int(
            (rfm_df["Segment"] == "At Risk").sum()
        )
        customer_revenue = rfm_df["Monetary"].sum()

        c1, c2, c3, c4 = st.columns(4)

        c1.metric("Customers Analyzed", f"{total_customers:,}")
        c2.metric("Champions", f"{champions:,}")
        c3.metric("At-Risk Customers", f"{at_risk:,}")
        c4.metric("Customer Revenue", f"₹{customer_revenue:,.2f}")

        # Segment distribution chart
        st.subheader("Customer Segment Distribution")

        segment_counts = (
            rfm_df["Segment"]
            .value_counts()
            .rename_axis("Segment")
            .reset_index(name="Customers")
        )

        st.plotly_chart(
            px.pie(
                segment_counts,
                names="Segment",
                values="Customers",
                hole=0.45,
                title="Customers by Segment",
            ),
            use_container_width=True,
        )

        # Segment summary
        st.subheader("Segment Performance")

        st.dataframe(
            summary_df.style.format({
                "Total Revenue": "₹{:,.2f}",
                "Average Revenue": "₹{:,.2f}",
                "Average Orders": "{:.2f}",
                "Average Recency (days)": "{:.1f}",
            }),
            use_container_width=True,
            hide_index=True,
        )

        # Customer-level explorer
        st.subheader("Customer-Level RFM Analysis")

        segment_options = ["All Segments"] + sorted(
            rfm_df["Segment"].dropna().unique().tolist()
        )

        selected_segment = st.selectbox(
            "Filter by customer segment",
            segment_options,
            key="rfm_segment_filter",
        )

        customer_view = rfm_df.copy()

        if selected_segment != "All Segments":
            customer_view = customer_view[
                customer_view["Segment"] == selected_segment
            ]

        sort_option = st.selectbox(
            "Sort customers by",
            [
                "Monetary",
                "Frequency",
                "Recency",
                "RFM_Score",
            ],
            key="rfm_sort_option",
        )

        customer_view = customer_view.sort_values(
            sort_option,
            ascending=(sort_option == "Recency"),
        )

        st.dataframe(
            customer_view,
            use_container_width=True,
            hide_index=True,
        )

        # Download customer analysis
        csv_data = customer_view.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="Download RFM Customer Report (CSV)",
            data=csv_data,
            file_name="rfm_customer_report.csv",
            mime="text/csv",
        )

        summary_csv = summary_df.to_csv(index=False).encode("utf-8-sig")

        st.download_button(
            label="Download Segment Summary (CSV)",
            data=summary_csv,
            file_name="rfm_segment_summary.csv",
            mime="text/csv",
        )

except (ValueError, KeyError) as error:
    st.error(f"RFM analysis could not be completed: {error}")


# --------------------------------------------------
# FILTER STATUS AND EMPTY STATE
# --------------------------------------------------

st.caption(
    f"Selected period: {start_date} to {end_date} | "
    f"Showing {len(filtered):,} line items."
)

if filtered.empty:
    st.warning(
        "No records match the selected filters. "
        "Choose more regions/categories or widen the date range."
    )
    st.stop()

# --------------------------------------------------
# KPI METRICS AND PERIOD COMPARISON
# --------------------------------------------------

try:
    metrics = kpis(filtered)

    comparison = get_comparison(
        base_filtered,
        start_date,
        end_date,
    )

except Exception as exc:
    st.error(f"Could not calculate analytics: {exc}")
    st.stop()

st.subheader("📈 Business overview")

st.caption(
    f"Comparison period: {comparison['previous_start']} "
    f"to {comparison['previous_end']}. "
    "Growth is compared with the previous equal-length period."
)

growth = comparison["growth"]
margin_change = comparison["margin_change"]

cols = st.columns(4)

show_metric(
    cols[0],
    "Net revenue",
    f"₹{metrics['revenue']:,.2f}",
    growth["revenue"],
)

show_metric(
    cols[1],
    "Profit",
    f"₹{metrics['profit']:,.2f}",
    growth["profit"],
)

show_metric(
    cols[2],
    "Orders",
    f"{metrics['orders']:,}",
    growth["orders"],
)

if margin_change is None:
    cols[3].metric(
        "Profit margin",
        f"{metrics['margin_pct']:.2f}%",
        delta="No previous baseline",
        delta_color="off",
    )
else:
    cols[3].metric(
        "Profit margin",
        f"{metrics['margin_pct']:.2f}%",
        delta=f"{margin_change:+.2f} pp",
        delta_color="normal",
        help="Change in percentage points versus the previous period.",
    )

cols = st.columns(3)

show_metric(
    cols[0],
    "Unique customers",
    f"{metrics['customers']:,}",
    growth["customers"],
)

show_metric(
    cols[1],
    "Units sold",
    f"{metrics['units']:,.0f}",
    growth["units"],
)

show_metric(
    cols[2],
    "Average order value",
    f"₹{metrics['aov']:,.2f}",
    growth["aov"],
)

st.divider()

# --------------------------------------------------
# REVENUE AND PROFIT TREND
# --------------------------------------------------

left, right = st.columns(2)

with left:
    st.subheader("Revenue and profit trend")

    trend = monthly_trend(filtered)

    if trend.empty:
        st.info("No monthly trend data is available.")
    else:
        fig = go.Figure()

        fig.add_trace(
            go.Scatter(
                x=trend["month"],
                y=trend["sales"],
                name="Revenue",
                mode="lines+markers",
                line=dict(width=3),
            )
        )

        fig.add_trace(
            go.Scatter(
                x=trend["month"],
                y=trend["profit"],
                name="Profit",
                mode="lines+markers",
                line=dict(width=3),
            )
        )

        fig.update_layout(
            template="plotly_dark",
            height=360,
            margin=dict(l=10, r=10, t=20, b=10),
            yaxis_title="Amount (₹)",
            xaxis_title="Month",
            legend=dict(orientation="h"),
            hovermode="x unified",
        )

        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Revenue by category")

    cat = group_performance(filtered, "category")

    if cat.empty:
        st.info("No category data is available.")
    else:
        fig = px.pie(
            cat,
            names="category",
            values="sales",
            hole=0.55,
        )

        fig.update_layout(
            template="plotly_dark",
            height=360,
            margin=dict(l=10, r=10, t=20, b=10),
        )

        st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# REGION AND PRODUCT PERFORMANCE
# --------------------------------------------------

left, right = st.columns(2)

with left:
    st.subheader("Regional performance")

    region_df = group_performance(filtered, "region")

    if region_df.empty:
        st.info("No regional data is available.")
    else:
        fig = px.bar(
            region_df,
            x="region",
            y="sales",
            color="profit",
            color_continuous_scale="Blues",
            labels={
                "sales": "Revenue (₹)",
                "region": "Region",
                "profit": "Profit (₹)",
            },
            hover_data=["quantity"],
        )

        fig.update_layout(
            template="plotly_dark",
            height=350,
            margin=dict(l=10, r=10, t=20, b=10),
        )

        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Top products by revenue")

    products = top_products(filtered, 10)

    if products.empty:
        st.info("No product data is available.")
    else:
        products = products.sort_values("sales")

        fig = px.bar(
            products,
            x="sales",
            y="product",
            orientation="h",
            color="profit",
            color_continuous_scale="RdYlGn",
            labels={
                "sales": "Revenue (₹)",
                "product": "Product",
                "profit": "Profit (₹)",
            },
        )

        fig.update_layout(
            template="plotly_dark",
            height=350,
            margin=dict(l=10, r=10, t=20, b=10),
        )

        st.plotly_chart(fig, use_container_width=True)

# --------------------------------------------------
# BOTTOM-PERFORMING PRODUCTS
# --------------------------------------------------

st.subheader("⚠️ Lowest-performing products")

product_performance = group_performance(filtered, "product")

if not product_performance.empty:
    bottom_products = product_performance.sort_values(
        "profit",
        ascending=True,
    ).head(10)

    fig = px.bar(
        bottom_products,
        x="profit",
        y="product",
        orientation="h",
        color="profit",
        color_continuous_scale="RdYlGn",
        labels={
            "profit": "Profit (₹)",
            "product": "Product",
        },
    )

    fig.update_layout(
        template="plotly_dark",
        height=350,
        margin=dict(l=10, r=10, t=20, b=10),
    )

    st.plotly_chart(fig, use_container_width=True)

    loss_count = int((product_performance["profit"] < 0).sum())
    st.caption(
        f"{loss_count:,} products have negative aggregate profit "
        "in the selected data."
    )
else:
    st.info("No product profitability data is available.")

# --------------------------------------------------
# DETAILED PRODUCT TABLE
# --------------------------------------------------

st.subheader("📋 Detailed product performance")

if not product_performance.empty:
    table = product_performance.copy()

    table["profit_margin_pct"] = (
        table["profit"]
        .div(table["sales"].where(table["sales"] != 0))
        .mul(100)
        .fillna(0)
        .round(2)
    )

    table = table.rename(
        columns={
            "product": "Product",
            "sales": "Revenue (₹)",
            "profit": "Profit (₹)",
            "quantity": "Units",
            "profit_margin_pct": "Profit margin (%)",
        }
    )

    sort_options = [
        "Revenue (₹)",
        "Profit (₹)",
        "Units",
        "Profit margin (%)",
    ]

    selected_sort = st.selectbox(
        "Sort product table by",
        sort_options,
    )

    table = table.sort_values(
        selected_sort,
        ascending=(selected_sort == "Profit (₹)"),
    )

    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
    )

# --------------------------------------------------
# DATA QUALITY SUMMARY
# --------------------------------------------------

with st.expander("🧪 Data quality summary"):
    quality_cols = st.columns(4)

    quality_cols[0].metric("Rows in database", f"{len(df):,}")
    quality_cols[1].metric("Valid-date rows", f"{len(valid_df):,}")
    quality_cols[2].metric("Invalid dates", f"{invalid_dates:,}")
    quality_cols[3].metric(
        "Rows in current selection",
        f"{len(filtered):,}",
    )

    missing_counts = filtered.isna().sum()
    missing_counts = missing_counts[missing_counts > 0]

    if missing_counts.empty:
        st.success("No missing values in the selected records.")
    else:
        st.write("Missing values by column")
        st.dataframe(
            missing_counts.rename("Missing rows").reset_index(
                names="Column"
            ),
            use_container_width=True,
            hide_index=True,
        )

# --------------------------------------------------
# CSV EXPORTS
# --------------------------------------------------

st.subheader("📥 Export reports")

export_left, export_right = st.columns(2)

with export_left:
    csv_bytes = filtered.to_csv(index=False).encode("utf-8")

    st.download_button(
        "Download filtered sales CSV",
        data=csv_bytes,
        file_name="sales_filtered_export.csv",
        mime="text/csv",
        use_container_width=True,
    )

with export_right:
    if not product_performance.empty:
        report_bytes = product_performance.to_csv(
            index=False
        ).encode("utf-8")

        st.download_button(
            "Download product summary CSV",
            data=report_bytes,
            file_name="sales_product_summary.csv",
            mime="text/csv",
            use_container_width=True,
        )

st.caption(
    "Sales Intelligence Dashboard | Python, Pandas, SQLite, "   
    "Streamlit and Plotly"
)
import numpy as np
import plotly.express as px
import streamlit as st

# ==========================================================
# STEP 3: PRODUCT & REGIONAL ANALYTICS
# ==========================================================

st.divider()
st.header("📊 Product & Regional Analytics")

if filtered.empty:
    st.warning("Selected filters ke liye sales data available nahi hai.")
else:
    product_data = (
        filtered.groupby("product", as_index=False)
        .agg(
            Revenue=("sales", "sum"),
            Profit=("profit", "sum"),
            Units_Sold=("quantity", "sum"),
            Orders=("order_id", "nunique"),
        )
    )

    product_data["Profit_Margin_%"] = (
        product_data["Profit"]
        .div(product_data["Revenue"].replace(0, np.nan))
        .mul(100)
        .fillna(0)
    )

    # 1. Product performance
    st.subheader("🏆 Product Performance")

    left, right = st.columns(2)

    with left:
        best_products = product_data.nlargest(10, "Revenue")

        st.plotly_chart(
            px.bar(
                best_products.sort_values("Revenue"),
                x="Revenue",
                y="product",
                orientation="h",
                title="Top 10 Products by Revenue",
                labels={"product": "Product", "Revenue": "Revenue (₹)"},
            ),
            use_container_width=True,
        )

    with right:
        low_products = product_data.nsmallest(10, "Units_Sold")

        st.plotly_chart(
            px.bar(
                low_products.sort_values("Units_Sold"),
                x="Units_Sold",
                y="product",
                orientation="h",
                title="10 Products with Lowest Units Sold",
                labels={"product": "Product", "Units_Sold": "Units Sold"},
            ),
            use_container_width=True,
        )

    # 2. Loss-making products
    st.subheader("⚠️ Loss-Making Products")

    loss_products = (
        product_data[product_data["Profit"] < 0]
        .sort_values("Profit")
    )

    if loss_products.empty:
        st.success("Selected data mein koi loss-making product nahi hai.")
    else:
        st.dataframe(
            loss_products,
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "Download Loss-Making Products CSV",
            data=loss_products.to_csv(index=False).encode("utf-8-sig"),
            file_name="loss_making_products.csv",
            mime="text/csv",
        )

    # 3. Regional performance
    st.subheader("🌍 Regional Performance")

    region_data = (
        filtered.groupby("region", as_index=False)
        .agg(
            Revenue=("sales", "sum"),
            Profit=("profit", "sum"),
            Orders=("order_id", "nunique"),
            Units_Sold=("quantity", "sum"),
        )
    )

    region_data["Profit_Margin_%"] = (
        region_data["Profit"]
        .div(region_data["Revenue"].replace(0, np.nan))
        .mul(100)
        .fillna(0)
    )

    st.plotly_chart(
        px.bar(
            region_data.sort_values("Revenue", ascending=False),
            x="region",
            y=["Revenue", "Profit"],
            barmode="group",
            title="Revenue vs Profit by Region",
            labels={"value": "Amount (₹)", "region": "Region"},
        ),
        use_container_width=True,
    )

    st.dataframe(
        region_data.sort_values("Profit", ascending=False),
        use_container_width=True,
        hide_index=True,
    )

    # 4. Category analysis
    st.subheader("📦 Category Performance")

    category_data = (
        filtered.groupby("category", as_index=False)
        .agg(
            Revenue=("sales", "sum"),
            Profit=("profit", "sum"),
            Units_Sold=("quantity", "sum"),
        )
        .sort_values("Revenue", ascending=False)
    )

    st.plotly_chart(
        px.bar(
            category_data,
            x="category",
            y="Revenue",
            color="Profit",
            title="Category Revenue and Profit",
            labels={"Revenue": "Revenue (₹)", "category": "Category"},
        ),
        use_container_width=True,
    )

    st.dataframe(
        category_data,
        use_container_width=True,
        hide_index=True,
    )

    # 5. Automatic business insights
    st.subheader("💡 Business Insights")

    best_region = region_data.loc[region_data["Revenue"].idxmax()]
    best_profit_region = region_data.loc[region_data["Profit"].idxmax()]
    worst_profit_region = region_data.loc[region_data["Profit"].idxmin()]
    best_product = product_data.loc[product_data["Revenue"].idxmax()]

    st.markdown(
        f"- **Highest-revenue region:** {best_region['region']} "
        f"(₹{best_region['Revenue']:,.2f})"
    )
    st.markdown(
        f"- **Highest-profit region:** {best_profit_region['region']} "
        f"(₹{best_profit_region['Profit']:,.2f})"
    )
    st.markdown(
        f"- **Lowest-profit region:** {worst_profit_region['region']} "
        f"(₹{worst_profit_region['Profit']:,.2f})"
    )
    st.markdown(
        f"- **Top product by revenue:** {best_product['product']} "
        f"(₹{best_product['Revenue']:,.2f})"
    )
    st.markdown(
        f"- **Loss-making products:** {len(loss_products)}"
    )


# ==========================================================
# STEP 4: DATA QUALITY & DOWNLOADABLE REPORTS
# ==========================================================

from io import BytesIO

st.divider()
st.header("📁 Data Quality & Export Center")

# Use the currently selected, filtered dataset.
quality_df = filtered.copy()

# ----------------------------------------------------------
# A. DATA QUALITY REPORT
# ----------------------------------------------------------

st.subheader("🔎 Data Quality Report")

if quality_df.empty:
    st.warning("Selected filters ke liye data available nahi hai.")
else:
    missing_count = int(quality_df.isna().sum().sum())
    duplicate_count = int(quality_df.duplicated().sum())

    quality_checks = []

    # Missing values by column
    for column in quality_df.columns:
        missing = int(quality_df[column].isna().sum())

        quality_checks.append({
            "Check": f"Missing values: {column}",
            "Problem Rows": missing,
            "Status": "Issue" if missing else "Passed",
        })

    quality_checks.extend([
        {
            "Check": "Duplicate rows",
            "Problem Rows": duplicate_count,
            "Status": "Issue" if duplicate_count else "Passed",
        }
    ])

    # Numeric validation
    for column in ["sales", "profit", "quantity"]:
        if column in quality_df.columns:
            numeric_values = pd.to_numeric(
                quality_df[column], errors="coerce"
            )

            invalid_count = int(
                (
                    numeric_values.isna()
                    | ~np.isfinite(numeric_values.fillna(0))
                ).sum()
            )

            quality_checks.append({
                "Check": f"Invalid numeric values: {column}",
                "Problem Rows": invalid_count,
                "Status": "Issue" if invalid_count else "Passed",
            })

    # Date validation
    if "order_date" in quality_df.columns:
        parsed_dates = pd.to_datetime(
            quality_df["order_date"], errors="coerce"
        )
        invalid_dates = int(parsed_dates.isna().sum())

        quality_checks.append({
            "Check": "Invalid order dates",
            "Problem Rows": invalid_dates,
            "Status": "Issue" if invalid_dates else "Passed",
        })

    quality_report = pd.DataFrame(quality_checks)

    q1, q2, q3 = st.columns(3)
    q1.metric("Rows Analyzed", f"{len(quality_df):,}")
    q2.metric("Missing Cells", f"{missing_count:,}")
    q3.metric("Duplicate Rows", f"{duplicate_count:,}")

    st.dataframe(
        quality_report,
        use_container_width=True,
        hide_index=True,
    )

    # Download quality report
    st.download_button(
        label="Download Data Quality Report (CSV)",
        data=quality_report.to_csv(index=False).encode("utf-8-sig"),
        file_name="data_quality_report.csv",
        mime="text/csv",
    )

    # ------------------------------------------------------
    # B. CSV EXPORT
    # ------------------------------------------------------

    st.subheader("📄 Download CSV Reports")

    st.download_button(
        label="Download Filtered Sales (CSV)",
        data=quality_df.to_csv(index=False).encode("utf-8-sig"),
        file_name="filtered_sales.csv",
        mime="text/csv",
    )

    # Product summary: calculate independently for reliability.
    export_product_summary = (
        quality_df.groupby("product", as_index=False)
        .agg(
            Revenue=("sales", "sum"),
            Profit=("profit", "sum"),
            Units_Sold=("quantity", "sum"),
            Orders=("order_id", "nunique"),
        )
        .sort_values("Revenue", ascending=False)
    )

    st.download_button(
        label="Download Product Summary (CSV)",
        data=export_product_summary.to_csv(index=False).encode("utf-8-sig"),
        file_name="product_summary.csv",
        mime="text/csv",
    )

    # ------------------------------------------------------
    # C. MULTI-SHEET EXCEL WORKBOOK
    # ------------------------------------------------------

    def create_excel_report(
        sales_data,
        product_summary,
        quality_summary,
    ):
        """Create a downloadable Excel workbook in memory."""

        output = BytesIO()

        with pd.ExcelWriter(
            output,
            engine="openpyxl",
        ) as writer:

            sales_data.to_excel(
                writer,
                sheet_name="Filtered Sales",
                index=False,
            )

            product_summary.to_excel(
                writer,
                sheet_name="Product Summary",
                index=False,
            )

            quality_summary.to_excel(
                writer,
                sheet_name="Data Quality",
                index=False,
            )

            # Include region and category summaries when possible.
            if "region" in sales_data.columns:
                region_summary = (
                    sales_data.groupby("region", as_index=False)
                    .agg(
                        Revenue=("sales", "sum"),
                        Profit=("profit", "sum"),
                        Orders=("order_id", "nunique"),
                    )
                    .sort_values("Revenue", ascending=False)
                )

                region_summary.to_excel(
                    writer,
                    sheet_name="Regional Summary",
                    index=False,
                )

            if "category" in sales_data.columns:
                category_summary = (
                    sales_data.groupby("category", as_index=False)
                    .agg(
                        Revenue=("sales", "sum"),
                        Profit=("profit", "sum"),
                        Units_Sold=("quantity", "sum"),
                    )
                    .sort_values("Revenue", ascending=False)
                )

                category_summary.to_excel(
                    writer,
                    sheet_name="Category Summary",
                    index=False,
                )

            # Add RFM results if Step 2 has produced them.
            if "rfm_df" in globals() and not rfm_df.empty:
                rfm_df.to_excel(
                    writer,
                    sheet_name="RFM Customers",
                    index=False,
                )

            if "summary_df" in globals() and not summary_df.empty:
                summary_df.to_excel(
                    writer,
                    sheet_name="RFM Segments",
                    index=False,
                )

        output.seek(0)
        return output.getvalue()

    excel_data = create_excel_report(
        quality_df,
        export_product_summary,
        quality_report,
    )

    st.subheader("📊 Complete Excel Workbook")

    st.download_button(
        label="Download Complete Excel Report (.xlsx)",
        data=excel_data,
        file_name="sales_analytics_complete_report.xlsx",
        mime=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )

    st.success(
        "Reports are ready. Excel workbook mein filtered sales, "
        "product, regional, category aur data-quality sheets hongi."
    )
