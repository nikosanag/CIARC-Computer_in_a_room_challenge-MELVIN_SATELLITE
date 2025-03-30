import cv2 as cv
import numpy as np
import os

DEBUG = False

def create_dynamic_canvas(top_left, bottom_right):
    '''
    Create a canvas of the exact size needed based on corner coordinates.

    :param top_left: Tuple (x, y) of the top-left corner
    :param bottom_right: Tuple (x, y) of the bottom-right corner
    :return canvas: The initialized canvas
    :return stitched_images: Dictionary to track stitched images
    :return origin: Tuple (x, y) of the canvas origin in the global coordinate system
    '''
    # Calculate dimensions
    x_min, y_min = top_left
    x_max, y_max = bottom_right
    
    # Ensure x_min <= x_max and y_min <= y_max
    if x_min > x_max:
        x_min, x_max = x_max, x_min
    if y_min > y_max:
        y_min, y_max = y_max, y_min
    
    width = x_max - x_min + 1
    height = y_max - y_min + 1
    
    if DEBUG:
        print(f"Creating canvas with dimensions: {width}x{height}", flush=True)
    
    # Create the canvas (white background)
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255
    
    # Dictionary to track stitched images
    stitched_images = {}
    
    # Origin point in the global coordinate system
    origin = (x_min, y_min)
    
    return canvas, stitched_images, origin

def parse_image_filename(filename):
    '''
    Parse the lens type and coordinates from filename.
    Expected format: lens{precision}_{x}_{y}.jpg
    
    :param:
    Returns:
        lens_precision: The lens precision value
        x: The x coordinate
        y: The y coordinate
    '''
    try:
        # Get the base filename without extension
        base = os.path.basename(filename)
        name = os.path.splitext(base)[0]
        
        # Split by underscore
        parts = name.split('_')
        if len(parts) < 3:
            return None, None, None
        
        # Extract lens precision (lens1, lens8, lens6)
        lens_part = parts[0]
        lens_precision = lens_part.replace('lens', '')
        
        # Extract coordinates
        x = int(parts[1])
        y = int(parts[2])
        
        return lens_precision, x, y
    except Exception as e:
        print(f"Error parsing filename {filename}: {e}")
        return None, None, None


def stitch_from_filenames(image_dir, filenames, canvas, stitched_images, origin):
    '''
    Stitch images from a list of filenames onto the canvas.
        
    :param image_dir: Directory containing the images
    :param filenames: List of filenames to stitch
    :param canvas: The canvas numpy array
    :param stitched_images: Dictionary to track stitched images
    :param origin: Tuple (x, y) of the canvas origin in the global coordinate system
    '''
    lens_size = {'1': 1000, '8': 800, '6': 600}  # Wide, normal, narrow
    
    # Origin point
    origin_x, origin_y = origin
    
    # Canvas dimensions
    canvas_height, canvas_width = canvas.shape[:2]
    
    # Process each filename
    for filename in filenames:
        try:
            # Parse coordinates from filename
            lens_precision, global_x, global_y = parse_image_filename(filename)
            
            if lens_precision is None or global_x is None or global_y is None:
                if DEBUG:
                    print(f"Skipping invalid filename: {filename}")
                continue
                
            # Create a unique identifier for this position
            position_key = f"lens{lens_precision}_{global_x}_{global_y}"
            
            # Skip if we already have an image for this position
            if position_key in stitched_images:
                if DEBUG:
                    print(f"Image {position_key} already stitched, skipping")
                continue
            
            # Load the image
            img_path = os.path.join(image_dir, filename)
            if not os.path.exists(img_path):
                if DEBUG:
                    print(f"Image file not found: {img_path}")
                continue
                
            img = cv.imread(img_path)
            if img is None:
                if DEBUG:
                    print(f"Failed to load image: {img_path}")
                continue
            
            # Resize image based on lens type (if needed)
            if lens_precision in lens_size:
                current_lens_size = lens_size[lens_precision]
                img = cv.resize(img, (current_lens_size, current_lens_size))
            
            # Get image dimensions
            h, w = img.shape[:2]
            
            # Calculate canvas coordinates (top-left corner of the image)
            canvas_x = global_x - origin_x -w // 2
            canvas_y = global_y - origin_y - h // 2
            
            # Handle edge cases where the image extends beyond the canvas
            if canvas_x < 0 or canvas_y < 0 or canvas_x + w > canvas_width or canvas_y + h > canvas_height:
                # Calculate the region of the image that fits within the canvas
                start_x = max(0, -canvas_x)
                start_y = max(0, -canvas_y)
                end_x = min(w, canvas_width - canvas_x)
                end_y = min(h, canvas_height - canvas_y)
                
                # Calculate the valid region on the canvas
                valid_canvas_x = max(0, canvas_x)
                valid_canvas_y = max(0, canvas_y)
                
                # Extract the valid portion of the image
                valid_img = img[start_y:end_y, start_x:end_x]
                valid_h, valid_w = valid_img.shape[:2]
                
                # Check that dimensions are valid before attempting to place the image
                if valid_h > 0 and valid_w > 0:
                    if DEBUG:
                        print(f"Placing partial image {position_key} at canvas coordinates ({valid_canvas_x}, {valid_canvas_y}) with size {valid_w}x{valid_h}")
                    canvas[valid_canvas_y:valid_canvas_y+valid_h, valid_canvas_x:valid_canvas_x+valid_w] = valid_img
                    
                    # Store the actual position and image in the dictionary
                    stitched_images[position_key] = {
                        'x': global_x,
                        'y': global_y,
                        'canvas_x': valid_canvas_x,
                        'canvas_y': valid_canvas_y,
                        'width': valid_w,
                        'height': valid_h,
                        'filename': filename
                    }
                elif DEBUG:
                    print(f"Warning: Invalid dimensions for image region - w:{valid_w}, h:{valid_h}")
            else:
                # Normal case - place the entire image
                if DEBUG:
                    print(f"Placing full image {position_key} at canvas coordinates ({canvas_x}, {canvas_y}) with size {w}x{h}")
                canvas[canvas_y:canvas_y+h, canvas_x:canvas_x+w] = img
                
                # Store the position and image in the dictionary
                stitched_images[position_key] = {
                    'x': global_x,
                    'y': global_y,
                    'canvas_x': canvas_x,
                    'canvas_y': canvas_y,
                    'width': w,
                    'height': h,
                    'filename': filename
                }
                
        except Exception as e:
            print(f"Error processing image {filename}: {e}")


def get_zoned_bytes(canvas, format='.jpg', quality=85):
    ''' 
    Convert the canvas to bytes.

    :param canvas: the canvas with the desired dimensions
    '''
    success, buffer = cv.imencode(format, canvas, [cv.IMWRITE_JPEG_QUALITY, quality])
    if success:
        return buffer.tobytes()
    return None

def stitch_zoned(top_left, bottom_right, specific_files, final_name):
    '''
    Stitches images constituting a zoned objective.

    :param top_left: (x_min, y_min) coordinates of the top left corner
    :param bottom_right: (x_max, y_max) coordinates of the bottom right corner
    :param specific_files: the list of the desired image names to look for
    '''
    # Directory containing the images
    image_dir = 'D:/Desktop/CIARC 2024/part1/eval_map_stitching/'
    
    # Create the dynamic canvas
    canvas, stitched_images, origin = create_dynamic_canvas(top_left, bottom_right)
    
    # Stitch the images
    stitch_from_filenames(image_dir, specific_files, canvas, stitched_images, origin)
    if DEBUG:
        print(f"Successfully stitched {len(stitched_images)} images")
    
    # Save the panorama
    panorama_bytes = get_zoned_bytes(canvas)
    with open(final_name, "wb") as f:
        f.write(panorama_bytes)

    if DEBUG:
        print("Saved panorama to custom_panorama.png")

if __name__ == '__main__':
    # Provide a list of filenames to stitch
    # Format lensL_X_Y where L = {1 (wide), 8(normal), 6(narrow)}, X, Y are the x-coordinate and y-coordinate (respectively) where the picture was taken
    specific_files = []

    top_left = (19618, 6568)  # Example values (xmin, ymin)
    bottom_right = (20024, 7001)  # Example values (xmax, ymax)

    stitch_zoned(top_left, bottom_right, specific_files, 'test_unknown_stitch.png')