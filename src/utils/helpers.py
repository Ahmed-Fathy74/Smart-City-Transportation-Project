import math
from geopy.distance import geodesic

def haversine(lon1, lat1, lon2, lat2):
    """Calculate the great circle distance between two points on the earth"""
    lon1, lat1, lon2, lat2 = map(math.radians, [lon1, lat1, lon2, lat2])
    
    
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(max(0, min(1, a))))  
    
    # radius of earth
    r = 6371
    
    return r * c

def get_coordinates(id, neighborhoods, facilities):
    """Extract coordinates from tables"""
    if str(id).isdigit():
        df = neighborhoods[neighborhoods["id"].astype(str) == str(id)]
    else:
        df = facilities[facilities["id"] == id]
    return (float(df["x_coordinate"].values[0]), float(df["y_coordinate"].values[0]))

def calculate_travel_time(start, end, neighborhoods, facilities, traffic_factor=1.0):
    """Calculate travel time using geodesic distance"""
    start_coord = get_coordinates(start, neighborhoods, facilities)
    end_coord = get_coordinates(end, neighborhoods, facilities)
    distance = geodesic(start_coord, end_coord).kilometers
    base_speed = 30  
    return (distance / (base_speed / traffic_factor)) * 60  
