import streamlit as st
import pandas as pd
import altair as alt

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
        SELECT * FROM supply.pricing_visualization
        ''', ttl=600)

        return sql_df


    # --- MODIFIED FUNCTION ---
    def grouped_by_category3(product_df):
        """
        Calculates the median of key metrics, now grouped by region,
        category level 3, and category level 2.
        """
        columns_to_aggregate = [
            'Executed_Margin',
            'Margin_Target',
            'All_Indexes',
            'Club',
            'Crawlers',
            'Infoprice',
            'NF'
        ]

        # Group by region, category3, and category2, then calculate the median.
        median_values = product_df.groupby(['region', 'category3', 'category2'])[
            columns_to_aggregate].median().reset_index()

        # Reorder columns for a more logical presentation.
        median_values = median_values[['region', 'category2', 'category3'] + columns_to_aggregate]

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

    view_level = st.sidebar.radio(
        "Selecione Nível de Visualização:",
        ("Por produto", "Por Categoria Nível 3"),
        key='view_level'
    )

    if view_level == "Por produto":
        data_for_filtering = df
    else:
        data_for_filtering = df_median

    # --- NEW: REGION FILTER ---
    # Get unique region options from the dataframe, ensuring 'PE' is first if it exists.
    try:
        region_options = sorted(data_for_filtering['region'].unique())
        default_region_index = region_options.index('PE') if 'PE' in region_options else 0

        selected_region = st.sidebar.selectbox(
            'Selecione a Região:',
            options=region_options,
            index=default_region_index  # Set 'PE' as the default
        )
        # Filter the dataframe immediately based on the selected region
        data_for_filtering = data_for_filtering[data_for_filtering['region'] == selected_region]

    except (KeyError, AttributeError):
        st.sidebar.error("A coluna 'region' não foi encontrada nos dados.")
        # Stop execution in the sidebar if the crucial 'region' column is missing.
        st.stop()

    # --- END OF NEW CODE ---

    # Dropdown for selecting the price index
    index_options = {
        "All Competitors": "All_Indexes",
        "Club da Cotação": "Club",
        "Crawlers": "Crawlers",
        "Infoprice": "Infoprice",
        "Nota Fiscal (NF)": "NF"
    }
    selected_index_name = st.sidebar.selectbox(
        'Selecione Price Index para comparação:',
        options=list(index_options.keys())
    )
    selected_index_col = index_options[selected_index_name]

    # Filters now use the region-filtered dataframe
    category2_options = ['All'] + list(data_for_filtering['category2'].unique())
    selected_category2 = st.sidebar.selectbox(
        'Selecione Categoria Nível 2:',
        options=category2_options
    )

    if selected_category2 == 'All':
        filtered_df = data_for_filtering
    else:
        filtered_df = data_for_filtering[data_for_filtering['category2'] == selected_category2]

    category3_options = ['All'] + list(filtered_df['category3'].unique())
    selected_category3 = st.sidebar.selectbox(
        'Selecione Categoria Nível 3:',
        options=category3_options
    )

    if selected_category3 == 'All':
        final_df = filtered_df
    else:
        final_df = filtered_df[filtered_df['category3'] == selected_category3]

    # --- MAIN PANEL: HEATMAP / SCATTER PLOT ---
    st.header(f"Análise de Price Index vs. {selected_index_name} (Região: {selected_region})")

    if final_df.empty:
        st.warning("Nenhum dado disponível para a combinação de filtros selecionada.")
    else:
        # --- MODIFIED: DYNAMIC TOOLTIPS WITH REGION ---
        if view_level == "Por produto":
            circle_size = 100
            tooltip_config = [
                alt.Tooltip('id:Q', title='Product ID'),
                alt.Tooltip('title:N', title='Product Title'),
                alt.Tooltip('region:N', title='Região'),
                alt.Tooltip('category2:N', title='Category L2'),
                alt.Tooltip('category3:N', title='Category L3'),
                alt.Tooltip('Executed_Margin:Q', title='Margem Executada (%)', format='.2f'),
                alt.Tooltip(f'{selected_index_col}:Q', title=f'Selected Index ({selected_index_name})', format='.2f'),
                alt.Tooltip('All_Indexes:Q', title='Index (All)', format='.2f'),
            ]
        else:  # Category Median view
            circle_size = 200
            tooltip_config = [
                alt.Tooltip('region:N', title='Região'),
                alt.Tooltip('category2:N', title='Category L2'),
                alt.Tooltip('category3:N', title='Category L3'),
                alt.Tooltip('Executed_Margin:Q', title='Median Executed Margin (%)', format='.2f'),
                alt.Tooltip(f'{selected_index_col}:Q', title=f'Median Selected Index ({selected_index_name})',
                            format='.2f'),
                alt.Tooltip('All_Indexes:Q', title='Median Index (All)', format='.2f'),
            ]

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
            color=color_encoding,
            tooltip=tooltip_config
        ).properties(
            width='container',
            height=500
        ).interactive()

        target_margin = final_df['Margin_Target'].mean()
        target_line = alt.Chart(pd.DataFrame({'Executed_Margin': [target_margin]})).mark_rule(
            color='red',
            strokeDash=[4, 4],
            size=2
        ).encode(
            y='Executed_Margin:Q'
        )

        target_label = alt.Chart(pd.DataFrame({'y': [target_margin], 'label': [f'Margem Target: {target_margin:.2f}%']})
                                 ).mark_text(
            align='left',
            baseline='bottom',
            dx=5,
            dy=-5,
            color='red'
        ).encode(
            y=alt.Y('y:Q'),
            text='label'
        )

        st.altair_chart(heatmap + target_line + target_label, use_container_width=True)

        with st.expander(f"Visualizar tabela {view_level} para a região de {selected_region}"):
            st.dataframe(final_df)
