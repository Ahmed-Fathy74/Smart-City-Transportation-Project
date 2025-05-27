import streamlit as st
import pandas as pd
import networkx as nx
from utils.database import load_data, load_traffic_data
from utils.helpers import get_coordinates
from algorithms.graph_algorithms import (
    build_graph, 
    a_star, 
    compute_mst, 
    build_combined_graph,
    identify_transfer_points
)
from visualization.map_visualization import prepare_road_data, prepare_lines_df, visualize_map
from transit.transit_optimizer import TransitOptimizer

def main():
    st.set_page_config(layout="wide")
    
    # Load all data
    (neighborhoods, facilities, existing_roads, potential_roads, 
     metro_lines, bus_routes, demand_data, traffic_flow) = load_data()
    
    global locations
    locations = {}
    for _, row in neighborhoods.iterrows():
        locations[str(row['id']).strip()] = (float(row['x_coordinate']), float(row['y_coordinate']))
    for _, row in facilities.iterrows():
        locations[str(row['id']).strip()] = (float(row['x_coordinate']), float(row['y_coordinate']))

    # Prepare road data for visualization
    roads_df = prepare_road_data(existing_roads, neighborhoods, facilities, locations)

    # Create tabs for different functionalities
    tab1, tab2, tab3 = st.tabs(["Emergency Routing", "Network Optimization", "Transit Planning"])

    with tab1:
        st.title("🚑 Cairo Emergency Response System")
        
        st.sidebar.header("Emergency Parameters")
        
        time_period = st.sidebar.selectbox(
            "Time Period",
            ["Morning_Peak", "Afternoon", "Evening_Peak", "Night"],
            help="""
            Morning Peak: High traffic (2500-3800 vehicles/hour)
            Afternoon: Moderate traffic (1200-2200 vehicles/hour)
            Evening Peak: High traffic (2400-3500 vehicles/hour)
            Night: Low traffic (400-1200 vehicles/hour)
            """
        )
        
        emergency_mode = st.sidebar.checkbox("Emergency Mode (Priority Routing)", True)
        
        # Create mappings for node names
        node_names = {}
        for _, row in neighborhoods.iterrows():
            node_id = str(row['id']).strip()
            node_names[node_id] = f"{row['name']} ({node_id})"
        for _, row in facilities.iterrows():
            node_id = str(row['id']).strip()
            node_names[node_id] = f"{row['name']} ({node_id})"
        
        # Get valid nodes and hospitals with their names
        valid_nodes = list(locations.keys())
        hospitals = facilities[facilities['type'].str.lower() == 'medical']['id'].tolist()
        hospitals = [str(h).strip() for h in hospitals]

        # Create selection dropdowns with names
        start = st.sidebar.selectbox(
            "Emergency Origin",
            options=valid_nodes,
            format_func=lambda x: node_names.get(x, x)
        )
        hospital = st.sidebar.selectbox(
            "Destination Hospital",
            options=hospitals,
            format_func=lambda x: node_names.get(x, x)
        )

        if st.sidebar.button("Calculate Emergency Route"):
            with st.spinner("Optimizing route..."):
                road_graph = build_graph(
                    existing_roads, 
                    traffic_flow, 
                    time_period,
                    potential_roads,
                    emergency_mode
                )
                path = a_star(road_graph, start, hospital, locations)
            
            if path:
                try:
                    travel_time = sum(road_graph[u][v] for u,v in zip(path[:-1], path[1:]))
                    
                    minutes = travel_time * 60
                    st.success(f"⏱️ Estimated Emergency Response Time: {minutes:.1f} minutes")
                    
                    if time_period == "Morning_Peak":
                        st.warning("⚠️ High traffic period (Morning Peak) - Route optimized for congestion avoidance")
                    elif time_period == "Evening_Peak":
                        st.warning("⚠️ High traffic period (Evening Peak) - Route optimized for congestion avoidance")
                    elif time_period == "Night":
                        st.info("🌙 Low traffic period - Faster response time expected")
                    
                    visualize_map(
                        neighborhoods, 
                        facilities, 
                        roads_df=roads_df,
                        path=path,
                        view_type="Standard Map",
                        locations=locations
                    )
                except KeyError as e:
                    st.error(f"Missing road segment: {e}")
            else:
                st.error("No valid path found. Check network connectivity or try Emergency Mode.")
        else:
            # Show standard map when no route is calculated
            visualize_map(
                neighborhoods, 
                facilities, 
                roads_df=roads_df,
                view_type="Standard Map",
                locations=locations
            )

    with tab2:
        st.title("🚦 Cairo Smart Transportation Network Optimization")
        
        st.sidebar.header("Network Optimization Settings")
        view_type = st.sidebar.radio(
            "Select Map View",
            ["Standard Map", "Optimized Network (MST)"],
            index=0
        )

        # Build combined graph including potential roads
        combined_graph = build_combined_graph(existing_roads, potential_roads, neighborhoods, facilities)

        # Calculate costs
        standard_total_cost = existing_roads['distance_km'].astype(float).sum()
        st.sidebar.info(f"Standard Network Total Cost: {standard_total_cost:.2f} units")

        if view_type == "Optimized Network (MST)":
            mst = compute_mst(combined_graph)
            mst_edges_df = prepare_lines_df(mst.edges(data=True), neighborhoods, facilities)
            
            total_cost = sum(float(d['weight']) for _, _, d in mst.edges(data=True))
            st.sidebar.success(f"Optimized Network Total Cost: {total_cost:.2f} units")
            
            cost_savings = standard_total_cost - total_cost
            savings_percentage = (cost_savings / standard_total_cost) * 100
            st.sidebar.info(f"Cost Savings: {cost_savings:.2f} units ({savings_percentage:.1f}%)")
        else:
            mst_edges_df = None

        visualize_map(
            neighborhoods, 
            facilities, 
            roads_df=roads_df,
            view_type=view_type,
            mst_edges_df=mst_edges_df,
            locations=locations
        )

        if view_type == "Optimized Network (MST)" and mst_edges_df is not None:
            st.subheader("Optimized Network Details")
            st.write(f"Total roads in optimized network: {len(mst_edges_df)}")
            st.write("The optimized network (MST) connects all neighborhoods and facilities with the minimum total cost while maintaining adequate connectivity to important facilities.")
        else:
            st.subheader("Standard Network Details")
            st.write(f"Total roads in standard network: {len(existing_roads)}")
            st.write("This shows all existing roads in the transportation network.")

    with tab3:
        st.title("🚌 Cairo Transit Planning System")
        
        st.sidebar.header("Transit Planning Settings")
        capacity = st.sidebar.slider("Bus Capacity", 30, 100, 50)
        utilization = st.sidebar.slider("Utilization Rate (%)", 50, 100, 80)
        max_transfers = st.sidebar.slider("Max Transfers", 1, 3, 2)

        # Initialize transit optimizer
        optimizer = TransitOptimizer(bus_routes, metro_lines, demand_data, traffic_flow, neighborhoods, facilities)
        
        # Get transfer points and optimize routes
        transfer_points, _ = identify_transfer_points(bus_routes, metro_lines, neighborhoods, facilities)
        optimized_routes = optimizer.optimize_routes()
        
        visualize_map(
            neighborhoods, 
            facilities, 
            roads_df=roads_df,
            transfer_points=transfer_points,
            view_type="Standard Map",
            locations=locations
        )
        
        # Show optimized routes
        st.subheader("Optimized Routes")
        if not optimized_routes.empty:
            for _, route in optimized_routes.iterrows():
                st.write(f"""
                Route {route['fromid']} → {route['toid']}
                - 🕒 Estimated Time: {route['estimated_time']:.1f} minutes
                - 👥 Demand: {route['demand']} passengers
                - 🚏 Path: {' → '.join(route['path'])}
                """)
        
        # Show scheduling information
        st.subheader("Smart Scheduling")
        buses_needed = optimizer.calculate_buses_needed(capacity, 4, utilization)
        st.write(f"Total Buses Needed: {buses_needed}")
        
        schedule = optimizer.optimize_schedule(capacity, utilization)
        schedule_df = pd.DataFrame({
            'Time Period': ['Morning', 'Afternoon', 'Evening', 'Night'],
            'Number of Buses': schedule
        })
        st.bar_chart(schedule_df.set_index('Time Period'))

if __name__ == "__main__":
    main() 
