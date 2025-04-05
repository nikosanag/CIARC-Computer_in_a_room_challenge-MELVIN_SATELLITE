from bitarray import bitarray
import zlib
import struct
from PIL import Image

DEBUG = True
Image.MAX_IMAGE_PIXELS = 933120000



class BitMatrix:
    '''
    A space-efficient binary matrix using a bit array, optimized for fast operations.
    '''
    def __init__(self, width=21600, height=10800, initial=0):
        """
        Initializes a binary matrix with given width and height.
        
        :param width: Number of columns in the matrix.
        :param height: Number of rows in the matrix.
        :initial: The initialization value of the matrix.
        """
        self.width = width
        self.height = height
        self.data = bitarray(width * height)
        if initial == 0:
          self.data.setall(0)
          self.points_taken = 0
        else:
          self.data.setall(1)  
          self.points_taken = 21600*10800

    def _check_bounds(self, x, y):
        """
        Ensures that given coordinates (x, y) are within valid matrix bounds.
        
        :raises IndexError: If (x, y) is out of bounds.
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            raise IndexError(f"[ERROR] Coordinates ({x}, {y}) out of bounds")

    def _index(self, x, y):
        """
        Converts 2D coordinates (x, y) to a 1D index for the bit array.
        
        :return: Integer index corresponding to (x, y).
        """
        return y * self.width + x

    def set_bit(self, x, y, value):
        """
        Sets a bit at position (x, y) to 0 or 1.
        
        :param x: X-coordinate.
        :param y: Y-coordinate.
        :param value: Boolean value (0 or 1) to set.
        """
        self._check_bounds(x, y)
        self.data[self._index(x, y)] = bool(value)

    def get_bit(self, x, y):
        """
        Retrieves the bit value at position (x, y).
        
        :param x: X-coordinate.
        :param y: Y-coordinate.
        :return: Boolean value of the bit at (x, y).
        """
        self._check_bounds(x, y)
        return self.data[self._index(x, y)]

    def update_map(self, x, y, angle, value):
        """
        Updates a square region around (x, y) based on camera angle.
        
        :param x: X-coordinate of center.
        :param y: Y-coordinate of center.
        :param angle: Camera angle ('wide', 'normal', or 'narrow') defining update range.
        :param value: Boolean value (0 or 1) to set.
        """
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

        :param step: Sampling step size for visualization.
        """
        print()
        # Calculate sampled dimensions
        sample_width = min(self.width // step + 1, 80)  # Limit width for terminal
        sample_height = min(self.height // step + 1, 40)  # Limit height for readability
        print("    ", end="")
        for _ in range(sample_width):
            print("_", end="")
        print()

        for y_idx in range(sample_height):
            y = y_idx * step
            print(f"{y//1000:2d}k| ", end="")

            for x_idx in range(sample_width):
                x = x_idx * step
                if x < self.width and y < self.height:
                    value = self.get_bit(x, y)
                    print("■" if value else "·", end="")
                else:
                    print(" ", end="")
            print()

    def save_to_file(self, filename, compress=False):
        """
        Saves the matrix to a binary file for storage.
        
        :param filename: File path to save the data.
        :param compress: If True, compresses data before saving.
        """
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
        """
        Loads a BitMatrix object from a previously saved file.
        
        :param filename: File path to load the data from.
        :return: A BitMatrix instance with restored data.
        """
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





def image_to_bitmatrix(image_path, output_file, compress=False):
    
    """
    Converts an image to a BitMatrix representation and saves it to a file.

    This function loads an image, checks that it matches the required dimensions (21600x10800),
    and converts all non-black pixels into `1`s in a BitMatrix. The resulting BitMatrix is then
    saved to a file in a space-efficient binary format, with optional compression.

    :param image_path: Path to the input image file (must be 21600x10800 pixels, RGB format).
    :param output_file: Path where the BitMatrix will be saved.
    :param compress (optional): If True, the BitMatrix data is compressed before saving (default is False).
    """
    
    image = Image.open(image_path).convert("RGB")  # Ensure RGB mode
    width, height = image.size
    
    if width != 21600 or height != 10800:
        raise ValueError(f"Image size must be 21600x10800, but got {width}x{height}")
    
    bitmatrix = BitMatrix(width, height)
    pixels = image.load()
    
    for y in range(height):
        for x in range(width):
            r, g, b = pixels[x, y]
            if (r, g, b) != (0, 0, 0):  # Check if pixel is NOT completely black
                bitmatrix.set_bit(x, y, 1)
                bitmatrix.points_taken += 1
    
    bitmatrix.save_to_file(output_file, compress)
    print(f"BitMatrix saved to {output_file}")


if __name__ == "__main__":
    image_path = '' # Fill with the path to the folder that contains the stitched map
    output_file = '' # Fill with the path to the output folder
    image_to_bitmatrix(image_path, output_file)

