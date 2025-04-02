# SPACE TRANSFORMERS - OPERATOR CONSOLE

1. Make sure you have installed all the requirements listed below:
  > tkinter
  > requests
  > paramiko
  > sshtunnel

2. Ensure that the variables SSH_USERNAME and SSH_PASSWORD defined in lines 16-17 of the program contain your credentials.

3. Run the python program. The operator console will appear.

4. Click on "Connect to Server". Wait until the Server Status changes to "Connected".

5. "Click on Start Monitoring". You will see the red dot (MELVIN) moving, its trajectory being drawn and its data in the upper right corner receiving updates.

6. If you wish to receive data more/less frequently, you can adjust the variable REFRESH_RATE defined in line 13 accordingly. After adjusting, go to step 2.

7. After starting monitoring, you can left click the black plane to add a point of interest. Right clicking on the plane removes it.

8. You can always clear the trajectory that is being drawed.

9. You can Select MELVIN's mode through the available option at the right part of the window. You can set it to communcation, acquisition or charge mode.

10. To help the visualisation of MELVIN's position. the grid on the black plane consists of squares with dimensions 1000x1000 pixels each.