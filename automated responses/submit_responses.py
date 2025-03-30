import requests
import re
import json

DEBUG = False

MELVIN_BASE_URL = "http://10.100.10.14:33000"
HEADERS = {"User-Agent": "curl/7.68.0", "Content-Type": "application/json"}

# Necessary URLs for submitting done objectives
BEACON_URL = f"{MELVIN_BASE_URL}/beacon" # PUT method
IMAGE_URL = f"{MELVIN_BASE_URL}/image" # POST method
DAILYMAP_URL = f"{MELVIN_BASE_URL}/dailyMap" # POST method

def submit_image(obj_id, path):
    ''' 
    Submitting Image objective zoned/secret. 

    :param obj_id: id (int) of the objective
    :param path: path (str) to zoned/secret location image 
    '''
    with open(path, "rb") as image_file:
        image_binary = image_file.read()

    parts = path.split('/')

    params = {
        'objective_id': obj_id
    }
    
    files = {
        'image': (parts[-1], image_binary, 'image/png')
    }

    # Send the POST request
    response = requests.post(IMAGE_URL, params=params, files=files)

    if response.status_code == 200:
        result = response.json()
        if DEBUG:
            print(f"[INFO] Objective submitted: {result}")
        return result
    else:
        raise Exception(f"Failed to submit objective image: {response.text}")


def submit_map(total_map):
    ''' 
    Submitting Daily Map.
    
    :param total_map (.png) stiched map ready for submition 
    '''
    
    with open(total_map, "rb") as image_file:
        image_binary = image_file.read()

    files = {
        "image": ("total_map", image_binary, "image/png")
    }
    response = requests.post(DAILYMAP_URL, files=files)

    if response.status_code == 200:
        result = response.json()
        if DEBUG:
            print(f"[INFO] Daily Map submitted: {result}")
        return result
    else:
        raise Exception(f"Failed to submit daily map: {response.text}")


def submit_EB(id, x, y):
    ''' 
    Submitting EB position estimation.
    
    :param id (int) beacon_id
    :param x (int) width
    :param y (int) height
    '''
    
    #Round x and y to the nearest integer
    x = round(x)
    y = round(y)

    params = {
        "beacon_id": id,
        "width": x,
        "height": y
    }
    response = requests.put(BEACON_URL, params=params)

    if response.status_code == 200:
        result = response.json()
        if DEBUG:
            print(f"[INFO] Beacon position submitted: {result}")
        
        text = json.dumps(result)

        return text

    else:
        raise Exception(f"Failed to submit beacon position: {response.text}")

