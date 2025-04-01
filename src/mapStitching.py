import cv2 as cv
import numpy as np
import requests
import time
import os
from utility import get_observation, set_mode, wait, simulation, protect_battery, safe, take_photo

MELVIN_BASE_URL = "http://10.100.10.14:33000"

DEBUG = False

# Create a blank canvas with the dimensions you need
def create_canvas():
    # Create a blank 21600x10800 canvas (initialized as black)
    canvas = np.zeros((10800, 21600, 3), dtype=np.uint8)
    
    return canvas


def capture_and_stitch(canvas):
    """Capture an image and stitch it to the canvas in memory."""

    if DEBUG:
        simulation(False, 1)
    
    time.sleep(0.5)
    save = get_observation()

    response = requests.get(f"{MELVIN_BASE_URL}/image")
    response.raise_for_status()
    
    lens_to_precision = {'wide': '1', 'normal': '8', 'narrow': '6'}
    lens_size = {'wide': 1000, 'normal': 800, 'narrow': 600}
    
    if DEBUG:
        simulation(False, 20)
    
    # Get position coordinates
    width_x = save["width_x"]
    height_y = save["height_y"]
    current_lens = save['angle']
    
    # Decode image directly from bytes to numpy array
    image_data = response.content
    img = cv.imdecode(np.frombuffer(image_data, np.uint8), cv.IMREAD_COLOR)
    
    current_lens_size = lens_size[current_lens]
    img = cv.resize(img, (current_lens_size, current_lens_size))

    # Get image dimensions
    h, w = img.shape[:2]
    
    # Calculate where to place this image on the canvas
    # You might need to adjust these calculations based on your coordinate system
    canvas_x = width_x
    canvas_y = height_y 
    
    # Make sure the position is valid on our canvas
    if canvas_x < 0 or canvas_y < 0 or canvas_x + w > 21600 or canvas_y + h > 10800:
        # Handle edge cases by clipping to canvas boundaries
        # Calculate valid portion of the image and valid position on canvas
        start_x = max(0, -canvas_x)
        start_y = max(0, -canvas_y)
        end_x = min(w, 21600 - canvas_x)
        end_y = min(h, 10800 - canvas_y)
        
        # Adjust canvas position to be within bounds
        valid_canvas_x = max(0, canvas_x)
        valid_canvas_y = max(0, canvas_y)
        
        # Extract valid portion of image
        valid_img = img[start_y:end_y, start_x:end_x]
        
        # Calculate valid dimensions
        valid_h, valid_w = valid_img.shape[:2]
        
        # Place the valid portion onto the canvas
        canvas[valid_canvas_y:valid_canvas_y+valid_h, valid_canvas_x:valid_canvas_x+valid_w] = valid_img
        
    else:
        # Normal case - place the entire image
        canvas[canvas_y:canvas_y+h, canvas_x:canvas_x+w] = img
        
    
    return img


''' 
@params
    canvas: the canvas 21600x10800
'''
def get_canvas_bytes(canvas, format='.png', quality=90):
    """Convert the entire stitched canvas to bytes."""
    success, buffer = cv.imencode(format, canvas, [cv.IMWRITE_JPEG_QUALITY, quality])
    if success:
        return buffer.tobytes()
    return None




# Usage example:
def main():
    # Create our initial canvas
    canvas = create_canvas()
    





    # simulation(True, 1)
    if DEBUG:
        simulation(False, 20)
    check = get_observation()
    set_mode("acquisition",check['vx'],check['vy'],"wide")
    wait("acquisition")

    # book_slot(5)
    # curr_time = ''
    # while curr_time != "2025-03-06T01:14:39":
    #     curr_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    # print("Exited while, setting simulation...")

    total = 0
    
    while total < 10:
        check = get_observation()
        safe(check["state"])
        time.sleep(1)
        protect_battery(6)
        time.sleep(0.5)
        capture_and_stitch(canvas)
        time.sleep(1)
        total += 1
    



    
    # When you're ready to get the bytes of the entire panorama
    panorama_bytes = get_canvas_bytes(canvas)
    
    # You can now use panorama_bytes without saving to disk
    # For example, send it somewhere:
    # requests.post('http://example.com/upload', data=panorama_bytes)
    
    # Or if you need to save it for debugging:
    with open("debug_panorama.png", "wb") as f:
        f.write(panorama_bytes)
    
    # return panorama_bytes
    # print(panorama_bytes)

if __name__ == '__main__':
    main()