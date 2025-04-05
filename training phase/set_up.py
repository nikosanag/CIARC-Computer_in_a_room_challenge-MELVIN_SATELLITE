import subprocess
import paramiko
import requests
import time
import os
import sys


MELVIN_BASE_URL = "http://10.100.10.14:33000"
HEADERS = {'Content-Type':'application/json'}



def get_slots():
    try:
        print(f"[DEBUG] Sending GET request to {MELVIN_BASE_URL}/slots")
        response = requests.get(f"{MELVIN_BASE_URL}/slots")
        print(f"[DEBUG] Response status code: {response.json}")
        response.raise_for_status()
        print(f"[DEBUG] Response JSON: {response.json()}")
        return response.json()["slots"]
    except Exception as e:
        print(f"[ERROR] Failed to fetch slot data: {str(e)}")
        return None

def book_slot(slot_id):
    try:
        print(f"[DEBUG] Sending PUT request to {MELVIN_BASE_URL}/slots")
        payload = {
                "slot_id" : slot_id,
                "enabled" : True
                }
        response = requests.put(f"{MELVIN_BASE_URL}/slots",params=payload)
        
        print(f"[DEBUG] Response status code: {response.status_code}")
        response.raise_for_status()
        print(f"[DEBUG] Response JSON: {response.json()}")
    except Exception as e:
        print(f"[ERROR] Failed to enable a slot: {str(e)}")
        return None



def check_for_enabled_slot():
    response = get_slots()
    for slot in response:
        slot_id = slot.get("id")
        start = slot.get("start")
        end = slot.get("end")
        enabled = slot.get("enabled")
        if enabled == True:
            print(f"Slot {slot_id} has already been  booked")
            return slot_id
    print("None of the slots has been booked. Calling book_slot()...")
    book_slot(slot_id)
        

def simulation(simulation,speed):
    payload = {
            "is_network_simulation" : simulation, 
            "user_speed_multiplier" : speed

            }
    response = requests.put(f"{MELVIN_BASE_URL}/simulation",params=payload)
    return

if __name__ == "__main__":
    if len(sys.argv)<2:
        print("Give simulation on?/simulation speed?\nTry again...")
         
    else :
        simulation(sys.argv[1],sys.argv[2])
        subprocess.Popen(["python3","security_slot.py"])    
        sys.exit(0)
