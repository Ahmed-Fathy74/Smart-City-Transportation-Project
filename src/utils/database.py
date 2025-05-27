import streamlit as st
import mysql.connector
import pandas as pd
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def connect_db():
    """Create a connection to MySQL database"""
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="531169",
        database="Cairo_Transportation"
    )

@st.cache_data
def load_data():
    """Load all data from MySQL"""
    try:
        conn = connect_db()
        
        def load_table(table_name, id_columns=[]):
            df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
            df.columns = df.columns.str.lower()
            for col in id_columns:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.strip()
            return df

        neighborhoods = load_table("Neighborhoods_Districts", ['id'])
        facilities = load_table("Important_Facilities", ['id'])
        existing_roads = load_table("Existing_Roads", ['fromid', 'toid'])
        potential_roads = load_table("Potential_Roads", ['fromid', 'toid'])
        metro_lines = load_table("Metro_Lines")
        bus_routes = load_table("Bus_Routes")
        demand_data = load_table("Transportation_Demand", ['fromid', 'toid'])
        traffic_flow = load_table("Traffic_Flow", ['fromid', 'toid'])
        
        emergency_roads = pd.DataFrame([
            {'fromid': '1', 'toid': 'F10', 'distance_km': 4.2, 'current_capacity': 2500, 'coondition': 8},
            {'fromid': '3', 'toid': 'F9', 'distance_km': 1.5, 'current_capacity': 1800, 'coondition': 9}
        ])
        existing_roads = pd.concat([existing_roads, emergency_roads], ignore_index=True)
        
        potential_roads['current_capacity'] = 2000
        potential_roads['coondition'] = 7
        
        conn.close()
        return (neighborhoods, facilities, existing_roads, potential_roads, 
                metro_lines, bus_routes, demand_data, traffic_flow)
        
    except Exception as e:
        st.error(f"Database error: {str(e)}")
        logger.exception("Data loading failed")
        return [pd.DataFrame()]*8

def load_traffic_data():
    """Load temporal traffic data"""
    try:
        conn = connect_db()
        traffic_df = pd.read_sql("SELECT * FROM Traffic_Flow", conn)
        conn.close()

        traffic_dict = {}
        for _, row in traffic_df.iterrows():
            key = (str(row['FromID']).strip(), str(row['ToID']).strip())  
            traffic_dict[key] = {
                'morning_peak': row['Morning_Peak'],
                'afternoon': row['Afternoon'],
                'evening_peak': row['Evening_Peak'],
                'night': row['Night']
            }
        return traffic_dict
    except Exception as e:
        st.error(f"Failed to load traffic data: {e}")
        return {} 
