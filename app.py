from flask import Flask, request, jsonify, render_template
#import pymongo
import math
import itertools
import functools
import requests

#conn = pymongo.MongoClient("mongodb://localhost:27017/")
app = Flask(__name__)

# OpenRouteService API Key (Replace with your actual key)
ORS_API_KEY = "5b3ce3597851110001cf6248c8d1e6a1b0764fdeb5350f8727807004"

def get_route_data(point1, point2):
    """Fetch real-time travel duration and distance between two points using OpenRouteService API"""
    url = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }
    lat1, lon1 = float(point1[0]), float(point1[1]) 
    lat2, lon2 = float(point2[0]), float(point2[1]) 
    payload = {
        #"coordinates": [[point1["lon"], point1["lat"]], [point2["lon"], point2["lat"]]],
        "coordinates": [[lon1, lat1], [lon2, lat2]],
        "profile": "driving-car",
        "format": "geojson",
        "radiuses": [2000, 2000]  # Allows a larger search radius for routable points
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        data = response.json()

        if "features" in data and len(data["features"]) > 0:
            summary = data["features"][0]["properties"]["segments"][0]
            travel_time = summary["duration"] / 60  # Convert seconds to minutes
            distance = summary["distance"] / 1000  # Convert meters to km
            return travel_time, distance
        else:
            print("Error in API response:", data)
            return float("inf"), float("inf")  # Return infinite cost if no valid route
    except Exception as e:
        print("Error processing response:", e)
        return float("inf"), float("inf")


def calculate_haversine_distance(point1, point2):
    lat1, lon1 = float(point1[0]), float(point1[1]) 
    lat2, lon2 = float(point2[0]), float(point2[1]) 

    R = 6371  
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

 #if distance based, second parameter will be False
def create_cost_matrix(delivery_points, isTravelTimeBased):
    n = len(delivery_points)
    cost_matrix = [[0] * n for _ in range(n)]

    for i in range(n):
        for j in range(n):
            if i != j:
                if isTravelTimeBased:
                    travel_time, _ = get_route_data(delivery_points[i], delivery_points[j])
                    cost_matrix[i][j] = travel_time
                else:
                    cost_matrix[i][j] = calculate_haversine_distance(delivery_points[i], delivery_points[j])
    
    return cost_matrix

def solve_tsp(cost_matrix):
    n = len(cost_matrix)
    if n <= 1:
        return [], 0
    
    @functools.lru_cache(None)
    def tsp(mask, pos):
        if mask == (1 << n) - 1:
            return cost_matrix[pos][0]
        
        min_cost = float('inf')
        for nxt in range(n):
            if mask & (1 << nxt) == 0:
                new_cost = cost_matrix[pos][nxt] + tsp(mask | (1 << nxt), nxt)
                min_cost = min(min_cost, new_cost)
        
        return min_cost
    
    def reconstruct_path():
        mask, pos = 1, 0
        path = [0]
        while len(path) < n:
            best_nxt = None
            best_cost = float('inf')
            for nxt in range(n):
                if mask & (1 << nxt) == 0:
                    cost = cost_matrix[pos][nxt] + tsp(mask | (1 << nxt), nxt)
                    if cost < best_cost:
                        best_cost = cost
                        best_nxt = nxt
            path.append(best_nxt)
            mask |= (1 << best_nxt)
            pos = best_nxt
        return path
    
    best_route = reconstruct_path()
    min_cost = tsp(1, 0)
    
    return best_route, min_cost



'''def solve_tsp(cost_matrix):
    n = len(cost_matrix)
    if n <= 1:
        return [], 0

    min_cost = float('inf')
    best_route = None

    for perm in itertools.permutations(range(n)):
        cost = sum(cost_matrix[perm[i]][perm[i + 1]] for i in range(n - 1)) + cost_matrix[perm[-1]][perm[0]]
        if cost < min_cost:
            min_cost = cost
            best_route = perm

    return list(best_route), min_cost
'''
@app.route('/')
def home():
    return render_template('index.html')

@app.route("/map_input")
def map_input():
    return render_template("map_input.html")

@app.route("/routes")
def show_routes():
    return render_template("routes.html")  


@app.route('/calculate', methods=['POST'])
def calculate():
    try:
        data = request.json
        print("Received data:", data)  

        if "delivery_points" not in data or not data["delivery_points"]:
            return jsonify({"error": "No delivery points provided!"}), 400

        delivery_points = data["delivery_points"]
        print(delivery_points)

        try:
            delivery_points = [[float(point[0]), float(point[1])] for point in delivery_points]
        except ValueError:
            return jsonify({"error": "Invalid coordinates! Ensure they are numbers."}), 400

        print("Processed Delivery Points:", delivery_points)

        #if distance based, second parameter should be False
        cost_matrix = create_cost_matrix(delivery_points, False)
        print("Cost Matrix:", cost_matrix)

        if not cost_matrix or all(all(val == 0 for val in row) for row in cost_matrix):
            return jsonify({"error": "Invalid cost matrix. Please select different points!"}), 400

        

        optimal_route, optimal_cost = solve_tsp(cost_matrix)
        print("Optimal Route:", optimal_route, "Optimal Cost:", optimal_cost)
        return jsonify({
            "optimal_route": optimal_route,
            "optimal_cost": optimal_cost,
            "delivery_points": delivery_points,  
            "cost_matrix": cost_matrix
        })

        '''return jsonify({
            "cost_matrix": cost_matrix,
            "optimal_route": optimal_route,
            "optimal_cost": optimal_cost
        })'''

    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route('/calculate_time_based', methods=['POST'])
def calculate_time_based():
    try:
        data = request.json
        print("Received data:", data)  

        if "delivery_points" not in data or not data["delivery_points"]:
            return jsonify({"error": "No delivery points provided!"}), 400

        delivery_points = data["delivery_points"]

        try:
            delivery_points = [[float(point[0]), float(point[1])] for point in delivery_points]
        except ValueError:
            return jsonify({"error": "Invalid coordinates! Ensure they are numbers."}), 400

        print("Processed Delivery Points:", delivery_points)

         #if time based, second parameter should be True
        cost_matrix = create_cost_matrix(delivery_points, True)
        print("Cost Matrix:", cost_matrix)

        if not cost_matrix or all(all(val == 0 for val in row) for row in cost_matrix):
            return jsonify({"error": "Invalid cost matrix. Please select different points!"}), 400

        optimal_route, optimal_cost = solve_tsp(cost_matrix)
        print("Optimal Route:", optimal_route, "Optimal Cost:", optimal_cost)
        return jsonify({
            "optimal_route": optimal_route,
            "optimal_cost": optimal_cost,
            "delivery_points": delivery_points,  
            "cost_matrix": cost_matrix
        })

        '''return jsonify({
            "cost_matrix": cost_matrix,
            "optimal_route": optimal_route,
            "optimal_cost": optimal_cost
        })'''

    except Exception as e:
        print("Error:", str(e))
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
