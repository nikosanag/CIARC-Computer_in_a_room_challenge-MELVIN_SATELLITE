# ESA Computer In A Room Challenge (CIARC) 3 - SPACE TRANSFORMERS TEAM

## Description
In this challenge of esa we were called to create an autonomous system that manages tasks and controls a Satellite -MELVIN- in space. More precisely, the tasks we were given were:
1. **Daily Map**: Capture and update the global map of MELVIN's world, 
2. **Zoned Objectives**: Capture specific zone images with predifined lens,
3. **Secret Objectives**: Recognise and stitch together images of uknown locations containing hidden sprites for identification,
4. **Emergency Beacon (EB)**: Detect distress signals worldwide and estimate their location.


## Installation
### Prerequisites
- Python = 3.11.2

### Setup
1. **Clone the repository:**
    ```sh 
    git clone https://github.com/nikosanag/CIARC-Computer_in_a_room_challenge-MELVIN_SATELLITE.git

2. **Create a virtual environment (optional but recommended):**

   *On Unix-based systems (Linux/macOS):*
   ```bash
    python3 -m venv venv
    source venv/bin/activate
   ```
   *On Windows:*
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```   

4. **Install dependancies:**
    ```sh
    pip install -r requirements.txt
    ```
    These are the dependencies needed to run everything inside the "src" folder. Other programs that run outside of MELVIN might need other dependencies. Please install all the missing imports in order to run these programs.


## Usage
**Run the main program of Part 4 (located inside src folder) with:**

    python3 part4.py


## Configuration
In **src/zonedStitching.py:** need to adjust the folder where the images for the objectives will be saved, currently inside "./images". 

In **src/part4.py:** Folders to be created or automatically generated by the program when needed: 
- "ping_log.txt": Contains the ping messages from EBs,
- "exceptions.log": Contains the exceptions caught,
- "debug_stitched_map.png": The stitched map when saved from the RAM,
- "FAILURES.txt": Any objective that was either not submitted successfully or not done,
- "SUCCESSES.txt": The objectives that were handled successfully.

        
## User Console
See the README.md into the "operator console" folder


## Usefull guide
The **src** folder typically contains our source code and all the necessary peripherals that we were running during the evaluation phase.

The **tools** folder typically contains essential scripts and functions that manage Melvin's safety requirements, such as *protect_battery* and other critical utilities. 

The **image processing** folder typically contains essential fucntions for stitching, image processing and map traversal.

The **automated responses** folder typically contains our API calls concerning submissions.

The **beacon probability analysis** folder contains a theoritical based analysis concerning beacon's position estimation probability.

The **training phase** folder contains code used during the training process.


## Members of the Team 
1. NIKOLAOS ANAGNOSTOU [nikos.r.anagnostou@gmail.com]
2. ILIAS MAKRAS [ilias.makras@gmail.com]
3. NIKOLAOS LAPPAS [nikolas.lappas.2003@gmail.com]
4. IOANNIS MARIOS MAVROMATIS [giamavro@gmail.com]
5. PETROS VITALIS [minuspetran@gmail.com]

>Please contact us for any questions or issues




