import requests
import time
import math
import random
import threading
from set_up import simulation
import datetime
import os
from beacon_position_calculator import find_solution


# Configuration
headers = {
    "Accept": "text/event-stream",
    # Include other headers if needed
}
MELVIN_BASE_URL = "http://10.100.10.14:33000"
HEADERS = {"User-Agent": "curl/7.68.0", "Content-Type": "application/json"}
BEACON_URL = f"{MELVIN_BASE_URL}/beacon"
ANNOUNCEMENTS_URL = f"{MELVIN_BASE_URL}/announcements"

# PHOTO_FOLDER = "images"  # Folder to save images


VX_DESIRED = 4
VY_DESIRED = 40 #because 40 takes an extra charge!!

MAXIMUM_BATTERY = 100
MINIMUM_BATTERY_CHECK = 5

ALLOWED_DELTA = 75
NOISE_RANGE = [-1, 1]

# Constants
STEP_SIZE = 2  # How finely to sample points on each GL (smaller = more accuracy)
THRESHOLD = 5  # Maximum distance tolerance for intersection matching

ping_threshold = 8 # Number of pings to make the estimation of EB position

# Store pings (Melvin's positions and measured distances)
pings = {}
gl_sets = {}

def get_observation():
    """Retrieve MELVIN's observation data."""
    try:
        # print(f"[DEBUG] Sending GET request to {MELVIN_BASE_URL}/observation")
        response = requests.get(f"{MELVIN_BASE_URL}/observation")
        # print(f"[DEBUG] Response status code: {response.status_code}")
        response.raise_for_status()
        # print(f"[DEBUG] Response JSON: {response.json()}")
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch observation data: {str(e)}")
        # time.sleep(2)  # ✅ Wait before retrying
        return get_observation()


def set_mode(mode, x, y, angle):
    """Set MELVIN's mode (e.g., acquisition or safe)."""
    if mode == 'communication':
        simulation(False, 20)
    payload = {"state": mode, "vel_x": x, "vel_y": y, "camera_angle": angle}
    response = requests.put(f"{MELVIN_BASE_URL}/control", json=payload)
    response.raise_for_status()


def wait(new):
    while True:
        check_wait = get_observation()
        time.sleep(0.3)
        #        obj = get_and_sort_objectives()
        set_mode(new, check_wait["vx"], check_wait["vy"], check_wait["angle"])

        if check_wait["state"] == new:
            break
        if check_wait["state"] == "safe":
            safe()
            break
        time.sleep(0.3)
    return


def safe():
    check = get_observation()
    # time.sleep(2)
    if check["state"] == "safe":
        simulation(False, 20)
        print("SAFE MODE ANOMALLY DETECTED AND HANDLED", flush=True)

        if check["battery"] <= 4:
            # time.sleep(3)
            protect_battery(MAXIMUM_BATTERY)
        else:
            # time.sleep(0.3)
            if check["state"] != "communication":
                set_mode("communication", check["vx"], check["vy"], check["angle"])
                # time.sleep(0.3)
                wait("communication")
    return


def protect_battery(x, angle="wide"):
    check1 = get_observation()
    # time.sleep(0.3)
    if check1["battery"] < x:
        simulation(False, 20)
        # time.sleep(0.3)
        set_mode("charge", check1["vx"], check1["vy"], angle)
        # time.sleep(0.3)
        wait("charge")

        while True:
            time.sleep(480 // 20)  # time to fully charge if x == 5
            check_new = get_observation()
            if check_new["battery"] == check_new["max_battery"]:
                simulation(False, 20)
                break

            if check_new["state"] == "safe":
                # time.sleep(0.3)
                safe()
                break
    return


################## STARTING WITH THE BEACON OBJECTIVE ROUTINES #########################################################


# Global variable to store the open connection
announcement_stream = None
got_ping = 0
beacon_id = None
d_noisy = {}



def listen_to_announcements():
    """ Continuously listen to /announcements in a separate thread. """
    global announcement_stream
    global got_ping, d_noisy
    global beacon_id
    print("[INFO] Subscribing to /announcements (SSE) for real-time updates...")
    check_start = get_observation()
    if check_start['state'] == 'communication':

        try:
            announcement_stream = requests.get(ANNOUNCEMENTS_URL, stream=True, headers=headers)
            announcement_stream.raise_for_status()

            if announcement_stream is None:
                print("[ERROR] Announcement stream is not initialized.")
                return

            if announcement_stream.status_code != 200:
                print(f"[ERROR] Status code {announcement_stream.status_code} from {ANNOUNCEMENTS_URL}")
                print("[ERROR] Response text:", announcement_stream.text)
                return

            if not os.path.exists(PING_SAVER_ANNOUNCEMENTS):
                try:
                    with open(PING_SAVER_ANNOUNCEMENTS, "w") as file:
                        file.write("")  # Create an empty file
                    print(f"[INFO] Created log file: {PING_SAVER_ANNOUNCEMENTS}")
                except PermissionError:
                    print("[ERROR] Permission denied! Unable to create log file in root directory.")
                    return None

            print(f"[DEBUG] Entering while loop inside func listen_to_announcements()")
            while True:
                    safe()
                    protect_battery(5)
                    simulation(False, 1)
                    check69=get_observation()
                    if check69['state'] != 'communication':
                        set_mode('communication', check69['vx'], check69['vy'], check69['angle'])
                        wait('communication')
                    if check69['state'] == 'communication':
                        for line in announcement_stream.iter_lines(chunk_size=1, decode_unicode=True):
                            check70=get_observation()
                            if line:
                                print(line)
                                with open(BEACON_LOG_FILE_PATH, "w") as file:
                                    file.write(
                                        f"Line {line}  - Timestamp: {datetime.datetime.now()}\n")

                                # print(f"[DEBUG] Received announcement: {line}")
                                message = line.strip()
                                if ('ping' in message):
                                    print(f'MESSAGE WITH PING: {line}')
                                if ("GALILEO_MSG_EB,ID" in line or "GALILEO_MSG_EB, ID" in line):
                                    print(line)
                                    print("[DEBUG] It was Gallileoooo")

                                    parts = line.split(",")
                                    beacon_id = int(parts[1].split("_")[-1])
                                    d_noisy[got_ping] = float(parts[2].split("_")[-1])
                                    print(f"[INFO] Received ping for beacon {beacon_id} with noisy distance: {d_noisy[got_ping]}")

                                    print("x_ping_melvin")
                                    print(check70['width_x'])
                                    print("y_ping_melvin")
                                    print(check70['height_y'])

                                    # Best file ever hahaha, stores all necessary EB information
                                    store_ping(check70['width_x'], check70['height_y'], estimated_beacon_position(d_noisy[got_ping]), beacon_id)
                                    got_ping += 1 # Increase the number of pings that we have taken
                    simulation(False, 20)

        except requests.RequestException as e:
            print(f"[ERROR] Failed to track announcements: {str(e)}")

    else:
        print("[DEBUG] Not in comm mode, probably retrying later")




def start_announcement_thread():
    announcement_thread = threading.Thread(target=listen_to_announcements, daemon=True)
    # Creates a new thread → threading.Thread(target=listen_to_announcements, daemon=True)
    #
    # This tells Python: "Run the function listen_to_announcements, but do it in a separate worker
    # (thread) instead of the main program."
    announcement_thread.start()



# def track_beacon_messages():
#     try:
#         time.sleep(0.3)
#         response = requests.get(ANNOUNCEMENTS_URL, stream=True)
#         response.raise_for_status()
# # ?????????????????????????????????????????????????????????????????????????????????
#         lines = (list(response.iter_lines(decode_unicode=True))).reverse()
#
#         if not lines:
#             # time.sleep(10)  # ✅ Wait before retrying
#             print("didnt get anything in /announcements")
#         else:
#             match = ''
#             for line in reversed(lines):
#                 print(line)
#                 if "GALILEO_MSG_EB_DETECTED" in line:
#                     match = line
#                     break
#
#             if match:
#                 print(f"Found a match: {match}")
#                 # beacon_id = match.group(3)
#                 beacon_id = match[-4:-1] # string
#                 handle_beacon_detection(beacon_id)
#                 print(f"[INFO] Beacon detected! Beacon ID: {beacon_id}")
#
#             else:
#                 print("Did not found a match yet")
#
#     except Exception as e:
#         print(f"[ERROR] Failed to track beacon messages: {str(e)}")


def estimated_beacon_position(dnoisy):
    k = random.uniform(NOISE_RANGE[0], NOISE_RANGE[1])

    d_actual = round(dnoisy - k * (3 * ALLOWED_DELTA + 0.4 * (dnoisy + 1)) / 4)
    return d_actual


def handle_beacon_detection():
    """ If we get here it means we got an EB
    and we need to estimate its position. """

    # Need to change into communication mode ...
    while True:
        try:
            safe()
            protect_battery(5)
            check = get_observation()
            if check['state'] != 'communication':
                set_mode('communication', check['vx'], check['vy'], check['angle'])
                wait('communication')
            if got_ping >= 1: #bc it starts from 0 !!!!!!!!!!!!
                if beacon_id is not None:
                    locate_beacon(beacon_id)
            # if got_ping >= 3:
            #     if beacon_id in beacon_locations_map_with_id:
            #         print("FOUND!!! Submit manually.")
            #         print(beacon_locations_map_with_id)
            #         # submit_beacon_position(beacon_id, beacon_locations_map_with_id[beacon_id])
            if got_ping >= ping_threshold:
                set_mode('charge', check['vx'], check['vy'], check['angle'])
                wait('charge')
                print("=============================SOLUTION FOUND==========================")
                find_solution()
                return

        except Exception as e:
            print(f"[ERROR]: {str(e)}")


def euclidean_distance(x1, y1, x2, y2):
    """Calculate Euclidean distance between two points."""
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)


def generate_geometric_locus(melvin_x, melvin_y, distance):
    """Generate a set of possible beacon locations forming a circle around Melvin."""
    points = set()
    for angle in range(0, 360, STEP_SIZE):  # Sampling points along the circle
        rad = math.radians(angle)
        x = melvin_x + distance * math.cos(rad)
        y = melvin_y + distance * math.sin(rad)
        points.add((round(x), round(y)))  # Rounding to reduce floating point errors
    return points


def find_intersection(set1, set2):
    """Find intersection between two geometric loci (circles)."""
    return {p1 for p1 in set1 for p2 in set2 if euclidean_distance(*p1, *p2) <= THRESHOLD}



# Define the log file path in the root directory of Melvin
BEACON_LOG_FILE_PATH = "beacon_log.txt"
PING_SAVER_ANNOUNCEMENTS = "ping_saver_announcements.txt"

PING_LOG_FILE_PATH = "ping_log.txt"

# Global dictionary to store definite beacon locations
beacon_locations_map_with_id = {}


def locate_beacon(beacon_identifier):
    """Process pings and estimate the beacon's location until only one candidate remains."""
    global pings, gl_sets, beacon_locations_map_with_id  # Ensure all global variables are accessed

    # Ensure we have stored pings for the given beacon_id
    if beacon_identifier not in pings or len(pings[beacon_identifier]) < 2:
        print(f"[ERROR] Not enough pings for beacon {beacon_identifier}. Need at least 2.")
        time.sleep(3)
        return None

    # Ensure the log file exists; if not, create it
    if not os.path.exists(BEACON_LOG_FILE_PATH):
        try:
            with open(BEACON_LOG_FILE_PATH, "w") as file:
                file.write("")  # Create an empty file
            print(f"[INFO] Created log file: {BEACON_LOG_FILE_PATH}")
        except PermissionError:
            print("[ERROR] Permission denied! Unable to create log file in root directory.")
            return None

    # Check if the beacon was already located
    if beacon_identifier in beacon_locations_map_with_id:
        print(f"[INFO] Beacon {beacon_identifier} already located at {beacon_locations_map_with_id[beacon_identifier]}.")
        # return beacon_locations_map_with_id[beacon_identifier]

    # Ensure gl_sets[beacon_id] exists
    if beacon_identifier not in gl_sets:
        gl_sets[beacon_identifier] = []

    # Generate geometric loci for each new ping received (if not already in gl_sets)
    for ping in pings[beacon_identifier]:
        gl = generate_geometric_locus(*ping)
        if gl not in gl_sets[beacon_identifier]:  # Ensure unique geometric loci
            gl_sets[beacon_identifier].append(gl)

    # Start with the first geometric locus
    intersection_set = gl_sets[beacon_identifier][0]

    for i in range(1, len(gl_sets[beacon_identifier])):
        intersection_set = find_intersection(intersection_set, gl_sets[beacon_identifier][i])

        # If we find exactly one point, we have found the beacon!
        if len(intersection_set) == 1:
            beacon_location = list(intersection_set)[0]
            print(f"[SUCCESS] Beacon {beacon_identifier} found at: {beacon_location}")

            # Store the beacon location in the global dictionary
            beacon_locations_map_with_id[beacon_identifier] = beacon_location

            # Append result to the log file
            with open(BEACON_LOG_FILE_PATH, "a") as file:
                file.write(
                    f"[SUCCESS] Beacon with ID: {beacon_identifier} found at {beacon_location} - Timestamp: {datetime.datetime.now()}\n")

            return beacon_location

        # If multiple possible locations remain, print and log them
        elif len(intersection_set) > 1:
            print(
                f"[INFO] Multiple possible beacon locations detected, for beacon {beacon_identifier} ({len(intersection_set)} candidates):")

            with open(BEACON_LOG_FILE_PATH, "a") as file:
                file.write(f"[INFO] Multiple possible beacon locations detected at {datetime.datetime.now()}:\n")
                file.write("  - Candidate Locations: " + ", ".join(map(str, intersection_set)) + "\n")

            for point in intersection_set:
                print(f"Possible Beacon (ID: {beacon_identifier}) Location: {point}")

                # Log each possible beacon location
                with open(BEACON_LOG_FILE_PATH, "a") as file:
                    file.write(f"  - Possible Beacon Location: {point}\n")

    print(f"[ERROR] Even with all pings, multiple possible locations remain for beacon {beacon_identifier}.")
    time.sleep(10)
    return None  # If no single beacon location is found, return None


# Example of how pings are received
def store_ping(melvin_x, melvin_y, actual_distance, beacon_identifier):
    """Store Melvin's location and received distance from beacon, avoiding duplicates."""
    global pings  # Ensure we modify the global dictionary

    # If beacon_id is not in the dictionary, initialize a new list
    if beacon_identifier not in pings:
        pings[beacon_identifier] = [] # dict num: list


    #  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@
    #     FOR REFERENCE, THIS:
    # print(pings[beacon_identifier])
    # WOULD PRINT THIS:
    # {beacon id: [(melvin_x1, melvin_y1, distance1), (melvin_x2, melvin_y2, distance2)]}
    #  @@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@



    # Ensure the log file exists; if not, create it
    if not os.path.exists(PING_LOG_FILE_PATH):
        try:
            with open(PING_LOG_FILE_PATH, "w") as file:
                file.write("")  # Create an empty file
            print(f"[INFO] Created log file: {PING_LOG_FILE_PATH}")
        except PermissionError:
            print("[ERROR] Permission denied! Unable to create log file in root directory.")
            return None

    # Append result to the log file
    with open(PING_LOG_FILE_PATH, "a") as file:
        file.write(
            f"[SUCCESS] PING for Beacon with ID: {beacon_identifier} found at {melvin_x} , {melvin_y - 400}, with actual distance: {actual_distance} - Timestamp: {datetime.datetime.now()}\n")

    # Check if the exact same ping already exists before adding
    if (melvin_x, melvin_y, actual_distance) not in pings[beacon_identifier]:
        pings[beacon_identifier].append((melvin_x, melvin_y, actual_distance))
        print(f"[INFO] Stored ping for beacon with ID:{beacon_identifier} at ({melvin_x}, {melvin_y}) with distance {actual_distance}")
    else:
        print(f"[WARNING] Ping already exists for beacon {beacon_identifier}, not storing duplicate.")



def reach_desired_velocity(vx, vy):
    while True:
        safe()
        protect_battery(5)
        simulation(False, 20)
        set_mode("acquisition", vx, vy, "wide")
        wait("acquisition")

        check = get_observation()

        if check["vx"] == vx and check["vy"] == vy:
            break
        if check["fuel"] == 0:
            break


def new_main():
    try:

        print("[DEBUG] Starting in main...")
        simulation(False, 20)
        reach_desired_velocity(VX_DESIRED, VY_DESIRED)
        check1 = get_observation()
        set_mode("communication", check1["vx"], check1["vy"], check1["angle"])
        time.sleep(0.3)
        wait("communication")

        start_announcement_thread()
        handle_beacon_detection()

    except Exception as e:
        print(f"[ERROR] An error occured: {str(e)}")


################ END OF BEACON HANDLERS ##################


if __name__ == "__main__":

    new_main()
