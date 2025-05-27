import streamlit as st
import pydeck as pdk
import pandas as pd
from geopy.distance import geodesic

def prepare_road_data(roads, neighborhoods, facilities, locations):
    """Prepare road data for visualization"""
    road_segments = []
    
    for _, road in roads.iterrows():
        from_id = str(road['fromid']).strip()
        to_id = str(road['toid']).strip()
        
        if from_id in locations and to_id in locations:
            road_segments.append({
                'start_lon': locations[from_id][0],
                'start_lat': locations[from_id][1],
                'end_lon': locations[to_id][0],
                'end_lat': locations[to_id][1],
                'road_type': 'existing'
            })
    
    return pd.DataFrame(road_segments)

def prepare_lines_df(edges, neighborhoods, facilities):
    """Prepare line data for pydeck visualization"""
    lines = []
    nodes_df = pd.concat([
        neighborhoods.rename(columns={'id': 'nodeid'}),
        facilities.rename(columns={'id': 'nodeid'})
    ], ignore_index=True)
    nodes_df['nodeid'] = nodes_df['nodeid'].astype(str)
    nodes_df.set_index('nodeid', inplace=True)

    for u, v, data in edges:
        try:
            start_lat = float(nodes_df.loc[u]['y_coordinate'])
            start_lon = float(nodes_df.loc[u]['x_coordinate'])
            end_lat = float(nodes_df.loc[v]['y_coordinate'])
            end_lon = float(nodes_df.loc[v]['x_coordinate'])
        except KeyError:
            continue

        lines.append({
            'start_lat': start_lat,
            'start_lon': start_lon,
            'end_lat': end_lat,
            'end_lon': end_lon,
            'weight': data.get('weight', 1),
            'road_type': data.get('road_type', 'existing')
        })
    return pd.DataFrame(lines)

def visualize_map(neighborhoods, facilities, roads_df=None, path=None, transfer_points=None, 
                 view_type="Standard Map", mst_edges_df=None, locations=None):
    """Visualize the map with various optional layers"""
    view_state = pdk.ViewState(latitude=30.05, longitude=31.25, zoom=9.5, pitch=45)

    layers = [
        # Neighborhoods layer
        pdk.Layer(
            "ScatterplotLayer",
            data=neighborhoods,
            get_position=["x_coordinate", "y_coordinate"],
            get_color=[255, 0, 0, 160],
            get_radius=500,
            pickable=True,
            auto_highlight=True
        ),
        # Facilities layer
        pdk.Layer(
            "ScatterplotLayer",
            data=facilities,
            get_position=["x_coordinate", "y_coordinate"],
            get_color=[0, 0, 255, 160],
            get_radius=400,
            pickable=True,
            auto_highlight=True
        )
    ]

    if roads_df is not None and view_type == "Standard Map":
        layers.append(
            pdk.Layer(
                "LineLayer",
                data=roads_df,
                get_source_position=["start_lon", "start_lat"],
                get_target_position=["end_lon", "end_lat"],
                get_color=[255, 165, 0, 200],  # Orange for standard roads
                get_width=2,
                pickable=True,
                auto_highlight=True
            )
        )
    
    if mst_edges_df is not None and view_type == "Optimized Network (MST)":
        layers.append(
            pdk.Layer(
                "LineLayer",
                data=mst_edges_df,
                get_source_position=["start_lon", "start_lat"],
                get_target_position=["end_lon", "end_lat"],
                get_color=[0, 255, 0, 200],  # Green for MST roads
                get_width=4,
                pickable=True,
                auto_highlight=True
            )
        )

    if transfer_points is not None and not transfer_points.empty:
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=transfer_points,
                get_position=["x_coordinate", "y_coordinate"],
                get_color=[255, 255, 0, 200],  # Yellow for transfer points
                get_radius=300,
                pickable=True,
                auto_highlight=True
            )
        )

    if path and len(path) > 1:
        # Create path segments for visualization
        path_segments = []
        for i in range(len(path) - 1):
            start_node = path[i]
            end_node = path[i + 1]
            
            if start_node in locations and end_node in locations:
                path_segments.append({
                    "start_lon": locations[start_node][0],
                    "start_lat": locations[start_node][1],
                    "end_lon": locations[end_node][0],
                    "end_lat": locations[end_node][1]
                })
        
        if path_segments:
            layers.append(pdk.Layer(
                "LineLayer",
                data=pd.DataFrame(path_segments),
                get_source_position=["start_lon", "start_lat"],
                get_target_position=["end_lon", "end_lat"],
                get_color=[255, 0, 0, 200],  # red for path
                get_width=5,
                pickable=True,
                auto_highlight=True
            ))
            
            start_point = {
                "lon": locations[path[0]][0],
                "lat": locations[path[0]][1],
                "color": [0, 255, 0]  # Green for start
            }
            end_point = {
                "lon": locations[path[-1]][0],
                "lat": locations[path[-1]][1],
                "color":[0, 0, 139] # Dark blue for end
            }
            
            layers.append(pdk.Layer(
                "ScatterplotLayer",
                data=pd.DataFrame([start_point, end_point]),
                get_position=["lon", "lat"],
                get_color="color",
                get_radius=600,
                pickable=True,
                auto_highlight=True
            ))

    st.pydeck_chart(pdk.Deck(
        map_style="mapbox://styles/mapbox/light-v9",
        initial_view_state=view_state,
        layers=layers,
        tooltip={"html": "<b>ID:</b> {id}<br><b>Name:</b> {name}<br><b>Type:</b> {type}<br><b>Weight:</b> {weight}<br><b>Road Type:</b> {road_type}"}
    )) 
