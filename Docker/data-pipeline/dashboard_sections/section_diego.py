import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from data_utilities import database_connector  # Import the shared connection helpers


# =======================================================
# 1. DATA LOADING (Isolated and Cached)
# =======================================================

@st.cache_data(show_spinner="Loading Jose's Data: Provider Market Share...", ttl=600)
def load_jose_market_share():
    """Loads total trip counts and earnings per provider."""
    engine = database_connector.get_sqlalchemy_engine()

    query = """
            SELECT p.provider_name, \
                   COUNT(*)                   AS total_trips, \
                   SUM(t.base_passenger_fare) AS total_fare_revenue
            FROM trips t
                     JOIN providers p ON t.provider_id = p.id
            GROUP BY p.provider_name
            ORDER BY total_trips DESC \
            """
    df = pd.read_sql_query(query, engine)
    return df


# =======================================================
# 2. RENDERING FUNCTION (Called by app.py)
# =======================================================

def render():
    st.header("Diego's Analysis: Provider Market Share & Earnings")
    st.markdown("This section analyzes total trip volume and revenue across all providers.")

    # 1. Load Data
    market_share_df = load_jose_market_share()

    # 2. Visualization 1: Market Share
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.pie(
        market_share_df['total_trips'],
        labels=market_share_df['provider_name'],
        autopct='%1.1f%%',
        startangle=90
    )
    ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.
    plt.title("Trip Volume Distribution by Provider")
    st.pyplot(fig)

    # 3. Visualization 2: Revenue Table
    st.subheader("Revenue Details")
    st.dataframe(
        market_share_df.rename(columns={'total_fare_revenue': 'Total Revenue ($)'}),
        use_container_width=True
    )

    st.markdown("---")
