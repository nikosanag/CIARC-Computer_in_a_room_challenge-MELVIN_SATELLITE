import tkinter as tk
from tkinter import messagebox, ttk
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
LOCAL_PORT = 8080
MELVIN_BASE_URL = "http://10.100.10.14:33000"
SCALE_FACTOR = 0.05
MELVIN_SIZE = 7

class SatelliteMonitor:
  def __init__(self, root):
    self.root = root
    self.root.title("MELVIN Console")
    self.root.geometry("1500x720")
    
    self.ssh_client = None
    self.tunnel = None
    
    self.is_monitoring = False
    self.monitoring_thread = None
    
    self.satellite_data = {
      "angle": "narrow", 
      "width_x": 0, 
      "height_y": 0, 
      "vx": 0, 
      "vy": 0, 
      "battery": 0, 
      "fuel": 0
    }
    
  
    # Get current satellite mode
    
    try:
      curr = self.get_observation()
    except Exception as e:
      print("Could not get observation for starting mode")
      curr = {'state': 'safe'}
    self.current_mode = curr['state']

    self.setup_ui()
    
  def setup_ui(self):
    # Create main frames
    left_frame = tk.Frame(self.root)
    left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)
    
    right_frame = tk.Frame(self.root)
    right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)
    
    # Satellite position
    self.setup_canvas(left_frame)
    
    # Telemetry data and controls
    self.setup_control_tabs(right_frame)
  
  def setup_control_tabs(self, parent):
    # Main sections (no tabs)
    self.setup_telemetry(parent)
    self.setup_controls(parent)

    tab_control = ttk.Notebook(parent)
    tab_control.pack(fill=tk.BOTH, expand=False, padx=5, pady=5)
    mode_tab = ttk.Frame(tab_control)
    tab_control.add(mode_tab, text="Select Mode")  
    
    self.setup_mode_selection(mode_tab)
  
  def setup_canvas(self, parent):
    canvas_frame = tk.LabelFrame(parent, text="MELVIN Real-Time Position")
    canvas_frame.pack(fill=tk.BOTH, expand=True)
    
    # Create canvas with scrollbars
    canvas_container = tk.Frame(canvas_frame)
    canvas_container.pack(fill=tk.BOTH, expand=True)
    
    # Scaled canvas dimensions
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
    
    # Coordinate grid
    self.draw_grid()
    
    self.satellite = self.canvas.create_oval(
      (CANVAS_WIDTH/2) * SCALE_FACTOR - MELVIN_SIZE, 
      (CANVAS_HEIGHT/2) * SCALE_FACTOR - MELVIN_SIZE,
      (CANVAS_WIDTH/2) * SCALE_FACTOR + MELVIN_SIZE, 
      (CANVAS_HEIGHT/2) * SCALE_FACTOR + MELVIN_SIZE,
      fill="red",
      tags="satellite"
    )
    
    # Target point marker
    self.target_point = self.canvas.create_oval(
      0, 0, 0, 0,
      fill="green",
      outline="white",
      width=2,
      state="hidden",
      tags="target"
    )
    
    # Click handler for setting targets
    self.canvas.bind("<Button-1>", self.on_canvas_click)
    self.canvas.bind("<Button-3>", self.hide_target_point)
    
  def on_canvas_click(self, event):
    if self.is_monitoring:
      # Convert scaled coordinates back to real coordinates
      real_x = event.x / SCALE_FACTOR
      real_y = event.y / SCALE_FACTOR
      
      # Show the target on the canvas
      if 0 <= real_x <= 21600 and 0 <= real_y <= 10800:
        self.show_target_point(real_x, real_y)
  
  def hide_target_point(self, event=None):
    self.canvas.itemconfig(self.target_point, state="hidden")

  def show_target_point(self, x, y):
    # Scale the coordinates
    scaled_x = x * SCALE_FACTOR
    scaled_y = y * SCALE_FACTOR
    
    # Update and show the target point
    self.canvas.coords(
      self.target_point,
      scaled_x - 5, scaled_y - 5,
      scaled_x + 5, scaled_y + 5
    )
    self.canvas.itemconfig(self.target_point, state="normal")
    
    self.canvas.delete("path_line")

  
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
      
    # Coordinate labels at intervals
    label_spacing = 5000
    
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
      outline="white",
      width=2,
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
    
    # Mode info
    mode_frame = tk.Frame(telemetry_frame)
    mode_frame.pack(fill=tk.X, padx=5, pady=5)
    
    tk.Label(mode_frame, text="Current Mode:").grid(row=0, column=0, sticky=tk.W)
    self.mode_var = tk.StringVar(value=self.current_mode)
    tk.Label(mode_frame, textvariable=self.mode_var).grid(row=0, column=1, sticky=tk.W)
    
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
  
  def setup_controls(self, parent):
    control_frame = tk.LabelFrame(parent, text="Real-Time Monitoring")
    control_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # SSH connection details frame
    ssh_frame = tk.Frame(control_frame)
    ssh_frame.pack(fill=tk.X, padx=5, pady=5)
    
    # Host input
    self.host_var = tk.StringVar(value=SSH_HOST)
    
    # Port input
    self.port_var = tk.StringVar(value=str(SSH_PORT))
    
    # Username input
    self.username_var = tk.StringVar(value=SSH_USERNAME)
    
    # Password input
    self.password_var = tk.StringVar(value=SSH_PASSWORD)
    
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
  
  
  def setup_mode_selection(self, parent):
    mode_frame = tk.Frame(parent)
    mode_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
    self.mode_selection_var = tk.StringVar(value=self.current_mode)
    
    modes = [
      ("Acquisition", "acquisition"),
      ("Charge", "charge"),
      ("Communication", "communication")
    ]
    
    # Create radio buttons for each mode
    for text, mode in modes:
      rb = tk.Radiobutton(
        mode_frame, 
        text=text, 
        variable=self.mode_selection_var, 
        value=mode,
        command=self.on_mode_change
      )
      rb.pack(anchor=tk.W, padx=5, pady=2)
    
    # Mode change status
    self.mode_status_var = tk.StringVar(value="")
    tk.Label(mode_frame, textvariable=self.mode_status_var).pack(fill=tk.X, padx=5, pady=5)
  
  def on_mode_change(self):
    selected_mode = self.mode_selection_var.get()
    if selected_mode != self.current_mode:
      # Only try to change if different and connected
      if self.is_monitoring:
        self.change_satellite_mode(selected_mode)
      else:
        messagebox.showwarning("Mode Change", "Please connect and start monitoring first")
        # Reset radio selection to current mode
        self.mode_selection_var.set(self.current_mode)
  
  def change_satellite_mode(self, new_mode):
    self.mode_status_var.set(f"Switching to {new_mode} mode...")
    self.root.update()

    def set_mode(mode, x, y, angle):
      payload = {"state": mode, "vel_x": x, "vel_y": y, "camera_angle": angle}
      response = requests.put(f"{MELVIN_BASE_URL}/control", json=payload)
      response.raise_for_status()

    curr = self.get_observation()
    try:
      set_mode(new_mode, curr['vx'], curr['vy'], curr['angle'])
    except Exception as e:
      print(f"[ERROR] Failed to fetch observation data: {str(e)}")
      time.sleep(2)  # Wait before retrying
      return self.get_observation()
    # Update mode
    self.current_mode = new_mode
    self.mode_var.set(new_mode)
    self.mode_status_var.set(f"Mode switched to {new_mode}")
    
    if new_mode == "charge":
      messagebox.showinfo("Mode Change", "Entered charge mode. Battery will recharge.")
  
  def clear_trajectory(self):
    self.canvas.delete("trajectory")
    self.canvas.delete("velocity_vector")
    self.canvas.delete("path_line")
    self.canvas.itemconfig(self.target_point, state="hidden")
  
  def connect_to_server(self):
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
    
    self._cleanup_connection()
  
  def _cleanup_connection(self):
    if self.ssh_client:
      try:
        self.ssh_client.close()
      except:
        pass
      self.ssh_client = None
      
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

        
        # Update with new data
        self.update_satellite_data(observation) # , acceleration)
        
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
      response = requests.get(f"{MELVIN_BASE_URL}/observation")
      response.raise_for_status()
      return response.json()
    except Exception as e:
      print(f"[ERROR] Failed to fetch observation data: {str(e)}")
      time.sleep(2)
      return self.get_observation()
  
  
  def update_satellite_data(self, observation_data):
    self.satellite_data = observation_data
    
    # Update UI on main thread
    self.root.after(0, self.update_ui)
  
  def update_ui(self):
    # Update position label
    self.pos_var.set(f"{self.satellite_data['width_x']}, {self.satellite_data['height_y']}")
    
    # Update velocity label
    self.vel_var.set(f"{self.satellite_data['vx']}, {self.satellite_data['vy']}")
    
    # Update mode label
    self.mode_var.set(f"{self.satellite_data['state']}")

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
            width=1,
            tags="velocity_vector"
          )
    
    # Store current position for trajectory
    self.last_x = x
    self.last_y = y
  
     



if __name__ == "__main__":
    root = tk.Tk()
    app = SatelliteMonitor(root)
    root.mainloop()