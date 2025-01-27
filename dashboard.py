import os
import streamlit as st
import pandas as pd
import pydeck as pdk
import plotly.express as px
import matplotlib.pyplot as plt
import calendar

# 1) ------------ CONFIGURE PAGE + WIDER SIDEBAR -------------
# Automatically use wide layout
st.set_page_config(layout="wide")

st.markdown(
    """
    <style>
    /* Main content container */
    [data-testid="stAppViewContainer"] {
        transition: margin-left 0.3s ease; /* Smooth transition when sidebar is toggled */
    }

    /* Apply centered alignment when sidebar is collapsed */
    [data-testid="collapsedSidebar"] + div [data-testid="stAppViewContainer"] {
        margin-left: auto;
        margin-right: auto;
        max-width: 80%; /* Limit the width for better centering */
    }

    /* Ensure charts are centered */
    [data-testid="stChart"] {
        margin: 0 auto; /* Center align charts */
    }
    </style>
    """,
    unsafe_allow_html=True
)






# 2) ------------- CACHING / LOAD DATA FUNCTIONS -------------
@st.cache_data
def load_bus_data(folder_path="bus_data_splits"):
    """
    Load and preprocess bus route data by merging all CSV files in the specified folder.

    Args:
        folder_path (str): Path to the folder containing CSV files. Default is "bus_data_splits".

    Returns:
        pd.DataFrame: Combined DataFrame with all data from the smaller CSV files.
    """
    def merge_csvs(input_folder):
        """
        Merge all CSV files in a folder into a single DataFrame.

        Args:
            input_folder (str): Directory containing the CSV files to merge.

        Returns:
            pd.DataFrame: Combined DataFrame with all data from the smaller CSV files.
        """
        all_files = [os.path.join(input_folder, f) for f in os.listdir(input_folder) if f.endswith('.csv')]
        combined_data = []

        for file in all_files:
            df = pd.read_csv(file)
            combined_data.append(df)

        merged_df = pd.concat(combined_data, ignore_index=True)
        return merged_df

    df = merge_csvs(folder_path)
    return df

@st.cache_data
def load_train_data(csv_path="timetable_train_database_preproccesed.csv"):
    """
    Load and preprocess train status data (also used for ridership analysis).
    """
    df = pd.read_csv(csv_path)
    return df


# 3) ------------- VISUALIZATION #1: BUS ROUTES CONNECTIVITY -------------
def show_bus_routes_connectivity():
    """
    Displays the bus routes connectivity map using pydeck.
    """
    # Research Question
    st.markdown("<h1 style='color: #D2691E;'>Israel Bus Routes Visualization 🚌</h1>", unsafe_allow_html=True)
    st.markdown(
        "### What are the most connected cities in Israel, and is there a strong dependency on specific transportation hubs?"
    )

    # -- Hideable filters for bus routes
    with st.expander("Filters (Bus Routes)", expanded=False):
        # Load bus data once (cached)
        df = load_bus_data("bus_data_splits")

        selected_years = st.multiselect(
            "Select Year(s):",
            sorted(df["year"].unique()),
            default=df["year"].unique()
        )
        if not selected_years:
            st.warning("Please select at least one year.")
            st.stop()

        # Filter by selected years
        df_filtered = df[df["year"].isin(selected_years)]

        origin_cities = sorted(df_filtered["origin_yishuv_nm"].unique())
        selected_origin = st.selectbox("Select Origin City:", origin_cities)

    # Filter by chosen origin city
    df_city = df_filtered[df_filtered["origin_yishuv_nm"] == selected_origin]

    # Group the filtered city data
    df_city_grouped = (
        df_city.groupby(
            [
                "origin_yishuv_nm",
                "destination_yishuv_nm",
                "lat_origin",
                "lon_origin",
                "lat_dest",
                "lon_dest",
            ],
            as_index=False
        )["trips_count"].sum()
    )

    # Choose top 15 routes
    df_top15 = df_city_grouped.nlargest(15, "trips_count")

    if df_top15.empty:
        st.warning("No data available for this selection.")
        return

    # Normalize trips_count for arc width
    df_top15["normalized_width"] = (
            df_top15["trips_count"] / df_top15["trips_count"].max() * 6
    )

    # Coordinates of the selected origin city
    origin_lat = df_top15.iloc[0]["lat_origin"]
    origin_lon = df_top15.iloc[0]["lon_origin"]

    # Define the view state
    view_state = pdk.ViewState(
        latitude=origin_lat,
        longitude=origin_lon,
        zoom=10,
        pitch=2
    )

    # ArcLayer
    arc_layer = pdk.Layer(
        "ArcLayer",
        data=df_top15,
        get_source_position="[lon_origin, lat_origin]",
        get_target_position="[lon_dest, lat_dest]",
        get_width="normalized_width",
        get_source_color="[240, 59, 32, 200]",
        get_target_color="[189, 189, 189, 200]",
        pickable=True
    )

    # Destination Layer
    destination_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_top15,
        get_position="[lon_dest, lat_dest]",
        get_radius=1000,
        get_fill_color="[49, 163, 84, 180]",
        pickable=True
    )

    # Origin Layer
    origin_layer = pdk.Layer(
        "ScatterplotLayer",
        data=df_top15.head(1),
        get_position="[lon_origin, lat_origin]",
        get_radius=2000,
        get_fill_color="[117, 107, 177, 200]",
        pickable=True
    )

    # Create the deck
    deck = pdk.Deck(
        layers=[arc_layer, destination_layer, origin_layer],
        initial_view_state=view_state,
        map_style="mapbox://styles/mapbox/dark-v10",
        tooltip={
            "html": (
                "<b>Origin:</b> {origin_yishuv_nm}<br/>"
                "<b>Destination:</b> {destination_yishuv_nm}<br/>"
                "<b>Total Trips Count:</b> {trips_count}"
            )
        }
    )

    # Make the chart bigger by specifying a height
    st.pydeck_chart(deck, use_container_width=True)

    # -- Key Insights Section (under the graph) --
    st.markdown("<h2 style='color: #9ACD32;'>Key Insights for the Bus Routes Connectivity</h2>", unsafe_allow_html=True)
    st.markdown(
        """
- **🧭 Identify Major Hubs**: Notice which origin cities frequently appear, indicating they're central hubs.
- **📊 Observe Changes Over Years**: Switch between different years to see how some routes grow in importance or diminish.
- **🚏 Potential Bottlenecks**: Very thick arcs may suggest routes that need increased service to handle demand.
- **🌐 Regional Disparities**: Cities in remote areas may have fewer connections, indicating potential gaps.
"""
    )


# 4) ------------- VISUALIZATION #2: TRAIN STATUS ANALYSIS -------------
def show_train_status_analysis():
    """
    Displays the train status stacked bar chart using Plotly.
    """
    # Research Question
    st.markdown("<h1 style='color: #8B4513;'>Train Status Analysis 🚂</h1>", unsafe_allow_html=True)
    st.markdown(
        "### To what extent does public transportation in Israel adhere to schedules, and where can improvements be made?"
    )

    # -- Hideable filters for train status
    with st.expander("Filters (Train Status)", expanded=False):
        df = load_train_data("timetable_train_database_preproccesed.csv")

        # Determine top 15 most popular stations in 2024 (if 2024 data exists)
        if 2024 in df['shana'].unique():
            top_stations_2024 = (
                df[df['shana'] == 2024]
                .groupby('train_station_nm')['status_count']
                .sum()
                .nlargest(15)
                .index
                .tolist()
            )
            default_year_filter = 2024
        else:
            top_stations_2024 = []
            default_year_filter = df['shana'].min()  # fallback

        # Select year
        available_years = sorted(df['shana'].unique())
        if default_year_filter in available_years:
            default_idx = available_years.index(default_year_filter)
        else:
            default_idx = 0

        year_filter = st.selectbox(
            "Select Year:",
            options=available_years,
            index=default_idx
        )

        # Two-way slider for selecting a range of months
        min_month, max_month = int(df['hodesh'].min()), int(df['hodesh'].max())
        month_range = st.slider(
            "Select Month Range:",
            min_value=min_month,
            max_value=max_month,
            value=(min_month, max_month)
        )

        # Limit the number of stations selectable to 20
        station_counts = df.groupby('train_station_nm')['status_count'].sum().sort_values(ascending=False)
        station_filter = st.multiselect(
            "Select Station Name (up to 20):",
            options=station_counts.index.tolist(),
            default=top_stations_2024
        )

        if len(station_filter) > 20:
            st.warning("You can select a maximum of 20 stations. Please remove some stations.")
            st.stop()

    # Apply filters
    if year_filter and station_filter:
        filtered_df = df[
            (df['shana'] == year_filter) &
            (df['train_station_nm'].isin(station_filter)) &
            (df['hodesh'] >= month_range[0]) &
            (df['hodesh'] <= month_range[1])
            ]

        # Get month names for the selected range
        start_month_name = calendar.month_name[month_range[0]]
        end_month_name = calendar.month_name[month_range[1]]

        st.subheader(f"Filters Applied: {start_month_name} - {end_month_name}, {year_filter}")

        # Custom color mapping for train status
        color_mapping = {
            "איחור": "#E41A1C",  # Red for delays
            "בזמן": "#377EB8",  # Blue for on-time
            "הקדמה ביציאה": "#4DAF4A"  # Green for early
        }

        grouped_data = filtered_df.groupby(
            ['train_station_nm', 'station_status_nm'], as_index=False
        )['status_count'].sum()

        stacked_bar_chart = px.bar(
            grouped_data,
            x='train_station_nm',
            y='status_count',
            color='station_status_nm',
            labels={
                'train_station_nm': 'Station Name',
                'status_count': 'Total Count',
                'station_status_nm': 'Status'
            },
            barmode='stack',
            color_discrete_map=color_mapping
        )

        stacked_bar_chart.update_layout(
            xaxis=dict(title='Station Name', categoryorder='total descending'),
            yaxis=dict(title='Total Count'),
            font=dict(size=12)
        )

        st.plotly_chart(stacked_bar_chart)

        # -- Key Insights Section (now placed under the chart) --
        st.markdown("<h2 style='color: #DC143C;'>Key Insights for Train Status Analysis</h2>", unsafe_allow_html=True)
        st.markdown(
            """
- **⏱️ Schedule Adherence**: Look for stations with high "on-time" rates (בזמן).
- **⚠️ Delays & Early Departures**: Stations with many "איחור" or "הקדמה ביציאה" may need operational improvements.
- **📆 Seasonal Trends**: Certain months (e.g., holidays, winter) could show spikes in delays.
- **🔍 Comparative Station Analysis**: See which stations fall behind relative to others.
"""
        )
    else:
        st.info("Please select a year, a range of months, and at least one station name.")


# 5) ------------- VISUALIZATION #3: TRAIN RIDERSHIP (LINE CHART) -------------
def show_train_ridership_events():
    """
    Displays how significant events in recent years affected train ridership across Israel.
    This includes a line chart with event annotations.
    """
    # Research Question
    st.markdown("<h1 style='color: #2E8B57;'>Train Ridership Over Time 📈</h1>", unsafe_allow_html=True)
    st.markdown(
        "### How have significant events in recent years affected train ridership across Israel?"
    )

    # -- Hideable filters and event annotations
    with st.expander("Filters (Train Ridership)", expanded=False):
        # Load the same train data (cached)
        data = load_train_data("timetable_train_database_preproccesed.csv")

     
        # Filter out rows with dates later than September 2024
        data = data[
            (data['shana'] < 2024) |
            ((data['shana'] == 2024) & (data['hodesh'] <= 9))
        ]
        
        # 1. City Filter (default to שדרות, if it exists; otherwise 'All')
        station_options = ["All"] + data['train_station_nm'].unique().tolist()
        default_city_index = 0
        if 'שדרות' in data['train_station_nm'].unique():
            default_city_index = station_options.index('שדרות')
        selected_city = st.selectbox(
            "Select Train Station",
            options=station_options,
            index=default_city_index
        )

        # 2. Year Range Slider (2019 to 2024)
        min_year, max_year = 2019, 2024
        year_range = st.slider(
            "Select Year Range:",
            min_value=min_year,
            max_value=max_year,
            value=(min_year, max_year),
            step=1
        )

    # Display event descriptions
    st.markdown("<h3 style='color: #696969;'>Event Descriptions</h3>", unsafe_allow_html=True)
    if selected_city == "All":
        station_description = "All train stations are included."
    else:
        station_description = f"Data specifically includes the {selected_city} train station."

    st.markdown(f"**Selected Station Description:** {station_description}")
    st.markdown(
        """
- **Corona (2020-03):** First major closure due to the COVID-19 pandemic.
- **Corona 2 (2020-12):** Second closure during the COVID-19 pandemic.
- **War (2023-10):** Iron Swords war in Israel.
- **Repair Work (2024-05):** Repair work in the south impacting train services.
"""
    )

    # Filter data by city
    if selected_city != "All":
        filtered_data = data[data['train_station_nm'] == selected_city].copy()
    else:
        filtered_data = data.copy()

    # Filter by chosen year range
    filtered_data = filtered_data[
        (filtered_data['shana'] >= year_range[0]) &
        (filtered_data['shana'] <= year_range[1])
        ]

    # Calculate total trips per month
    trips_per_month = filtered_data.groupby(['shana', 'hodesh'])['status_count'].sum().reset_index()

    # Combine year and month for plotting
    trips_per_month['year_month'] = (
            trips_per_month['shana'].astype(str) +
            '-' +
            trips_per_month['hodesh'].astype(str).str.zfill(2)
    )
    trips_per_month = trips_per_month.sort_values(by=['shana', 'hodesh']).reset_index(drop=True)

    # Event annotations to highlight on the chart
    annotation_mapping = {
        "Corona (2020-03)": {
            "date": "2020-03", "text": "Corona", "color": "#FF5733", "offset": (-30, -40)
        },
        "Corona 2 (2020-12)": {
            "date": "2020-12", "text": "Corona 2", "color": "#FF5733", "offset": (-30, -40)
        },
        "War (2023-10)": {
            "date": "2023-10", "text": "War", "color": "#B3B3B3", "offset": (-30, 20)
        },
        "Repair Work (2024-05)": {
            "date": "2024-05", "text": "Repair Work", "color": "#FFD700", "offset": (10, 20)
        }
    }

    # Utility function for reversing Hebrew text (for demonstration)
    def reverse_hebrew_text(text):
        return ''.join(reversed(text))

    # Dynamic Hebrew title (optional)
    if selected_city == "All":
        city_text = reverse_hebrew_text("מכל הערים")
    else:
        city_text = reverse_hebrew_text(selected_city)

    start_yr, end_yr = year_range
    if start_yr == end_yr:
        year_text = str(start_yr)
    else:
        year_text = f"{start_yr}-{end_yr}"

    hebrew_title = (
            f"{year_text} " +
            reverse_hebrew_text("החל משנת") +
            f" {city_text} " +
            reverse_hebrew_text("נסיעות חודשיות מתחנת")
    )

    # Plot using matplotlib
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.patch.set_facecolor('#2E2E2E')  # Dark gray background
    ax.set_facecolor('#1E1E1E')  # Slightly darker for plot area

    # Plot line
    ax.plot(
        trips_per_month['year_month'],
        trips_per_month['status_count'],
        marker='o',
        linestyle='-',
        linewidth=2,
        color='#3498DB',  # Bright blue line
        markerfacecolor='#78C679'  # Vibrant green markers
    )

    # Event Annotations
    for event, ann in annotation_mapping.items():
        date = ann["date"]
        if date in trips_per_month['year_month'].values:
            x_idx = trips_per_month[trips_per_month['year_month'] == date].index[0]
            y_value = trips_per_month.loc[x_idx, 'status_count']
            ax.annotate(
                ann["text"],
                (x_idx, y_value),
                textcoords="offset points",
                xytext=ann["offset"],
                ha='center',
                fontsize=14,
                fontweight='bold',
                color=ann["color"]
            )
            ax.scatter(x_idx, y_value, color=ann["color"], s=150, zorder=5)

    # Chart labeling
    ax.set_title(hebrew_title, fontsize=20, fontweight='bold', color='white')
    ax.set_xlabel('Year-Month', fontsize=16, color='white')
    ax.set_ylabel('Number of Trips', fontsize=16, color='white')
    ax.grid(color='gray', linestyle='--', linewidth=0.5, alpha=0.5)
    ax.tick_params(axis='y', colors='white')
    ax.tick_params(axis='x', colors='white')

    # Thin out the x-tick labels for readability
    x_labels = trips_per_month['year_month'].unique()
    reduced_labels = [x_labels[i] if i % 6 == 0 else '' for i in range(len(x_labels))]
    ax.set_xticks(range(len(x_labels)))
    ax.set_xticklabels(reduced_labels, rotation=45, fontsize=12, color='white')

    plt.tight_layout()
    st.pyplot(fig)

    # -- Key Insights Section (under the chart) --
    st.markdown("<h2 style='color: #CD853F;'>Key Insights for Train Ridership Over Time</h2>", unsafe_allow_html=True)
    st.markdown(
        """
- **📉 Impact of Major Events**: Notice sharp dips (or slower growth) during COVID lockdowns and war periods.
- **📈 Recovery Patterns**: See how ridership rebounds post-event; helps planning for future crises.
- **📍 Station-Specific Trends**: If a single station is chosen, you can spot local anomalies or spikes.
- **🔧 Maintenance & Seasonal Factors**: Repair work or seasonality can also shift ridership trends notably.
"""
    )


# 5) ------------- INTRODUCTION -------------
def show_introduction():
    """
    Introduction page with custom HTML and CSS blocks.
    """
    st.title("🎉 Welcome to the Israel Public Transportation Dashboard 🚍🚆")

    st.markdown(
        """
        <div style='background-color: #2b2b2b; padding: 20px; border-radius: 10px;'>
            <h2 style='color: #f4d03f;'>🌍 Overview</h2>
            <p style='color: #f0f0f0;'>This dashboard provides <strong>interactive visualizations</strong> of public transportation data in Israel, 
            focusing on <span style='color: #f39c12;'>bus routes connectivity</span>, 
            <span style='color: #27ae60;'>train status analysis</span>, 
            and <span style='color: #9b59b6;'>train ridership trends</span>.</p>
        </div>

        <div style='background-color: #353535; padding: 20px; margin-top: 20px; border-radius: 10px;'>
            <h2 style='color: #e74c3c;'>🎯 Purpose</h2>
            <ul style='color: #f0f0f0;'>
                <li>📊 <strong>Identify key insights</strong> into public transportation patterns.</li>
                <li>🔍 <strong>Highlight areas for improvement</strong> in schedule adherence and ridership.</li>
                <li>🛠 <strong>Provide tools</strong> for analyzing connectivity and usage trends.</li>
            </ul>
        </div>

        <div style='background-color: #2f3640; padding: 20px; margin-top: 20px; border-radius: 10px;'>
            <h2 style='color: #e84393;'>📖 How to Use</h2>
            <ul style='color: #f0f0f0;'>
                <li>🗺 Use the <strong>sidebar navigation</strong> to explore different visualizations.</li>
                <li>⚙ Apply <strong>filters</strong> to customize the data and focus on areas of interest.</li>
                <li>ℹ <strong>Hover over charts</strong> and maps to view additional information.</li>
            </ul>
        </div>

        <div style='background-color: #222f3e; padding: 20px; margin-top: 20px; border-radius: 10px;'>
            <h2 style='color: #6c5ce7;'>📌 Key Visualizations</h2>
            <ul style='color: #f0f0f0;'>
                <li>🚍 <strong>Bus Routes Connectivity:</strong> Explore the most connected cities and transportation hubs.</li>
                <li>🚉 <strong>Train Status Analysis:</strong> Evaluate adherence to schedules across train stations.</li>
                <li>📈 <strong>Train Ridership Over Time:</strong> Understand the impact of significant events on ridership.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.sidebar.markdown(
        """
        - <span style='color: #FF4500;'>**🚍 Bus Routes Connectivity**</span>:  
          Explore how Israeli cities are connected by bus routes, with visualizations highlighting top routes and their frequency.
        
        - <span style='color: #20B2AA;'>**🚂 Train Status Analysis**</span>:  
          Analyze train schedule adherence (on-time, delayed, or early departures) across various stations.
        
        - <span style='color: #6A5ACD;'>**📈 Train Ridership Over Time**</span>:  
          Investigate the impact of major events (e.g., COVID, war, repairs) on monthly train ridership trends.
        """,
        unsafe_allow_html=True
    )




# 6) ------------- MAIN APP -------------
def main():
    """
    Main function to combine all three visualizations.
    """
    # We can style the sidebar titles and sections with custom HTML + emojis
    st.sidebar.markdown("<h1 style='color: #FFA07A;'>🔎 Navigation</h1>", unsafe_allow_html=True)
    graph_option = st.sidebar.selectbox(
        "Choose a Graph:",
        [
            "Introduction",
            "Bus Routes Connectivity",
            "Train Status Analysis",
            "Train Ridership Over Time"
        ]
    )

    # Depending on the selected graph, show relevant info in the sidebar + call function
    if graph_option == "Bus Routes Connectivity":
        # --- Sidebar Explanation for Bus Routes ---
        st.sidebar.markdown("<hr style='border: 1px solid #FFA07A;'/>", unsafe_allow_html=True)
        st.sidebar.markdown("<h2 style='color: #FF4500;'>About the Bus Routes Connectivity Visualization 🚌</h2>",
                            unsafe_allow_html=True)
        st.sidebar.markdown(
            """
This dashboard displays how different Israeli cities are connected by bus routes, 
highlighting the top routes based on trip frequency.

**Key benefits**:
- Detect **major transportation hubs**.
- Spot **patterns of growth/decline** over time.
- Uncover **dependencies** on central routes.
"""
        )

        st.sidebar.markdown("<h2 style='color: #FFA500;'>How to Use</h2>", unsafe_allow_html=True)
        st.sidebar.markdown(
            """
1. **Select Year(s)**: Filter by one or multiple years.
2. **Select Origin City**: The map shows the **top 15** routes from that city.
3. **Map Interpretation**:
   - **Arc Thickness** = Frequency of trips
   - **Colors**:
     - Red arcs: connect origin to destinations
     - Green markers: destination cities
     - Purple marker: origin city
   - **Hover** to see trip counts and city names
4. **Zoom & Pan**: Use mouse or trackpad gestures to explore the map.
"""
        )
        show_bus_routes_connectivity()

    elif graph_option == "Train Status Analysis":
        # --- Sidebar Explanation for Train Status ---
        st.sidebar.markdown("<hr style='border: 1px solid #20B2AA;'/>", unsafe_allow_html=True)
        st.sidebar.markdown("<h2 style='color: #A52A2A;'>About the Train Status Dashboard 🚂</h2>",
                            unsafe_allow_html=True)
        st.sidebar.markdown(
            """
Evaluate **train schedule adherence** across various Israeli stations. 
This reveals how often trains are on time, early, or delayed.

**Use cases**:
- Identify **delay hotspots**.
- Compare **performance** across stations/months.
- Detect **seasonal or event-based disruptions**.
"""
        )

        st.sidebar.markdown("<h2 style='color: #2E8B57;'>How to Use</h2>", unsafe_allow_html=True)
        st.sidebar.markdown(
            """
1. **Select Year**: Focus on a single year's data.
2. **Select Month Range**: Narrow the analysis window (e.g., Jan–Mar).
3. **Select Stations** (up to 20): Compare these stations side-by-side.
4. **Check the Bar Chart**:
   - Each bar is subdivided by status type (on-time, early, delay).
   - Station performance is easy to compare at a glance.
"""
        )
        show_train_status_analysis()

    elif graph_option == "Train Ridership Over Time":
        # --- Sidebar Explanation for Train Ridership ---
        st.sidebar.markdown("<hr style='border: 1px solid #9370DB;'/>", unsafe_allow_html=True)
        st.sidebar.markdown("<h2 style='color: #6A5ACD;'>About the Train Ridership Dashboard 📈</h2>",
                            unsafe_allow_html=True)
        st.sidebar.markdown(
            """
Explore how **major events** (COVID, war, repair work) influenced train ridership. 
A line chart displays monthly ridership with annotations for noteworthy events.

**Insights**:
- Visualize **impact** of crises or special occasions.
- Compare **local vs. national** trends (by station).
- Understand **recovery patterns** post-event.
"""
        )

        st.sidebar.markdown("<h2 style='color: #8A2BE2;'>How to Use</h2>", unsafe_allow_html=True)
        st.sidebar.markdown(
            """
1. **Select Train Station**: Single station or "All" for aggregated data.
2. **Select Year Range**: Focus on a particular period (2019–2024).
3. **Line Chart**:
   - Monthly ridership counts
   - **Annotated events** highlight potential reasons for dips/spikes
"""
        )
        show_train_ridership_events()

    elif graph_option == "Introduction":
        show_introduction()


if __name__ == "__main__":
    main()
