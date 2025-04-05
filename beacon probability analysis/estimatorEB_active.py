import re
import matplotlib

matplotlib.use('Agg')  # Use a non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime
from scipy.optimize import minimize

DEBUG = False

'''
The main logic used in the evaluation phase. Its logic is described in the report.
'''

def find_solution():
    file_path = 'ping_log.txt'


    with open(file_path, 'r') as file:
        data = file.readlines()

    pattern = r'\[SUCCESS\] PING for Beacon with ID: (\d+) found at (\d+) , (\d+), with actual distance: (\d+) - Timestamp: ([\d-]+\s[\d:.]+)'

    # Store points by ID
    points_by_id = {}

    def objective_function(point, unique_points):
        x, y = point

        def wrap_distance(a, b, limit):
            direct = abs(a - b)
            wrapped = limit - direct
            return min(direct, wrapped)

        return sum((np.sqrt(wrap_distance(x, cx, 21600)**2 + wrap_distance(y, cy, 10800)**2) - r)**2 for cx, cy, r in unique_points)


    # Function to calculate optimal point
    def calculate_optimal_point(points):
        # Average radius for duplicate coordinates
        point_dict = {}
        for x, y, radius in points:
            key = (x, y)
            point_dict.setdefault(key, []).append(radius)

        unique_points = [(x, y, np.mean(radii)) for (x, y), radii in point_dict.items()]

        if len(unique_points) < 2:
            return None  # Need at least 2 unique points for triangulation

        # Initial guess for optimization
        x_coords = [p[0] for p in unique_points]
        y_coords = [p[1] for p in unique_points]

        x_min, x_max = min(x_coords), max(x_coords)
        y_min, y_max = min(y_coords), max(y_coords)
        initial_guess = [(x_min + x_max) / 2, (y_min + y_max) / 2]

        result = minimize(objective_function, initial_guess, args=(unique_points,), method='BFGS')
        return result.x


    for line in data:
        match = re.search(pattern, line)
        if match:
            device_id, x, y, radius, timestamp = match.groups()

            # Convert to integers
            x = int(x)
            y = int(y)
            radius = int(radius)

            # Group by device_id
            if device_id not in points_by_id:
                points_by_id[device_id] = []

            # Add new ping data
            points_by_id[device_id].append((x, y, radius))

            # Calculate new optimal point after each ping
            optimal_point = calculate_optimal_point(points_by_id[device_id])

            if DEBUG and optimal_point is not None:
                print(f"[ID: {device_id}] New ping at ({x}, {y}) with radius {radius} - "
                    f"Updated optimal point: ({optimal_point[0]:.2f}, {optimal_point[1]:.2f}) - "
                    f"Total pings: {len(points_by_id[device_id])}")

    # Create final plots for each ID
    for device_id, points in points_by_id.items():
        if len(points) < 2:
            if DEBUG:
                print(f"\nDevice {device_id}: Not enough data points for triangulation.")
            continue

        optimal_point = calculate_optimal_point(points)
        if optimal_point is None:
            if DEBUG:
                print(f"\nDevice {device_id}: Could not calculate optimal point.")
            continue

        green_circle_radius = 75

        if DEBUG:
            print(f"\nFinal results for Device {device_id}: Optimal point ({optimal_point[0]:.0f}, {optimal_point[1]:.0f})")

        if DEBUG: # This will be necessary, unless we scp the ping_log.txt locally inside a slot
            # Create plot for each ID
            fig, ax = plt.subplots(figsize=(10, 8))

            # Average radius for duplicate coordinates to reduce visual clutter
            point_dict = {}
            for x, y, radius in points:
                key = (x, y)
                point_dict.setdefault(key, []).append(radius)

            unique_points = [(x, y, np.mean(radii)) for (x, y), radii in point_dict.items()]

            # Draw detected circles
            for x, y, radius in unique_points:
                circle = plt.Circle((x, y), radius, fill=False, edgecolor='blue', alpha=0.7)
                ax.add_patch(circle)

            # Draw the optimized green circle
            green_circle = plt.Circle((optimal_point[0], optimal_point[1]), green_circle_radius,
                                    fill=False, edgecolor='green', linewidth=2)
            ax.add_patch(green_circle)

            # Set axis properties
            ax.set_aspect('equal')
            plt.xlim(0, 21600)
            plt.ylim(10800, 0)  # Inverted y-axis

            plt.grid(True)
            plt.xlabel('X Coordinate')
            plt.ylabel('Y Coordinate')
            plt.title(f'Optimal Point for Device {device_id}')

            # Save each plot by ID
            output_file = f'output_device_{device_id}.png'
            plt.savefig(output_file, dpi=300)
            print(f"Plot saved as {output_file}")

            # Close the figure to free memory
            plt.close(fig)
            
        return round(optimal_point[0]), round(optimal_point[1])

if __name__ == '__main__':
    find_solution()