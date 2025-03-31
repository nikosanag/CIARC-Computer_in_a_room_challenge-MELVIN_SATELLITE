from utility import get_observation, set_mode, wait, simulation, protect_battery, safe, take_photo, check_for_next_slot
from submit_responses import submit_EB, submit_image, submit_map
from beacon_position_calculator import find_solution
from objectives import get_and_sort_objectives, get_current_objectives, parse_datetime
from objectives_total import sort_objectives
from vel_calculation import calculate_velocity
from compute_time import time_computation
from zonedStitching import stitch_zoned
# from mapStitching import capture_and_stitch

import traceback
import time
import numpy as np
import math
from datetime import datetime, timezone, timedelta
from bitarray import bitarray
from collections import namedtuple
import zlib
import struct


# -------------------------------- CREATION OF MAP MATRIX ---------------------------------


DEBUG = False


#Do not touch if u dont have a clue
class BitMatrix:
    def __init__(self, width=21600, height=10800):
        self.width = width
        self.height = height
        self.data = bitarray(width * height)
        self.data.setall(0)
        self.points_taken = 0

    def _check_bounds(self, x, y):
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"[ERROR] Coordinates ({x}, {y}) out of bounds")

    def _index(self, x, y):  # Convert 2D coordinates to 1D index.
        return y * self.width + x

    def set_bit(self, x, y, value):
        self._check_bounds(x, y)
        self.data[self._index(x, y)] = bool(value)

    def get_bit(self, x, y):
        self._check_bounds(x, y)
        return self.data[self._index(x, y)]

    def update_map(self, x, y, angle, value):
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
        Displays the matrix in a more terminal-friendly format.
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




Map = BitMatrix.load_from_file("backup_map.bmap")


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

    try:
        
       
        safe()


        if DEBUG:
            print("[] Starting whole operation.")
            print("[MELVIN] LAW - when mini charge break happens anything else will become useless until the charge completes")
            simulation(False, 1) # Can change this to True

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
        check = get_observation()
        change_speed(check['vx'], check['vy'], battery_order)
        if DEBUG:
            print("[DAILY PILOT] Speed reached , from now on i will speak with code commander when I am in charge!")
        #initial booster completed
        
        
        
        

            
        while True: #   main commander
            if DEBUG:
                simulation(False,20)
            safe()
            protect_battery(3)
            
        

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
                        vacant = 0
                        detection_range = 500
                        if Map.get_bit(i,j) == 1:
                            continue
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
                        
                        
                        # if Map.get_bit(j,i) == 0:
                        # if Map.get_bit(i,j) == 0:
                        #     target = (i,j)
                        #     break
                    
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
                    

                    
                if defender:
                    if DEBUG:
                        simulation(False,20)  
                    continue
                
                if DEBUG:
                    print("[DAILY PILOT] Taking photo on the point I had not yet!")
                    simulation(False,1)
                take_photo()
                
                current = get_observation()
                if DEBUG:
                    print(f"[DAILY PILOT] Updating my memory with this point marked as photographed/my current battery {current['battery']}")
                Map.update_map (current["width_x"],current["height_y"],current["angle"],1)
                if DEBUG:
                    Map.print_matrix()
                    simulation(False,20)
    except BaseException as e:
        safe("charge")
        print("An error occurred:")
        traceback.print_exc()
        # check_for_next_slot(current_time) # Booking the first available slot if not already booked
        Map.save_to_file("backup_map.bmap")




if __name__ == '__main__':
    part4_main()