import streamlit as st
import pandas as pd
import altair as alt
import SQLAlchemy

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="B2B Pricing Policy Review",
    page_icon="📊",
    layout="wide",
)


# --- PASSWORD AUTHENTICATION ---
def check_password():
    """Returns `True` if the user had the correct password."""

    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # First run, show input for password.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        return False
    elif not st.session_state["password_correct"]:
        # Password not correct, show input + error.
        st.text_input(
            "Password", type="password", on_change=password_entered, key="password"
        )
        st.error("😕 Password incorrect")
        return False
    else:
        # Password correct.
        return True


if check_password():
    # --- DATABASE CONNECTION ---
    @st.cache_data
    def get_data_from_db():
        # Initialize connection.

        conn = st.connection('mysql', type='sql')

        # Perform query.

        sql_df = conn.query('''
        WITH realized AS (WITH pnl_product AS (SELECT DATE_FORMAT(date, '%Y-%m-01')                                        AS month,
                                                      product.warehouse,
                                                      product.id,
                                                      product.sku,
                                                      product.category2,
                                                      product.title,
                                                      product.price,
                                                      sext.dist_cost + sext.warehouse_cost                                 AS ops_costs,
                                                      sext.cost_perc_rev                                                   AS other_costs,
                                                      SUM(lucro_bruto.total_quantity)                                      AS units,
                                                      SUM(lucro_bruto.total_gmv - lucro_bruto.total_discount) /
                                                      SUM(lucro_bruto.total_quantity)                                      AS avg_price,
                                                      SUM(lucro_bruto.total_gmv)                                           as gross_revenue,
                                                      SUM(lucro_bruto.total_net_revenue)                                   as net_revenue,
                                                      SUM(lucro_bruto.total_gross_profit)                                  as gross_profit,
                                                      SUM(lucro_bruto.total_adj_cost)                                      as cogs,
                                                      (SUM((sext.dist_cost + sext.warehouse_cost) * lucro_bruto.total_kg)) AS total_ops_cost,
                                                      (SUM(sext.cost_perc_rev * lucro_bruto.total_gmv))                    as total_other_costs,
                                                      (SUM(lucro_bruto.total_kg))                                          as weight,
                                                      ((SUM(lucro_bruto.total_gross_profit)
                                                          - (SUM((sext.dist_cost + sext.warehouse_cost) * lucro_bruto.total_kg))
                                                          - (SUM(sext.cost_perc_rev * lucro_bruto.total_gmv)))
                                                          )                                                                AS cont_profit
                                               FROM supply.lucro_bruto_raw_v2 lucro_bruto
                                                        INNER JOIN prasodata.product on lucro_bruto.product_id = product.id
                                                        LEFT JOIN supply.sheets_expenses_tree sext
                                                                  ON sext.state = product.region and
                                                                     sext.temperature = product.temperature AND
                                                                     DATE_FORMAT(sext.month, '%Y-%m-01') =
                                                                     DATE_FORMAT(date, '%Y-%m-01')
                                               WHERE DATE_FORMAT(date, '%Y-%m-01') = DATE_FORMAT(CURDATE(), '%Y-%m-01')
                                                 AND lucro_bruto.region IN ('PE', 'CE')
                                                 AND lucro_bruto.flag_transfer = 0
                                                 AND lucro_bruto.flag_transfer_devolution = 0
                                               GROUP BY lucro_bruto.product_id)
                          SELECT pl.month
                               , pl.warehouse
                               , pl.id
                               , pl.title
                               , pl.avg_price                     as avg_price
                               , pl.gross_profit / pl.net_revenue as gross_margin
                               , pl.gross_profit / pl.weight      as profit_kg
                               , pl.cont_profit / pl.net_revenue  as cont_margin
                               , pl.gross_revenue
                               , pl.net_revenue
                               , pl.gross_profit
                               , pl.cont_profit
                               , pl.other_costs
                               , pl.ops_costs
                               , pl.weight
                          FROM pnl_product pl
                          GROUP BY pl.id
                          ORDER BY net_revenue desc)
        SELECT p.id,
               p.title,
               p.category2,
               p.category3,
               ROUND(r.cont_margin * 100, 2) AS Executed_Margin,
               ROUND(piap.maco_target * 100, 2) AS Margin_Target,
               piap.price_index_all_all,
               piap.price_index_all_clube,
               piap.price_index_all_crawlers,
               piap.price_index_all_infoprice,
               piap.price_index_all_nf
        FROM pricing.price_index_active_pe piap
                 LEFT JOIN prasodata.product p ON piap.product_id = p.id
        LEFT JOIN realized r on piap.product_id = r.id
        WHERE piap.price_index_all_all BETWEEN 65 AND 135
          AND p.flag_weighted = 0
        ORDER BY category2, 
            category3, 
            price_index_all_all

        ''', ttl=600)

        return sql_df


    def grouped_by_category3(product_df):
        # Define the columns for which you want to calculate the median
        columns_to_aggregate = [
            'Executed_Margin',
            'Margin_Target',
            'price_index_all_all',
            'price_index_all_clube',
            'price_index_all_crawlers',
            'price_index_all_infoprice',
            'price_index_all_nf'
        ]

        # Group by both 'category3' and 'category2', calculate the median,
        # and then reset the index to turn the grouped columns back into regular columns.
        median_values = product_df.groupby(['category3', 'category2'])[columns_to_aggregate].median().reset_index()

        # Reorder columns for a more logical presentation
        median_values = median_values[['category2', 'category3'] + columns_to_aggregate]

        return median_values


    # --- LOAD DATA ---
    df = get_data_from_db()
    df_median = grouped_by_category3(df)

    # --- APP TITLE AND DESCRIPTION ---
    st.title("📊 Price Index Praso")
    st.markdown("""
    Esta aplicação permite-lhe rever a política de preços atual, visualizando os 
    produtos num mapa de calor com base na sua **Margem Target** e **Price Index**. 
    Utilize os filtros à esquerda para refinar a análise.
    """)

    # --- SIDEBAR FILTERS ---
    st.sidebar.header("Configurações")

    # --- NEW: SELECTOR FOR VIEW LEVEL ---
    view_level = st.sidebar.radio(
        "Selecione Nível de Visualização:",
        ("Por produto", "Por Categoria Nível 3"),
        key='view_level'
    )

    # --- NEW: CHOOSE DATAFRAME BASED ON SELECTION ---
    if view_level == "Por produto":
        data_for_filtering = df
    else:
        data_for_filtering = df_median

    # Dropdown for selecting the price index
    index_options = {
        "All Competitors": "price_index_all_all",
        "Club da Cotação": "price_index_all_clube",
        "Crawlers": "price_index_all_crawlers",
        "Infoprice": "price_index_all_infoprice",
        "Nota Fiscal (NF)": "price_index_all_nf"
    }
    selected_index_name = st.sidebar.selectbox(
        'Selecione Price Index para comparação:',
        options=list(index_options.keys())
    )
    selected_index_col = index_options[selected_index_name]

    # --- MODIFIED: FILTERS NOW USE THE DYNAMICALLY SELECTED DATAFRAME ---
    # Create a list of options for Category 2, including 'All'
    category2_options = ['All'] + list(data_for_filtering['category2'].unique())
    selected_category2 = st.sidebar.selectbox(
        'Selecione Categoria Nível 2:',
        options=category2_options
    )

    # Filter dataframe based on Category 2 selection
    if selected_category2 == 'All':
        filtered_df = data_for_filtering
    else:
        filtered_df = data_for_filtering[data_for_filtering['category2'] == selected_category2]

    # Create a list of options for Category 3 based on the filtered_df, including 'All'
    category3_options = ['All'] + list(filtered_df['category3'].unique())
    selected_category3 = st.sidebar.selectbox(
        'Selecione Categoria Nível 3:',
        options=category3_options
    )

    # Final filtered dataframe based on Category 3 selection
    if selected_category3 == 'All':
        final_df = filtered_df
    else:
        final_df = filtered_df[filtered_df['category3'] == selected_category3]

    # --- MAIN PANEL: HEATMAP / SCATTER PLOT ---
    st.header(f"Análise de Price Index vs. {selected_index_name}")

    if final_df.empty:
        st.warning("No data available for the selected filter combination.")
    else:
        # --- NEW: DYNAMIC TOOLTIPS AND SIZES BASED ON VIEW LEVEL ---
        if view_level == "Por produto":
            circle_size = 100
            tooltip_config = [
                alt.Tooltip('id:Q', title='Product ID'),
                alt.Tooltip('title:N', title='Product Title'),
                alt.Tooltip('category2:N', title='Category L2'),
                alt.Tooltip('category3:N', title='Category L3'),
                alt.Tooltip('Executed_Margin:Q', title='Margem Executada (%)', format='.2f'),
                alt.Tooltip(f'{selected_index_col}:Q', title=f'Selected Index ({selected_index_name})', format='.2f'),
                alt.Tooltip('price_index_all_all:Q', title='Index (All)', format='.2f'),
                alt.Tooltip('price_index_all_clube:Q', title='Index (Club)', format='.2f'),
                alt.Tooltip('price_index_all_crawlers:Q', title='Index (Crawlers)', format='.2f'),
                alt.Tooltip('price_index_all_infoprice:Q', title='Index (Infoprice)', format='.2f'),
                alt.Tooltip('price_index_all_nf:Q', title='Index (NF)', format='.2f')
            ]
        else:  # Category Median view
            circle_size = 200
            tooltip_config = [
                alt.Tooltip('category2:N', title='Category L2'),
                alt.Tooltip('category3:N', title='Category L3'),
                alt.Tooltip('Executed_Margin:Q', title='Median Executed Margin (%)', format='.2f'),
                alt.Tooltip(f'{selected_index_col}:Q', title=f'Median Selected Index ({selected_index_name})',
                            format='.2f'),
                alt.Tooltip('price_index_all_all:Q', title='Median Index (All)', format='.2f'),
            ]

        # --- MODIFIED SECTION: DYNAMIC COLOR ENCODING ---
        # Determine the color encoding based on the filter selection.
        # If a specific Category L2 is chosen, we color by Category L3 for better insight.
        if selected_category2 == 'All':
            color_encoding = alt.Color('category2:N', title='Categoria Nível 2')
        else:
            color_encoding = alt.Color('category3:N', title='Categoria Nível 3')

        heatmap = alt.Chart(final_df).mark_circle(size=circle_size, opacity=0.7).encode(
            x=alt.X(f'{selected_index_col}:Q',
                    title=f'Price Index ({selected_index_name})',
                    scale=alt.Scale(domain=[65, 135])),
            y=alt.Y('Executed_Margin:Q',
                    title='Executed Margin (%)' if view_level == "Por produto" else "Median Executed Margin (%)"),
            # Use the dynamically defined color encoding here
            color=color_encoding,
            tooltip=tooltip_config
        ).properties(
            width='container',
            height=500
        ).interactive()

        # ... the rest of your code for target lines and labels remains the same ...

        # Define the horizontal target line at the Margin Target
        target_margin = final_df['Margin_Target'].mean()

        target_line = alt.Chart(pd.DataFrame({'Executed_Margin': [target_margin]})).mark_rule(
            color='red',
            strokeDash=[4, 4],
            size=2
        ).encode(
            y='Executed_Margin:Q'
        )

        # Add a text label for the target line
        target_label = alt.Chart(pd.DataFrame({'y': [target_margin], 'label': [f'Margem Target: {target_margin:.2f}%']})
                                 ).mark_text(
            align='left',
            baseline='bottom',
            dx=5,  # Nudge text to the right
            dy=-5,  # Nudge text up
            color='red'
        ).encode(
            y=alt.Y('y:Q'),
            text='label'
        )

        st.altair_chart(heatmap + target_line + target_label, use_container_width=True)

        # --- DISPLAY FILTERED DATA TABLE ---
        with st.expander(f"Visualizar tabela {view_level}"):
            st.dataframe(final_df)
