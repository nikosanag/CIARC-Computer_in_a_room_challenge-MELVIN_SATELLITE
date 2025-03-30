import requests
import math
from datetime import datetime, timedelta
from objectives import get_and_sort_objectives
#from observation import get_observation

MELVIN_BASE_URL = "http://10.100.10.14:33000"
HEADERS = {"User-Agent": "curl/7.68.0", "Content-Type": "application/json"}

MAXIMUM_BATTERY = 100
MINIMUM_BATTERY_CHECK = 5
FUEL_HANDLE = 10
A_CONST = 0.02
FUEL_LOSS = 0.03

DEBUG = False

def get_observation():
    """Retrieve MELVIN's observation data."""

    try:
        #print(f"[DEBUG] Sending GET request to {MELVIN_BASE_URL}/observation")
        response = requests.get(f"{MELVIN_BASE_URL}/observation")
        #print(f"[DEBUG] Response status code: {response.status_code}")
        response.raise_for_status()
        #print(f"[DEBUG] Response JSON: {response.json()}")
        return response.json()
    except Exception as e:
        #print(f"[ERROR] Failed to fetch observation data: {str(e)}")
        return get_observation()


def time_computation(desired_dist): #Currently not using all the functionalities
    ''' 
    Function that takes desired distance as argument and returns whether MELVIN 
    can reach that from his current position in time (before the endtime of the objective).
    '''

    observe = get_observation()
    vel_x1 = observe['vx']
    vel_y1 = observe['vy']
    #battery = observe['battery']
    #fuel = observe['fuel']
    timestamp = observe['timestamp']
    pos_x = observe['width_x']
    pos_y = observe['height_y']
    state = observe['state']

    sorted_obj = get_and_sort_objectives()
    start_t = sorted_obj[0]['start']
    end_t = sorted_obj[0]['end']

    # Battery unit loss per second
    if state == "acquisition":
        # Get observation again to check for the thruster
        obs = get_observation()
        vel_x2 = obs['vx']
        vel_y2 = obs['vy']
        unit_loss = 0.15 # Battery loss when in acquisition mode
        dv_x = abs(vel_x2 - vel_x1)
        dv_y = abs(vel_y2 - vel_y1)
        if dv_x > 0:
            thruster_x = math.sqrt((A_CONST ** 2) / (1 + (dv_y / dv_x) ** 2))
        else:
            thruster_x = 0
        if dv_y >0:
            thruster_y = math.sqrt((A_CONST ** 2) / (1 + (dv_x / dv_y) ** 2))
        else:
            thruster_y = 0
        fuel_loss_x = thruster_x * FUEL_LOSS
        fuel_loss_y = thruster_y * FUEL_LOSS
    elif state == "deployment":
        unit_loss = 0.0125 # Battery loss when in deployment mode
        fuel_loss_x = 0
        fuel_loss_y = 0
    elif state == "communication":
        unit_loss = 0.008 # Battery loss when in communication mode
        fuel_loss_x = 0
        fuel_loss_y = 0
    else:
        unit_loss = 0
        fuel_loss_x = 0
        fuel_loss_y = 0

    # Time to reach desired spot with current speed
    speed = math.sqrt(vel_x1**2 + vel_y1**2)
    dt = desired_dist / speed

    # Calculate how much battery and fuel will that consume
    battery_use = dt * unit_loss
    fuel_use = fuel_loss_x * FUEL_LOSS + fuel_loss_y * FUEL_LOSS

    # Check whether this time is enough or not
    #hours = dt // 3600
    #minutes = (dt % 3600) // 60
    #seconds = (dt % 3600) % 60

    parse_timestamp = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
    time = parse_timestamp + timedelta(seconds=dt)
    des_time = time.strftime("%Y-%m-%dT%H:%M:%S.%fZ") # Convert it back to its format

    if (des_time < end_t):
        # Calculated the battery amount if enough return True, else need to adjust the time
        obs = get_observation()
        battery = obs['battery']
        fuel = obs['fuel']
        #if (battery - battery_use > MINIMUM_BATTERY_CHECK and fuel - fuel_use > FUEL_HANDLE):
        #   return True
        #else:
        #   time_to_fully_charge = (MAXIMUM_BATTERY - battery) * 0.1
        #   parse_timestamp = datetime.strptime(des_time, "%Y-%m-%dT%H:%M:%S.%fZ")
            #   time = parse_timestamp + timedelta(seconds=time_to_fully_charge)
            #   des_time_bat = time.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        #   if (des_time_bat < end_t): # If we arrive on time even with recharging
        return (True, dt)
        #   else:
                # Check how much accelaration is needed in order to arrive early
        #       return False
    else:
        # Check how much accelaration is needed in order to arrive early
        return (False, dt)


if __name__ == "__main__":
    time_computation()
