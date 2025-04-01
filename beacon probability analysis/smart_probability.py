#Author: NIKOLAOS ANAGNOSTOU
#SPACE TRANSFORMERS TEAM
"""
This script simulates the process of determining the number of pings required to find a target within a specified tolerance range. The simulation runs multiple tests to gather statistical data on the performance of the pinging process.
Modules:
    - random: Provides functions to generate random numbers.
    - collections: Provides the Counter class to count occurrences of elements.
    - os: Provides functions to interact with the operating system.
    - time: Provides functions to measure time.
    - datetime: Provides functions to manipulate dates and times.
Constants:
    - ACCEPTED_POSSIBILITIES: Threshold for the minimum number of pings to be printed.
    - MAX_TESTINGS: Number of beacon tests to run.
    - TOTAL_TIMES: Number of times each position is pinged repeatedly.
    - distance_max: Maximum distance for the target.
    - distance_min: Minimum distance for the target.
    - tolerance: Acceptable error range for the pings.
    - ACTIVATOR_OF_MULTIPLE_PINGS_IN_SAME_LOCATIONS: Flag to enable multiple pings in the same location.
    - wall: Threshold for focusing mode.
    - focusing: Flag to enable focusing mode.
Variables:
    - grandmaster: Counter to save numbers contributing to chances calculation.
    - path: Path to the output text file.
    - text_file: File object for writing the output.
    - sum: Sum of the ping errors.
    - pings_quantity: Number of pings performed.
    - testings: Number of tests performed.
    - result: Total number of pings required.
    - useless: Number of pings that resulted in out-of-range distances.
    - save_worst_case_scenario: Worst case scenario for the number of pings.
    - save_best_case_scenario: Best case scenario for the number of pings.
Functions:
    - None
Main Logic:
    1. Initialize variables and open the output text file.
    2. Run the first simulation without noise removal.
    3. Calculate and write the results to the output file.
    4. Run the second simulation with noise removal.
    5. Calculate and write the results to the output file.
    6. Print the execution time for both simulations.
"""
from random import randint
from random import uniform
from collections import Counter
import os
import time
from datetime import datetime 
begin = time.time()
start = time.time()



################### command panel ~edit what changes you want for this simulation~
ACCEPTED_POSSIBILITIES = 0.1 #the pings quantities that offers below this number will not be printed...
MAX_TESTINGS = 1000000#defines how many beacons will this execute will run...the higher the more stable results
TOTAL_TIMES = 3 #defines how many times the beacon will ping each position reapetedly ...dramatically increases chances
distance_max = 2000 #defines on what areas you estimate melvin will be when it receives the ping
distance_min = 0
tolerance = 37.5 #it defines how much error you are eager to take
ACTIVATOR_OF_MULTIPLE_PINGS_IN_SAME_LOCATIONS = True #enables the TOTAL_TIMES so its function work
wall = 3
focusing = True
focusing = False
average_trick_activated = True #testing of the smart average
################# end of command panel



grandmaster = Counter() #great name ... a counter used to save numbers that contributes to chances calculation
#################
path = os.path.join("data", f"{datetime.fromtimestamp(start).strftime("%d_%B_%Y__%I_%M_%S_%p")}###{focusing}###_{distance_min}_{distance_max}_{tolerance}_!{TOTAL_TIMES}!__!!{ACTIVATOR_OF_MULTIPLE_PINGS_IN_SAME_LOCATIONS}!!__!!!{MAX_TESTINGS}!!!.txt")
text_file = open(path,"w")


sum = 0
pings_quantity = 0
testings = 0
result = 0
useless = 0

save_worst_case_scenario = 0
save_best_case_scenario = 10000000
text_file.write("@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n")
text_file.write(f"Total simulation run : {MAX_TESTINGS}\n")
text_file.write("\n----------------------TESTING WITHOUT TRYING TO REMOVE THE NOISE WITH ANY RANDOM WAY---------------------------\n")
text_file.write(f"Testing with tolerance 2*{tolerance} and distance between {distance_min} and {distance_max} and with ordered iterations and simulations {MAX_TESTINGS}")
text_file.write("\n")



while True:
    distance_achieved = randint(distance_min,distance_max)
    for i in range(0,TOTAL_TIMES):
        test = round(uniform(-1,1),3)
        trick = round(uniform(-1,1),3)
        pings_quantity += 1
        
        num  = (test) * (3*75 + (distance_achieved+1)*0.1)
        
       
        
        if (distance_achieved + num >2000 or distance_achieved + num <0): 
            useless+=1
            
        
        sum += num
        
        if not ACTIVATOR_OF_MULTIPLE_PINGS_IN_SAME_LOCATIONS:
            break
    
    
    if ACTIVATOR_OF_MULTIPLE_PINGS_IN_SAME_LOCATIONS:
        sum = round(sum/TOTAL_TIMES,2)
    else :
        sum = round(sum,2)
        
    if focusing and pings_quantity==wall*TOTAL_TIMES+TOTAL_TIMES:
        testings += 1
        if testings == MAX_TESTINGS:
            break
        pings_quantity = 0
        sum = 0
        continue
        
    if (sum/pings_quantity < tolerance  and sum/pings_quantity > -tolerance):
        if pings_quantity<wall:
            continue
        if  ACTIVATOR_OF_MULTIPLE_PINGS_IN_SAME_LOCATIONS:
            if not pings_quantity>=wall*TOTAL_TIMES:
                continue
        
        sum = 0
        grandmaster.update([pings_quantity])
        
        if (save_worst_case_scenario<pings_quantity):
            save_worst_case_scenario = pings_quantity
        if (save_best_case_scenario>pings_quantity):
            save_best_case_scenario = pings_quantity
       
                
        result += pings_quantity
        pings_quantity = 0
        testings +=1
        
        if testings == MAX_TESTINGS :
            
            break
        
        else:
            continue
    
    
        
    
if not focusing:    
    result = result/testings    
    useless = useless/testings
    text_file.write(f"Τhe total avarage pings_quantity needed is {round(result,2)} and best performance noticed : {save_best_case_scenario} and worst performance noticed : {save_worst_case_scenario} and pings irrational : {useless}\n")
    text_file.write("Below the important chances:\n")


LIMIT = 1000

for i in range(0,LIMIT+1):
   
    if i in grandmaster and round(grandmaster[i]/testings*100,3)>ACCEPTED_POSSIBILITIES:
        text_file.write(f"The beacons that only |{i}| pings were needed in order to find the target with average mistake of |{2*tolerance}| meters/pixels were |{grandmaster[i]}| and in a chance = |{round(grandmaster[i]/testings*100,2)}%| of total tested different beacons!\n")
print(f"\nExecution time:{round(time.time()-start,2)} seconds\n") 
text_file.write(f"\nExecution time:{round(time.time()-start,2)} seconds\n")
text_file.write("--------------------------------------NOW WITH TRYING TO REMOVE THE NOISE WITH RANDOMNESS-----------------------------------\n")
grandmaster.clear()
testings = 2
sum = 0
pings_quantity = 0
testings = 0
result = 0
useless = 0

save_worst_case_scenario = 0
save_best_case_scenario = 10000000
start = time.time()
text_file.write(f"Testing with tolerance 2*{tolerance} and distance between {distance_min} and {distance_max} and with ordered iterations and simulations {MAX_TESTINGS}")
if average_trick_activated:
    text_file.write("\nTake note I will use the smart average method between the after denoise error and the returned noise error")
text_file.write("\n")

while True:
    distance_achieved = randint(distance_min,distance_max)
    for i in range(0,TOTAL_TIMES):
        test = round(uniform(-1,1),3)
        trick = round(uniform(-1,1),3)
        pings_quantity += 1
        
       
        save =  test * (3*75 + (distance_achieved+1)*0.1) #here
        num = distance_achieved + save
        
        num =round(num-trick*(3*75+0.4*(num+1))/4) # estimated distance
        num = distance_achieved - num # error  in distance
        
        
        if (distance_achieved + num >2000 or distance_achieved + num <0): 
            useless+=1
            
        if average_trick_activated:
            sum += (num+save)/2 # taking the average
        else:
            sum += num
        
        if not ACTIVATOR_OF_MULTIPLE_PINGS_IN_SAME_LOCATIONS:
            break
        
    if ACTIVATOR_OF_MULTIPLE_PINGS_IN_SAME_LOCATIONS:
        sum = round(sum/TOTAL_TIMES,2)
    else :
        sum = round(sum,2)
        
    if focusing and pings_quantity==wall*TOTAL_TIMES+TOTAL_TIMES:
        testings += 1
        if testings == MAX_TESTINGS:
            break
        pings_quantity = 0
        sum=0
        continue
    
    if (sum/pings_quantity < tolerance  and sum/pings_quantity > -tolerance):
        if pings_quantity<wall:
            continue
        if  ACTIVATOR_OF_MULTIPLE_PINGS_IN_SAME_LOCATIONS:
            if not pings_quantity>=wall*TOTAL_TIMES:
                continue
        
        sum = 0
        grandmaster.update([pings_quantity])
        
        if (save_worst_case_scenario<pings_quantity):
            save_worst_case_scenario = pings_quantity
        if (save_best_case_scenario>pings_quantity):
            save_best_case_scenario = pings_quantity
       
                
        result += pings_quantity
        pings_quantity = 0
        testings +=1
        #text_file.write(f"testings currently: {testings}")
        if testings == MAX_TESTINGS:
            
            break
        
        else:
            continue
    
    
        
    
if not focusing:   
    result = result/testings        
    useless = useless/testings
    text_file.write(f"Τhe total avarage pings_quantity needed is {round(result,2)} and best performance noticed : {save_best_case_scenario} and worst performance noticed : {save_worst_case_scenario} and pings irrational : {useless}\n")
    text_file.write("Below the important chances:\n")


LIMIT = 1000

for i in range(0,LIMIT+1):
   
    if i in grandmaster and round(grandmaster[i]/testings*100,3)>ACCEPTED_POSSIBILITIES:
        text_file.write(f"The beacons that only |{i}| pings were needed in order to find the target with average mistake of |{2*tolerance}| meters/pixels were |{grandmaster[i]}| and in a chance = |{round(grandmaster[i]/testings*100,2)}%| of total tested different beacons!\n")
   
print(f"\nExecution time:{round(time.time()-start,2)} seconds\n")
text_file.write(f"\nExecution time:{round(time.time()-start,2)} seconds\n")
text_file.write(f"TOTAL execution time on pc : {round(time.time()-begin,2)}")
text_file.write("\n#############################################################################################################\n\n")
print(f"TOTAL execution time on pc : {round(time.time()-begin,2)} seconds")


