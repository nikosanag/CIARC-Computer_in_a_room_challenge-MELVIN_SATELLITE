import subprocess
import paramiko
import requests
import time
import os

# Configuration

MELVIN_BASE_URL = "http://10.100.10.14:33000"
HEADERS = {"User-Agent": "curl/7.68.0", "Content-Type": "application/json"}
PHOTO_FOLDER = "images"  # Folder to save images

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


def set_mode(mode,x,y,angle):
    """Set MELVIN's mode (e.g., acquisition or safe)."""

    payload = {"state": mode, "vel_x": x, "vel_y": y, "camera_angle": angle}
    response = requests.put(f"{MELVIN_BASE_URL}/control", json=payload)
        #response = requests.put(f"{MELVIN_BASE_URL}/control", json={"state": mode})
    response.raise_for_status()
        #print(f"[INFO] Mode set to {mode}.")
    #except Exception as e:
        #print(f"[ERROR] Failed to set mode: {str(e)}")


def take_photo():
    """Capture an image and save it with coordinates as the name."""
    #try:
    save = get_observation()
    response = requests.get(f"{MELVIN_BASE_URL}/image")
    response.raise_for_status()
    image_data = response.content
    width_x = save["width_x"]
    height_y = save["height_y"]
    filename = f"{PHOTO_FOLDER}/photo_{width_x}_{height_y}.jpg"
    with open(filename, "wb") as img_file:
        img_file.write(image_data)

    #except Exception as e:
    #    print(f"[ERROR] Failed to take photo: {str(e)}")

def wait(new):
    while True:
        check = get_observation()
        set_mode(new,check["vx"],check["vy"],"wide")
        if check["state"] == new:
            break
        if check["state"] == "safe":
            safe()
            break

    return

def safe():
    check = get_observation()
    if check["state"]=="safe":
        print("SAFE MODE-ANOMALLY DETECTED AND HANDLED",flush=True)
        if check["battery"]<=4:
            protect_battery(100)
        else:
            set_mode("acquisition",check["vx"],check["vy"],"wide")
            wait("acquisition")
    return

def protect_battery(x):
    check1 = get_observation()

    
    if(check1["battery"]<x):
        set_mode("charge",check1["vx"],check1["vy"],"wide")
        wait("charge")
        while True:
            time.sleep(2)
            check_new = get_observation()
            if check_new["battery"]==check_new["max_battery"]:

                break

            if check_new["state"]=="safe":
                safe()
                break

    return


def main():

    x = 100

    vx = 40
    vy = 5

    while True:
        safe()
        protect_battery(5)
        set_mode("acquisition",vx,vy,"wide")
        wait("acquisition")

        check = get_observation()



        if check["vx"] == vx and check["vy"] == vx:
            break
        if check["fuel"] == 0:
            break



    number = 0

    while True:
        safe()
        protect_battery(6)
        check = get_observation()

        set_mode("acquisition",vx,vy,"wide")
        wait("acquisition")

        take_photo()
        time.sleep(1)
        number+=1


        if number == 300:
            print("OPERATION : CHANGE ORBIT",flush=True)
            print("CHANGE SPEED 20,21***",flush=True)
            vx += 1
            while True:
                safe()
                protect_battery(6)
                set_mode("acquisition",vx,vy,"wide")
                wait("acquisition")

                check = get_observation()
                time.sleep(1)
                if check["vx"] == vx and check["vy"] == vy:
                    break


            print("DONE",flush=True)

            print("CHARGE SESSION***",flush=True)


            protect_battery(100)

            set_mode("acquisition",vx,vy,"wide")
            wait("acquisition")
            while True:

                check = get_observation()
                if check["battery"]<=6:
                    break

                take_photo()
                time.sleep(1)
                safe()
                continue

            protect_battery(100)


            print("PHASE DARK COMPLETED",flush=True)



            set_mode("acquisition",vx,vy,"wide")

            wait("acquisition")

            print("DONE",flush=True)
            print("going back to normal speed 20,20***",flush=True)
            vy+=1
            while True:
                safe()
                protect_battery(6)
                set_mode("acquisition",vx,vy,"wide")
                wait("acquisition")

                time.sleep(1)
                check = get_observation()
                if check["vx"] == vx and check["vy"] == vy:
                    break


            number = 0

            print("WHOLE OPERATION WAS SUCCESS",flush=True)

            print("NEW HORIZON",flush=True)


if __name__ == "__main__":
    main()
