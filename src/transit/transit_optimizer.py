import math
import pandas as pd
from collections import defaultdict
from typing import Dict, List, Tuple
from utils.helpers import get_coordinates, calculate_travel_time
from algorithms.graph_algorithms import identify_transfer_points

class RouteOptimizer:
    def __init__(self, graph, demands):
        self.graph = graph
        self.demands = demands
        self.memo = {}

    def find_optimal_path(self, origin, destination, max_stops=3):
        """Find the optimal path using memoization"""
        def dp(current, time, stops, visited):
            if current == destination:
                return (time, [current])
            if stops == 0:
                return (float('inf'), [])
            
            key = (current, stops)
            if key in self.memo:
                return self.memo[key]
            
            min_time = float('inf')
            best_path = []
            for neighbor, edge_time in self.graph[current].items():
                if neighbor not in visited:
                    new_time = time + edge_time
                    new_visited = visited.copy()
                    new_visited.add(neighbor)
                    future_time, path = dp(neighbor, new_time, stops-1, new_visited)
                    total_time = new_time + future_time
                    
                    if total_time < min_time:
                        min_time = total_time
                        best_path = [current] + path
            
            self.memo[key] = (min_time, best_path)
            return (min_time, best_path)
        
        return dp(origin, 0, max_stops, set([origin]))

class TransitOptimizer:
    def __init__(self, bus_routes, metro_lines, demand_data, traffic_flow, neighborhoods, facilities):
        self.bus_routes = bus_routes.copy()
        self.metro_lines = metro_lines.copy()
        self.demand_data = demand_data.copy()
        self.traffic_flow = traffic_flow.copy()
        self.neighborhoods = neighborhoods
        self.facilities = facilities
        
        if isinstance(self.bus_routes['stops'].iloc[0], str):
            self.bus_routes['stops'] = self.bus_routes['stops'].str.split(',')
        if isinstance(self.metro_lines['stations'].iloc[0], str):
            self.metro_lines['stations'] = self.metro_lines['stations'].str.split(',')
            
        self.demand_pairs = self.demand_data.set_index(['fromid', 'toid'])['daily_passengers']
        
        self.transfer_points, self.connections = identify_transfer_points(
            self.bus_routes, self.metro_lines, self.neighborhoods, self.facilities)
        self.transport_graph = self.build_transport_graph()

    def build_transport_graph(self):
        """Build the transportation network graph"""
        graph = defaultdict(dict)
        
        for _, route in self.bus_routes.iterrows():
            stops = route['stops']
            for i in range(len(stops)-1):
                from_stop = stops[i]
                to_stop = stops[i+1]
                time = calculate_travel_time(from_stop, to_stop, 
                                          self.neighborhoods, self.facilities)
                graph[from_stop][to_stop] = time
                graph[to_stop][from_stop] = time

        for _, line in self.metro_lines.iterrows():
            stations = line['stations']
            for i in range(len(stations)-1):
                from_station = stations[i]
                to_station = stations[i+1]
                time = calculate_travel_time(from_station, to_station,
                                          self.neighborhoods, self.facilities,
                                          traffic_factor=0.8)
                graph[from_station][to_station] = time
                graph[to_station][from_station] = time

        for metro, buses in self.connections.items():
            for bus in buses:
                transfer_time = 5  # 5 minutes transfer time
                graph[metro][bus] = transfer_time
                graph[bus][metro] = transfer_time

        return graph

    def optimize_routes(self, threshold=30000):
        """Optimize routes using dynamic programming"""
        optimizer = RouteOptimizer(self.transport_graph, self.demand_pairs)
        optimized_paths = []
        
        top_demands = self.demand_pairs.nlargest(10).index.tolist()
        
        for origin, destination in top_demands:
            time, path = optimizer.find_optimal_path(str(origin), str(destination))
            if time < float('inf'):
                optimized_paths.append({
                    'fromid': origin,
                    'toid': destination,
                    'path': path,
                    'estimated_time': time,
                    'demand': self.demand_pairs[(origin, destination)]
                })
        
        return pd.DataFrame(optimized_paths)

    def calculate_buses_needed(self, capacity=50, trips_per_day=4, target_utilization=80):
        """Calculate the number of buses needed"""
        total_demand = self.demand_data['daily_passengers'].sum()
        effective_capacity = capacity * trips_per_day * (target_utilization / 100)
        return math.ceil(total_demand / effective_capacity)

    def optimize_schedule(self, vehicle_capacity=50, target_utilization=80):
        """Optimize bus scheduling"""
        time_windows = {
            'morning_peak': self.traffic_flow['morning_peak'].sum(),
            'afternoon': self.traffic_flow['afternoon'].sum(),
            'evening_peak': self.traffic_flow['evening_peak'].sum(),
            'night': self.traffic_flow['night'].sum()
        }
        
        schedule = []
        for tw, demand in time_windows.items():
            buses = demand / (vehicle_capacity * (target_utilization / 100))
            schedule.append(math.ceil(buses))
        
        return schedule 
