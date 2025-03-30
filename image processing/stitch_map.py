import cv2
import numpy as np
import os

LIMITATIONS = []


def stitch_image(name):
  global path
  global canvas
  lens = 0
  def get_coords(filename):
    parts = filename.split('_')
    nonlocal lens
    idx = int(parts[0][-1])
    if idx == 1: lens = 1000
    elif idx == 6: lens = 600
    elif idx == 8: lens = 800
    else:
      return -1, -1
    x = int(parts[1])
    y = int(parts[2][:-4])
    return x, y

  canvas_x, canvas_y = get_coords(name)
  # img = Image.open(BytesIO(image_data)).resize((lens, lens))

  # Lap ------------------------
  # img = cv2.imdecode(np.frombuffer(image_data, np.uint8), cv2.IMREAD_COLOR)
  if LIMITATIONS == [] or (LIMITATIONS[0] <= canvas_x <= LIMITATIONS[2] and LIMITATIONS[1] <= canvas_y <= LIMITATIONS[3]):
    img = cv2.imread(path + name)
    img = cv2.resize(img, (lens, lens))

    # Get image dimensions
    h, w = img.shape[:2]

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


canvas = np.zeros((10800, 21600, 3), dtype=np.uint8)

path = 'D:/Desktop/CIARC 2024/part1/eval_map_stitching/'

output = 'D:/Desktop/CIARC 2024/part1/stitch_resutls/SAFE_MAP_5.png'

images = [f for f in os.listdir(path) if os.path.isfile(path + f)]



# print(images)
for image in images:
  stitch_image(image)


def get_canvas_bytes(canvas, format='.png', quality=90):
    """Convert the entire stitched canvas to bytes."""
    success, buffer = cv2.imencode(format, canvas, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if success:
        return buffer.tobytes()
    return None

stitched_map_bytes = get_canvas_bytes(canvas)

with open(output, "wb") as f:
  f.write(stitched_map_bytes)
  
