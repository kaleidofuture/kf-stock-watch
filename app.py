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
import json
import duckdb
import pandas as pd
from streamlit_js_eval import streamlit_js_eval

STORAGE_KEY = "kf-stock-watch-menus"

# --- Header ---
render_header()
st.info("💻 " + t("desktop_recommended"))

# --- Session state initialization ---
if "menus" not in st.session_state:
    st.session_state.menus = []  # [{name, price, ingredients: [{item, quantity, unit}]}]
if "reorder_points" not in st.session_state:
    st.session_state.reorder_points = {}  # {item_name: threshold}

# --- Load from localStorage ---
if "data_loaded" not in st.session_state:
    stored = streamlit_js_eval(js_expressions=f'localStorage.getItem("{STORAGE_KEY}")')
    if stored and stored != "null":
        try:
            st.session_state.menus = json.loads(stored)
        except Exception:
            pass
    st.session_state.data_loaded = True


def save_to_local_storage():
    """Save menus to browser localStorage."""
    data_json = json.dumps(st.session_state.menus, ensure_ascii=False)
    streamlit_js_eval(js_expressions=f'localStorage.setItem("{STORAGE_KEY}", {json.dumps(data_json)})')

# --- Sample CSV for download ---
SAMPLE_CSV = """item,quantity,unit,unit_price,date
Rice,50,kg,300,2026-03-01
Rice,45,kg,300,2026-03-08
Rice,30,kg,300,2026-03-15
Soy Sauce,20,bottles,250,2026-03-01
Soy Sauce,15,bottles,250,2026-03-08
Soy Sauce,8,bottles,250,2026-03-15
Chicken,30,kg,500,2026-03-01
Chicken,20,kg,500,2026-03-08
Chicken,10,kg,500,2026-03-15
Cooking Oil,10,L,400,2026-03-01
Cooking Oil,7,L,400,2026-03-08
Cooking Oil,3,L,400,2026-03-15
Napkins,500,sheets,5,2026-03-01
Napkins,350,sheets,5,2026-03-08
Napkins,100,sheets,5,2026-03-15
"""

# --- Inventory template CSV ---
TEMPLATE_CSV = "item,quantity,unit,unit_price,date\n"

# --- Tabs ---
tab_inventory, tab_menu, tab_cost = st.tabs([
    t("tab_inventory"),
    t("tab_menu"),
    t("tab_cost"),
])

# ============================================================
# TAB 1: Inventory Tracking (existing functionality)
# ============================================================
with tab_inventory:
    st.subheader(t("upload_title"))
    st.caption(t("upload_help"))

    # Download buttons
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        st.download_button(
            label=t("download_sample"),
            data=SAMPLE_CSV.encode("utf-8"),
            file_name="stock_sample.csv",
            mime="text/csv",
        )
    with btn_col2:
        st.download_button(
            label=t("download_template"),
            data=TEMPLATE_CSV.encode("utf-8"),
            file_name="stock_template.csv",
            mime="text/csv",
        )

    uploaded_file = st.file_uploader(t("upload_prompt"), type=["csv"])

    if uploaded_file is not None:
        content = uploaded_file.read().decode("utf-8-sig", errors="replace")

        with st.spinner(t("processing")):
            try:
                con = duckdb.connect(":memory:")

                # Load CSV into DuckDB via pandas (read_csv_auto doesn't accept StringIO as parameter)
                df_stock = pd.read_csv(io.StringIO(content))
                con.register("stock_view", df_stock)
                con.execute("CREATE TABLE stock AS SELECT * FROM stock_view")

                # Get column names
                columns = [col[0] for col in con.execute("DESCRIBE stock").fetchall()]
                col_lower = [c.lower() for c in columns]

                # Auto-detect column roles
                item_col = None
                qty_col = None
                unit_col = None
                date_col = None
                price_col = None

                item_keywords = ["item", "product", "name", "品名", "商品", "品目", "アイテム"]
                qty_keywords = ["quantity", "qty", "amount", "count", "数量", "在庫", "残量", "個数"]
                unit_keywords = ["unit", "単位"]
                date_keywords = ["date", "日付", "日時", "記録日"]
                price_keywords = ["unit_price", "price", "単価", "価格", "原価"]

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
                    if price_col is None:
                        for kw in price_keywords:
                            if kw in c:
                                price_col = columns[i]
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
                map_cols = st.columns(4 if price_col is None else 5)
                with map_cols[0]:
                    item_col = st.selectbox(t("item_column"), columns,
                                            index=columns.index(item_col) if item_col in columns else 0)
                with map_cols[1]:
                    qty_col = st.selectbox(t("qty_column"), columns,
                                           index=columns.index(qty_col) if qty_col in columns else min(1, len(columns) - 1))
                with map_cols[2]:
                    unit_col = st.selectbox(t("unit_column"), columns,
                                            index=columns.index(unit_col) if unit_col in columns else min(2, len(columns) - 1))
                with map_cols[3]:
                    date_col = st.selectbox(t("date_column"), columns,
                                            index=columns.index(date_col) if date_col in columns else min(3, len(columns) - 1))
                if price_col is not None and len(map_cols) > 4:
                    with map_cols[4]:
                        price_col = st.selectbox(t("price_column"), columns,
                                                 index=columns.index(price_col) if price_col in columns else min(4, len(columns) - 1))

                # Global threshold setting
                threshold = st.number_input(t("threshold_input"), min_value=0, value=10, step=1)

                # --- Per-item reorder points ---
                st.markdown(f"**{t('reorder_point_title')}**")
                st.caption(t("reorder_point_help"))

                # Get unique item names
                item_names = [row[0] for row in con.execute(f'SELECT DISTINCT "{item_col}" FROM stock ORDER BY "{item_col}"').fetchall()]

                rp_cols = st.columns(min(len(item_names), 4)) if item_names else []
                for idx, item_name in enumerate(item_names):
                    with rp_cols[idx % len(rp_cols)]:
                        current_rp = st.session_state.reorder_points.get(str(item_name), 0)
                        new_rp = st.number_input(
                            f"{item_name}",
                            min_value=0,
                            value=int(current_rp),
                            step=1,
                            key=f"rp_{item_name}",
                        )
                        st.session_state.reorder_points[str(item_name)] = new_rp

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

                    # Build unit price lookup if price column exists
                    unit_prices = {}
                    if price_col:
                        price_rows = con.execute(f"""
                            SELECT DISTINCT "{item_col}", CAST("{price_col}" AS DOUBLE)
                            FROM stock
                            WHERE "{price_col}" IS NOT NULL
                        """).fetchall()
                        for pitem, pprice in price_rows:
                            unit_prices[str(pitem)] = pprice
                        # Store in session for menu cost calculation
                        st.session_state["unit_prices"] = unit_prices
                        st.session_state["stock_items"] = [
                            {"item": str(row[0]), "unit": str(row[2])} for row in latest
                        ]

                    # Alert for low stock (global threshold)
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

                    # --- Per-item reorder point alerts ---
                    reorder_alerts = []
                    for item, qty, unit, date_val in latest:
                        try:
                            qty_num = float(qty)
                        except (ValueError, TypeError):
                            qty_num = 0
                        item_rp = st.session_state.reorder_points.get(str(item), 0)
                        if item_rp > 0 and qty_num <= item_rp:
                            reorder_alerts.append({
                                "item": str(item),
                                "qty": qty,
                                "unit": str(unit),
                                "threshold": item_rp,
                            })

                    if reorder_alerts:
                        st.subheader(t("reorder_recommend_title"))
                        st.warning(t("reorder_recommend_msg").format(count=len(reorder_alerts)))
                        df_reorder = pd.DataFrame(reorder_alerts, columns=["item", "qty", "unit", "threshold"])
                        df_reorder.columns = [t("col_item"), t("col_qty"), t("col_unit"), t("reorder_point_label")]
                        st.dataframe(df_reorder, use_container_width=True)

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

# ============================================================
# TAB 2: Menu Registration
# ============================================================
with tab_menu:
    st.subheader(t("menu_register_title"))
    st.caption(t("menu_register_help"))

    # --- Register new menu ---
    with st.form("menu_form", clear_on_submit=True):
        st.markdown(f"**{t('menu_new')}**")
        menu_name = st.text_input(t("menu_name_label"))
        menu_price = st.number_input(t("menu_price_label"), min_value=0, value=0, step=10)

        st.markdown(f"**{t('menu_ingredients_label')}**")
        st.caption(t("menu_ingredients_help"))

        # Up to 8 ingredient rows
        ingredient_rows = []
        for i in range(8):
            ing_cols = st.columns([3, 2, 2])
            with ing_cols[0]:
                ing_name = st.text_input(t("ingredient_name"), key=f"ing_name_{i}",
                                         label_visibility="collapsed" if i > 0 else "visible")
            with ing_cols[1]:
                ing_qty = st.number_input(t("ingredient_qty"), min_value=0.0, value=0.0, step=0.1,
                                          key=f"ing_qty_{i}",
                                          label_visibility="collapsed" if i > 0 else "visible")
            with ing_cols[2]:
                ing_unit = st.text_input(t("ingredient_unit"), key=f"ing_unit_{i}",
                                         label_visibility="collapsed" if i > 0 else "visible")
            ingredient_rows.append((ing_name, ing_qty, ing_unit))

        submitted = st.form_submit_button(t("menu_register_button"), type="primary")
        if submitted:
            if not menu_name:
                st.warning(t("menu_name_required"))
            else:
                ingredients = []
                for ing_name, ing_qty, ing_unit in ingredient_rows:
                    if ing_name.strip() and ing_qty > 0:
                        ingredients.append({
                            "item": ing_name.strip(),
                            "quantity": float(ing_qty),
                            "unit": ing_unit.strip(),
                        })
                menu_entry = {
                    "name": menu_name.strip(),
                    "price": int(menu_price),
                    "ingredients": ingredients,
                }
                st.session_state.menus.append(menu_entry)
                save_to_local_storage()
                st.success(t("menu_registered").format(name=menu_name.strip()))

    # --- Display registered menus ---
    if st.session_state.menus:
        st.markdown("---")
        st.subheader(t("menu_list_title"))

        unit_prices = st.session_state.get("unit_prices", {})

        for idx, menu in enumerate(st.session_state.menus):
            with st.expander(f"📋 {menu['name']}  —  ¥{menu['price']:,}"):
                if menu["ingredients"]:
                    ing_data = []
                    total_cost = 0.0
                    for ing in menu["ingredients"]:
                        up = unit_prices.get(ing["item"], 0)
                        cost = up * ing["quantity"]
                        total_cost += cost
                        ing_data.append({
                            t("col_item"): ing["item"],
                            t("col_qty"): ing["quantity"],
                            t("col_unit"): ing["unit"],
                            t("col_unit_price"): f"¥{up:,.0f}" if up else t("no_price_data"),
                            t("col_cost"): f"¥{cost:,.0f}" if up else "-",
                        })
                    df_ing = pd.DataFrame(ing_data)
                    st.dataframe(df_ing, use_container_width=True, hide_index=True)

                    # Cost summary
                    cost_ratio = (total_cost / menu["price"] * 100) if menu["price"] > 0 else 0
                    sc1, sc2, sc3 = st.columns(3)
                    with sc1:
                        st.metric(t("menu_total_cost"), f"¥{total_cost:,.0f}")
                    with sc2:
                        st.metric(t("menu_selling_price"), f"¥{menu['price']:,}")
                    with sc3:
                        st.metric(t("menu_cost_ratio"), f"{cost_ratio:.1f}%")

                    if cost_ratio > 35:
                        st.warning(t("cost_ratio_high"))
                    elif cost_ratio > 0:
                        st.success(t("cost_ratio_ok"))
                    else:
                        st.info(t("cost_ratio_no_price"))
                else:
                    st.info(t("menu_no_ingredients"))

                # Delete button
                if st.button(t("menu_delete"), key=f"del_menu_{idx}"):
                    st.session_state.menus.pop(idx)
                    save_to_local_storage()
                    st.rerun()
    else:
        st.info(t("menu_empty"))

# ============================================================
# TAB 3: Menu Cost Calculator
# ============================================================
with tab_cost:
    st.subheader(t("cost_calc_title"))
    st.caption(t("cost_calc_help"))

    unit_prices = st.session_state.get("unit_prices", {})

    if not st.session_state.menus:
        st.info(t("cost_calc_no_menus"))
    else:
        if not unit_prices:
            st.warning(t("cost_calc_no_prices"))

        # Summary table of all menus
        summary_data = []
        for menu in st.session_state.menus:
            total_cost = 0.0
            has_price = False
            for ing in menu["ingredients"]:
                up = unit_prices.get(ing["item"], 0)
                if up > 0:
                    has_price = True
                total_cost += up * ing["quantity"]

            cost_ratio = (total_cost / menu["price"] * 100) if menu["price"] > 0 else 0
            summary_data.append({
                t("menu_name_label"): menu["name"],
                t("menu_selling_price"): f"¥{menu['price']:,}",
                t("menu_total_cost"): f"¥{total_cost:,.0f}" if has_price else "-",
                t("menu_cost_ratio"): f"{cost_ratio:.1f}%" if has_price else "-",
                t("col_ingredients_count"): len(menu["ingredients"]),
            })

        df_cost = pd.DataFrame(summary_data)
        st.dataframe(df_cost, use_container_width=True, hide_index=True)

        # Detailed breakdown
        st.markdown("---")
        st.subheader(t("cost_detail_title"))

        selected_menu = st.selectbox(
            t("cost_select_menu"),
            options=[m["name"] for m in st.session_state.menus],
        )

        if selected_menu:
            menu = next((m for m in st.session_state.menus if m["name"] == selected_menu), None)
            if menu and menu["ingredients"]:
                detail_data = []
                total_cost = 0.0
                for ing in menu["ingredients"]:
                    up = unit_prices.get(ing["item"], 0)
                    cost = up * ing["quantity"]
                    total_cost += cost
                    detail_data.append({
                        t("col_item"): ing["item"],
                        t("ingredient_qty"): ing["quantity"],
                        t("col_unit"): ing["unit"],
                        t("col_unit_price"): f"¥{up:,.0f}" if up else t("no_price_data"),
                        t("col_cost"): f"¥{cost:,.0f}" if up else "-",
                    })

                df_detail = pd.DataFrame(detail_data)
                st.dataframe(df_detail, use_container_width=True, hide_index=True)

                cost_ratio = (total_cost / menu["price"] * 100) if menu["price"] > 0 else 0

                mc1, mc2, mc3, mc4 = st.columns(4)
                with mc1:
                    st.metric(t("menu_selling_price"), f"¥{menu['price']:,}")
                with mc2:
                    st.metric(t("menu_total_cost"), f"¥{total_cost:,.0f}")
                with mc3:
                    st.metric(t("menu_cost_ratio"), f"{cost_ratio:.1f}%")
                with mc4:
                    profit = menu["price"] - total_cost
                    st.metric(t("menu_profit"), f"¥{profit:,.0f}")

                # Visual bar for cost ratio
                if cost_ratio > 0:
                    st.progress(min(cost_ratio / 100, 1.0))
                    if cost_ratio > 35:
                        st.warning(t("cost_ratio_high"))
                    else:
                        st.success(t("cost_ratio_ok"))
            elif menu:
                st.info(t("menu_no_ingredients"))

# --- Footer ---
render_footer(libraries=["DuckDB", "Streamlit charts"], repo_name="kf-stock-watch")
