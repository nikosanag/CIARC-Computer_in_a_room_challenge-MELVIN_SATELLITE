import tkinter as tk
from tkinter import messagebox
import time
import threading
import requests
import math
import paramiko
import sshtunnel

# Constants
CANVAS_WIDTH = 21600
CANVAS_HEIGHT = 10800
REFRESH_RATE = 0.5  # seconds
SSH_HOST = "10.100.50.1"
SSH_PORT = 22
SSH_USERNAME = "root"
SSH_PASSWORD = "password"
LOCAL_PORT = 8080  # Local port for SSH tunnel
MELVIN_BASE_URL = "http://10.100.10.14:33000"
SCALE_FACTOR = 0.05
MELVIN_SIZE = 7

class SatelliteMonitor:
  def __init__(self, root):
    self.root = root
    self.root.title("MELVIN Console")
    self.root.geometry("1500x720")  # Adjust as needed for your screen
    
    # SSH connection objects
    self.ssh_client = None
    self.tunnel = None
    
    # Track if monitoring is active
    self.is_monitoring = False
    self.monitoring_thread = None
    
    # Last known satellite position and data
    self.satellite_data = {
      "angle": "narrow", 
      "width_x": 0, 
      "height_y": 0, 
      "vx": 0, 
      "vy": 0, 
      "battery": 0, 
      "fuel": 0
    }
    
  
    self.setup_ui()
    
  def setup_ui(self):
    # Create main frames
    left_frame = tk.Frame(self.root)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    right_frame = tk.Frame(self.root)
    right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
    
    # Satellite position visualization (canvas)
    self.setup_canvas(left_frame)
    
    # Telemetry data display
    self.setup_telemetry(right_frame)
    
    # Control buttons
    self.setup_controls(right_frame)
  
  def setup_canvas(self, parent):
    canvas_frame = tk.LabelFrame(parent, text="MELVIN Real-Time Position")
    canvas_frame.pack(fill=tk.BOTH, expand=True)
    
    # Create canvas with scrollbars
    canvas_container = tk.Frame(canvas_frame)
    canvas_container.pack(fill=tk.BOTH, expand=True)
    
    # Calculate the scaled canvas dimensions
    scaled_width = int(CANVAS_WIDTH * SCALE_FACTOR)
    scaled_height = int(CANVAS_HEIGHT * SCALE_FACTOR)
    
    # Create canvas
    self.canvas = tk.Canvas(
      canvas_container, 
      width=scaled_width,
      height=scaled_height,
      bg="black"
    )
    self.canvas.pack(fill=tk.BOTH, expand=True)
    
    # Draw coordinate grid
    self.draw_grid()
    
    # Initial satellite representation (scaled position)
    self.satellite = self.canvas.create_oval(
      (CANVAS_WIDTH/2) * SCALE_FACTOR - MELVIN_SIZE, 
      (CANVAS_HEIGHT/2) * SCALE_FACTOR - MELVIN_SIZE,
      (CANVAS_WIDTH/2) * SCALE_FACTOR + MELVIN_SIZE, 
      (CANVAS_HEIGHT/2) * SCALE_FACTOR + MELVIN_SIZE,
      fill="red",
      tags="satellite"
    )
    
    # Add alternative view option
    view_frame = tk.Frame(canvas_frame)
    view_frame.pack(fill=tk.X, padx=5, pady=5)
    
  def draw_grid(self):
    # Draw major grid lines
    grid_spacing = 1000  # Actual grid spacing
    
    # Vertical lines
    for x in range(0, CANVAS_WIDTH + 1, grid_spacing):
      scaled_x = x * SCALE_FACTOR
      self.canvas.create_line(
        scaled_x, 0, 
        scaled_x, CANVAS_HEIGHT * SCALE_FACTOR, 
        fill="#333333", 
        tags="grid"
      )
    
    # Horizontal lines
    for y in range(0, CANVAS_HEIGHT + 1, grid_spacing):
      scaled_y = y * SCALE_FACTOR
      self.canvas.create_line(
        0, scaled_y, 
        CANVAS_WIDTH * SCALE_FACTOR, scaled_y, 
        fill="#333333", 
        tags="grid"
      )
      
    # Add coordinate labels at intervals (less frequent due to scaling)
    label_spacing = 5000  # Larger spacing for labels to avoid crowding
    
    for x in range(label_spacing, CANVAS_WIDTH + 1, label_spacing):
      scaled_x = x * SCALE_FACTOR
      self.canvas.create_text(
        scaled_x, 10, 
        text=str(x), 
        fill="white", 
        tags="grid_label",
        font=("Arial", 8)
      )
      
    for y in range(label_spacing, CANVAS_HEIGHT + 1, label_spacing):
      scaled_y = y * SCALE_FACTOR
      self.canvas.create_text(
        20, scaled_y, 
        text=str(y), 
        fill="white", 
        tags="grid_label",
        font=("Arial", 8)
      )

    self.canvas.create_rectangle(
      0, 0,
      CANVAS_WIDTH * SCALE_FACTOR, CANVAS_HEIGHT * SCALE_FACTOR,
      outline="white",  # Change color as needed
      width=2,          # Adjust the width as desired
      tags="grid_box"
    )


  
  def setup_telemetry(self, parent):
    telemetry_frame = tk.LabelFrame(parent, text="MELVIN Data")
    telemetry_frame.pack(fill=tk.BOTH, padx=5, pady=5)
    
    # Position info
    pos_frame = tk.Frame(telemetry_frame)
    pos_frame.pack(fill=tk.X, padx=5, pady=5)
    
    tk.Label(pos_frame, text="Position (X, Y):").grid(row=0, column=0, sticky=tk.W)
    self.pos_var = tk.StringVar(value="0, 0")
    tk.Label(pos_frame, textvariable=self.pos_var).grid(row=0, column=1, sticky=tk.W)
    
    # Velocity info
    vel_frame = tk.Frame(telemetry_frame)
    vel_frame.pack(fill=tk.X, padx=5, pady=5)
    
    tk.Label(vel_frame, text="Velocity (X, Y):").grid(row=0, column=0, sticky=tk.W)
    self.vel_var = tk.StringVar(value="0, 0")
    tk.Label(vel_frame, textvariable=self.vel_var).grid(row=0, column=1, sticky=tk.W)
    
    # Angle info
    angle_frame = tk.Frame(telemetry_frame)
    angle_frame.pack(fill=tk.X, padx=5, pady=5)
    
    tk.Label(angle_frame, text="Angle:").grid(row=0, column=0, sticky=tk.W)
    self.angle_var = tk.StringVar(value="narrow")
    tk.Label(angle_frame, textvariable=self.angle_var).grid(row=0, column=1, sticky=tk.W)
    
    # Battery info
    battery_frame = tk.Frame(telemetry_frame)
    battery_frame.pack(fill=tk.X, padx=5, pady=5)
    
    tk.Label(battery_frame, text="Battery:").grid(row=0, column=0, sticky=tk.W)
    self.battery_var = tk.StringVar(value="0%")
    tk.Label(battery_frame, textvariable=self.battery_var).grid(row=0, column=1, sticky=tk.W)
    
    # Fuel info
    fuel_frame = tk.Frame(telemetry_frame)
    fuel_frame.pack(fill=tk.X, padx=5, pady=5)
    
    tk.Label(fuel_frame, text="Fuel:").grid(row=0, column=0, sticky=tk.W)
    self.fuel_var = tk.StringVar(value="0%")
    tk.Label(fuel_frame, textvariable=self.fuel_var).grid(row=0, column=1, sticky=tk.W)
    
    # Last update time
    update_frame = tk.Frame(telemetry_frame)
    update_frame.pack(fill=tk.X, padx=5, pady=5)
    
    tk.Label(update_frame, text="Last Update:").grid(row=0, column=0, sticky=tk.W)
    self.update_var = tk.StringVar(value="Never")
    tk.Label(update_frame, textvariable=self.update_var).grid(row=0, column=1, sticky=tk.W)
  
  def setup_controls(self, parent): # Do we want the command in comment????
    control_frame = tk.LabelFrame(parent, text="Real-Time Monitoring")
    control_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # SSH connection details frame
    ssh_frame = tk.Frame(control_frame)
    ssh_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # Host input
    # tk.Label(ssh_frame, text="Host:").grid(row=0, column=0, sticky=tk.W, pady=2)
    self.host_var = tk.StringVar(value=SSH_HOST)
    # tk.Entry(ssh_frame, textvariable=self.host_var).grid(row=0, column=1, sticky=tk.EW, pady=2)
    
    # Port input
    # tk.Label(ssh_frame, text="Port:").grid(row=1, column=0, sticky=tk.W, pady=2)
    self.port_var = tk.StringVar(value=str(SSH_PORT))
    # tk.Entry(ssh_frame, textvariable=self.port_var).grid(row=1, column=1, sticky=tk.EW, pady=2)
    
    # Username input
    # tk.Label(ssh_frame, text="Username:").grid(row=2, column=0, sticky=tk.W, pady=2)
    self.username_var = tk.StringVar(value=SSH_USERNAME)
    # tk.Entry(ssh_frame, textvariable=self.username_var).grid(row=2, column=1, sticky=tk.EW, pady=2)
    
    # Password input
    # tk.Label(ssh_frame, text="Password:").grid(row=3, column=0, sticky=tk.W, pady=2)
    self.password_var = tk.StringVar(value=SSH_PASSWORD)
    # tk.Entry(ssh_frame, textvariable=self.password_var, show="*").grid(row=3, column=1, sticky=tk.EW, pady=2)
    
    # Configure grid column to expand
    ssh_frame.columnconfigure(1, weight=1)
    
    # Connect button
    self.connect_btn = tk.Button(control_frame, text="Connect to Server", command=self.connect_to_server)
    self.connect_btn.pack(fill=tk.X, padx=5, pady=5)
    
    # Start/Stop monitoring button
    self.monitor_btn = tk.Button(control_frame, text="Start Monitoring", command=self.toggle_monitoring, state=tk.DISABLED)
    self.monitor_btn.pack(fill=tk.X, padx=5, pady=5)
    
    # Clear trajectory button
    self.clear_btn = tk.Button(control_frame, text="Clear Trajectory", command=self.clear_trajectory)
    self.clear_btn.pack(fill=tk.X, padx=5, pady=5)
    
    # Server status
    status_frame = tk.Frame(control_frame)
    status_frame.pack(fill=tk.X, padx=5, pady=5)
    
    tk.Label(status_frame, text="Server Status:").pack(side=tk.LEFT)
    self.status_var = tk.StringVar(value="Disconnected")
    self.status_label = tk.Label(status_frame, textvariable=self.status_var, fg="red")
    self.status_label.pack(side=tk.LEFT)
  
  def clear_trajectory(self):
    # Remove all trajectory lines
    self.canvas.delete("trajectory")
    self.canvas.delete("velocity_vector")
  
  def connect_to_server(self):
    # Get connection details from UI
    host = self.host_var.get()
    try:
      port = int(self.port_var.get())
    except ValueError:
      messagebox.showerror("Invalid Port", "Port must be a number")
      return
      
    username = self.username_var.get()
    password = self.password_var.get()
    
    # Update status
    self.status_var.set("Connecting...")
    self.status_label.config(fg="orange")
    self.root.update()
    
    # Disable connect button during connection attempt
    self.connect_btn.config(state=tk.DISABLED)
    
    # Start connection in a separate thread to keep UI responsive
    threading.Thread(target=self._establish_connection, 
            args=(host, port, username, password), 
            daemon=True).start()
  
  def _establish_connection(self, host, port, username, password):
    try:
      # Set up SSH tunnel
      self.tunnel = sshtunnel.SSHTunnelForwarder(
        (host, port),
        ssh_username=username,
        ssh_password=password,
        remote_bind_address=('127.0.0.1', 80),  # Assuming the API runs on port 80
        local_bind_address=('127.0.0.1', LOCAL_PORT)
      )
      
      # Start the tunnel
      self.tunnel.start()
      
      # Set the MELVIN base URL to use the local tunnel port
      self.melvin_base_url = MELVIN_BASE_URL

      
      # Also establish direct SSH connection for any command execution needs
      self.ssh_client = paramiko.SSHClient()
      self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      self.ssh_client.connect(host, port=port, username=username, password=password)

      # Update UI on success
      self.root.after(0, self._on_connection_success)
      
    except Exception as e:
      # Update UI on failure
      self.root.after(0, lambda: self._on_connection_failure(str(e)))
  
  def _on_connection_success(self):
    self.status_var.set("Connected")
    self.status_label.config(fg="green")
    self.connect_btn.config(state=tk.DISABLED)
    self.monitor_btn.config(state=tk.NORMAL)
  
  def _on_connection_failure(self, error_msg):
    self.status_var.set("Connection Failed")
    self.status_label.config(fg="red")
    self.connect_btn.config(state=tk.NORMAL)
    messagebox.showerror("Connection Error", f"Failed to connect to the server: {error_msg}")
    
    # Clean up any partial connections
    self._cleanup_connection()
  
  def _cleanup_connection(self):
    # Close SSH client if it exists
    if self.ssh_client:
      try:
        self.ssh_client.close()
      except:
        pass
      self.ssh_client = None
      
    # Close SSH tunnel if it exists
    if self.tunnel and self.tunnel.is_active:
      try:
        self.tunnel.stop()
      except:
        pass
      self.tunnel = None
  
  def toggle_monitoring(self):
    if not self.is_monitoring:
      self.start_monitoring()
    else:
      self.stop_monitoring()
  
  def start_monitoring(self):
    self.is_monitoring = True
    self.monitor_btn.config(text="Stop Monitoring")
    
    # Start monitoring thread
    self.monitoring_thread = threading.Thread(target=self.monitoring_loop)
    self.monitoring_thread.daemon = True
    self.monitoring_thread.start()
  
  def stop_monitoring(self):
    self.is_monitoring = False
    self.monitor_btn.config(text="Start Monitoring")
  
  def monitoring_loop(self):
    while self.is_monitoring:
      try:
        # Get observation data
        observation = self.get_observation()
        
        # Update UI with new data
        self.update_satellite_data(observation)
        
        # Sleep for refresh rate
        time.sleep(REFRESH_RATE)
      except Exception as e:
        print(f"Error in monitoring loop: {str(e)}")
        self.root.after(0, lambda: self.status_var.set(f"Error: {str(e)}"))
        self.root.after(0, lambda: self.status_label.config(fg="red"))
        self.is_monitoring = False
        self.root.after(0, lambda: self.monitor_btn.config(text="Start Monitoring"))
        break
  
  def get_observation(self):
    """Retrieve MELVIN's observation data."""
    try:
      # Use the tunnel URL for requests
      response = requests.get(f"{self.melvin_base_url}/observation")
      response.raise_for_status()
      return response.json()
    except Exception as e:
      print(f"[ERROR] Failed to fetch observation data: {str(e)}")
      time.sleep(2)  # Wait before retrying
      return self.get_observation()
  
  def update_satellite_data(self, data):
    self.satellite_data = data
    
    # Update UI on main thread
    self.root.after(0, self.update_ui)
  
  def update_ui(self):
    # Update position label
    self.pos_var.set(f"{self.satellite_data['width_x']}, {self.satellite_data['height_y']}")
    
    # Update velocity label
    self.vel_var.set(f"{self.satellite_data['vx']}, {self.satellite_data['vy']}")
    
    # Update angle label
    self.angle_var.set(f"{self.satellite_data['angle']}")
    
    # Update battery label
    self.battery_var.set(f"{self.satellite_data['battery']}%")
    
    # Update fuel label
    self.fuel_var.set(f"{self.satellite_data['fuel']}%")
    
    # Update last update time
    current_time = time.strftime("%H:%M:%S")
    self.update_var.set(current_time)
    
    # Update satellite position on canvas
    self.update_satellite_position()
  
  def update_satellite_position(self):
    # Get satellite position from data
    x = self.satellite_data['width_x']
    y = self.satellite_data['height_y']
    
    # Scale the position to match canvas scale
    scaled_x = x * SCALE_FACTOR
    scaled_y = y * SCALE_FACTOR
    self.canvas.coords(
      self.satellite,
      scaled_x - MELVIN_SIZE,
      scaled_y - MELVIN_SIZE,
      scaled_x + MELVIN_SIZE,
      scaled_y + MELVIN_SIZE
    )
    
    # Draw trajectory line if we have previous position and movement isn't too large
    if hasattr(self, 'last_x') and hasattr(self, 'last_y'):

      if x >= self.last_x and y >= self.last_y:
        self.canvas.create_line(
          self.last_x * SCALE_FACTOR, 
          self.last_y * SCALE_FACTOR, 
          scaled_x, 
          scaled_y, 
          fill="yellow", 
          tags="trajectory",
          width=1
        )
        
        # Draw velocity vector
        vx = self.satellite_data['vx']
        vy = self.satellite_data['vy']
        vector_length = math.sqrt(vx**2 + vy**2)
        if vector_length > 0:
          # Scale vector for visibility
          scale = min(50, vector_length) / vector_length * SCALE_FACTOR
          self.canvas.create_line(
            scaled_x, 
            scaled_y, 
            scaled_x + vx * scale, 
            scaled_y + vy * scale,
            fill="green",
            # arrow=tk.LAST,
            width=1,
            tags="velocity_vector"
          )
    
   
    # Store current position for trajectory
    self.last_x = x
    self.last_y = y
  
  def on_closing(self):
    # Clean up resources
    self.is_monitoring = False
    if self.monitoring_thread and self.monitoring_thread.is_alive():
      self.monitoring_thread.join(1.0)  # Wait for monitoring thread to terminate
      
    self._cleanup_connection()
    self.root.destroy()

# Create main application window
def main():
  root = tk.Tk()
  app = SatelliteMonitor(root)
  root.protocol("WM_DELETE_WINDOW", app.on_closing)  # Handle window closing
  root.mainloop()

if __name__ == "__main__":
  main()