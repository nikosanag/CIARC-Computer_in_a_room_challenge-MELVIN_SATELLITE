import re
import numpy as np
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import random

DEBUG = True

# Global Parameters
X_MAX = 21600
Y_MAX = 10800
GREEN_CIRCLE_RADIUS = 75
PRUNING_RESIDUAL_THRESHOLD = 50
MIN_SAMPLE_POINTS = 3


def parse_data(data_lines):
    pattern = r'\[SUCCESS\] PING for Beacon with ID: (\d+) found at (\d+) , (\d+), with actual distance: (\d+) - Timestamp: ([\d-]+\s[\d:.]+)'
    points_by_id = {}

    for line in data_lines:
        match = re.search(pattern, line)
        if match:
            device_id, x, y, radius, timestamp = match.groups()
            try:
                points_by_id.setdefault(device_id, []).append((
                    int(x), int(y), int(radius), timestamp.strip()
                ))
            except ValueError as e:
                print(f"Error parsing line: {line}\nError: {e}")
    return points_by_id


def wrap_distance(a, b, limit):
    return min(abs(a - b), limit - abs(a - b))


def get_initial_guess(points):
    x_angles = np.radians([p[0] * 360 / X_MAX for p in points])
    y_angles = np.radians([p[1] * 360 / Y_MAX for p in points])
    mean_x = np.arctan2(np.mean(np.sin(x_angles)), np.mean(np.cos(x_angles))) * X_MAX / (2 * np.pi) % X_MAX
    mean_y = np.arctan2(np.mean(np.sin(y_angles)), np.mean(np.cos(y_angles))) * Y_MAX / (2 * np.pi) % Y_MAX
    return [mean_x, mean_y]


def weighted_objective(point, points):
    x, y = point
    total_error = 0
    for (cx, cy, r, _) in points:
        dx = wrap_distance(x, cx, X_MAX)
        dy = wrap_distance(y, cy, Y_MAX)
        dist = np.hypot(dx, dy)
        weight = 1 / (r + 1e-6)
        total_error += weight * (dist - r) ** 2
    return total_error


def estimate_position(points):
    initial_guess = get_initial_guess(points)
    return initial_guess if initial_guess else None


def iterative_pruning(points, min_points=MIN_SAMPLE_POINTS, max_iterations=100):
    current_points = points.copy()
    best_point = None
    best_points = None
    best_residual = float('inf')

    for _ in range(max_iterations):
        if len(current_points) < min_points:
            break

        optimal_point = estimate_position(current_points)
        if not optimal_point:
            break

        residuals = []
        for (x, y, r, _) in current_points:
            dx = wrap_distance(optimal_point[0], x, X_MAX)
            dy = wrap_distance(optimal_point[1], y, Y_MAX)
            residuals.append(abs(np.hypot(dx, dy) - r))

        avg_residual = np.mean(residuals)
        if avg_residual < best_residual:
            best_residual = avg_residual
            best_point = optimal_point
            best_points = current_points.copy()

        worst_idx = np.argmax(residuals)
        current_points.pop(worst_idx)

    return best_point, best_points, best_residual


def hybrid_localization(points):
    pruned_point, pruned_points, pruned_residual = iterative_pruning(points.copy())
    return pruned_point, pruned_points


def plot_results(points, optimal_point, device_id):
    if DEBUG:
        fig, ax = plt.subplots(figsize=(12, 8))
        for x, y, r, _ in points:
            circle = plt.Circle((x, y), r, fill=False, color='blue', alpha=0.2)
            ax.add_patch(circle)
            plt.scatter(x, y, color='blue', s=10)

        plt.scatter(optimal_point[0], optimal_point[1], color='green', s=100, label=f'Estimated Position')
        green_circle = plt.Circle(optimal_point, GREEN_CIRCLE_RADIUS, fill=False, color='green', linestyle='--',
                                  linewidth=1)
        ax.add_patch(green_circle)

        plt.title(f'Device {device_id}')
        ax.set_aspect('equal')
        plt.xlim(0, X_MAX)
        plt.ylim(Y_MAX, 0)
        plt.grid(True)
        plt.legend()
        plt.tight_layout()
        plt.savefig(f'output_device_{device_id}.png', dpi=300)
        plt.close()


def main():
    try:
        with open('ping_log.txt', 'r') as f:
            data_lines = f.readlines()

        points_by_id = parse_data(data_lines)
        for device_id, points in points_by_id.items():
            if DEBUG:
                print(f"\nProcessing Device {device_id} ({len(points)} pings)")
            if len(points) < 3:
                print("Not enough points for triangulation")
                continue

            optimal_point, filtered_points = hybrid_localization(points)
            if not optimal_point:
                print("Localization failed")
                continue
            if DEBUG:
                print(f"Final position: ({optimal_point[0]:.0f}, {optimal_point[1]:.0f})")
                print(f"Using {len(filtered_points)}/{len(points)} beacons")


            plot_results(filtered_points, optimal_point, device_id)
    except FileNotFoundError:
        print("Error: ping_log.txt file not found")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")


if __name__ == "__main__":
    main()
