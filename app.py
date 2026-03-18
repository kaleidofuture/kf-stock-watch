"""KF-StockWatch — Track restaurant/shop inventory and consumption trends."""

import streamlit as st

st.set_page_config(
    page_title="KF-StockWatch",
    page_icon="\U0001F4E6",
    layout="wide",
)

from components.header import render_header
from components.footer import render_footer
from components.i18n import t

import io
import csv
import duckdb
import pandas as pd

# --- Header ---
render_header()

# --- Sample CSV for download ---
SAMPLE_CSV = """item,quantity,unit,date
Rice,50,kg,2026-03-01
Rice,45,kg,2026-03-08
Rice,30,kg,2026-03-15
Soy Sauce,20,bottles,2026-03-01
Soy Sauce,15,bottles,2026-03-08
Soy Sauce,8,bottles,2026-03-15
Chicken,30,kg,2026-03-01
Chicken,20,kg,2026-03-08
Chicken,10,kg,2026-03-15
Cooking Oil,10,L,2026-03-01
Cooking Oil,7,L,2026-03-08
Cooking Oil,3,L,2026-03-15
Napkins,500,sheets,2026-03-01
Napkins,350,sheets,2026-03-08
Napkins,100,sheets,2026-03-15
"""


# --- Main Content ---
st.subheader(t("upload_title"))
st.caption(t("upload_help"))

# Download sample CSV
st.download_button(
    label=t("download_sample"),
    data=SAMPLE_CSV.encode("utf-8"),
    file_name="stock_sample.csv",
    mime="text/csv",
)

uploaded_file = st.file_uploader(t("upload_prompt"), type=["csv"])

if uploaded_file is not None:
    content = uploaded_file.read().decode("utf-8-sig", errors="replace")

    with st.spinner(t("processing")):
        try:
            con = duckdb.connect(":memory:")

            # Load CSV into DuckDB
            con.execute("""
                CREATE TABLE stock AS
                SELECT * FROM read_csv_auto(?)
            """, [io.StringIO(content)])

            # Get column names
            columns = [col[0] for col in con.execute("DESCRIBE stock").fetchall()]
            col_lower = [c.lower() for c in columns]

            # Auto-detect column roles
            item_col = None
            qty_col = None
            unit_col = None
            date_col = None

            item_keywords = ["item", "product", "name", "品名", "商品", "品目", "アイテム"]
            qty_keywords = ["quantity", "qty", "amount", "count", "数量", "在庫", "残量", "個数"]
            unit_keywords = ["unit", "単位"]
            date_keywords = ["date", "日付", "日時", "記録日"]

            for i, c in enumerate(col_lower):
                if item_col is None:
                    for kw in item_keywords:
                        if kw in c:
                            item_col = columns[i]
                            break
                if qty_col is None:
                    for kw in qty_keywords:
                        if kw in c:
                            qty_col = columns[i]
                            break
                if unit_col is None:
                    for kw in unit_keywords:
                        if kw in c:
                            unit_col = columns[i]
                            break
                if date_col is None:
                    for kw in date_keywords:
                        if kw in c:
                            date_col = columns[i]
                            break

            # Fallback: use positional
            if item_col is None and len(columns) >= 1:
                item_col = columns[0]
            if qty_col is None and len(columns) >= 2:
                qty_col = columns[1]
            if unit_col is None and len(columns) >= 3:
                unit_col = columns[2]
            if date_col is None and len(columns) >= 4:
                date_col = columns[3]

            # Let user confirm mapping
            st.markdown(f"**{t('detected_columns')}**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                item_col = st.selectbox(t("item_column"), columns,
                                        index=columns.index(item_col) if item_col in columns else 0)
            with col2:
                qty_col = st.selectbox(t("qty_column"), columns,
                                       index=columns.index(qty_col) if qty_col in columns else min(1, len(columns) - 1))
            with col3:
                unit_col = st.selectbox(t("unit_column"), columns,
                                        index=columns.index(unit_col) if unit_col in columns else min(2, len(columns) - 1))
            with col4:
                date_col = st.selectbox(t("date_column"), columns,
                                        index=columns.index(date_col) if date_col in columns else min(3, len(columns) - 1))

            # Threshold setting
            threshold = st.number_input(t("threshold_input"), min_value=0, value=10, step=1)

            if st.button(t("analyze_button"), type="primary"):
                # --- Current stock (latest per item) ---
                st.subheader(t("current_stock"))

                latest = con.execute(f"""
                    SELECT
                        "{item_col}" as item,
                        "{qty_col}" as quantity,
                        "{unit_col}" as unit,
                        "{date_col}" as date
                    FROM stock
                    WHERE ("{item_col}", "{date_col}") IN (
                        SELECT "{item_col}", MAX("{date_col}")
                        FROM stock
                        GROUP BY "{item_col}"
                    )
                    ORDER BY CAST("{qty_col}" AS DOUBLE)
                """).fetchall()

                # Alert for low stock
                alerts = []
                for item, qty, unit, date_val in latest:
                    try:
                        qty_num = float(qty)
                    except (ValueError, TypeError):
                        qty_num = 0
                    if qty_num <= threshold:
                        alerts.append(f"- **{item}**: {qty} {unit}")

                if alerts:
                    st.error(t("low_stock_alert").format(count=len(alerts)))
                    for alert in alerts:
                        st.markdown(alert)

                # Display current stock table
                df_latest = pd.DataFrame(latest, columns=[t("col_item"), t("col_qty"), t("col_unit"), t("col_date")])
                st.dataframe(df_latest, use_container_width=True)

                # --- Consumption trend ---
                st.subheader(t("trend_title"))

                trend_data = con.execute(f"""
                    SELECT
                        "{date_col}" as date,
                        "{item_col}" as item,
                        CAST("{qty_col}" AS DOUBLE) as quantity
                    FROM stock
                    ORDER BY "{date_col}"
                """).fetchall()

                if trend_data:
                    df_trend = pd.DataFrame(trend_data, columns=["date", "item", "quantity"])

                    # Pivot for chart
                    items = df_trend["item"].unique()
                    for item_name in items:
                        item_df = df_trend[df_trend["item"] == item_name].copy()
                        item_df = item_df.set_index("date")[["quantity"]]
                        st.markdown(f"**{item_name}**")
                        st.line_chart(item_df)

                # --- Summary statistics ---
                st.subheader(t("summary_title"))

                summary = con.execute(f"""
                    SELECT
                        "{item_col}" as item,
                        MIN(CAST("{qty_col}" AS DOUBLE)) as min_qty,
                        MAX(CAST("{qty_col}" AS DOUBLE)) as max_qty,
                        ROUND(AVG(CAST("{qty_col}" AS DOUBLE)), 1) as avg_qty,
                        COUNT(*) as records
                    FROM stock
                    GROUP BY "{item_col}"
                    ORDER BY "{item_col}"
                """).fetchall()

                df_summary = pd.DataFrame(
                    summary,
                    columns=[t("col_item"), t("col_min"), t("col_max"), t("col_avg"), t("col_records")]
                )
                st.dataframe(df_summary, use_container_width=True)

                # --- Download report ---
                st.markdown("---")

                report_data = con.execute(f"""
                    SELECT
                        "{item_col}" as item,
                        "{qty_col}" as quantity,
                        "{unit_col}" as unit,
                        "{date_col}" as date,
                        CASE
                            WHEN CAST("{qty_col}" AS DOUBLE) <= {threshold} THEN 'LOW'
                            ELSE 'OK'
                        END as status
                    FROM stock
                    ORDER BY "{item_col}", "{date_col}"
                """).fetchall()

                csv_buffer = io.StringIO()
                writer = csv.writer(csv_buffer)
                writer.writerow(["item", "quantity", "unit", "date", "status"])
                for row in report_data:
                    writer.writerow(row)

                st.download_button(
                    label=t("download_report"),
                    data=csv_buffer.getvalue(),
                    file_name="stock_report.csv",
                    mime="text/csv",
                )

            con.close()

        except Exception as e:
            st.error(t("error").format(error=str(e)))
else:
    st.info(t("no_file"))

# --- Footer ---
render_footer(libraries=["DuckDB", "Streamlit charts"])
