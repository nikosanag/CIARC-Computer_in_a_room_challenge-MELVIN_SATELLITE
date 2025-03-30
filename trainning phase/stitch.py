from PIL import Image
import os

Image.MAX_IMAGE_PIXELS = 933120000

def get_coords(filename):
  parts = filename.split('_')
  x = int(parts[1])
  y = int(parts[2][:-4])
  return x, y

canvas_width, canvas_height = 21600, 10800


path = 'D:/Onedrive-ilias/OneDrive/Έγγραφα/CIARC 2024/images_new/'
images = [f for f in os.listdir(path) if os.path.isfile(path + f)]

images_info = []

for name in images:
  x, y = get_coords(name)
  img = Image.open(path + name).resize((1000, 1000))
  images_info.append({'x': x, 'y': y, 'image': img})
  xprev, yprev = x, y

# canvas = Image.open('D:/Onedrive-ilias/OneDrive/Έγγραφα/CIARC 2024/onlyold.png')
canvas = Image.new('RGB', (canvas_width, canvas_height), color=(255, 255, 255))

for info in images_info:
  x_offset = info['x'] - 500
  y_offset = info['y'] - 500
  canvas.paste(info['image'], (x_offset, y_offset))

output = 'D:/Onedrive-ilias/OneDrive/Έγγραφα/CIARC 2024/total_onlynew_corr2.png'
canvas.save(output, format = 'PNG')