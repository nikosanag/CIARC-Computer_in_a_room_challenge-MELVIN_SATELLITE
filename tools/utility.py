import requests
import time

DEBUG = False

MELVIN_BASE_URL = "http://10.100.10.14:33000"
HEADERS = {"User-Agent": "curl/7.68.0", "Content-Type": "application/json"}

MAXIMUM_BATTERY = 100
MINIMUM_BATTERY_CHECK = 5

PHOTO_FOLDER = "images"  # Folder to save images

def take_photo(): 
    '''Fucntion to take pictures and save with a specific name in a directory named "images".'''
           
    if DEBUG:
        simulation(False,1)
    time.sleep(0.5)
    response = requests.get(f"{MELVIN_BASE_URL}/image")
    response.raise_for_status()

    save = get_observation()
    lens_to_precision = {'wide': '1', 'normal': '8', 'narrow': '6'}
    if DEBUG:
        simulation(False,20)
    image_data = response.content
    width_x = save["width_x"]
    height_y = save["height_y"]

    filename = f"{PHOTO_FOLDER}/lens{lens_to_precision[save['angle']]}_{width_x}_{height_y}.jpg"
    with open(filename, "wb") as img_file:
        img_file.write(image_data)
    # return image_data, filename 
    # if DEBUG:
    #     print(f"[TAKE_PHOTO] Filename: {filename}")
    return filename 


def simulation(simulation,speed):
    ''' Only for debugging reasons '''

    payload = {
            "is_network_simulation" : simulation, 
            "user_speed_multiplier" : speed
        }
    response = requests.put(f"{MELVIN_BASE_URL}/simulation", params=payload)
    return

def get_observation():
    '''Retrieve MELVIN's observation data.'''
           
    try:
        # print(f"[DEBUG] Sending GET request to {MELVIN_BASE_URL}/observation")
        response = requests.get(f"{MELVIN_BASE_URL}/observation")
        # print(f"[DEBUG] Response status code: {response.status_code}")
        response.raise_for_status()
        # print(f"[DEBUG] Response JSON: {response.json()}")
        return response.json()
    except Exception as e:
        print(f"[ERROR] Failed to fetch observation data: {str(e)}")
        return get_observation()


def set_mode(mode, x, y, angle):
    ''' 
    Control MELVIN's state, velocity and camera angle.
    
    :param mode: (str) e.g. 'acquisition', 'communication', 'charge'
    :param x: (float) velocity x axis
    :param y: (float) velocity y axis
    :param angle: (str) e.g. 'wide', 'narrow', 'normal'
    '''
    payload = {"state": mode, "vel_x": x, "vel_y": y, "camera_angle": angle}
    response = requests.put(f"{MELVIN_BASE_URL}/control", json=payload)
    response.raise_for_status()


def wait(new):
    ''' 
    Function to make sure MELVIN changed to desired mode.
    
    :param new: (str) Desired new mode
    '''
    while True:
        check_wait = get_observation()
        set_mode(new, check_wait["vx"], check_wait["vy"], check_wait["angle"])

        if check_wait["state"] == new:
            break
        if check_wait["state"] == "safe":
            safe()
            break
        time.sleep(0.3)
    return


def safe(prev_mode="acquisition"): # Not necessarily acquisition, but to be safe I set it as default
    ''' 
    Make sure MELVIN never enters safe mode. 

    :param prev_mode: (str) Mode it had before entering safe mode -> in order to set this mode before returning
    '''

    check = get_observation()
    if check["state"] == "safe":
        if DEBUG:
            simulation(False, 20)
            print("SAFE MODE ANOMALLY DETECTED AND HANDLED", flush=True)

        if check["battery"] <= MINIMUM_BATTERY_CHECK:
            protect_battery(MAXIMUM_BATTERY)
        else:
            if check["state"] != prev_mode:
                set_mode(prev_mode, check["vx"], check["vy"], check["angle"])
                wait(prev_mode)
    return


def protect_battery(x, angle="wide", prev_mode="acquisition"):
    ''' 
    Protect battery leak, not to drop more that the desired threshold. 
    
    :param x: (int) Threshold for minimum battery acceptable
    :param angle: (str) e.g. 'wide', 'narrow', 'normal'
    '''

    global MAXIMUM_BATTERY

    check1 = get_observation()
    if check1["battery"] < x:
        if DEBUG:
            simulation(False, 20)
            print(f"Maximum battery: {MAXIMUM_BATTERY}")
        
        # Update MAXIMUM_BATTERY if a new maximum is found
        if check1["max_battery"] < MAXIMUM_BATTERY:
            MAXIMUM_BATTERY = check1["max_battery"]
            if DEBUG:
                print(f"[INFO] New maximum battery capacity detected: {MAXIMUM_BATTERY}")

        set_mode("charge", check1["vx"], check1["vy"], angle)
        wait("charge")

        while True:
            #time.sleep(480)  # time to fully charge if x == 5
            time.sleep(4)

            check_new = get_observation()
            if DEBUG:
                battery = check_new["battery"]
                print(f"[CHARGING] Maximum battery: {MAXIMUM_BATTERY}, battery now: {battery}")

            if check_new["battery"] == check_new["max_battery"]:
                if DEBUG:
                    simulation(False, 20)

                # This line missing caused errors, DEBUG
                set_mode(prev_mode, check1["vx"], check1["vy"], angle)
                wait(prev_mode)

                break

            if check_new["state"] == "safe":
                safe()
                break
    return


def get_slots():
    ''' Return available slots. '''
           
    try:
        #print(f"[DEBUG] Sending GET request to {MELVIN_BASE_URL}/slots")
        response = requests.get(f"{MELVIN_BASE_URL}/slots")
        #print(f"[DEBUG] Response status code: {response.json}")
        response.raise_for_status()
        #print(f"[DEBUG] Response JSON: {response.json()}")
        return response.json()["slots"]
    except Exception as e:
        if DEBUG:
            print(f"[ERROR] Failed to fetch slot data: {str(e)}")
        return None
    

def check_for_next_slot(des_time):
    ''' 
    Check for the timestamps, and book wisely. 
    
    :param des_time: Desired time to have booked a slot (format: "%Y-%m-%dT%H:%M:%S.6fZ")
    '''

    response = get_slots()
    for slot in response:
        slot_id = slot.get("id")
        start = slot.get("start")
        end = slot.get("end")
        enabled = slot.get("enabled")

        if des_time < start: # First slot to satisfy this, will be booked if not already done so
            if not enabled:
                book_slot(slot_id)
                if DEBUG:
                    print(f"[DEBUG] Booked slot {slot_id} with starting/ending time {start}/{end}")
                return 
            else:
                if DEBUG:
                    print(f"[DEBUG] Already booked slot {slot_id}")

        elif DEBUG:
            print(f"None slots available with desired time: {des_time}")
    return


def book_slot(slot_id):
    ''' 
    Book one slot. 

    :param slot_id: (int) The id of the desired slot to book
    '''

    try:
        #print(f"[DEBUG] Sending PUT request to {MELVIN_BASE_URL}/slots")
        payload = {
                "slot_id" : slot_id,
                "enabled" : True
            }
        response = requests.put(f"{MELVIN_BASE_URL}/slots",params=payload)
        
        #print(f"[DEBUG] Response status code: {response.status_code}")
        response.raise_for_status()
        #print(f"[DEBUG] Response JSON: {response.json()}")

    except Exception as e:
        if DEBUG:
            print(f"[ERROR] Failed to enable a slot: {str(e)}")
        return None
