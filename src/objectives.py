import requests
from datetime import datetime, timezone, timedelta

DEBUG = False

beacon_start_time = {}
beacon_end_time = {}
zoned_start_time = {}
zoned_end_time = {}
started_beacon_objectives = []
started_zoned_objectives = []
sorted_beacon_objectives = []
sorted_zoned_objectives = []

def get_and_sort_objectives(contain_secret=True):
    BASE_URL = "http://10.100.10.14:33000/objective"
    HEADERS = {"Content-Type": "application/json"}

    try:
        response = requests.get(BASE_URL, headers=HEADERS)
        response.raise_for_status()
        objectives = response.json()

        if "zoned_objectives" not in objectives:
            if DEBUG:
                print("Error: The response does not contain 'zoned_objectives'.")
            return

        if contain_secret:
            sorted_objectives = sorted(
                objectives["zoned_objectives"],
                key=lambda obj: (
                    datetime.strptime(obj["start"], "%Y-%m-%dT%H:%M:%SZ"),
                    datetime.strptime(obj["end"], "%Y-%m-%dT%H:%M:%SZ")
                )
            )
        else:
            result = [i for i in objectives['zoned_objectives'] if i['secret']]
            sorted_objectives = sorted(
                result,
                key=lambda obj: (
                    datetime.strptime(obj["start"], "%Y-%m-%dT%H:%M:%SZ"),
                    datetime.strptime(obj["end"], "%Y-%m-%dT%H:%M:%SZ")
                )
            )
        return sorted_objectives

    except requests.exceptions.RequestException as e:
        if DEBUG:
            print(f"Error during API request: {e}")
    except KeyError as e:
        if DEBUG:
            print(f"Error accessing key in JSON: {e}")
    except ValueError as e:
        if DEBUG:
            print(f"Error parsing date: {e}")

def get_current_objectives(contain_secret=True):
    BASE_URL = "http://10.100.10.14:33000/objective"
    HEADERS = {"Content-Type": "application/json"}

    try:
        response = requests.get(BASE_URL, headers=HEADERS)
        response.raise_for_status()
        objectives = response.json()

        beacons = objectives.get("beacon_objectives", [])
        zoned = objectives.get("zoned_objectives", [])
        
        current_t = datetime.now(timezone.utc)
        started_zoned_objectives = []

        for obj in zoned:
            zoned_id = obj["id"]
            zoned_start_time[zoned_id] = parse_datetime(obj['start'])
            zoned_end_time[zoned_id] = parse_datetime(obj['end'])

            if zoned_start_time[zoned_id] <= current_t and zoned_end_time[zoned_id] >= current_t:
                if not contain_secret and obj['secret']:
                    continue
                started_zoned_objectives.append(obj)

        sorted_zoned_objectives = sorted(
            started_zoned_objectives,
            key=lambda x: parse_datetime(x["end"])
        )

        sorted_beacon_objectives = sorted(
            started_beacon_objectives,
            key=lambda x: parse_datetime(x["end"])
        )
        
        return sorted_zoned_objectives

    except requests.exceptions.RequestException as e:
        if DEBUG:
            print(f"Error during API request: {e}")
    except KeyError as e:
        if DEBUG:
            print(f"Error accessing key in JSON: {e}")
    except ValueError as e:
        if DEBUG:
            print(f"Error parsing date: {e}")

def parse_datetime(date_str):
    if date_str.endswith('Z'):
        date_str = date_str.replace('Z', '+00:00')
    dt = datetime.fromisoformat(date_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt

if __name__ == "__main__":
    objectives = get_current_objectives()
    current_t = datetime.now(timezone.utc)
    current_t_plus2 = current_t + timedelta(hours=2)
    
    for obj in objectives:
        obj_end = datetime.fromisoformat(obj['end'].replace("Z", "+00:00"))
        if obj_end > current_t_plus2:
            print(f"ID: {obj['id']}, Name: {obj['name']}")
            print(f"Start: {obj['start']}, End: {obj['end']}")
            print(f"Description: {obj['description']}")
            print(f"Zone: {obj['zone']}, Lens: {obj['optic_required']}, Sprite: {obj['sprite']}")
            print("-" * 40)