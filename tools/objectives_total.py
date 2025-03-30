import requests
import sys
from datetime import datetime, timezone, timedelta

DEBUG = False

def sort_objectives():
    BASE_URL = "http://10.100.10.14:33000/objective"
    HEADERS = {"Content-Type": "application/json"}

    try:
        response = requests.get(BASE_URL, headers=HEADERS)
        response.raise_for_status()

        objectives = response.json()

        if "beacon_objectives" not in objectives:
            if DEBUG:
                print("Error: The response does not contain 'beacon_objectives'.")
            return

        sorted_objectives_beacon = sorted(objectives["beacon_objectives"], key=lambda obj: datetime.strptime(obj["start"], "%Y-%m-%dT%H:%M:%SZ"))
        sorted_objectives_images = sorted(objectives["zoned_objectives"], key=lambda obj: datetime.strptime(obj["start"], "%Y-%m-%dT%H:%M:%SZ"))

        #if DEBUG:
        #    print("Sorted Objectives by Starting Time")
        return sorted_objectives_images, sorted_objectives_beacon

    except requests.exceptions.RequestException as e:
        if DEBUG:
            print(f"Error during API request: {e}")
    except KeyError as e:
        if DEBUG:
            print(f"Error accessing key in JSON: {e}")
    except ValueError as e:
        if DEBUG:
            print(f"Error parsing date: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
       if DEBUG:
        print("Need to give the word \"images\" or \"beacon\" in order to get the desired objectives' list")
       sys.exit(1)

    objectives_images, objectives_beacon = sort_objectives()
    current_t = datetime.utcnow().replace(tzinfo=timezone.utc)
    current_t_plus2 = current_t# + timedelta(hours=2)
 
    if sys.argv[1] == "beacon":
        for obj in objectives_beacon:
            obj_end = datetime.fromisoformat(obj['end'].replace("Z", "+00:00"))
            if obj_end > current_t_plus2:
                if DEBUG:
                    print(f"ID: {obj['id']}, Name: {obj['name']}, Start: {obj['start']}, End: {obj['end']}, Desc: {obj['description']}, Dec_rate: {obj['decrease_rate']}, Attempts_made: {obj['attempts_made']}")

    elif sys.argv[1] == "images":
        for obj in objectives_images:
            obj_end = datetime.fromisoformat(obj['end'].replace("Z", "+00:00"))
            if obj_end > current_t_plus2:
                if DEBUG:
                    print(f"ID: {obj['id']}, Name: {obj['name']}, Start: {obj['start']}, End: {obj['end']}")
        
