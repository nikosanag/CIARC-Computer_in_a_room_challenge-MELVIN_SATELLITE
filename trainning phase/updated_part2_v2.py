import requests
import time
from decimal import ROUND_UP


from set_up import simulation
from objectives import get_and_sort_objectives
from automated import main
from vel_calculation import calculate_velocity
from compute_time import time_computation

# Configuration

MELVIN_BASE_URL = "http://10.100.10.14:33000"
HEADERS = {"User-Agent": "curl/7.68.0", "Content-Type": "application/json"}
PHOTO_FOLDER = "images"  # Folder to save images

MAXIMUM_BATTERY = 100
MINIMUM_BATTERY_CHECK = 5

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


def set_mode(mode, x, y, angle):
    """Set MELVIN's mode (e.g., acquisition or safe)."""

    payload = {"state": mode, "vel_x": x, "vel_y": y, "camera_angle": angle}
    response = requests.put(f"{MELVIN_BASE_URL}/control", json=payload)
    response.raise_for_status()
    #print(f"[INFO] Mode set to {mode}.")


def take_photo(precision):
     """Capture an image and save it with coordinates as the name."""

     simulation(False,1)
     time.sleep(0.5)
     #save = get_observation()
     response = requests.get(f"{MELVIN_BASE_URL}/image")
     response.raise_for_status()
     save = get_observation()
     simulation(False,20)
     image_data = response.content
     width_x = save["width_x"]
     height_y = save["height_y"]
     filename = f"{PHOTO_FOLDER}/lens{precision}_{width_x}_{height_y}.jpg"
     with open(filename, "wb") as img_file:
        img_file.write(image_data)


def wait(new):
    while True:
        check = get_observation()
        obj = get_and_sort_objectives()
        set_mode(new, check["vx"], check["vy"], obj[0]["optic_required"])

        if check["state"] == new:
            break
        if check["state"] == "safe":
            safe()
            break
    return


def safe():
    check = get_observation()
    objectives = get_and_sort_objectives()
    if check["state"] == "safe":
        simulation(False, 20)
        print("SAFE MODE ANOMALLY DETECTED AND HANDLED", flush=True)
        if check["battery"] <= 4:
            protect_battery(MAXIMUM_BATTERY)
        else:
            set_mode("acquisition", check["vx"], check["vy"], objectives[0]["optic_required"])
            wait("acquisition")
            simulation(False, 1)

    return


def protect_battery(x, angle="wide"):
    check1 = get_observation()
    if(check1["battery"] < x):
        simulation(False,20)
        set_mode("charge", check1["vx"], check1["vy"], angle)
        wait("charge")

        while True:
            time.sleep(1)
            check_new = get_observation()
            if check_new["battery"] == check_new["max_battery"]:
                simulation(False,1)
                break

            if check_new["state"] == "safe":
                safe()
                break
    return

def func_main():
    simulation(False,20)
    
    while True:
        simulation(False,20)
        safe()

        objectives = get_and_sort_objectives()
        desired_angle = objectives[0]["optic_required"]

        protect_battery(6, desired_angle)
        check = get_observation()
        set_mode("acquisition", check["vx"], check["vy"], desired_angle)
        wait("acquisition")


        if check["fuel"] == 0:
            print("Out of fuel!")
            break

        elif objectives[0]["zone"] == "unknown":
             print("Brutally check the whole map", flush = True)
             main() # Brutally check the whole map and find differences

        else:
             print("----------------------Known location. BEGIN PROCESS-------------------", flush=True)
             vx = 12.5
             vy = 12.5


            # Wait until desired initial speed is achieved
             while True:
                safe()
                protect_battery(5)
                simulation(False, 20)
                set_mode("acquisition", vx, vy, "wide")
                wait("acquisition")

                check = get_observation()

                if check["vx"] == vx and check["vy"] == vx:
                    break
                if check["fuel"] == 0:
                    break
            # Getting the down left corner
             des_x = objectives[0]["zone"][0]
             des_y = objectives[0]["zone"][3]
             already_taken_photo = False
            
             while True:
                    safe()

                    check = get_observation()
                    

                    if already_taken_photo:
                        lens = get_and_sort_objectives()[0]["optic_required"]
                        if lens == "wide":
                            offset = 500
                        elif lens == "normal":
                            offset = 400
                        else:
                            offset = 300

                        if des_y - offset >= objectives[0]["zone"][1]:
                            des_x = des_x
                            des_y = des_y - offset
                        else:
                            des_x = des_x + offset
                            des_y = des_y

                            if des_x > objectives[0]["zone"][2] + offset / 2:
                                print("OBJECTIVE DONE!", flush=True)

                                set_mode("charge", check["vx"], check["vy"], desired_angle)
                                wait("charge")
                                return 0

                    else:
                        lens = check["angle"]
                        if lens == "wide":
                            offset = 500
                        elif lens == "normal":
                            offset = 400
                        else:
                            offset = 300

                        des_y = des_y - offset / 2

                    if offset == 500:
                        precision = 2 * (offset // 1000)
                    else:
                        precision = 2 * (offset // 100)
                    print(f"New desired position: ({des_x},{des_y})", flush=True)

                    while True:

                        check = get_observation()
                        cur_x = check["width_x"]
                        cur_y = check["height_y"]
                        cur_vx = check["vx"]
                        cur_vy = check["vy"]
                        
                        simulation(False, 20)
                        set_mode("acquisition", cur_vx, cur_vy, desired_angle)
                        wait("acquisition")
                        simulation(False, 1)

                        # Returns {'vx': vx, 'vy': vy, 'distance': dist}
                        vel_data = calculate_velocity(cur_x, cur_y, des_x, des_y, cur_vx, cur_vy)
                        current_velocity = get_observation()
                        safe()
                        print(f"Current velx: {current_velocity['vx']}, current vely: {current_velocity['vy']} | Desired velx: {vel_data['vx']}, desired vely: {vel_data['vy']}", flush=True)
                        if ((current_velocity["vx"] == vel_data["vx"]) and (current_velocity["vy"] == vel_data["vy"])):
                            break

                        for i in range (0, 5, 1):
                            protect_battery(6, desired_angle)
                            safe()
                            set_mode("acquisition", vel_data["vx"], vel_data["vy"], desired_angle)

                    while True:
                        print("----------------------Checking if can reach des distance-------------------", flush=True)
                        can_reach = time_computation(vel_data['distance'])
                        print(f"The time we computed in order to reach desired destination: {round(can_reach[1], 1)}", flush=True)
                        print(f"Is reachable? {can_reach[0]}", flush=True)

                        if can_reach[0] == True:
                            set_mode("charge", vel_data["vx"], vel_data["vy"], desired_angle)
                            #print(f"Estimated reach time: {can_reach[1]}", flush=True)

                            # Check if MELVIN is very close to the target spot
                            if round(can_reach[1], 1) < 360:
                                simulation(False, 20)
                                time.sleep((can_reach[1]/20)+1)
                                simulation(False, 1)
                                cur_x = check["width_x"]
                                cur_y = check["height_y"]
                                des_x = objectives[0]["zone"][0]
                                des_y = objectives[0]["zone"][3] - offset
                                cur_vx = check['vx']
                                cur_vy = check['vy']
                            
                            vel_data = calculate_velocity(cur_x, cur_y, des_x, des_y, cur_vx, cur_vy)
                            time1 = time_computation(vel_data["distance"])
                            print(f"Just got new time estimate: {round(time1[1], 1)}", flush=True)
                        

                            key = round(time1[1], 1)
                            key = key - 180 - 10
                            key =  key // 20
                            #key = key.quantize(Decimal("0.1"), rounding=ROUND_UP)  # Rounds up to one decimal place
                            #key = math.ceil((key / 20)*10)/10
                            print("Time was decided")
                            print(key, flush=True)
                            i=0
                            simulation(False, 20)

                            safe_occured = False
                            while True:
                                print("---------------------------Just doing nothing----------------------------", flush=True)
                                time.sleep(1)
                                state = get_observation()
                                if state["state"] == "safe":
                                    safe()
                                    safe_occured = True
                                    break
                                safe()
                                i+=1
                                if i >= key:
                                    break
                            break
                    
                    if safe_occured == True:
                        continue

                    print("--------------------------Getting ready to reach target-----------------------", flush=True)
                    simulation(False, 20)
                    set_mode("acquisition", vel_data["vx"], vel_data["vy"], desired_angle)
                    wait("acquisition")
                    simulation(False, 1)

                
                    while True:
                        protect_battery(3, desired_angle)
                        check = get_observation()
                        safe()
                        print(f"Checking if in the desired zone.\nNow in {(check['width_x'], check['height_y'])}", flush=True)
                        if (objectives[0]["zone"][2] >= check["width_x"] >= objectives[0]["zone"][0] and objectives[0]["zone"][3] >= check["height_y"] >= objectives[0]["zone"][1]):
                            break
                    
                    
                    while True:
                        check = get_observation()
                        if (check["width_x"] >= objectives[0]["zone"][0] and check["height_y"] >= objectives[0]["zone"][1]):
                             protect_battery(4.9, desired_angle) # Check battery levels
                             safe()
                             #print("-------------------Not yet in desired position------------------", flush=True)
                             if (check["width_x"] <= objectives[0]["zone"][2] and check["height_y"] <= objectives[0]["zone"][3]):
                                  objectives = get_and_sort_objectives()
                                  take_photo(precision)
                                  print("Just took a photo", flush=True)
                                  time.sleep(1)
                             else:
                                  already_taken_photo = True
                                  break


if __name__ == "__main__":
    simulation(False, 20)
    func_main()
