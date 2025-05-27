import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import networkx as nx
import pydeck as pdk
from datetime import datetime, timedelta
import random
import plotly.express as px # For charts

# --- MySQL connection settings ---
USER = "root"
PASSWORD = "531169"
HOST = "localhost"
PORT = 3306
DATABASE = "Cairo_Transportation"

engine = create_engine(f"mysql+pymysql://{USER}:{PASSWORD}@{HOST}:{PORT}/{DATABASE}")

@st.cache_data(ttl=3600)
def load_data():
    neighborhoods = pd.read_sql("SELECT * FROM Neighborhoods_Districts", con=engine)
    facilities = pd.read_sql("SELECT * FROM Important_Facilities", con=engine)
    roads = pd.read_sql("SELECT * FROM Existing_Roads", con=engine)
    traffic = pd.read_sql("SELECT * FROM Traffic_Flow", con=engine)
    return neighborhoods, facilities, roads, traffic


def get_time_congestion_factor(hour):
    """Returns congestion multipliers based on time of day"""
    if 7 <= hour < 10:  
        return 1.8
    elif 16 <= hour < 19:  
        return 2.0
    elif 12 <= hour < 14:  # Lunch hour
        return 1.3
    elif hour >= 22 or hour < 5:  # Late night
        return 0.5
    else:  # Regular daytime
        return 1.0

def build_graph(roads_df, traffic_df, time_hour, selected_strategy="none", assume_two_way=False):
    G = nx.DiGraph()
    
    # Factor depends on time of day
    time_factor = get_time_congestion_factor(time_hour)
    
    # Select traffic column based on time
    traffic_col = 'Morning_Peak' if 5 <= time_hour < 12 else 'Evening_Peak'
    
    # Create a traffic lookup dictionary
    traffic_dict = {(row['FromID'], row['ToID']): row[traffic_col] for idx, row in traffic_df.iterrows()}
    
    processed_edges = set() # To keep track of edges for two-way addition

    # Strategy-specific preparations
    major_intersection_nodes = set()
    if selected_strategy == "smart_intersections":
        # Identify major intersections (e.g., nodes with degree > N)
        # For simplicity, let's consider nodes with degree > 4 as major for now.
        # This requires a temporary graph build or degree calculation beforehand if G is not yet populated.
        # A better approach might be to pre-calculate or use a specific attribute if available.
        # For now, we'll build a temporary full graph to get degrees then apply to the main G build.
        temp_G_for_degree = nx.DiGraph()
        for idx, row in roads_df.iterrows():
            temp_G_for_degree.add_edge(row['FromID'], row['ToID'])
            if assume_two_way:
                temp_G_for_degree.add_edge(row['ToID'], row['FromID'])
        
        for node in temp_G_for_degree.nodes():
            if temp_G_for_degree.degree(node) > 4: # Arbitrary threshold for major intersection
                major_intersection_nodes.add(node)

    key_corridor_road_ids = set() # Store (FromID, ToID) tuples for key corridors
    if selected_strategy == "key_corridors":
        # Identify key corridors (e.g., roads with capacity in top 25%)
        if not roads_df.empty:
            capacity_threshold = roads_df['Current_Capacity'].quantile(0.75)
            key_corridor_df = roads_df[roads_df['Current_Capacity'] >= capacity_threshold]
            for idx, row in key_corridor_df.iterrows():
                key_corridor_road_ids.add((row['FromID'], row['ToID']))

    for idx, row in roads_df.iterrows():
        from_id = row['FromID']
        to_id = row['ToID']
        dist = float(row['Distance_km'])
        capacity = row['Current_Capacity']
        
        # Forward Edge
        if (from_id, to_id) not in processed_edges:
            traffic_vol = traffic_dict.get((from_id, to_id), 0)

            if selected_strategy == "general_reduction":
                traffic_vol *= 0.85 # Simulate 15% general traffic reduction
            
            time_adjusted_traffic = traffic_vol * time_factor
            congestion = time_adjusted_traffic / capacity if capacity > 0 else 1
            
            # Apply strategy-specific congestion adjustments
            if selected_strategy == "smart_intersections":
                # Reduce congestion on roads leading to/from major intersections
                if (from_id in major_intersection_nodes or to_id in major_intersection_nodes) and congestion > 0.4:
                    congestion *= 0.7 # 30% reduction for smart signals effect
            elif selected_strategy == "key_corridors":
                if (from_id, to_id) in key_corridor_road_ids and congestion > 0.6:
                    congestion *= 0.65 # 35% reduction for key corridors
            # The old generic strategy: elif use_congestion_strategy and congestion > 0.5: congestion *= 0.7

            weight = dist * (1 + congestion)
            G.add_edge(from_id, to_id, weight=weight, distance=dist, congestion=congestion)
            processed_edges.add((from_id, to_id))

        # Reverse Edge (if assume_two_way)
        if assume_two_way and (to_id, from_id) not in processed_edges:
            traffic_vol_rev = traffic_dict.get((to_id, from_id), traffic_dict.get((from_id, to_id), 0) * 0.75)

            if selected_strategy == "general_reduction":
                traffic_vol_rev *= 0.85 # Simulate 15% general traffic reduction for reverse path too

            time_adjusted_traffic_rev = traffic_vol_rev * time_factor
            congestion_rev = time_adjusted_traffic_rev / capacity if capacity > 0 else 1
            
            # Apply strategy-specific congestion adjustments for reverse edge
            if selected_strategy == "smart_intersections":
                if (to_id in major_intersection_nodes or from_id in major_intersection_nodes) and congestion_rev > 0.4:
                    congestion_rev *= 0.7
            elif selected_strategy == "key_corridors":
                 # Assuming key corridor definition is directional as per roads_df. 
                 # If reverse is also a key corridor, it would be in key_corridor_road_ids as (to_id, from_id)
                if (to_id, from_id) in key_corridor_road_ids and congestion_rev > 0.6: 
                    congestion_rev *= 0.65
            
            weight_rev = dist * (1 + congestion_rev)
            G.add_edge(to_id, from_id, weight=weight_rev, distance=dist, congestion=congestion_rev)
            processed_edges.add((to_id, from_id))
    
    return G

def get_coordinates_map(neighborhoods_df, facilities_df):
    """Create a lookup dictionary of coordinates for all locations"""
    coords = {}
    for idx, row in neighborhoods_df.iterrows():
        coords[str(row['ID'])] = {
            'name': row['Name'],
            'lat': float(row['Y_coordinate']),
            'lon': float(row['X_coordinate'])
        }
    for idx, row in facilities_df.iterrows():
        coords[str(row['ID'])] = {
            'name': row['Name'],
            'lat': float(row['Y_coordinate']),
            'lon': float(row['X_coordinate'])
        }
    return coords

def find_multiple_paths(G, source, target, max_paths=2):
    """Find multiple diverse paths between source and target"""
    paths = []
    
    # Find the shortest path first
    try:
        main_path = nx.shortest_path(G, source=source, target=target, weight='weight')
        main_length = nx.shortest_path_length(G, source=source, target=target, weight='weight')
        paths.append((main_path, main_length))
        
        # Try to find an alternative route
        if max_paths > 1:
            # Create a copy of the graph for modifications
            G_temp = G.copy()
            
            # Penalize edges from the first path
            for i in range(len(main_path) - 1):
                u, v = main_path[i], main_path[i+1]
                if G_temp.has_edge(u, v):
                    # Increase the weight to discourage reusing this edge
                    G_temp[u][v]['weight'] *= 1.5
            
            # Find the alternative path
            try:
                alt_path = nx.shortest_path(G_temp, source=source, target=target, weight='weight')
                # Calculate the length using original edge weights
                alt_length = sum(G[alt_path[i]][alt_path[i+1]]['weight'] for i in range(len(alt_path)-1))
                
                # Only include if sufficiently different
                if len(set(alt_path) - set(main_path)) > 1:
                    paths.append((alt_path, alt_length))
            except nx.NetworkXNoPath:
                pass
    except nx.NetworkXNoPath:
        return []
    
    return paths

def shortest_path_with_closed(G, source, target, closed_edges):
    """Find shortest path avoiding closed edges"""
    # Remove closed edges
    G_temp = G.copy()
    for edge in closed_edges:
        if G_temp.has_edge(*edge):
            G_temp.remove_edge(*edge)
    
    # Try to find a path
    try:
        path = nx.shortest_path(G_temp, source=source, target=target, weight='weight')
        length = nx.shortest_path_length(G_temp, source=source, target=target, weight='weight')
        return path, length
    except nx.NetworkXNoPath:
        return None, None

def format_path(coords_map, path):
    """Format path for visualization"""
    route = []
    for node in path:
        data = coords_map.get(str(node), None)
        if data:
            route.append(data)
    return route

def calculate_eta(path, G):
    """Calculate estimated travel time based on distance and congestion"""
    if not path or len(path) < 2:
        return 0
    
    total_time_minutes = 0
    for i in range(len(path) - 1):
        if G.has_edge(path[i], path[i+1]):
            edge_data = G[path[i]][path[i+1]]
            distance = edge_data['distance']  # in km
            congestion = edge_data['congestion']
            
            # Base speed: 60 km/h, reduced by congestion
            speed = 60 / (1 + 2 * congestion)  # km/h
            time_minutes = (distance / speed) * 60
            total_time_minutes += time_minutes
    
    return total_time_minutes

def calculate_average_route_congestion(path, G):
    """Calculate the average congestion along a given path."""
    if not path or len(path) < 2 or not G:
        return 0.0  # Or None, depending on how you want to handle missing data
    
    path_congestions = []
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        if G.has_edge(u, v) and 'congestion' in G[u][v]:
            path_congestions.append(G[u][v]['congestion'])
    
    if not path_congestions:
        return 0.0 
    
    return sum(path_congestions) / len(path_congestions)

def get_road_status_color(congestion):
    """Return color based on congestion level"""
    if congestion < 0.3:
        return [0, 200, 0]  # Green
    elif congestion < 0.7:
        return [255, 165, 0]  # Orange
    else:
        return [200, 0, 0]  # Red

# Set page configuration
st.set_page_config(
    page_title="Cairo Transportation Planner",
    page_icon="🚦",
    layout="wide"
)

# Apply consistent styling
st.markdown("""
<style>
    /* Main theme colors */
    :root {
        --primary: #1E88E5;
        --primary-dark: #1565C0;
        --success: #4CAF50;
        --warning: #FFC107;
        --danger: #F44336;
        --background: #F5F7F9;
        --card: #FFFFFF;
        --text: #212121;
    }
    
    /* Main container */
    .main .block-container {
        padding: 2rem;
    }
    
    /* Headers */
    h1 {
        color: var(--primary-dark);
        font-size: 2.2rem;
        margin-bottom: 1rem;
    }
    
    h2, h3 {
        color: var(--primary);
    }
    
    /* Cards */
    .card {
        background-color: var(--card);
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    
    /* Metrics */
    .metric {
        text-align: center;
        padding: 1rem;
        background-color: white;
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    .metric-value {
        font-size: 1.8rem;
        font-weight: 600;
        color: var(--primary);
    }
    
    .metric-label {
        color: #757575;
        font-size: 0.9rem;
    }
    
    /* Route info */
    .route-info {
        background-color: #E3F2FD;
        border-radius: 8px;
        padding: 1rem;
        margin: 1rem 0;
        border-left: 4px solid var(--primary);
    }
    
    /* Notice boxes */
    .notice-box {
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
    }
    
    .help-box {
        background-color: #E8EAF6;
        border-left: 4px solid #3F51B5;
    }
    
    /* Improve sidebar section headers */
    .sidebar-header {
        color: var(--primary-dark);
        font-weight: 600;
        margin: 1.5rem 0 0.5rem 0;
        padding-bottom: 0.3rem;
        border-bottom: 1px solid #e0e0e0;
    }
    
    .tab-content {
        padding-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Page Header with welcome message
st.markdown("# 🚦 Cairo Transportation Planner")

# All content below was previously under a higher indentation level and is now unindented.
neighborhoods_df, facilities_df, roads_df, traffic_df = load_data()
coords_map = get_coordinates_map(neighborhoods_df, facilities_df)
all_nodes = {nid: f"{info['name']} ({nid})" for nid, info in coords_map.items()}

main_col, sidebar_col = st.columns([7, 3])

with sidebar_col:
    st.markdown("<div class='sidebar-header'>Journey Settings</div>", unsafe_allow_html=True)
    current_time = datetime.now()
    time_options = {
        "current": f"Current Time ({current_time.strftime('%H:%M')})",
        "morning_rush": "Morning Rush Hour (8:00)",
        "evening_rush": "Evening Rush Hour (17:00)",
        "off_peak": "Off-Peak Hours (14:00)"
    }
    time_setting = st.selectbox(
        "When are you traveling?",
        options=list(time_options.keys()),
        format_func=lambda x: time_options[x],
        key="planner_time_setting"
    )
    if time_setting == "current": time_hour = current_time.hour
    elif time_setting == "morning_rush": time_hour = 8
    elif time_setting == "evening_rush": time_hour = 17
    else: time_hour = 14
    
    congestion_factor = get_time_congestion_factor(time_hour)
    traffic_status = ("Heavy traffic" if congestion_factor >= 1.5 else "Moderate traffic" if congestion_factor >= 1.0 else "Light traffic")
    traffic_color = ("#F44336" if congestion_factor >= 1.5 else "#FFC107" if congestion_factor >= 1.0 else "#4CAF50")
    st.markdown(f'''<div style="padding: 8px; border-radius: 4px; background-color: {traffic_color}20; margin: 8px 0; text-align: center; color: {traffic_color}; font-weight: 500;">{traffic_status}</div>''', unsafe_allow_html=True)
    
    strategy_options = {
        "none": "None",
        "smart_intersections": "Smart Intersection Control",
        "key_corridors": "Key Corridor Management",
        "general_reduction": "General Traffic Reduction"
    }
    selected_strategy_planner = st.selectbox(
        "Congestion Reduction Strategy",
        options=list(strategy_options.keys()),
        format_func=lambda x: strategy_options[x],
        help="Apply a specific traffic management strategy to observe its potential impact.",
        key="planner_congestion_strategy_select"
    )
    
    st.markdown("<div class='sidebar-header'>Road Closures</div>", unsafe_allow_html=True)
    road_options_planner = []
    for idx, row in roads_df.iterrows():
        from_name = coords_map.get(str(row['FromID']), {}).get('name', str(row['FromID']))
        to_name = coords_map.get(str(row['ToID']), {}).get('name', str(row['ToID']))
        road_options_planner.append((row['FromID'], row['ToID'], f"{from_name} → {to_name}"))
    sample_roads_planner = road_options_planner[:min(10, len(road_options_planner))]
    closed_roads_selected_planner = st.multiselect(
        "Select closed roads (Planner)",
        options=[(r[0], r[1]) for r in sample_roads_planner],
        format_func=lambda x: f"{coords_map.get(str(x[0]), {}).get('name', x[0])} → {coords_map.get(str(x[1]), {}).get('name', x[1])}",
        help="Select roads that are currently closed due to construction, accidents, etc.",
        key="planner_closed_roads"
    )
    st.markdown("<div class='sidebar-header'>Map Legend</div>", unsafe_allow_html=True)
    st.markdown("""<div style="font-size: 0.9rem;">
        <div><span style="color: #27AE60;">●</span> Start point</div>
        <div><span style="color: #C0392B;">●</span> Destination</div>
        <div><span style="color: #27AE60;">━━</span> Free-flowing traffic</div>
        <div><span style="color: #F39C12;">━━</span> Moderate congestion</div>
        <div><span style="color: #C0392B;">━━</span> Heavy congestion</div>
    </div>""", unsafe_allow_html=True)

    st.markdown("<div class='sidebar-header'>Documentation</div>", unsafe_allow_html=True)
    try:
        with open("Algorithm_Explanation.pdf", "rb") as pdf_file:
            PDFbyte = pdf_file.read()
        st.download_button(
            label="Download Algorithm Explanation (PDF)",
            data=PDFbyte,
            file_name="Algorithm_Explanation.pdf",
            mime="application/octet-stream",
            key="download_algo_pdf"
        )
    except FileNotFoundError:
        pass # Silently skip creating the button if the PDF is not found

with main_col:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    route_col1, route_col2 = st.columns(2)
    with route_col1:
        source = st.selectbox("Starting Point", options=list(all_nodes.keys()), format_func=lambda x: all_nodes[x], help="Select your starting location", key="planner_source")
    with route_col2:
        target = st.selectbox("Destination", options=list(all_nodes.keys()), format_func=lambda x: all_nodes[x], help="Select where you want to go", key="planner_target")
    
    if st.button("Find Route", use_container_width=True, type="primary", key="planner_find_route"):
        if source == target:
            st.warning("⚠️ Please select different starting and destination points")
        else:
            with st.spinner("Finding the best route..."):
                G = build_graph(roads_df, traffic_df, time_hour, selected_strategy_planner)
                path, length = shortest_path_with_closed(G, source, target, closed_roads_selected_planner)
                alt_paths = [] 
            
            if path is None:
                st.info("ℹ️ Direct route not found. Trying to find a route to the nearest major facility to your destination...")
                facilities_nodes = {str(row['ID']): row for idx, row in facilities_df.iterrows()}
                if not facilities_df.empty:
                    target_coords = coords_map.get(str(target))
                    if not target_coords:
                        st.error("Could not get coordinates for the original target to find nearest facility.")
                        st.error("❌ No route found. The destination may be unreachable. This could be due to selected road closures or missing road segments in the database for this specific journey.")
                    else:
                        hubs_with_dist = []
                        for idx, fac_row in facilities_df.iterrows():
                            fac_id = str(fac_row['ID'])
                            fac_coords = coords_map.get(fac_id)
                            if fac_coords:
                                dist_sq = (fac_coords['lon'] - target_coords['lon'])**2 + (fac_coords['lat'] - target_coords['lat'])**2
                                hubs_with_dist.append({'id': fac_id, 'name': fac_row['Name'], 'dist_sq_to_target': dist_sq})
                        sorted_hubs = sorted(hubs_with_dist, key=lambda x: x['dist_sq_to_target'])
                        found_hub_route = False
                        for hub_candidate in sorted_hubs:
                            hub_id_str = str(hub_candidate['id'])
                            if hub_id_str not in G: continue
                            if hub_id_str == str(source): continue
                            hub_path, hub_length = shortest_path_with_closed(G, source, hub_id_str, closed_roads_selected_planner)
                            if hub_path:
                                st.success(f"✅ Could not route directly to {coords_map[target]['name']}. Instead, found route to nearest major facility: **{hub_candidate['name']}**.")
                                path = hub_path
                                length = hub_length
                                st.markdown(f"From **{hub_candidate['name']}**, you will need to find local transport to your original destination: **{coords_map[target]['name']}**.")
                                found_hub_route = True
                                break
                        if not found_hub_route:
                            st.error("❌ No route found. Tried direct path and routing to nearest major facilities without success. This could be due to road closures or missing/disconnected road segments in the database.")
                else:
                    st.error("❌ No facilities data available to attempt routing to a nearby hub. Direct route not found.")
            
            if path:
                eta_minutes = calculate_eta(path, G)
                arrival_time = datetime.now() + timedelta(minutes=eta_minutes)
                metrics_cols = st.columns(3)
                with metrics_cols[0]: st.markdown(f'''<div class="metric"><div class="metric-value">{length:.1f} km</div><div class="metric-label">Distance</div></div>''', unsafe_allow_html=True)
                with metrics_cols[1]: st.markdown(f'''<div class="metric"><div class="metric-value">{int(eta_minutes)} min</div><div class="metric-label">Travel Time</div></div>''', unsafe_allow_html=True)
                with metrics_cols[2]: st.markdown(f'''<div class="metric"><div class="metric-value">{arrival_time.strftime('%H:%M')}</div><div class="metric-label">Arrival Time</div></div>''', unsafe_allow_html=True)

                route_coords = format_path(coords_map, path)
                if route_coords:
                    midpoint_lat = sum(p['lat'] for p in route_coords) / len(route_coords)
                    midpoint_lon = sum(p['lon'] for p in route_coords) / len(route_coords)
                    path_segments = []
                    for i in range(len(path) - 1):
                        if G.has_edge(path[i], path[i+1]):
                            congestion = G[path[i]][path[i+1]]['congestion']
                            from_coord = coords_map.get(str(path[i]), {})
                            to_coord = coords_map.get(str(path[i+1]), {})
                            if 'lon' in from_coord and 'lat' in from_coord and 'lon' in to_coord and 'lat' in to_coord:
                                path_segments.append({"path": [(from_coord['lon'], from_coord['lat']), (to_coord['lon'], to_coord['lat'])], "color": get_road_status_color(congestion)})
                    segment_layers = [pdk.Layer("PathLayer",data=[segment],get_path="path",get_color="color",width_scale=10,width_min_pixels=5,pickable=True,rounded=True) for segment in path_segments]
                    for i_coord, p_coord in enumerate(route_coords):
                        if i_coord == 0: p_coord['color'] = [39, 174, 96]
                        elif i_coord == len(route_coords) - 1: p_coord['color'] = [192, 57, 43]
                        else: p_coord['color'] = [41, 128, 185]
                    points_layer = pdk.Layer("ScatterplotLayer",data=route_coords,get_position='[lon, lat]',get_fill_color='color',get_radius=150,pickable=True,stroked=True,get_line_color=[255,255,255],get_line_width=2)
                    alt_route_layers = [] 
                    general_congestion_map_data = []
                    if G:
                        for u_node, v_node, edge_data in G.edges(data=True):
                            from_coord_map = coords_map.get(str(u_node), {})
                            to_coord_map = coords_map.get(str(v_node), {})
                            if 'lon' in from_coord_map and 'lat' in from_coord_map and 'lon' in to_coord_map and 'lat' in to_coord_map:
                                base_color = get_road_status_color(edge_data['congestion'])
                                heatmap_color = base_color[:3] + [100]
                                general_congestion_map_data.append({"path": [(from_coord_map['lon'], from_coord_map['lat']), (to_coord_map['lon'], to_coord_map['lat'])], "color": heatmap_color})
                    general_congestion_layer = pdk.Layer("PathLayer", data=general_congestion_map_data, get_path="path", get_color="color", width_scale=5, width_min_pixels=1, pickable=False)
                    all_layers = [general_congestion_layer] + alt_route_layers + segment_layers + [points_layer]
                    view_state = pdk.ViewState(longitude=midpoint_lon,latitude=midpoint_lat,zoom=11,pitch=0)
                    st.pydeck_chart(pdk.Deck(layers=all_layers,initial_view_state=view_state,tooltip={"text":"{name}"},map_style="mapbox://styles/mapbox/streets-v11"))
                    
                    st.markdown('<div class="route-info">', unsafe_allow_html=True)
                    st.markdown(f"#### Route: {coords_map[source]['name']} to {coords_map[target]['name']}")
                    st.markdown("**Path:** " + " → ".join([coords_map.get(str(node), {}).get('name', str(node)) for node in path]))
                    st.markdown('</div>', unsafe_allow_html=True)

                with st.expander("Traffic Simulation & Analytics Insight", expanded=False):
                    st.markdown("Explore traffic patterns, network-wide statistics, and the impact of congestion reduction strategies.")

                    # 2. Before/after metrics for congestion strategies
                    st.subheader("Impact of Congestion Reduction Strategy on Selected Route")
                    if source and target:
                        st.markdown(f"Comparison for route from **{coords_map[source]['name']}** to **{coords_map[target]['name']}** at **{time_hour}:00**.")
                        st.caption("The metrics below compare the selected route with and without the chosen congestion reduction strategy.")
                        
                        # Calculate route metrics without strategy
                        G_analytics_no_strategy = build_graph(roads_df, traffic_df, time_hour, selected_strategy="none")
                        path_ns, len_ns = shortest_path_with_closed(G_analytics_no_strategy, source, target, closed_roads_selected_planner)
                        eta_ns = calculate_eta(path_ns, G_analytics_no_strategy) if path_ns else 0
                        avg_congestion_ns = calculate_average_route_congestion(path_ns, G_analytics_no_strategy) if path_ns else 0

                        # Calculate route metrics with selected strategy
                        strategy_name = strategy_options.get(selected_strategy_planner, "Selected Strategy")
                        G_analytics_with_strategy = build_graph(roads_df, traffic_df, time_hour, selected_strategy=selected_strategy_planner)
                        path_ws, len_ws = shortest_path_with_closed(G_analytics_with_strategy, source, target, closed_roads_selected_planner)
                        eta_ws = calculate_eta(path_ws, G_analytics_with_strategy) if path_ws else 0
                        avg_congestion_ws = calculate_average_route_congestion(path_ws, G_analytics_with_strategy) if path_ws else 0

                        if path_ns and path_ws:
                            # Create data for bar chart focusing only on Average Route Congestion
                            congestion_only_data = pd.DataFrame({
                                'Average Route Congestion': {
                                    'Baseline (Before Strategy)': float(f"{avg_congestion_ns:.2f}"),
                                    f'With Strategy ({strategy_name})': float(f"{avg_congestion_ws:.2f}")
                                }
                            })
                            
                            st.bar_chart(congestion_only_data)
                            
                            time_saved = eta_ns - eta_ws
                            if time_saved > 0.5: # Using a small threshold to avoid saying "0 minutes saved"
                                st.success(f"Applying the **{strategy_name}** strategy could save approximately **{int(round(time_saved))} minutes**.")
                            elif time_saved < -0.5:
                                st.warning(f"Applying the **{strategy_name}** strategy could add approximately **{int(round(abs(time_saved)))} minutes**.")
                            else:
                                st.info(f"Applying the **{strategy_name}** strategy made no significant difference in travel time for this route.")
                        else:
                            st.info("Could not calculate all route metrics for comparison with/without strategy. One or both paths not found.")
                    else:
                        st.info("Select a source and target in the main planner to see the strategy impact comparison.")
    st.markdown("</div>", unsafe_allow_html=True) # End card
