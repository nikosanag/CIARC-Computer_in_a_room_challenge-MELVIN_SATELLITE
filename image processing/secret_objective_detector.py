import os
import cv2
import numpy as np
from skimage.metrics import structural_similarity as ssim
import re

def extract_region_wrapped(image, center_x, center_y, size):
    """
    Extracts a square region from the image centered at (center_x, center_y).

    :param image: The input image (as a NumPy array) from which the region is extracted.
    :param center_x: The x-coordinate of the center of the region to extract.
    :param center_y: The y-coordinate of the center of the region to extract.
    :param size: The size (width and height) of the square region to extract.
    :return: The extracted image region as a NumPy array.
    """
    h, w = image.shape[:2]
    half = size // 2

    x_coords = [(center_x - half + i) % w for i in range(size)]
    y_coords = [(center_y - half + i) % h for i in range(size)]

    region = image[np.ix_(y_coords, x_coords)]
    return region


def find_sprite(stitched_map_path, input_photo_path):
    """
    Compares an input photo to the corresponding region in a stitched map image, using SSIM to detect 
    if an sprite (alteration) is present. If differences are found and SSIM is low, returns the bounding 
    box of the altered area mapped onto the stitched image.

    :param stitched_map_path: File path to the large stitched map image.
    :param input_photo_path: File path to the smaller input photo which may contain an sprite.
    :return: A tuple (min_x, min_y, max_x, max_y) representing the bounding box of detected sprite zone
             on the stitched map, or an empty list if no sprite is detected.
    """
    map_width, map_height = 21600, 10800
    match = re.search(r"lens(\d+)_(\d+)_(\d+)", input_photo_path)
    if match:
        lens_code = int(match.group(1))
        x1 = int(match.group(2))
        y1 = int(match.group(3))
    else:
        raise ValueError("Could not extract lens and coordinates from '{}'".format(input_photo_path))

    lens_sizes = {1: 1000, 8: 800, 6: 600}
    if lens_code not in lens_sizes:
        raise ValueError("Invalid lens code: {}".format(lens_code))
    size = lens_sizes[lens_code]

    stitched_map = cv2.imread(stitched_map_path)
    input_photo = cv2.imread(input_photo_path)

    if stitched_map is None:
        raise FileNotFoundError("Could not load stitched map from {}".format(stitched_map_path))
    if input_photo is None:
        raise FileNotFoundError("Could not load input photo from {}".format(input_photo_path))

    input_gray = cv2.cvtColor(input_photo, cv2.COLOR_BGR2GRAY)

    if lens_code == 6:
        dx = dy = -64 
    else:
        dx = dy = 4 

    x_shifted = x1 + dx
    y_shifted = y1 + dy
    
    crop = extract_region_wrapped(stitched_map, x_shifted, y_shifted, size)
    crop_resized = cv2.resize(crop, (600, 600), interpolation=cv2.INTER_AREA)

    crop_gray = cv2.cvtColor(crop_resized, cv2.COLOR_BGR2GRAY)
    similarity_score, diff = ssim(input_gray, crop_gray, full=True)

    diff = (diff * 255).astype("uint8")
    
    print("SSIM Similarity Score: {:.4f}".format(similarity_score))

    if similarity_score > 0.84:
        return []

    _, thresh = cv2.threshold(diff, 30, 255, cv2.THRESH_BINARY)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    max_x = 0
    max_y = 0
    min_x = 30000
    min_y = 20000
    for contour in contours:
        x, y, _, _ = cv2.boundingRect(contour)
        sprite_x = (x1 - size // 2 + x + dx) % map_width
        sprite_y = (y1 - size // 2 + y + dy) % map_height
        if max_x < sprite_x:
          max_x = sprite_x  
        if min_x > sprite_x:
          min_x = sprite_x  
        if max_y < sprite_y:
          max_y = sprite_y  
        if min_y > sprite_y:
          min_y = sprite_y  
    possible_zone = (min_x, min_y, max_x, max_y)
    return possible_zone


if __name__ == '__main__':
    stitched_map_path = "" # Fill with the stitched map path here
    folder_path = ""  # Fill with your images folder path here

    max_x = 0
    max_y = 0
    min_x = 30000
    min_y = 20000
    for filename in os.listdir(folder_path):
        if filename.endswith(".jpg") or filename.endswith(".png"):
            full_path = os.path.join(folder_path, filename)
            try:
                coords = find_sprite(stitched_map_path, full_path)
                if coords:
                    x1, y1, x2, y2 = coords
                    max_x = max(max_x, x2)
                    max_y = max(max_y, y2)
                    min_x = min(min_x, x1)
                    min_y = min(min_y, y1)
                    print("[{}] Possible sprite at: {}".format(filename, coords))
                else:                print("[{}] No sprite visible".format(filename))

            except Exception as e:
                print("[{}] ERROR: {}".format(filename, e))


    print(f"Secret zone result: {(min_x, min_y, max_x, max_y)}")
