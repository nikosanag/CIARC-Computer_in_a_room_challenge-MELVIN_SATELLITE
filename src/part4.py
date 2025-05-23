from utility import get_observation, set_mode, wait, simulation, protect_battery, safe, take_photo, check_for_next_slot
from submit_responses import submit_EB, submit_image
from beacon_position_calculator import find_solution
from objectives import get_current_objectives, parse_datetime
from objectives_total import sort_objectives
from vel_calculation import calculate_velocity
from compute_time import time_computation
from zonedStitching import stitch_zoned
from collections import defaultdict

import zlib
import struct
import traceback
import sys
import multiprocessing
import cv2
import queue
import os
import threading
import requests
import time
import numpy as np
import re
import random
import math
import subprocess
from datetime import datetime, timezone, timedelta
from bitarray import bitarray


DEBUG = False



MELVIN_BASE_URL = "http://10.100.10.14:33000"
HEADERS = {"User-Agent": "curl/7.68.0", "Content-Type": "application/json"}


# -------------------------------- EXCEPTION HANDLING MECHANISM (IN CASE OF ERROR) --------------------------
EXCEPTIONS_LOG = 'exceptions.log'
stitched_map_path = 'debug_stitched_map.png'

def handler_exception(exc_type, exc_value, exc_traceback):
    '''
    This function handles any exceptions that may occur during excecution.
    It first sets MELVIN to "charge" mode and saves the exception and the corresponding timestamp to a file and then books the next available
    slot, so that the operator can connect and fix the issue. Finally, it backs up the BitMatrix object
    and it runs the program "safety_handler.py", which is a backup safety program that only captures the
    map.
    '''

    global Map
    safe()


    """Log exceptions with detailed diagnostics."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Extract full traceback details
    tb_list = traceback.extract_tb(exc_traceback)
    last_frame = tb_list[-1]  # Get the last (most recent) stack frame
    error_line = last_frame.line.strip() if last_frame.line else "No line information"

    # Build a dynamic error message
    if exc_type is TypeError and 'NoneType' in str(exc_value):
        error_msg = "NULL_REFERENCE: "
        error_msg += f"Attempted to use None as a valid object at:\n"
        error_msg += f"  → File: {last_frame.filename}\n"
        error_msg += f"  → Line {last_frame.lineno}\n"
        error_msg += f"  → Code: {error_line}"
    else:
        error_msg = str(exc_value) if exc_value else "No error message provided"

    # Construct full traceback string
    full_traceback = ''.join(traceback.format_tb(exc_traceback))

    log_entry = (
        f"\n{'=' * 80}\n"
        f"EXCEPTION TIME GREECE [{timestamp}]\n"
        f"Type: {exc_type.__name__}\n"
        f"Message: {error_msg}\n"
        f"\nFull Traceback:\n{full_traceback}"
        f"\n{'=' * 80}\n"
    )

    fd = os.open(EXCEPTIONS_LOG, os.O_APPEND | os.O_CREAT | os.O_WRONLY)
    os.write(fd, log_entry.encode())  # Convert string to bytes before writing
    os.close(fd)  # Close the file descriptor

    # Books the next slot available
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    check_for_next_slot(current_time)

    Map.save_to_file("backup_map.bmap")

    # Launch safety handler as a proper subprocess
    handler_path = os.path.join(os.path.dirname(__file__), "safety_handler.py")
    proc = subprocess.Popen(
        ["python3", handler_path],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=os.setsid  # Create new process group
    )
    
    print(f"[ERROR] Parent PID={os.getpid()} crashing. Subprocess PID={proc.pid}")
    sys.exit(1)


def thread_exception_handler(args):
    # Adapt threading.excepthook's single argument to the original handler's signature
    handler_exception(
        args.exc_type, 
        args.exc_value, 
        args.exc_traceback
    )

# Set global exception handler
sys.excepthook = handler_exception

# Set thread exception handler
threading.excepthook = thread_exception_handler

# --------------------------------------------------------------------------------------------------




# ---------------------------------- KNOWN LOCATION OBJECTIVE MONITORING THREAD ----------------------------------
objective_queue = queue.Queue()

objective_available = threading.Event()

def objective_monitor():
    """
    Thread that monitors for new known location objectives via API calls. Every 5 seconds, it adds any new objectives detected to the objective_queue.
    """
    
    if DEBUG:
        print("[OBJECTIVES] Started monitoring.")
    already_seen = set()
    while True:
        curr_objectives = get_current_objectives(contain_secret=False)
        flag = False
        for obj in curr_objectives:
            if DEBUG:
                print(f"[OBJECTIVES] Looking at objective with id {obj['id']}")
            if obj['id'] not in already_seen:
                already_seen.add(obj['id'])
                objective_queue.put(obj)
                if DEBUG:
                    print("[OBJECTIVES] Added a new objective.")
                flag = True

        if flag:
            objective_available.set()
            if DEBUG:
                print("[OBJECTIVES] New objectives detected!")
    
        time.sleep(5)

def start_objectives_monitoring():
    """
    Starts the objective monitoring thread.
    """
    monitor_thread = threading.Thread(target=objective_monitor, daemon=True)
    monitor_thread.start()

def objective_check_routine(image_queue):
    """
    Pops any new known location objectives from the objective_queue and completes them.
    """

    if not objective_available.is_set():
        # No new objectives
        if DEBUG:
            print("[OBJECTIVES] Did not find the flag set!")
        return False

    """
    Main implementation behind zoned objectives handler.
    """
    try:
        global Map

        while objective_available.is_set():
            
            current_obj = objective_queue.get()
            desired_angle = current_obj["optic_required"]
            objective_image_list = []

            # --------- Be sure to keep MELVIN alive ----------
            safe() 
            check = get_observation()
            time.sleep(1)
            protect_battery(5, desired_angle, check["state"])
            # -------------------------------------------------


            # ------------------------------ From here we consider handling zoned objectives -----------------------------------
            
            
            now = datetime.now(timezone.utc) - timedelta(minutes=15) 
            date_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            now = parse_datetime(date_str)
            limit = datetime.fromisoformat(current_obj['end'].replace("Z", "+00:00"))
            if now >= limit:
                if DEBUG:
                    print("[OBJECTIVE FAILED] DID NOT HAVE TIME FOR OBJECTIVE")
                with open("FAILURES.txt", "a") as file: # If it doesn't exist, then creates it
                    file.write(f"Objective:\n{current_obj}\nFailed: Ending time had expired when we found it!.\n")
                if objective_queue.empty():
                    objective_available.clear()
                continue


            
            if DEBUG:
                print(f'[OBJECTIVES] SCANNING OBJECTIVE: {current_obj}')

            if DEBUG:
                print(f"[OBJECTIVES] Chose desired angle {desired_angle}")
            set_mode("acquisition", check["vx"], check["vy"], desired_angle)
            wait("acquisition")

            des_x = current_obj["zone"][0]
            des_y = current_obj["zone"][3]
            already_taken_photo = False

            # precise_picture = False # Flag in order to check if precise picture objective is given
            xIsMax = False
            yIsMax = False

            axis_x = current_obj["zone"][2] - current_obj["zone"][0]
            axis_y = current_obj["zone"][3] - current_obj["zone"][1]

            while True:
                
                safe()
                protect_battery(4, desired_angle)

                check = get_observation()
                
                # If already taken photo we should update the target point and check whether the objective in done
                if already_taken_photo:
                    # if precise_picture:
                    #     if DEBUG:
                    #         print("[OBJECTIVES] ==================== PRECISE OBJECTIVE DONE! =====================", flush=True)
                            
                    #         charge_check = get_observation()
                    #         if charge_check["battery"] < 5:
                    #             set_mode("charge", check["vx"], check["vy"], desired_angle)
                    #             wait("charge")

                    #         stitch_and_submit_obj(objective_image_list, current_obj)
                    #         if objective_queue.empty():
                    #             objective_available.clear()
                    #         return True
                    
                    if desired_angle == "wide":
                        offset = 500
                    elif desired_angle == "normal":
                        offset = 400
                    else:
                        offset = 300

                    if not xIsMax and not yIsMax:
                        if des_y - offset >= current_obj["zone"][1]:
                            des_x = des_x
                            des_y = des_y - 3*(offset // 2)
                        else:
                            des_x = des_x + 3*(offset // 2)
                            des_y = des_y

                            if des_x >= current_obj["zone"][2]: # + offset / 2:
                                if DEBUG:
                                    print("[OBJECTIVES] ==================== OBJECTIVE DONE! =====================", flush=True)
                                charge_check = get_observation()
                                if charge_check["battery"] < 5:
                                    set_mode("charge", check["vx"], check["vy"], desired_angle)
                                    wait("charge")

                                stitch_and_submit_obj(objective_image_list, current_obj)
                                with open("SUCCESSES.txt", "a") as file: # If it doesn't exist, then creates it
                                    file.write(f"Objective:\n{current_obj}\nSUCCESS\n")
                                if objective_queue.empty():
                                    objective_available.clear()
                                return True
                                # END OF ZONED OBJECTIVE SUBMISSION

                    elif xIsMax:
                        des_x = des_x + min(axis_x // 2, offset)

                        if des_x >= current_obj["zone"][2]: # + offset / 2:
                            if DEBUG:
                                print("[OBJECTIVES] ==================== OBJECTIVE DONE! =====================", flush=True)
                            charge_check = get_observation()
                            if charge_check["battery"] < 5:
                                set_mode("charge", check["vx"], check["vy"], desired_angle)
                                wait("charge")

                            stitch_and_submit_obj(objective_image_list, current_obj)
                            with open("SUCCESSES.txt", "a") as file: # If it doesn't exist, then creates it
                                file.write(f"Objective:\n{current_obj}\nSUCCESS\n")
                            if objective_queue.empty():
                                objective_available.clear()
                            return True

                    elif yIsMax:
                        if des_y - min(axis_y // 2, offset) > current_obj["zone"][1]:
                            des_y = des_y - min(axis_y // 2, offset)
                            des_x = des_x
                        else:
                            des_y = current_obj["zone"][1]
                            des_x = des_x + min(axis_x // 2, offset)

                            if des_x >= current_obj["zone"][2]: # + offset / 2:
                                if DEBUG:
                                    print("[OBJECTIVES] ==================== OBJECTIVE DONE! =====================", flush=True)
                                charge_check = get_observation()
                                if charge_check["battery"] < 5:
                                    set_mode("charge", check["vx"], check["vy"], desired_angle)
                                    wait("charge")

                                stitch_and_submit_obj(objective_image_list, current_obj)
                                with open("SUCCESSES.txt", "a") as file: # If it doesn't exist, then creates it
                                    file.write(f"Objective:\n{current_obj}\nSUCCESS\n")
                                if objective_queue.empty():
                                    objective_available.clear()
                                return True
                                # END OF ZONED OBJECTIVE SUBMISSION

                else:
                    lens = desired_angle
                    if lens == "wide":
                        offset = 500
                    elif lens == "normal":
                        offset = 400
                    else:
                        offset = 300
                    
                    des_y = des_y - offset #/ 2 # REMEMBER TO MODIFY
                
                    # if (current_obj["zone"][2] - current_obj["zone"][0] == offset * 2) and (current_obj["zone"][3] - current_obj["zone"][1] == offset * 2):
                    #     des_x = des_x + offset / 2 # Going directly to the center of the precise picture
                    #     precise_picture = True
                    #     if DEBUG:
                    #         print("[OBJECTIVE] Precise picture objective")
                    
                    
                    if (axis_x <= offset * 2) and (axis_y <= offset * 2): # Less than a photo needed
                        if (axis_x >= axis_y):
                            xIsMax = True
                            des_y = current_obj["zone"][1] # Upper Corner
                        else:
                            yIsMax = True
                            des_y = current_obj["zone"][3] - axis_y // 2 # A little bit upper from the downmost left corner



                if DEBUG:
                    print(f"[CO-PILOT OF OBJECTIVE] New desired position: ({des_x},{des_y})", flush=True)

                while True:
                    if DEBUG:
                        simulation(False,1)
                        print("[CO-PILOT OF OBJECTIVE] getting the speed order...this is a blocking command")
                    check = get_observation()
                    cur_x = check["width_x"]
                    cur_y = check["height_y"]
                    cur_vx = check["vx"]
                    cur_vy = check["vy"]

                    vel_data = calculate_velocity(cur_x, cur_y, des_x, des_y, cur_vx, cur_vy)
                    current_velocity = get_observation()

                    safe()
                    if DEBUG:
                        print(f"Current velx: {current_velocity['vx']}, current vely: {current_velocity['vy']} | Desired velx: {vel_data['vx']}, desired vely: {vel_data['vy']}", flush=True)
                    if ((current_velocity["vx"] == vel_data["vx"]) and (current_velocity["vy"] == vel_data["vy"])):
                        break

                    # Time passes, set mode to 'acquisition' and begin orbiting towards the target point
                    for _ in range(5):
                        protect_battery(6, desired_angle)
                        safe()
                        set_mode("acquisition", vel_data["vx"], vel_data["vy"], desired_angle) # Apply the computed velocity
                        wait("acquisition")
                        time.sleep(0.1)
                        if DEBUG:
                            print(f"[CO-PILOT OF OBJECTIVE] SET {desired_angle} angle")
                    
                        #name = take_photo()
                        # parts = name.split('_')
                        # x = int(parts[1])
                        # y = int(parts[2][:-4])

                        if DEBUG:
                            simulation(False, 1)
                        #Map.update_map(x, y, desired_angle, 1)
                        if DEBUG:
                            simulation(False, 20)
                        
                if DEBUG:
                    simulation(False,20)
                while True:
                    if DEBUG:
                        print("[CO-PILOT OF OBJECTIVE] Checking if i am already too close.", flush=True)
                    
                    can_reach = time_computation(vel_data['distance'])
                    check = get_observation()
                    can_reach_time = calculate_travel_time(check['width_x'], check['height_y'], check['vx'], check['vy'], des_x, des_y)
                    if DEBUG:
                        print(f"[CO-PILOT OF OBJECTIVE] The time we computed in order to reach desired destination: {round(can_reach[1], 1)}", flush=True)
                        print(f"[CO-PILOT OF OBJECTIVE] Is reachable? {can_reach[0]}", flush=True)

                    if can_reach[0]: # It can and it will find the target point
                      
                        # Check if MELVIN is very close to the target spot
                        if round(can_reach_time, 1) < 360:
                            if DEBUG:
                                simulation(False, 20)
                                time.sleep((can_reach_time/20)+1)
                            else:
                                time.sleep(can_reach_time+1)
                            if DEBUG:
                                simulation(False, 1)

                            check = get_observation() # I think this should added here ...
                            cur_x = check["width_x"]   # giati toso palio check ???
                            cur_y = check["height_y"]
                            cur_vx = check['vx']
                            cur_vy = check['vy']

                            des_x = current_obj["zone"][0]
                            des_y = current_obj["zone"][3] - offset
                            
                        # Just to be sure we are heading with the optimal speed
                        if DEBUG:
                            simulation(False,20)
                        mine = get_observation()
                        set_mode("charge", mine["vx"], mine["vy"], desired_angle)
                        wait("charge")
                        if DEBUG:
                            print(f"[CO-PILOT OF OBJECTIVE] SET {desired_angle} angle")
                        if DEBUG:
                            simulation(False,1)
                        
                        
                        
                        check = get_observation()

                        threshold = 20
                        time1 = float('inf')
                        while math.isinf(time1) and threshold <= 100:
                            time1 = calculate_travel_time(check["width_x"],check["height_y"],check["vx"],check["vy"],des_x,des_y,21600,10800,threshold)
                            threshold += 5

                        if DEBUG:
                            print(f"[CO-PILOT OF OBJECTIVE] Just got sleep order time estimate in REAL time: {round(time1, 1)} and i am in simulation 1", flush=True)
                    
                        key = round(time1, 2)
                        key = key - 180 - 60 # nikos anag - 60

                        if DEBUG:
                            key = round(key/20,2)
                            print(key, flush=True)

                        i = 0
                        if DEBUG:
                            simulation(False, 20)

                        safe_occured = False
                        while True:
                            if DEBUG:
                                print(f"[CO-PILOT OF OBJECTIVE] Sleeping and remaining time is {round(key - i,2)} seconds in x20 time", flush=True)
                            time.sleep(1)
                            state = get_observation()
                            if state["state"] == "safe":
                                safe()
                                safe_occured = True
                                break
                            safe()
                            protect_battery(5, desired_angle)
                            i += 1
                            if i >= key:
                                break
                        break
                    
                    #else we need to terminate this
                
                if safe_occured:
                    continue

                if DEBUG:
                    print("[CO-PILOT OF OBJECTIVE] Getting ready to reach target", flush=True)
                    simulation(False, 20)

                # Set mode to 'acquisition in order to enter the target zone and take pictures
                set_mode("acquisition", vel_data["vx"], vel_data["vy"], desired_angle)
                wait("acquisition")


                if DEBUG:
                    simulation(False, 1)

                while True:
                    protect_battery(3, desired_angle)
                    check = get_observation()
                    safe()

                    if DEBUG:
                        print(f"[CO-PILOT OF OBJECTIVE] Checking if in the desired zone.\nNow in {(check['width_x'], check['height_y'])}", flush=True)
                  
                    if ((current_obj["zone"][2] >= check["width_x"] >= current_obj["zone"][0] and current_obj["zone"][3] >= check["height_y"] >= current_obj["zone"][1])):
                        break

                    elif des_x < check['width_x'] and des_y < check['height_y']:
                        break

                    
                    set_mode("acquisition", check["vx"], check["vy"], desired_angle)
                    wait("acquisition")
                    

                while True:
                    check = get_observation()
                    if (check["width_x"] >= current_obj["zone"][0] and check["height_y"] >= current_obj["zone"][1]):
                        protect_battery(4.9, desired_angle) # Check battery levels
                        safe()

                        if (check["width_x"] <= current_obj["zone"][2] and check["height_y"] <= current_obj["zone"][3]):
                            if DEBUG:
                                print(f"[CO-PILOT OF OBJECTIVE]I am inside the zone targeted and in simulation x1 only", flush=True)
                            
                            
                            # name = take_photo()
                            name = take_and_enqueue_photo(image_queue)
                            parts = name.split('_')
                            x = int(parts[1])
                            y = int(parts[2][:-4])
                            Map.update_map(x, y, desired_angle, 1)
                            objective_image_list.append(name[7:])

                            
                            if DEBUG:
                                print("[OBJECTIVE] Just took a photo", flush=True)
                            
                            time.sleep(1)

                        else:
                            already_taken_photo = True
                            break

    except Exception as e:
        if DEBUG:
            print(f"[OBJECTIVES ERROR] An error occured: {str(e)}")
            traceback.print_exc()
        stitch_and_submit_obj(objective_image_list, current_obj)
        raise

# ------------------------------------------------------------------------------------------------



# ------------------------------------ AUTOMATIC IMAGE STITCHING ---------------------------------

canvas = None

def get_canvas_bytes(canvas, format='.png', quality=90):
    """
    Convert the entire stitched canvas to bytes.
    
    :param canvas: the canvas on which the image are being stitched
    :param format: format of the canvas
    :param quality: quality of encoding
    """
    success, buffer = cv2.imencode(format, canvas, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if success:
        return buffer.tobytes()
    return None

def stitch_image(name):
    """
    Stitch an image onto the global canvas.
    
    :param name: The name of the image in the following format: lens{precision}_{x}_{y}.jpg 
    """

    global canvas
    lens = 0
    def get_coords(filename):
        parts = filename.split('_')
        nonlocal lens
        idx = int(parts[0][-1])
        if idx == 1: lens = 1000
        elif idx == 6: lens = 600
        elif idx == 8: lens = 800
        else:
            if DEBUG:
                print("UNEXPECTED INDEX")
            return -1, -1
        x = int(parts[1])
        y = int(parts[2][:-4])
        return x, y

    canvas_x, canvas_y = get_coords(name)

    img = cv2.imread(name)
    img = cv2.resize(img, (lens, lens))

    h, w = img.shape[:2]

    # Make sure the position is valid on our canvas
    if canvas_x < 0 or canvas_y < 0 or canvas_x + w > 21600 or canvas_y + h > 10800:
        # Handle edge cases by clipping to canvas boundaries
        # Calculate valid portion of the image and valid position on canvas
        start_x = max(0, -canvas_x)
        start_y = max(0, -canvas_y)
        end_x = min(w, 21600 - canvas_x)
        end_y = min(h, 10800 - canvas_y)
        
        # Adjust canvas position to be within bounds
        valid_canvas_x = max(0, canvas_x)
        valid_canvas_y = max(0, canvas_y)
        
        # Extract valid portion of image
        valid_img = img[start_y:end_y, start_x:end_x]
        
        # Calculate valid dimensions
        valid_h, valid_w = valid_img.shape[:2]
        
        # Place the valid portion onto the canvas
        canvas[valid_canvas_y:valid_canvas_y+valid_h, valid_canvas_x:valid_canvas_x+valid_w] = valid_img
        
    else:
        # Place the whole image
        canvas[canvas_y:canvas_y+h, canvas_x:canvas_x+w] = img
    
    # return canvas

def stitch_worker(image_queue):
    """
    The function that will be run by the stitching subprocess.
    
    :param image_queue: the queue that contains the images waiting to be stitched 
    """
    global canvas
    canvas = np.zeros((10800, 21600, 3), dtype=np.uint8)

    try:
        # Continuously listens for images and stitches them onto the canvas.
        while True:
            if DEBUG:
                print("[IMAGES] Waiting for image in queue...")
            name = image_queue.get()  # Wait for an image
            stitch_image(name)  # Stitch image onto canvas
            
            stitched_map_bytes = get_canvas_bytes(canvas)
            with open("debug_stitched_map.png", "wb") as f:
                f.write(stitched_map_bytes)

            if DEBUG:
                print("[IMAGES] Image stitched and canvas updated.")
    
    except Exception as e:
        if DEBUG:
            print(f"[IMAGES ERROR] An error occured: {str(e)}")
        raise
    
        
def start_stitching_process():
    """
    Starts the stitching process.
    """
    image_queue = multiprocessing.Queue()
    process = multiprocessing.Process(target=stitch_worker, args=(image_queue,), daemon=True)
    process.start()
    return image_queue



def take_and_enqueue_photo(queue):
    filename = take_photo()
    if queue.qsize() < 40: # threshold to not overload memory
        queue.put(filename)
        if DEBUG:
            print(f"[IMAGES] Image {filename} taken and enqueued. Queue size now {queue.qsize()}")
    elif DEBUG:
        print(f"[IMAGES] Image {filename} taken. Queue FULL.")
    return filename


def stitch_and_submit_obj(image_files=[], objective={}):
    """
    Stitches and submits known location objectives.

    :param images_files: a list containing all the names of the image files taken in the function "objective_check_routine"
    :objective: a dictionary containing all the information about the objective that we want to submit 
    """
    try:
        if DEBUG:
            print(f"[STITCH OBJ] Image files received: {image_files}")
            print(f"[STITCH OBJ] Stitching objective {objective['id']}")
        final_name = f"./objective_images/OBJECTIVE_ID_{objective['id']}.png"
        xmin, ymin = objective['zone'][0], objective['zone'][1]
        xmax, ymax = objective['zone'][2], objective['zone'][3]
        stitch_zoned((xmin, ymin), (xmax, ymax), image_files, final_name)
        if DEBUG:
            print(f"[STITCH OBJ] Stitched, now submitting...")
        submit_image(objective['id'], final_name)
    except Exception as e:
        with open("FAILURES.txt", "a") as file: # If it doesn't exist, then creates it
            file.write(f"Objective:\n{objective}\nFailed to be submitted.\n")
        raise

# ------------------------------------------------------------------------------------------------

    




# -------------------------------------- EB DETECTION THREAD -------------------------------------

ALLOWED_DELTA = 75

NOISE_RANGE = [-1, 1]

ANNOUNCEMENTS_URL = f"{MELVIN_BASE_URL}/announcements"

PING_THRESHOLD = 8 # Number of pings to make the estimation of EB position (calling find_solution())

PING_LOG_FILE_PATH = "ping_log.txt"

beacon_active = threading.Event()
announcement_stream = None

ping_num = defaultdict(int)  # default value for all keys is 0


beacon_id = None
id = None
past_ids = set()
d_noisy = {}
pings = {}
headers = {"Accept": "text/event-stream"}

def start_announcement_thread():
    """
    Starts the thread that contiunuously listens to announcements
    """
    announcement_thread = threading.Thread(target=listen_to_announcements, daemon=True)
    announcement_thread.start()

def estimated_beacon_position(dnoisy):
    """
    Estimates the beacon's position by trying to guess the random number k
    """
    k = random.uniform(NOISE_RANGE[0], NOISE_RANGE[1])
    d_actual = round(dnoisy - k * (3 * ALLOWED_DELTA + 0.4 * (dnoisy + 1)) / 4)
    return d_actual

def listen_to_announcements():
    """
    Continuously listens to /announcements. It detects messages associated with beacons and updates the global flag accordingly.
    """
    global announcement_stream
    global ping_num, d_noisy
    global beacon_id
    global id # The id we currently working on

    try:
        if DEBUG:
            print("[BEACON] Subscribing to /announcements (SSE) for real-time updates...")

        announcement_stream = requests.get(ANNOUNCEMENTS_URL, stream=True, headers=headers)
        announcement_stream.raise_for_status()

        if announcement_stream is None:
            if DEBUG:
                print("[BEACON ERROR] Announcement stream is not initialized.")
            return

        if announcement_stream.status_code != 200:
            if DEBUG:
                print(f"[BEACON ERROR] Status code {announcement_stream.status_code} from {ANNOUNCEMENTS_URL}")
                print("[BEACON ERROR] Response text:", announcement_stream.text)
            return

        if DEBUG:
            print(f"[BEACON] Entering while loop inside func listen_to_announcements()")

        while True:

            for line in announcement_stream.iter_lines(chunk_size=1, decode_unicode=True):      
                if DEBUG:
                    simulation(False, 1)

                crucial_check = get_observation()
                
                if DEBUG:
                    simulation(False, 20)

                if line:
                    striped_line = line.strip()

                    if DEBUG:
                        print(f"[BEACON] GOT LINE:\n{line}")

                    if not beacon_active.is_set() and "GALILEO_MSG_EB_DETECTED" in line:
                        parts = line.split("_")
                        if int(parts[-1]) in past_ids:
                            continue
                        id = int(parts[-1])
                        past_ids.add(id)
                        pings[id] = 0
                        beacon_active.set()

                        if DEBUG:
                            print(f"[BEACON] GOT STARTING MESSAGE FOR EB, ID: {id}")
                        
                    
                    check = get_observation()
                    if 'ping' in striped_line:
                        if DEBUG:
                            print(f'[BEACON] MESSAGE WITH PING: {line}')
                            print(f"[BEACON] MELVIN had x: {check['width_x']} and y: {check['height_y']}")

                    if "GALILEO_MSG_EB,ID" in line or "GALILEO_MSG_EB, ID" in line:
                        if DEBUG:
                            print(line)
                            print("[BEACON] It was Gallileoooo")

                        parts = line.split(",")
                        beacon_id = int(parts[1].split("_")[-1])
                        if beacon_id == id:
                            d_noisy[ping_num[id]] = float(parts[2].split("_")[-1])
                            if DEBUG:
                                print(f"[BEACON] Received ping for beacon {beacon_id} with noisy distance: {d_noisy[ping_num[id]]}")
                                print("x_ping_melvin")
                                print(crucial_check['width_x'])
                                print("y_ping_melvin")
                                print(crucial_check['height_y'])

                            # Stores all necessary EB information in a file
                            store_ping(crucial_check['width_x'], crucial_check['height_y'], estimated_beacon_position(d_noisy[ping_num[id]]), beacon_id)
                            ping_num[id] += 1 # Increase the number of pings that we have taken
                        
                    
                    elif DEBUG:
                        simulation(False, 20)
                        
    except requests.RequestException as e:
        if DEBUG:
            print(f"[BEACON ERROR] Failed to track announcements: {str(e)}")
        raise

def store_ping(melvin_x, melvin_y, actual_distance, beacon_identifier):
    """
    Stores MELVIN's location and received distance from beacon, avoiding duplicates.
    """
    global pings  # Ensure we modify the global dictionary

    # If beacon_id is not in the dictionary, initialize a new list
    if beacon_identifier not in pings:
        pings[beacon_identifier] = []

    if not os.path.exists(PING_LOG_FILE_PATH):
        try:
            with open(PING_LOG_FILE_PATH, "w") as file:
                file.write("")
            if DEBUG:
                print(f"[BEACON] Created log file: {PING_LOG_FILE_PATH}")
        except PermissionError:
            if DEBUG:
                print("[BEACON ERROR] Permission denied! Unable to create log file in root directory.")
            raise
    with open(PING_LOG_FILE_PATH, "a") as file:
        file.write(
            f"[BEACON SUCCESS] PING for Beacon with ID: {beacon_identifier} found at {melvin_x} , {melvin_y}, with actual distance: {actual_distance} - Timestamp: {datetime.now()}\n")


def handle_beacon_detection(image_queue):
    """
    Looks for pings untill PING_THRESHOLD is achieved in order to estimate the location. Between waiting for groups of pings, efficiently changes MELVIN
    into acquisition mode, to take pictures for the Daily Map. MELVIN goes into charge mode when needed and wakes up in order to take pictures or receive more pings, depending on its position.
    """
    global ping_num 
    global id
    global Map

    def get_last_coordinates(filename):
        with open(filename, "r") as file:
            lines = file.readlines()
        last_line = lines[-1]
        parts = last_line.split("found at ")[1].split(",") 
        x, y = int(parts[0].strip()), int(parts[1].split("with")[0].strip()) 
        return x, y

    def get_target(vx, vy, x, y, dist=4000):
        result_x = (x - (math.cos(math.atan(vy/vx)) * dist)) % 21600
        result_y = (y - (math.sin(math.atan(vy/vx)) * dist)) % 10800
        return round(result_x), round(result_y)


    def lcm(a, b):
        return abs(a * b) // math.gcd(a, b)

    check = get_observation()
    period = lcm(round(21600 / check['vx']), round(10800 / check['vy']))
    if DEBUG:
        period = round(period / 20)
    time_of_check = datetime.now() + timedelta(seconds=period)

    while True:
        try:
            if ping_num[id] == 0 and datetime.now() >= time_of_check:
                return -2, -2
            safe("communication")
            protect_battery(5, "wide", "communication")
            check = get_observation()
            if check['state'] != 'communication':
                set_mode('communication', check['vx'], check['vy'], check['angle'])
                wait('communication')
            if ping_num[id] > 0:
                seconds_to_wait = 60
                # Wait 60 seconds to see if we are outside the EB's range
                if DEBUG:
                    print("[BEACON] Entering 60-sec waiting loop/")
                    seconds_to_wait = round(seconds_to_wait / 20)
                starting_ping_num = ping_num[id]
                for _ in range(seconds_to_wait):
                    time.sleep(1)
                    safe("communication")
                    protect_battery(5, "wide", "communication")
                    if starting_ping_num != ping_num[id]:
                        if DEBUG:
                            print("[BEACON] Got PING, so I have not escaped the circle yet!")
                        break
                if starting_ping_num == ping_num[id]:

                    if DEBUG:
                        print("[BEACON] I escaped the circle")
                        print("[BEACON] Setting co-pilot")


                    # The Daily Map capturing logic starts here (similar to function part4_main())

                    while True:
                        battery_order = 6
                        sleep_order = 1
                        battery_loss_acquisition = 0.15
                        battery_smart_trick = 4
                        
                        if DEBUG:
                            battery_smart_trick *= 2.5
                            battery_order *= 2
                            sleep_order /= 5
                        
                        last_x, last_y = get_last_coordinates(PING_LOG_FILE_PATH)
                        check = get_observation()
                        tar_x, tar_y = get_target(check['vx'], check['vy'], last_x, last_y)
                        total_time = calculate_travel_time(check['width_x'], check['height_y'], check['vx'], check['vy'], tar_x, tar_y) - 80
                        
                        current = get_observation()
                        if (total_time<180+(100 - check["battery"])/0.1 and current["state"]=="charge") or (total_time<360+(100 - check["battery"])/0.1 and current["state"]!="charge"):
                            if DEBUG:
                                print(f"[BEACON CO-PILOT] Brutally falling to sleep for due to beacon priotity!My destination is {tar_x} , {tar_y}!!!")
                            
                            if current["state"] == "charge":
                                total_time -= 180
                            
                            
                            set_mode("charge",check["vx"],check["vy"],check["angle"])
                            wait("charge")
                            
                            if DEBUG:
                                print(f"[BEACON CO-PILOT] Sleep session {total_time} x1 and {round(total_time/20,2)} x20")
                            
                            if total_time>180:
                                if DEBUG:
                                    time.sleep(round(total_time/20,2))
                                else:
                                    time.sleep(round(total_time,2))

                            if DEBUG:  
                                print("[BEACON CO-PILOT] Waking up and getting ready for Beacon duties!!!")
                            set_mode("communication",check["vx"],check["vy"],check["angle"])
                            wait("communication")
                            break
                        else:
                        
                            current = get_observation()

                            if DEBUG:
                                print("[BEACON CO-PILOT] Thinking about whether I go to sleep or not...!")
                            
                            l = get_trajectory()
                            save = (-1,-1)
                            for i in l:
                                if Map.get_bit(i[0],i[1]) == 0: 
                                    save = i
                                    break
                            current = get_observation()
                            
                            if DEBUG:
                                print(f"[BEACON CO-PILOT] My target is {save}")
                            
                            time_calculated = calculate_travel_time(current["width_x"],current["height_y"],current["vx"],current["vy"],save[0],save[1],21600,10800,10) 
                            current = get_observation()
                            if current["state"] == "charge":
                                time_calculated -= 180 
                                   
                                
                            if time_calculated>=360 : 
                                time_calculated -= 185
                                
                                if DEBUG:
                                    print(f"[BEACON CO-PILOT] Going to sleep for {time_calculated} REAL seconds(x1)..I will wake up after that!")
                                
                                current = get_observation()
                                set_mode("charge", current["vx"], current["vy"], current["angle"])
                                if DEBUG:
                                    simulation(False,20)
                                    time_calculated = (round(time_calculated / 20,2))
                                
                                time_for_sleep_here_only = round(time_calculated / 50,2)
                                
                                cont = False
                                for i in range(0,50):
                                    time.sleep(time_for_sleep_here_only)
                                    last_x, last_y = get_last_coordinates(PING_LOG_FILE_PATH)
                                    check = get_observation()
                                    tar_x, tar_y = get_target(check['vx'], check['vy'], last_x, last_y)
                                    total_time = calculate_travel_time(check['width_x'], check['height_y'], check['vx'], check['vy'], tar_x, tar_y,21600,10800,10) - 80 
                                    if DEBUG:
                                        print(f"[BEACON CO-PILOT] total_time {total_time}")
                                    if (total_time<180+(100 - check["battery"])/0.1 and current["state"]=="charge") or (total_time<360+(100 - check["battery"])/0.1 and current["state"]!="charge"):
                                        if DEBUG:
                                            print("[BEACON CO-PILOT] I am cancelling plans of commander logic due to beacon priority!")
                                            cont = True
                                        break
                                   
                                if cont: 
                                    continue
                                
                                current = get_observation()
                                set_mode("acquisition", current["vx"], current["vy"], current["angle"])
                                wait("acquisition")
                            
                            
                            else:
                                current = get_observation()
                                if battery_loss_acquisition*time_calculated >= current["battery"]-battery_smart_trick:
                                    if DEBUG:
                                        print("[BEACON CO-PILOT] Mini charge break")
                                        simulation(False,20)
                                    set_mode("charge", current["vx"], current["vy"], current["angle"])
                                    wait("charge")
                                    if DEBUG:
                                        simulation(False,1)
                                    
                                    l = get_trajectory()
                                    total = len(l)
                                    vacant = 0
                                    
                                    for i in l:
                                        if Map.get_bit(i[0],i[1]) == 0: 
                                            vacant+=1
                                            
                                    
                                    if DEBUG:
                                        simulation(False,20)
                                        print("[BEACON CO-PILOT] Mini charge duration for x20 simulation speed = ", round(1.01*45*vacant/total,2))
                                        time_for_sleep_here_only = round(1.01*45*vacant/total,2)
                                    else:
                                        time_for_sleep_here_only = round(1.2*900*vacant/total,2)
                                    

                                    cont = False
                                    time_for_sleep_here_only = round(time_for_sleep_here_only/50,2)
                                    for i in range(0,50):
                                    
                                        time.sleep(time_for_sleep_here_only)
                                        last_x, last_y = get_last_coordinates(PING_LOG_FILE_PATH)
                                        check = get_observation()
                                        tar_x, tar_y = get_target(check['vx'], check['vy'], last_x, last_y)
                                        total_time = calculate_travel_time(check['width_x'], check['height_y'], check['vx'], check['vy'], tar_x, tar_y,21600,10800,10) - 80
                                        if (total_time<180+(100 - check["battery"])/0.1 and current["state"]=="charge") or (total_time<360+(100 - check["battery"])/0.1 and current["state"]!="charge"):
                                            if DEBUG:
                                                print(f"[BEACON CO-PILOT] crucial time {total_time} ")
                                            if DEBUG:
                                                print("[BEACON CO-PILOT] I am cancelling plans of commander logic due to beacon priority!")
                                            cont = True
                                            break
                                        
                                    if cont: 
                                        continue
                                    
                                    current = get_observation()
                                    set_mode("acquisition",current["vx"],current["vy"],"wide")
                                    wait("acquisition")
                                    
                                    continue
                                    
                                else:
                                    if DEBUG:
                                        print("[BEACON CO-PILOT] Time-battery combination allows me to keep going")
                                    set_mode("acquisition", current["vx"], current["vy"], current["angle"])
                                    wait("acquisition")
                                    
                            
                            if DEBUG:
                                print("[BEACON CO-PILOT] I obliged to the decision order! Now I will start the scan and take pictures")

                            
                            if DEBUG:
                                simulation(False,4)
                            defender = False
                            cont = False
                            for i in range(2):
                                time.sleep(0.2)
                                safe()
                                last_x, last_y = get_last_coordinates(PING_LOG_FILE_PATH)
                                check = get_observation()
                                tar_x, tar_y = get_target(check['vx'], check['vy'], last_x, last_y)
                                total_time = calculate_travel_time(check['width_x'], check['height_y'], check['vx'], check['vy'], tar_x, tar_y,21600,10800,10) - 80
                                if DEBUG:
                                    print(f"[BEACON CO-PILOT] crucial time is {total_time}")
                                if (total_time<180+(100 - check["battery"])/0.1 and current["state"]=="charge") or (total_time<360+(100 - check["battery"])/0.1 and current["state"]!="charge"):
                                        if DEBUG:
                                            print("[BEACON CO-PILOT] I am cancelling plans of commander logic due to beacon priority!")
                                        
                                        cont = True
                                        break
                                
                                current = get_observation()
                                defender = False
                                break_com = False
                                detection_range = 300
                                for x in range(current["width_x"]-detection_range, current["width_x"]+detection_range):
                                    for y in range(current["height_y"]-detection_range,current["height_y"]+detection_range):
                                        if x<0:
                                            x = 21599 + x
                                        if y<0:
                                            y = 10799 + y
                                        if x>21599:
                                            x = x - 21599
                                        if y > 10799:
                                            y = y - 10799
                                            
                                        if Map.get_bit(x,y) == 0:
                                            break_com = True
                                            break
                                    if break_com == True:
                                        break
                                
                                
                                if break_com:
                                    defender = False
                                    break
                                
                                if DEBUG:    
                                    print("[BEACON CO-PILOT] Travelling above area already photographed...refusing to take photo for now!")  
                                        
                                    time.sleep(sleep_order)
                                    defender = True
                                    
                                    continue
                                
                                else :
                                    if DEBUG:
                                        simulation(False,20)   
                                        break
                            
                            if defender or cont:
                                if DEBUG:
                                    simulation(False,20)  
                                continue
                            
                            if DEBUG:
                                print("[BEACON CO-PILOT] Taking photo on the point I had not yet!")
                                simulation(False,1)
                            take_and_enqueue_photo(image_queue)
                            
                            current = get_observation()
                            if DEBUG:
                                print("[BEACON CO-PILOT] Updating my memory with this point marked as photographed")
                            Map.update_map (current["width_x"],current["height_y"],current["angle"],1)
                            if DEBUG:
                                Map.print_matrix()
                                simulation(False,20)
                                            
            


            if ping_num[id] >= PING_THRESHOLD: # If the desired number of pings appears, then call the find_solution()
                set_mode('charge', check['vx'], check['vy'], check['angle'])
                wait('charge') # Wait to get to charge mode first
                width, height = find_solution() # Function that estimates the Beacon's location based on gemoetric loci
                if DEBUG:
                    print("============================= BEACON LOCATION FOUND ==========================")
            
                return width, height
            
            _, beacons = sort_objectives()
            save = {}
            for beacon in beacons:
                if beacon['id'] == id:
                    save = beacon
                    break
            now = datetime.now(timezone.utc) - timedelta(minutes=15) 
            date_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
            now = parse_datetime(date_str)
            limit = datetime.fromisoformat(save['end'].replace("Z", "+00:00"))
            if now >= limit or save == {}:
                if DEBUG:
                    print(f'[BEACON FAILED] NOW:{now}')
                    print(f'[BEACON FAILED] LIMIT:{limit}')
                    print(limit)
                if DEBUG and save == {}:
                    print("[BEACON FAILED] DID NOT FIND BEACON INSIDE OBJECTIVES")
                elif DEBUG:
                    print("[BEACON FAILED] BEACON END TIME EXPIRED")
                return -1, -1



        except Exception as e:
            if DEBUG:
                print(f"[BEACON ERROR]: {str(e)}")
                print(traceback.extract_tb(e.__traceback__))
            raise

def beacon_check_routine(image_queue):
    """
    Checks whether a beacon objective is available and handles it by calling handle_beacon_detection. 

    :param image_queue: the image queue for the automatic stitching
    """    
    if not beacon_active.is_set():
        return False

    if DEBUG:
        print("[BEACON] First beacon message found. Starting routine...")
    global ping_num

    trials = 0

    while trials < 3: # Try to submit 3 times
        check = get_observation()
        vx, vy, angle = check['vx'], check['vy'], check['angle']
        set_mode('communication', vx, vy, angle) # Need to change to communication mode immediately
        wait('communication')

        if DEBUG:
            print(f"[BEACON ROUTINE] Going to find solution number {trials + 1}")
        width, height = handle_beacon_detection(image_queue, trials) # Take the optimal solution estimation

        fake_fail = False
        if width == -1 and height == -1:
            trials = 3
            break
        elif width == -2 and height == -2:
            fake_fail = True

        if not fake_fail:
            result = submit_EB(beacon_id, width, height)
        else: 
            result = ''
        
        pattern = r"{\"status\": \"The beacon was found!\", \"attempts_made\": (\d+)}"
        match = re.search(pattern, result)
        
        if match: # Case of success - return to main function
            beacon_active.clear() # Remember to set this to False in order to look for new EBs
            with open("SUCCESSES.txt", "a") as file:
                file.write(f"Beacon with id {id}\nSUCCESS\n")
            return True

        else: # Case of failure
            pattern1 = r"{\"status\": \"The beacon could not be found around the given location\", \"attempts_made\": (\d+)}"
            match1 = re.search(pattern1, result)
            if match1 or fake_fail: # Did not found EB location correctly
                if DEBUG:
                    simulation(False,20)
                
                check = get_observation()
                set_mode('acquisition', check["vx"], check["vy"], check['angle'])
                wait("acquisition")
                if DEBUG:
                    simulation(False,1)
                    print(f'[BEACON ROUTINE] Trial {trials + 1} failed, retrying...')
                check = get_observation()
                vel_data = calculate_velocity(check['width_x'], check['height_y'], width, height, check['vx'], check['vy'])
                if not fake_fail:
                    vx = vel_data['vx']
                    vy = vel_data['vy']
                else:
                    vx = check['vx']
                    vy = check['vy'] + 2
                if DEBUG:
                    print("[BEACON ROUTINE] Waiting to reach desired velocity...")
                while True:
                    set_mode('acquisition', vx, vy, check['angle']) # Change orbit
                    check = get_observation()
                    if check["vx"] == vx and check["vy"] == vy:
                        if DEBUG:
                            print("[BEACON ROUTINE] Reached desired velocity")
                        break
                    safe("communication") 
                    protect_battery(5, check["angle"], "communication")
                    
                if not fake_fail:
                    trials += 1 # Tried and failed
                ping_num[id] = 0 

                if DEBUG:
                    simulation(False,20)
                
                
    if trials == 3:
        if DEBUG:
            print('[BEACON ERROR] Found Error')
        with open("FAILURES.txt", "a") as file:
            file.write(f"\nBeacon with id {id} failed to be submitted.\n")


    if os.path.exists(PING_LOG_FILE_PATH):
        if DEBUG:
            print("[BEACON ROUTINE] Archiving ping log data.")

        # Write the logs to the file

        with open(PING_LOG_FILE_PATH, 'r', encoding="utf-8") as src, open('ping_log_archive.txt', 'a', encoding="utf-8") as dst:
            for line in src:
                dst.write(line)  

        with open(PING_LOG_FILE_PATH, 'w', encoding="utf-8"):
            pass  

    beacon_active.clear()
    if DEBUG:
        print("[BEACON ROUTINE] Trials ended")
        
    return True
    

# -----------------------------------------------------------------------------------------





# ----------------- CREATION OF BIT MATRIX - A REPRESENTATION OF THE MAP ------------------
class BitMatrix:
    '''
    A space-efficient binary matrix using a bit array, optimized for fast operations.
    '''
    def __init__(self, width=21600, height=10800):
        """
        Initializes a binary matrix with given width and height.
        
        :param width: Number of columns in the matrix.
        :param height: Number of rows in the matrix.
        :initial: The initialization value of the matrix.
        """
        self.width = width
        self.height = height
        self.data = bitarray(width * height)
        self.data.setall(0)
        self.points_taken = 0

    def _check_bounds(self, x, y):
        """
        Ensures that given coordinates (x, y) are within valid matrix bounds.
        
        :raises IndexError: If (x, y) is out of bounds.
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"[ERROR] Coordinates ({x}, {y}) out of bounds")

    def _index(self, x, y):
        """
        Converts 2D coordinates (x, y) to a 1D index for the bit array.
        
        :return: Integer index corresponding to (x, y).
        """
        return y * self.width + x

    def set_bit(self, x, y, value):
        """
        Sets a bit at position (x, y) to 0 or 1.
        
        :param x: X-coordinate.
        :param y: Y-coordinate.
        :param value: Boolean value (0 or 1) to set.
        """
        self._check_bounds(x, y)
        self.data[self._index(x, y)] = bool(value)

    def get_bit(self, x, y):
        """
        Retrieves the bit value at position (x, y).
        
        :param x: X-coordinate.
        :param y: Y-coordinate.
        :return: Boolean value of the bit at (x, y).
        """
        self._check_bounds(x, y)
        return self.data[self._index(x, y)]

    def update_map(self, x, y, angle, value):
        """
        Updates a square region around (x, y) based on camera angle.
        
        :param x: X-coordinate of center.
        :param y: Y-coordinate of center.
        :param angle: Camera angle ('wide', 'normal', or 'narrow') defining update range.
        :param value: Boolean value (0 or 1) to set.
        """
        lens_to_range = {'wide': 500, 'normal': 400, 'narrow': 300}
        range_val = lens_to_range[angle]

        if value == 1:
            self.points_taken += (2 * range_val) ** 2
        else:
            self.points_taken -= (2 * range_val) ** 2

        if range_val not in [300, 400, 500]:
            raise ValueError("[ERROR] Range must be one of: 300, 400, 500")

        x_min = max(0, x - range_val)
        x_max = min(self.width - 1, x + range_val)
        y_min = max(0, y - range_val)
        y_max = min(self.height - 1, y + range_val)

        bool_value = bool(value)
        width_span = x_max - x_min + 1

        row_template = bitarray(int(width_span))
        row_template.setall(bool_value)

        # fast copy operations for each row
        for y_pos in range(y_min, y_max + 1):
            start_idx = self._index(x_min, y_pos)
            # set the entire row segment at once
            self.data[start_idx:start_idx + width_span] = row_template

    def print_matrix(self, step=500):
        """
        Print a compact representation of the matrix, using step sampling.

        :param step: Sampling step size for visualization.
        """
        if DEBUG:
            print()
        # Calculate sampled dimensions
        sample_width = min(self.width // step + 1, 80)  # Limit width for terminal
        sample_height = min(self.height // step + 1, 40)  # Limit height for readability

        if DEBUG:
            print("    ", end="")
            for _ in range(sample_width):
                print("_", end="")
            print()

        for y_idx in range(sample_height):
            y = y_idx * step
            if DEBUG:
                print(f"{y//1000:2d}k| ", end="")

            for x_idx in range(sample_width):
                x = x_idx * step
                if x < self.width and y < self.height:
                    value = self.get_bit(x, y)
                    if DEBUG:
                        print("■" if value else "·", end="")
                else:
                    if DEBUG:
                        print(" ", end="")
            if DEBUG:
                print()

    def save_to_file(self, filename, compress=False):
        """
        Saves the matrix to a binary file for storage.
        
        :param filename: File path to save the data.
        :param compress: If True, compresses data before saving.
        """
        header = struct.pack('<IIQ?', self.width, self.height, self.points_taken, compress)

        # Prepare data
        raw_data = self.data.tobytes()
        if compress:
            raw_data = zlib.compress(raw_data)

        with open(filename, 'wb') as f:
            f.write(header)
            f.write(raw_data)

    @classmethod
    def load_from_file(cls, filename):
        """
        Loads a BitMatrix object from a previously saved file.
        
        :param filename: File path to load the data from.
        :return: A BitMatrix instance with restored data.
        """
        with open(filename, 'rb') as f:
            header = f.read(struct.calcsize('<IIQ?'))
            width, height, points_taken, compress = struct.unpack('<IIQ?', header)

            raw_data = f.read()
            if compress:
                raw_data = zlib.decompress(raw_data)

            bitmat = cls(width, height)
            bitmat.points_taken = points_taken
            bitmat.data = bitarray()
            bitmat.data.frombytes(raw_data)
        return bitmat



Map = BitMatrix(width=21600, height=10800)
# Map = BitMatrix.load_from_file("backup_map.bmap") # In case we need to load a backup

# -----------------------------------------------------------------------------------------







# -------------------------------- MAP CAPTURING LOGIC ----------------------------------------
def get_trajectory(x = -1,y = -1,vx = -1,vy = -1):
    """
    Returns a list of grid points (integer coordinates) that an object passes through
    given initial velocity components vx and vy, considering a bounded map.
    
    :param vx: Velocity in x direction
    :param vy: Velocity in y direction
    :param steps: Number of steps to simulate
    :param start: Starting point (x, y)
    :param map_size: Size of the map (width, height)
    :return: List of (x, y) positions within map bounds
    """
    if x == -1 or y == -1 or vx == -1 or vy == -1:
        check = get_observation()
        x = check["width_x"]
        y = check["height_y"]
        vx = check["vx"]
        vy = check["vy"]
        
    width, height = (21600,10800)
    trajectory = []
    steps = max(round(21600/vx),round(10800/vy))
    for _ in range(steps):
        x += vx
        y += vy
        
        # Ensure the position stays within map bounds
        if x>width-1:
            x = x-width+1
        if y>height-1:
            y = y-height+1    
        
        # x = max(0, min(width - 1, round(x)))
        # y = max(0, min(height - 1, round(y)))
        
        trajectory.append((round(x), round(y)))
    
    return trajectory

def think_about_it(list):
    """
    Evaluates a list of coordinates to determine if at least one of them corresponds 
    to a "good" condition based on the state of the global Map object.
    
    :param list: List of tuples representing coordinates (x, y) that is received from the get_trajectory function.
    
    
    """
    global Map
    good = False
    # print(list) # debug
    for i in list:
        # if Map.get_bit(i[1],i[0]) == 0:
        if Map.get_bit(i[0],i[1]) == 0:
            good = True
            break
    return good

def change_speed(x,y,battery_order):
    """
    function that changes speed on command
    :param x: x coordinate of the target
    :param y: y coordinate of the target
    :param battery_order: battery order for the speed change...if battery gets below that the change speed operation will be interrupted with a full charge break session
    """
    
    
    set_mode("acquisition",x, y,"wide")
    wait("acquisition")
    if not DEBUG:    
        while True:
            safe()
            set_mode("acquisition",x,y,"wide")
            time.sleep(0.2)
            protect_battery(battery_order)
            time.sleep(0.2)
            check = get_observation()
            if check["vx"] == x and check["vy"] == y:
                break
    else :
        if DEBUG:
            simulation(False,20)
        while True:
            safe()
            set_mode("acquisition",x,y,"wide")
            time.sleep(0.2)
            protect_battery(battery_order)
            time.sleep(0.2)
            check = get_observation()
            if check["vx"] == x and check["vy"] == y:
                break    
        if DEBUG:     
            simulation(False,1)




def mod_signed_diff(a, b, mod_val):
    """
    Returns the signed minimal difference between a and b on a circle of circumference mod_val.
    The result lies in [-mod_val/2, mod_val/2].
    :param a: First value
    :param b: Second value
    :param mod_val: Modulus value (circumference of the circle)
    """
    diff = (a - b) % mod_val
    if diff > mod_val/2:
        diff -= mod_val
    return diff

def calculate_travel_time(x, y, vx, vy, dest_x, dest_y, width=21600, height=10800, tolerance=2):
    """
    Calculates the time (in seconds) required to reach (dest_x, dest_y) from (x, y)
    with constant velocities (vx, vy) in a wrap-around world (toroidal map). 
    The function finds the first time t >= 0 such that both:
    
        |mod(x + vx*t - dest_x, width)| <= tolerance
        |mod(y + vy*t - dest_y, height)| <= tolerance
    
    If one of the velocity components is zero and the corresponding coordinate 
    is not already within tolerance, the destination is unreachable (returns infinity).
    
    The method computes, for each moving coordinate, the sequence of times when the
    coordinate “crosses” the destination (modulo the wrap) and the small time window 
    around that crossing when the coordinate is within tolerance. Then it looks for the 
    earliest time when both x and y are simultaneously within tolerance.
    :param x: Current x-coordinate
    :param y: Current y-coordinate
    :param vx: Velocity in x-direction
    :param vy: Velocity in y-direction
    :param dest_x: Destination x-coordinate
    :param dest_y: Destination y-coordinate
    :param width: Width of the map (wrap-around)
    :param height: Height of the map (wrap-around)
    :param tolerance: Tolerance for reaching the destination
    """
    
    # Handle the non-moving axes.
    if vx == 0:
        if abs(mod_signed_diff(x, dest_x, width)) > tolerance:
            return float('inf')
        # x is always valid; treat its valid time window as [0, ∞)
        x_intervals = [(0, float('inf'))]
    else:
        x_intervals = []
        # Determine the period for x
        period_x = width / abs(vx)
        # We will check over a range of wrap counts.
        # Estimate number of periods to check (say 100 periods)
        N_periods = 100
        # Choose a range for n. We solve: t_cross = (dest_x - x + n*width)/vx >= 0.
        # For safety, check n values in an interval that likely covers up to N_periods periods.
        n_min = int(math.floor(-width and ((dest_x - x) / width))) - 1
        n_max = n_min + N_periods
        for n in range(n_min, n_max+1):
            t_cross = (dest_x - x + n * width) / vx
            if t_cross < 0:
                continue
            # At t_cross the x coordinate exactly equals dest_x modulo width.
            # With constant velocity, the coordinate changes at rate |vx|.
            # Thus the time window during which the x position is within tolerance is:
            dt = tolerance / abs(vx)
            # The valid interval for x is:
            interval = (t_cross - dt, t_cross + dt)
            # Ensure the interval lower bound is nonnegative.
            x_intervals.append((max(interval[0], 0), interval[1]))
    
    if vy == 0:
        if abs(mod_signed_diff(y, dest_y, height)) > tolerance:
            return float('inf')
        y_intervals = [(0, float('inf'))]
    else:
        y_intervals = []
        period_y = height / abs(vy)
        N_periods = 100
        n_min = int(math.floor((dest_y - y) / height)) - 1
        n_max = n_min + N_periods
        for n in range(n_min, n_max+1):
            t_cross = (dest_y - y + n * height) / vy
            if t_cross < 0:
                continue
            dt = tolerance / abs(vy)
            interval = (t_cross - dt, t_cross + dt)
            y_intervals.append((max(interval[0], 0), interval[1]))
    
    # Now find the earliest time t >= 0 where an x-interval overlaps a y-interval.
    candidate_time = float('inf')
    for (t_start_x, t_end_x) in x_intervals:
        for (t_start_y, t_end_y) in y_intervals:
            # Find intersection of intervals
            t_start = max(t_start_x, t_start_y)
            t_end = min(t_end_x, t_end_y)
            if t_start <= t_end:
                candidate_time = min(candidate_time, t_start)
    
    if candidate_time == float('inf'):
        return float('inf')
    
    # Return the time rounded to the nearest integer second.
    return int(round(candidate_time))



def part4_main():
    """
    start of the commander logic for the daily map and simultaneously checking and giving the authority of melvin to 
    beacon handler and objective handler when the time comes.
    """
    try:
        safe()
        image_queue = start_stitching_process()

        if DEBUG:
            print("[PART4 MAY BEGIN] Starting whole operation.")
            print("[MELVIN] LAW - when mini charge break happens anything else will become useless until the charge completes")
            simulation(False, 1) # Can change this to True
            
        start_announcement_thread()
        start_objectives_monitoring()
        #threading.Thread(target=objective_logger_thread, daemon=True).start()


        


        #Beginning of all now i am in deployment
        global Map # Map is crucial
        check = get_observation()
        if DEBUG:
            simulation(False,20)
        set_mode("acquisition",check["vx"],check["vy"],"wide")
        wait("acquisition")
        if DEBUG:
            simulation(False,1)

        if DEBUG:
            print("[DAILY PILOT] Starting main logic")
            print("[DAILY PILOT] Calculating nessecary numbers for current simulation speed...")
        
        battery_order = 6
        sleep_order = 1
        battery_loss_acquisition = 0.15
        step = 300
        battery_smart_trick = 4
        
        if DEBUG:
            battery_smart_trick *= 2.5
            battery_order *= 2
            sleep_order /= 5
            print("[DAILY PILOT] I accomplished it!Now i start main logic!")
    
        #starting up the engine
        if DEBUG:
            print("[DAILY PILOT] I received the order and I am getting the initial speed commanded!")
        change_speed(8,8,battery_order)
        if DEBUG:
            print("[DAILY PILOT] Speed reached , from now on i will speak with code commander when I am in charge!")
        #initial booster completed
        
        
        
        
        start_announcement_thread()
        start_objectives_monitoring()
        # threading.Thread(target=objective_listener_thread, daemon=True).start()

            
        while True: #   main commander
            if DEBUG:
                simulation(False,20)
            safe()
            #protect_battery(battery_order)
        #   space and allowance of objectives to be handled # this is the part before any decision happens...
            objective_check_routine(image_queue)
            beacon_check_routine(image_queue)
            
        

            global Map
            
            positions = get_trajectory()
            do_not_change_velocity = think_about_it(positions)
            
        
            #do_not_change_velocity = False
                
            if not do_not_change_velocity:
                
                hold_fast = False
                if DEBUG:
                    print("[DAILY PILOT] Need to change my Trajectory")
                    print("[DAILY PILOT] Possibly long time of thinking requirements so I will sleep beforehand in charge mode")
                
                    
                current = get_observation()
                    
                set_mode("charge", current["vx"], current["vy"], current["angle"])
                
                if DEBUG:
                    print("[DAILY PILOT] scanning the whole Map... this might take from 20 seconds to 40 seconds maximum")
                target = (-1,-1)
                start = datetime.now()
                step_specific = 500
                for i in range(0,21600,step_specific):
                    for j in range(0,10800,step_specific):
                        #if goes wrong comment all this till 
                        vacant = 0
                        detection_range = 500
                        
                        for x in range(current["width_x"]-detection_range, current["width_x"]+detection_range):
                            for y in range(current["height_y"]-detection_range,current["height_y"]+detection_range):
                                if x<0:
                                    x = 21599 + x
                                if y<0:
                                    y = 10799 + y
                                
                                if x>21599:
                                    x = x - 21599
                                if y > 10799:
                                    y = y - 10799
                                if  Map.get_bit(x,y) == 0:
                                    vacant += 1
                                
                        if DEBUG:
                            print("Thought this : ",i,j)
                            print("the important percentages : ", vacant/(1000*1000),(21600 * 10800 - Map.points_taken) / (21600*10800))
                        if vacant/(1000*1000) >= (21600 * 10800 - Map.points_taken) / (21600*10800):
                            target = (i,j)
                            
                            break
                        if target!=(-1,-1):
                            break
                    if target != (-1,-1):
                        break
                        #HERE AND UNCOMMEND
                        
                        # if Map.get_bit(j,i) == 0:
                        # if Map.get_bit(i,j) == 0:
                        #     target = (i,j)
                        #     break
                        #HERE AND YOU WILL BE GOOD
                    if i%4000 == 0:
                        if beacon_check_routine(image_queue):
                            if DEBUG :
                                print("[DAILY PILOT] sending to beacon handler and then breaking")
                            hold_fast = True
                            break
                        
                        if objective_check_routine(image_queue):
                            if DEBUG:
                                print("[DAILY PILOT] sending to objective handler and then breaking")
                            hold_fast = True
                            break    
                
                if hold_fast:
                    continue
                ###################################### step decreasing 
                current = get_observation()
                speed = calculate_velocity(current["width_x"], current["height_y"], target[0], target[1], current["vx"], current["vy"])
                change_speed(speed["vx"],speed["vy"],battery_order)
                
                    
                if DEBUG:
                    print(f"[DAILY PILOT] Scanning whole meta map took {round((datetime.now() - start).total_seconds(),1)}")
                
                
            if do_not_change_velocity:
                
                
                current = get_observation()

                if DEBUG:
                    print("[DAILY PILOT] Thinking about whether I go to sleep or not...!")
                    simulation(False,1)
                
                
                l = get_trajectory()
                save = (-1,-1)
                for i in l:
                    if Map.get_bit(i[0],i[1]) == 0: 
                        save = i
                        break
                current = get_observation()
                
                if DEBUG:
                    print(f"[DAILY PILOT] My target is {save}")
                
                
                
                time_calculated = calculate_travel_time(current["width_x"],current["height_y"],current["vx"],current["vy"],save[0],save[1])
                hold_fast = False
                current = get_observation()
                if current["state"] == "charge":
                    time_calculated -= 180 
                    
                    
                    
                if time_calculated>=360 : 
                    time_calculated -= 180
                    
                    if DEBUG:
                        print(f"[DAILY PILOT] Going to sleep for {time_calculated} REAL seconds(x1)..I will wake up after that!")
                    
                    current = get_observation()
                    set_mode("charge", current["vx"], current["vy"], current["angle"])
                    if DEBUG:
                        simulation(False,20)
                        time_calculated = (round(time_calculated / 20,2)) 
                        
                    sleeping_time_for_this_for_loop_only = round(time_calculated/50,2)
                    for i in range(1,50):
                        
                        time.sleep(sleeping_time_for_this_for_loop_only)
                        
                        if beacon_check_routine(image_queue):
                            if DEBUG :
                                print("[DAILY PILOT] ABORTED: Beacon priority has interrupted me!!!Regaining the control!")
                            hold_fast = True
                            break
                        
                        if objective_check_routine(image_queue):
                            if DEBUG:
                                print("[DAILY PILOT] ABORTED: Objective priority has interrupted me!!!Regaining the control!")
                            hold_fast = True
                            break
                    
                    current = get_observation()
                    set_mode("acquisition", current["vx"], current["vy"], current["angle"])
                    wait("acquisition")
                
                
                else:
                    current = get_observation()
                    if battery_loss_acquisition*time_calculated >= current["battery"]-battery_smart_trick:
                        if DEBUG:
                            print("[DAILY PILOT] Mini charge break")
                            simulation(False,20)
                        set_mode("charge", current["vx"], current["vy"], current["angle"])
                        wait("charge")
                        if DEBUG:
                            simulation(False,1)
                        
                        l = get_trajectory()
                        total = len(l)
                        vacant = 0
                        
                        for i in l:
                            if Map.get_bit(i[0],i[1]) == 0: 
                                vacant+=1
                                
                        
                        if DEBUG:
                            simulation(False,20)
                            print("[DAILY PILOT] mini charge duration for x20 simulation speed = ", round(33*vacant/total,2))
                            time.sleep(round(1.01*45*vacant/total,2))
                        else:
                            time.sleep(round(1.2*900*vacant/total,2))
                        
                        current = get_observation()
                        set_mode("acquisition",current["vx"],current["vy"],"wide")
                        wait("acquisition")
                        
                        continue
                        
                    else:
                        if DEBUG:
                            print("[DAILY PILOT] Time-battery combination allows me to keep going")
                        set_mode("acquisition", current["vx"], current["vy"], current["angle"])
                        wait("acquisition")
                           
                if hold_fast:
                    continue
            
                if DEBUG:
                    print("[DAILY PILOT] I obliged to the decision order! Now I will start the scan and take pictures")
                    simulation(False,20)

                #####
                if DEBUG:
                    simulation(False,4)
                defender = False
                for i in range(2):
                    time.sleep(0.2)
                    safe()
                    #protect_battery(battery_order)
                    current = get_observation()
                    defender = False
                    break_com = False
                    detection_range = 300
                    for x in range(current["width_x"]-detection_range, current["width_x"]+detection_range):
                        for y in range(current["height_y"]-detection_range,current["height_y"]+detection_range):
                            if x<0:
                                x = 21599 + x
                            if y<0:
                                y = 10799 + y
                            if x>21599:
                                x = x - 21599
                            if y > 10799:
                                y = y - 10799
                                
                            if Map.get_bit(x,y) == 0:
                                break_com = True
                                break
                        if break_com == True:
                            break
                    
                    
                    if break_com:
                        defender = False
                        break
                    
                    if DEBUG:    
                        print("[DAILY PILOT] Travelling above area already photographed...refusing to take photo for now!")  
                            
                        #protect_battery(battery_order)
                    time.sleep(sleep_order)
                    defender = True
                    continue
                    
                    # else :
                    #     if DEBUG:
                    #         simulation(False,20)   
                    #     break
                    
                if defender:
                    if DEBUG:
                        simulation(False,20)  
                    continue
                
                if DEBUG:
                    print("[DAILY PILOT] Taking photo on the point I had not yet!")
                    simulation(False,1)
                take_and_enqueue_photo(image_queue)
                
                current = get_observation()
                if DEBUG:
                    print(f"[DAILY PILOT] Updating my memory with this point marked as photographed/my current battery {current['battery']}")
                Map.update_map (current["width_x"],current["height_y"],current["angle"],1)
                if DEBUG:
                    Map.print_matrix()
                    simulation(False,20)
    
    except Exception as e:
        if DEBUG:
            print(f"[MAIN ERROR] Error in main: {e}")
        raise
            
# ------------------------------------------------------------------------------------------------



if __name__ == "__main__":
    part4_main()