import subprocess
import paramiko
import requests
import os
import time

MELVIN_BASE_URL = "http://10.100.10.14:33000"
HEADERS = {"User-Agent": "curl/7.68.0", "Content-Type": "application/json"}

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


if __name__ == "__main__":
    while True:
        observe = get_observation()
        print(f"{observe}", flush=True)
        time.sleep(2)
