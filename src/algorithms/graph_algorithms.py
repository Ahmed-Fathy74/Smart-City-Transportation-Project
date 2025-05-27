import heapq
import logging
from collections import defaultdict
from typing import List, Tuple, Dict, Set
import networkx as nx
import pandas as pd
from geopy.distance import geodesic
from utils.helpers import get_coordinates, haversine

logger = logging.getLogger(__name__)

def build_graph(roads, traffic_flow, time_period, potential_roads, emergency_mode=False):
    """Build a graph for routing"""
    graph = defaultdict(dict)
    try:
        traffic_dict = {(str(row['fromid']).strip(), str(row['toid']).strip()): row[time_period.lower()]
                       for _, row in traffic_flow.iterrows()}
        
        # add existing roads
        for _, road in roads.iterrows():
            add_road_to_graph(graph, road, traffic_dict, time_period, emergency_mode)
        
        if emergency_mode:
            for _, road in potential_roads.iterrows():
                add_road_to_graph(graph, road, traffic_dict, time_period, emergency_mode)
                
        logger.info(f"Graph nodes: {list(graph.keys())}")
        return graph
        
    except Exception as e:
        logger.exception("Graph build error")
        return graph

def add_road_to_graph(graph, road, traffic_dict, time_period, emergency_mode):
    """Add a road to the graph with appropriate weights"""
    from_id = str(road['fromid']).strip()
    to_id = str(road['toid']).strip()
    
    for src, dst in [(from_id, to_id), (to_id, from_id)]:
        distance = float(road['distance_km'])
        capacity = int(road.get('current_capacity', 2000))
        condition = int(road.get('coondition', 7))
        
        traffic = traffic_dict.get((src, dst), 0)
        
        time_period_factors = {
            'morning_peak': {'base_speed': 40, 'congestion_factor': 1.3},
            'afternoon': {'base_speed': 45, 'congestion_factor': 1.0},
            'evening_peak': {'base_speed': 35, 'congestion_factor': 1.4},
            'night': {'base_speed': 55, 'congestion_factor': 0.8}
        }
        
        period = time_period.lower()
        base_speed = time_period_factors[period]['base_speed']
        congestion_factor = time_period_factors[period]['congestion_factor']
        
        if emergency_mode:
            traffic = traffic * 0.2  # 80% traffic reduction 
            capacity = int(capacity * 1.5)  
            base_speed *= 1.2  
        
        free_flow_speed = base_speed * (condition / 10)  
        
        free_flow_time = distance / free_flow_speed
        
        alpha = 0.15 * congestion_factor
        beta = 4
        
        traffic_ratio = min(traffic / capacity if capacity != 0 else 1.0, 2.0)  # maximum at 200% capacity
        
        travel_time = free_flow_time * (1 + alpha * (traffic_ratio ** beta))
        
        graph[src][dst] = travel_time

def a_star(graph, start, end, locations):
    """A* pathfinding algorithm"""
    start = str(start).strip()
    end = str(end).strip()
    
    if start not in graph:
        logger.error(f"Start node {start} not in graph. Available nodes: {list(graph.keys())}")
        return None
    if end not in graph:
        logger.error(f"End node {end} not in graph. Available nodes: {list(graph.keys())}")
        return None

    open_heap = []
    heapq.heappush(open_heap, (0, start))
    came_from = {}
    g_scores = {start: 0}
    f_scores = {start: heuristic(start, end, locations)}

    while open_heap:
        current_f, current = heapq.heappop(open_heap)

        if current == end:
            path = reconstruct_path(came_from, current)
            logger.info(f"Path found: {path}")
            return path

        for neighbor, time in graph[current].items():
            tentative_g = g_scores.get(current, float('inf')) + time
            if tentative_g < g_scores.get(neighbor, float('inf')):
                came_from[neighbor] = current
                g_scores[neighbor] = tentative_g
                f_scores[neighbor] = tentative_g + heuristic(neighbor, end, locations)
                heapq.heappush(open_heap, (f_scores[neighbor], neighbor))

    logger.warning(f"No path found from {start} to {end}")
    return None

def heuristic(node, end, locations):
    """Heuristic function for A* algorithm"""
    try:
        lon1, lat1 = locations[node]
        lon2, lat2 = locations[end]
        return haversine(lon1, lat1, lon2, lat2) / 50  # 50 km/h average
    except KeyError as e:
        logger.error(f"Missing coordinates for node {e}")
        return float('inf')

def reconstruct_path(came_from, current):
    """Reconstruct the path from came_from dictionary"""
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    return path[::-1]

class UnionFind:
    """Union-Find data structure for Kruskal's algorithm"""
    def __init__(self):
        self.parent = {}
        self.rank = {}
    
    def make_set(self, vertex):
        if vertex not in self.parent:
            self.parent[vertex] = vertex
            self.rank[vertex] = 0
    
    def find(self, vertex):
        if self.parent[vertex] != vertex:
            self.parent[vertex] = self.find(self.parent[vertex])
        return self.parent[vertex]
    
    def union(self, vertex1, vertex2):
        root1 = self.find(vertex1)
        root2 = self.find(vertex2)
        
        if root1 != root2:
            if self.rank[root1] < self.rank[root2]:
                root1, root2 = root2, root1
            self.parent[root2] = root1
            if self.rank[root1] == self.rank[root2]:
                self.rank[root1] += 1

def kruskal_mst(edges: List[Tuple], vertices: Set) -> List[Tuple]:
    """Implementation of Kruskal's MST algorithm"""
    sorted_edges = sorted(edges, key=lambda x: x[2])
    
    uf = UnionFind()
    for vertex in vertices:
        uf.make_set(vertex)
    
    mst_edges = []
    for u, v, weight, data in sorted_edges:
        if uf.find(u) != uf.find(v):
            uf.union(u, v)
            mst_edges.append((u, v, data))
    
    return mst_edges

def compute_mst(graph):
    """Compute MST with facility connectivity validation"""
    #standard MST
    edges = [(u, v, d['weight'], d) for u, v, d in graph.edges(data=True)]
    vertices = set(graph.nodes())
    
    mst_edges = kruskal_mst(edges, vertices)
    
    mst = nx.Graph()
    for u, v, data in mst_edges:
        mst.add_edge(u, v, **data)
    
    facilities = pd.DataFrame([node for node in graph.nodes() if not str(node).isdigit()], columns=['ID'])
    
    if not validate_facility_connectivity(mst, facilities):
        uf = UnionFind()
        for vertex in vertices:
            uf.make_set(vertex)
        
        for u, v in mst.edges():
            uf.union(u, v)
        
        for facility in facilities['ID']:
            if mst.degree(facility) < 2:
                potential_edges = []
                for u, v, d in graph.edges(facility, data=True):
                    if v not in mst.neighbors(facility):
                        potential_edges.append((u, v, d['weight'], d))
                
                if potential_edges:
                    potential_edges.sort(key=lambda x: x[2])
                    
                    for u, v, _, data in potential_edges:
                        if uf.find(u) != uf.find(v):  
                            mst.add_edge(u, v, **data)
                            uf.union(u, v)
                            break
    
    return mst

def validate_facility_connectivity(mst: nx.Graph, facilities: pd.DataFrame, min_connections: int = 2) -> bool:
    """Validate that each facility has adequate connectivity in the MST"""
    facility_connections = defaultdict(int)
    
    for u, v in mst.edges():
        if u in facilities['ID'].values:
            facility_connections[u] += 1
        if v in facilities['ID'].values:
            facility_connections[v] += 1
    
    # check if all facilities meet minimum connectivity
    for facility_id in facilities['ID']:
        if facility_connections[facility_id] < min_connections:
            return False
    return True

def identify_transfer_points(bus_routes, metro_lines, neighborhoods, facilities, max_distance=500):
    """Detect transfer points between networks"""
    metro_stations = set()
    for _, line in metro_lines.iterrows():
        stations = line['stations']
        if isinstance(stations, str):
            stations = stations.split(',')
        metro_stations.update(stations)
    
    bus_stops = set()
    bus_coords = {}
    for _, route in bus_routes.iterrows():
        stops = route['stops']
        if isinstance(stops, str):
            stops = stops.split(',')
        for stop in stops:
            bus_stops.add(stop)
            bus_coords[stop] = get_coordinates(stop, neighborhoods, facilities)
    
    transfer_points = []
    connections = defaultdict(list)
    
    for metro in metro_stations:
        metro_coord = get_coordinates(metro, neighborhoods, facilities)
        for bus_stop, bus_coord in bus_coords.items():
            if geodesic(metro_coord, bus_coord).meters <= max_distance:
                transfer_points.append({
                    'id': f"{metro}-{bus_stop}",
                    'type': 'Bus-Metro Transfer',
                    'x_coordinate': (metro_coord[0] + bus_coord[0])/2,
                    'y_coordinate': (metro_coord[1] + bus_coord[1])/2
                })
                connections[metro].append(bus_stop)
                connections[bus_stop].append(metro)
    
    return pd.DataFrame(transfer_points), connections 

def calculate_existing_road_weight(distance: float, condition: int, capacity: float) -> float:
    """Calculate weight for existing roads"""
    weight = distance
    condition_factor = 2.0 - (condition / 10.0)
    weight *= condition_factor
    
    if capacity > 0:
        capacity_factor = 1.5 - (0.5 * min(capacity, 4000) / 4000)
        weight *= capacity_factor
    
    return weight

def calculate_potential_road_weight(distance: float, construction_cost: float, 
                                  pop_factor: float, facility_priority: float) -> float:
    """Calculate weight for potential roads"""
    weight = distance
    
    cost_per_km = construction_cost / distance if distance > 0 else construction_cost
    cost_factor = min(2.0, cost_per_km / 500)
    weight *= cost_factor
    
    if pop_factor > 0:
        pop_scale = min(1.0, pop_factor / 600000)
        weight *= (1.0 - (0.5 * pop_scale))
    
    if facility_priority > 0:
        weight *= 0.6
    
    weight = max(weight, distance * 0.5)
    return weight

def build_combined_graph(existing_roads: pd.DataFrame, potential_roads: pd.DataFrame, 
                        neighborhoods: pd.DataFrame, facilities: pd.DataFrame) -> nx.Graph:
    """Build combined graph including both existing and potential roads"""
    G = nx.Graph()

    # Add existing roads
    for _, row in existing_roads.iterrows():
        weight = calculate_existing_road_weight(
            distance=float(row['distance_km']),
            condition=row['coondition'],
            capacity=float(row['current_capacity'])
        )
        G.add_edge(
            row['fromid'], row['toid'],
            weight=weight,
            capacity=row['current_capacity'],
            condition=row['coondition'],
            road_type='existing'
        )

    # Population and facility priority
    pop_dict = neighborhoods.set_index(neighborhoods['id'].astype(str))['population'].to_dict()
    facility_priority = {fid: 1000000 for fid in facilities['id']}

    for _, row in potential_roads.iterrows():
        from_id = row['fromid']
        to_id = row['toid']
        dist = float(row['distance_km'])
        cost = row['construction_cost']

        pop_from = pop_dict.get(from_id, 0)
        pop_to = pop_dict.get(to_id, 0)
        pop_factor = pop_from + pop_to

        has_facility = (from_id in facility_priority) or (to_id in facility_priority)
        
        weight = calculate_potential_road_weight(
            distance=dist,
            construction_cost=cost,
            pop_factor=pop_factor,
            facility_priority=1 if has_facility else 0
        )

        G.add_edge(
            from_id, to_id,
            weight=weight,
            estimated_capacity=row['estimated_capacity'],
            construction_cost=cost,
            road_type='potential'
        )

    return G 
