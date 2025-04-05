import re
import matplotlib

matplotlib.use('Agg')  # Use a non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize

DEBUG = True

'''
This method takes into account the previous (unsuccessful) submission and ignores some points that are within a ceratain radius (150px)
from the wrongly guessed beacon position.
It was not used in the evaluation phase because the results were not that accurate.
'''

def process_ping_data(file_path, prev_est=None, prev_est2=None):
    X_MAX, Y_MAX = 21600, 10800  # Maximum coordinates
    DESIRED_DISTANCE = 150  # Desired distance from previous estimations
    pattern = (r'\[SUCCESS\] PING for Beacon with ID: (\d+) found at (\d+) , (\d+), '
               r'with actual distance: (\d+) - Timestamp: ([\d-]+\s[\d:.]+)')
    points_by_id = {}

    def wrap_distance(a, b, limit):
        direct = abs(a - b)
        wrapped = limit - direct
        return min(direct, wrapped)

    def distance_between_points(point1, point2):
        """Safe distance calculation with input validation"""
        try:
            # Convert to numpy arrays if they aren't already
            p1 = np.array(point1, dtype=float)
            p2 = np.array(point2, dtype=float)
            return np.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)
        except (IndexError, TypeError, ValueError) as e:
            if DEBUG:
                print(f"Warning: Invalid points in distance calculation - {e}")
            return float('inf')  # Return large distance if invalid


    def move_point_to_distances(origin, target, prev_points, desired_distance):
        current_point = np.array(target, dtype=float)
        if not prev_points or all(p is None for p in prev_points):
            return target

        prev_points = [np.array(p, dtype=float) for p in prev_points if p is not None]
        vectors = []
        needs_adjustment = False

        # Check distances to all previous points
        for prev_point in prev_points:
            distance = distance_between_points(prev_point, current_point)
            if distance < desired_distance:
                needs_adjustment = True
                # Calculate vector from previous point to current point
                vector = current_point - prev_point
                if np.linalg.norm(vector) > 0:
                    vector = vector / np.linalg.norm(vector)  # Normalize
                else:
                    vector = np.array([1, 0])  # Default direction if points coincide
                vectors.append(vector)

        if not needs_adjustment:
            return target

        if len(vectors) == 1:
            new_point = prev_points[0] + vectors[0] * desired_distance

        elif len(vectors) == 2:
            direction_vector = prev_points[1] - prev_points[0]

            perp_vector1 = np.array([-direction_vector[1], direction_vector[0]]) 
            perp_vector2 = np.array([direction_vector[1], -direction_vector[0]])  

            if np.linalg.norm(perp_vector1) > 0:
                perp_vector1 = perp_vector1 / np.linalg.norm(perp_vector1)
            if np.linalg.norm(perp_vector2) > 0:
                perp_vector2 = perp_vector2 / np.linalg.norm(perp_vector2)

            new_candidate1 = current_point + perp_vector1 * desired_distance
            new_candidate2 = current_point + perp_vector2 * desired_distance

            if np.linalg.norm(new_candidate1 - optimal_point) < np.linalg.norm(new_candidate2 - optimal_point):
                resultant_vector = perp_vector1
            else:
                resultant_vector = perp_vector2

            new_point = current_point + resultant_vector * desired_distance

        else:
            return current_point

        return new_point



    def objective_function(point, unique_points):
        # Base triangulation error
        return sum((np.sqrt(wrap_distance(point[0], cx, X_MAX) ** 2 +
                            wrap_distance(point[1], cy, Y_MAX) ** 2) - r) ** 2
                   for cx, cy, r in unique_points)

    def calculate_optimal_point(points, prev_est=None, prev_est2=None):
        point_dict = {}
        for x, y, radius in points:
            point_dict.setdefault((x, y), []).append(radius)
        unique_points = [(x, y, np.mean(radii)) for (x, y), radii in point_dict.items()]

        if len(unique_points) < 2:
            return None

        x_coords, y_coords = zip(*[(p[0], p[1]) for p in unique_points])
        initial_guess = [(min(x_coords) + max(x_coords)) / 2,
                         (min(y_coords) + max(y_coords)) / 2]

        # Calculate optimal point using triangulation
        result = minimize(objective_function,
                          initial_guess,
                          args=(unique_points,),
                          method='BFGS')

        optimal_point = np.abs(result.x)
        print(f"Opt point: {optimal_point}")

        # If previous estimations exist, adjust point to desired distances
        prev_points = [p for p in [prev_est, prev_est2] if p is not None]
        if prev_points:
            # Use the first previous point as the reference for movement
            optimal_point = move_point_to_distances(prev_points[0], optimal_point, prev_points, DESIRED_DISTANCE)

        return optimal_point

    with open(file_path, 'r') as file:
        for line in file:
            match = re.search(pattern, line)
            if match:
                device_id, x, y, radius, _ = match.groups()
                x, y, radius = map(int, (x, y, radius))
                points_by_id.setdefault(device_id, []).append((x, y, radius))

                # Check previous estimations for this device
                device_prev_est = prev_est.get(device_id) if prev_est else None
                device_prev_est2 = prev_est2.get(device_id) if prev_est2 else None

                optimal_point = calculate_optimal_point(
                    points_by_id[device_id],
                    device_prev_est,
                    device_prev_est2
                )
                if optimal_point is not None:
                    print(f"[ID: {device_id}] New ping at ({x}, {y}) with radius {radius} - "
                          f"Updated optimal point: ({optimal_point[0]:.0f}, {optimal_point[1]:.0f}) - "
                          f"Total pings: {len(points_by_id[device_id])}")

    final_estimations = {}
    for device_id, points in points_by_id.items():
        if len(points) < 2:
            print(f"\nDevice {device_id}: Not enough data points for triangulation.")
            continue

        # Check previous estimations for this device
        device_prev_est = prev_est.get(device_id) if prev_est else None
        device_prev_est2 = prev_est2.get(device_id) if prev_est2 else None

        optimal_point = calculate_optimal_point(
            points,
            device_prev_est,
            device_prev_est2
        )
        if optimal_point is None:
            print(f"\nDevice {device_id}: Could not calculate optimal point.")
            continue

        print(f"\nFinal results for Device {device_id}: Optimal point ({optimal_point[0]:.0f}, {optimal_point[1]:.0f})")
        final_estimations[device_id] = optimal_point
        # print(type(optimal_point))

        if DEBUG:
            fig, ax = plt.subplots(figsize=(10, 8))
            point_dict = {}
            for x, y, radius in points:
                point_dict.setdefault((x, y), []).append(radius)
            unique_points = [(x, y, np.mean(radii)) for (x, y), radii in point_dict.items()]
            for x, y, radius in unique_points:
                ax.add_patch(plt.Circle((x, y), radius, fill=False, edgecolor='blue', alpha=0.7))
            ax.add_patch(
                plt.Circle((optimal_point[0], optimal_point[1]), 75, fill=False, edgecolor='green', linewidth=0.5))

            # Plot previous estimations if they exist
            colors = ['red', 'orange']
            labels = ['Previous Estimation 1', 'Previous Estimation 2']
            for i, prev_point in enumerate([device_prev_est, device_prev_est2]):
                if prev_point is not None:
                    ax.scatter(prev_point[0], prev_point[1], color=colors[i], s=50, label=labels[i])
                    # Add line showing distance and movement
                    ax.plot([prev_point[0], optimal_point[0]],
                            [prev_point[1], optimal_point[1]],
                            color=colors[i], linestyle='--')

            ax.scatter(20000, 10000, color='red', s=5)
            ax.set_aspect('equal')
            plt.xlim(0, X_MAX)
            plt.ylim(Y_MAX, 0)
            plt.grid(True)
            plt.xlabel('X Coordinate')
            plt.ylabel('Y Coordinate')
            plt.title(f'Optimal Point for Device {device_id}')
            plt.legend()
            output_file = f'output_device_{device_id}.png'
            plt.savefig(output_file, dpi=300)
            print(f"Plot saved as {output_file}")
            plt.close(fig)

    return final_estimations

# Example usage:
# First run (no previous estimation)
first_run_results = process_ping_data('ping_log.txt')
print(type(first_run_results))

import time
time.sleep(10)
with open('ping_log.txt', 'a') as file:
    file.write("\n[SUCCESS] PING for Beacon with ID: 15 found at 2556 , 339, with actual distance: 767 - Timestamp: 2025-03-26 01:57:39.712149\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 2876 , 659, with actual distance: 485 - Timestamp: 2025-03-26 01:57:41.718483\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 3196 , 979, with actual distance: 100 - Timestamp: 2025-03-26 01:57:43.722332\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 3516 , 1299, with actual distance: 415 - Timestamp: 2025-03-26 01:57:45.720055\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 3836 , 1619, with actual distance: 1007 - Timestamp: 2025-03-26 01:57:47.947836\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 4156 , 1939, with actual distance: 1207 - Timestamp: 2025-03-26 01:57:49.886044\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 4480 , 2263, with actual distance: 1998 - Timestamp: 2025-03-26 01:57:52.392319\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 2340 , 123, with actual distance: 1054 - Timestamp: 2025-03-26 01:59:56.282886\n"
    )

# Second run with first previous estimation
second_run_results = process_ping_data('ping_log.txt', first_run_results)
time.sleep(10)
with open('ping_log.txt', 'a') as file:
    file.write("[SUCCESS] PING for Beacon with ID: 15 found at 2776 , 216, with actual distance: 941 - Timestamp: 2025-03-26 02:04:33.488098\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 3100 , 621, with actual distance: 551 - Timestamp: 2025-03-26 02:04:36.067013\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 3420 , 1021, with actual distance: 308 - Timestamp: 2025-03-26 02:04:38.044588\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 3744 , 1426, with actual distance: 933 - Timestamp: 2025-03-26 02:04:40.572235\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 4068 , 1831, with actual distance: 1106 - Timestamp: 2025-03-26 02:04:43.045064\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 4392 , 2236, with actual distance: 1711 - Timestamp: 2025-03-26 02:04:45.398659\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 2792 , 236, with actual distance: 850 - Timestamp: 2025-03-26 02:09:05.743775\n"
        "[SUCCESS] PING for Beacon with ID: 15 found at 3116 , 641, with actual distance: 481 - Timestamp: 2025-03-26 02:09:08.040447\n"
    )
# Third run with two previous estimations
third_run_results = process_ping_data('ping_log.txt', second_run_results, first_run_results)