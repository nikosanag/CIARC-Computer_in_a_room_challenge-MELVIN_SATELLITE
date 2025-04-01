from PIL import Image
import os
import cv2
import numpy as np

Image.MAX_IMAGE_PIXELS = 933120000


def get_coords(filename):
    parts = filename.split('_')
    x = int(parts[1])
    y = int(parts[2][:-4])
    return x, y


# Canvas dimensions
canvas_width, canvas_height = 21600, 10800

# Path to images
path = 'D:/Onedrive-ilias/OneDrive/Έγγραφα/CIARC 2024/images_new/'
images = [f for f in os.listdir(path) if os.path.isfile(path + f)]

images_info = []

for name in images:
    x, y = get_coords(name)

    # Open the image using OpenCV (to process noise)
    img_cv = cv2.imread(path + name)

    # Denoise the image using OpenCV's fastNlMeansDenoisingColored
    denoised = cv2.fastNlMeansDenoisingColored(img_cv, None, h=10, hForColorComponents=10, templateWindowSize=7, searchWindowSize=21)

    # Convert back to PIL format for resizing and further processing
    img = Image.fromarray(cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB))
    img = img.resize((1000, 1000))

    # Append processed image and coordinates
    images_info.append({'x': x, 'y': y, 'image': img})
    xprev, yprev = x, y

# Create a blank canvas
canvas = Image.new('RGB', (canvas_width, canvas_height), color=(255, 255, 255))

# Paste images onto the canvas
for info in images_info:
    x_offset = info['x'] - 500
    y_offset = info['y'] - 500
    canvas.paste(info['image'], (x_offset, y_offset))

# Save the final stitched image
output = 'D:/Onedrive-ilias/OneDrive/Έγγραφα/CIARC 2024/total_onlynew_corr2.png'
canvas.save(output, format='PNG')
