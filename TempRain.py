import tkinter as tk
import requests
from tkinter import messagebox
from PIL import Image, ImageTk
import json
import pystray
from pystray import MenuItem as item
import threading
import sys
import os
import traceback

# Get API key from environment variable or use placeholder
API_KEY = os.getenv('OPENWEATHER_API_KEY', 'your_api_key_here')
if API_KEY == 'your_api_key_here':
    print("Warning: Please set your OpenWeatherMap API key in the OPENWEATHER_API_KEY environment variable")

CITY_FILE = 'city.txt'
UPDATE_INTERVAL = 1800000  # 30 minutes in milliseconds
WINDOW_POSITION_FILE = 'window_position.json'  # File to save the window position

# Load the raindrop image
def load_raindrop_image():
    try:
        # Try to load from relative path first
        script_dir = os.path.dirname(os.path.abspath(__file__))
        raindrop_path = os.path.join(script_dir, 'assets', 'raindrop.png')
        raindrop_image = Image.open(raindrop_path)
        raindrop_image = raindrop_image.resize((20, 20))
        return ImageTk.PhotoImage(raindrop_image)
    except IOError:
        # Log error instead of showing messagebox for GitHub version
        log_error("Raindrop image not found - rain indicator will not be displayed")
        return None

# Function to fetch weather data
def get_weather(city):
    base_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={API_KEY}&units=imperial"
    try:
        response = requests.get(base_url, timeout=10)  # Add timeout
        data = response.json()
        if response.status_code == 200:
            return data
        else:
            # Log error but don't show messagebox (which can cause issues in background)
            log_error(f"API Error for city {city}: {data.get('cod')} - {data.get('message')}")
            return None
    except requests.exceptions.RequestException as e:
        # Log error but don't show messagebox
        log_error(f"Network error: {e}")
        return None

# Global variables
tray_icon = None
app_running = True
root = None
temp_window = None
temp_value = None
rain_status = None

# Function to create system tray icon
def create_tray_icon():
    # Try to load the custom weather app icon from the same directory
    try:
        # Get the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(script_dir, 'assets', 'weatherAppIcon.png')
        icon_image = Image.open(icon_path)
        icon_image = icon_image.resize((64, 64))
    except:
        # Try alternative paths as fallbacks
        try:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(script_dir, 'weatherAppIcon.png')
            icon_image = Image.open(icon_path)
            icon_image = icon_image.resize((64, 64))
        except:
            # Create a simple colored square if no icon file exists
            icon_image = Image.new('RGB', (64, 64), color=(70, 130, 180))
            log_error("Weather app icon not found - using default icon")
    
    menu = pystray.Menu(
        item('Show Weather', show_weather_window),
        item('Change City', change_city_action),
        item('Refresh Now', refresh_now_action),
        item('Exit', quit_application)
    )
    
    return pystray.Icon("WeatherApp", icon_image, "Weather App", menu)

# Function to show the weather window
def show_weather_window(icon=None, item=None):
    try:
        if temp_window and temp_window.winfo_exists():
            temp_window.deiconify()
            temp_window.attributes("-topmost", True)
            temp_window.lift()
        else:
            # Recreate window if it doesn't exist
            root.after(0, recreate_temperature_window)
    except Exception as e:
        log_error(f"Error in show_weather_window: {e}")
        root.after(0, recreate_temperature_window)

# Function to change city from tray
def change_city_action(icon=None, item=None):
    try:
        # Use root.after to ensure it runs in the main thread
        def safe_prompt():
            try:
                prompt_for_city()
            except Exception as e:
                log_error(f"Error in change_city_action: {e}")
        root.after(0, safe_prompt)
    except Exception as e:
        log_error(f"Error scheduling change_city_action: {e}")

# Function to refresh weather immediately
def refresh_now_action(icon=None, item=None):
    try:
        # Use root.after to ensure it runs in the main thread
        def safe_refresh():
            try:
                display_weather()
            except Exception as e:
                log_error(f"Error in refresh_now_action: {e}")
        root.after(0, safe_refresh)
    except Exception as e:
        log_error(f"Error scheduling refresh_now_action: {e}")

# Function to quit the application
def quit_application(icon=None, item=None):
    global app_running, tray_icon
    app_running = False
    try:
        if temp_window and temp_window.winfo_exists():
            save_window_position(temp_window)
        if tray_icon:
            tray_icon.stop()
    except:
        pass
    try:
        root.quit()
    except:
        pass
    os._exit(0)

# Function to create the window for temperature display (borderless and movable)
def create_temperature_window():
    global root
    temp_window = tk.Toplevel(root)
    temp_window.geometry("100x30")
    
    # Remove window decorations and title bar
    temp_window.attributes("-topmost", True)
    temp_window.overrideredirect(True)
    
    # Set the window to be transparent
    temp_window.attributes("-transparentcolor", "#000000")
    temp_window.configure(bg="#000000")

    # Create a frame to hold the labels side by side
    display_frame = tk.Frame(temp_window, bg="#000000")
    display_frame.pack(pady=3)

    # Create label for rain status
    rain_status = tk.Label(display_frame, bg="#000000")
    rain_status.pack(side="left", padx=2)

    # Create label for temperature
    temp_value = tk.Label(display_frame, text="Loading...", font=("Helvetica", 10), fg="#ECF0F1", bg="#000000")
    temp_value.pack(side="left", padx=2)
    
    # Add right-click context menu to hide window
    def hide_window(event):
        temp_window.withdraw()
    
    temp_window.bind("<Button-3>", hide_window)  # Right-click to hide
    temp_window.bind("<Button-1>", on_drag_start)
    temp_window.bind("<B1-Motion>", on_drag_motion)
    
    # Load and set the last position of the window
    load_window_position(temp_window)

    return temp_window, temp_value, rain_status

# Function to save the window position
def save_window_position(window):
    position = {
        'x': window.winfo_x(),
        'y': window.winfo_y()
    }
    with open(WINDOW_POSITION_FILE, 'w') as file:
        json.dump(position, file)

# Function to load the window position
def load_window_position(window):
    try:
        with open(WINDOW_POSITION_FILE, 'r') as file:
            position = json.load(file)
            window.geometry(f"100x30+{position['x']}+{position['y']}")
    except (FileNotFoundError, json.JSONDecodeError):
        pass  # Use default position if file not found or invalid

# Variables to track the position of the window
drag_start_x = 0
drag_start_y = 0

# Function to start dragging the window
def on_drag_start(event):
    global drag_start_x, drag_start_y
    drag_start_x = event.x
    drag_start_y = event.y

# Function to handle dragging the window
def on_drag_motion(event):
    if temp_window:
        x = temp_window.winfo_x() - drag_start_x + event.x
        y = temp_window.winfo_y() - drag_start_y + event.y
        temp_window.geometry(f"+{x}+{y}")

# Function to flash the temperature label to indicate an update
def flash_temperature_label():
    try:
        if not temp_window or not temp_window.winfo_exists():
            return
            
        original_color = temp_value.cget("fg")
        flash_color = "#FF0000"

        def flash(count):
            try:
                if count > 0 and temp_window and temp_window.winfo_exists():
                    current_color = temp_value.cget("fg")
                    new_color = flash_color if current_color == original_color else original_color
                    temp_value.config(fg=new_color)
                    temp_window.after(500, flash, count-1)  # Flash 5 times, change every 500ms
                elif temp_window and temp_window.winfo_exists():
                    temp_value.config(fg=original_color)
            except Exception as e:
                log_error(f"Error in flash: {e}")

        flash(6)  # Flash 3 times (each flash consists of two color changes)
    except Exception as e:
        log_error(f"Error in flash_temperature_label: {e}")

# Function to update the temperature and rain status in the same window and trigger the flash
def update_weather_info(temperature, rain):
    try:
        # Ensure the window still exists
        if not temp_window or not temp_window.winfo_exists():
            log_error("Temperature window no longer exists")
            return
            
        # Set text color based on temperature
        if temperature >= 90:
            temp_color = "#ff4d00"  # Red for 90°F or above
        elif temperature >= 80:
            temp_color = "#ffae00"  # Orange for 80°F or above
        elif temperature <= 70:
            temp_color = "#33ceff"  # Blue for 70°F or below (same color for < 80°F)
        else:
            temp_color = "#33ceff"  # Use the same blue color for temperatures < 80°F and >= 70°F

        # Update temperature label with the chosen color
        temp_value.config(text=f"{temperature}°F", fg=temp_color)
        
        if rain:
            raindrop_image = load_raindrop_image()
            if raindrop_image:
                rain_status.config(image=raindrop_image)
                rain_status.image = raindrop_image  # Keep a reference to prevent garbage collection
                temp_window.geometry("120x30")  # Increase size to fit the image
            else:
                rain_status.config(image=None)
                temp_window.geometry("100x30")  # Default size
        else:
            rain_status.config(image=None)
            temp_window.geometry("100x30")  # Default size

        # Ensure the window is visible and on top
        temp_window.deiconify()
        temp_window.attributes("-topmost", True)
        
        flash_temperature_label()
        
    except Exception as e:
        log_error(f"Error updating weather info: {e}")

# Function to display weather info
def display_weather():
    try:
        city = load_city()
        if city:
            weather_data = get_weather(city)
            if weather_data:
                temperature = weather_data["main"]["temp"]
                # Check for rain condition in the weather data
                rain = any(weather['main'].lower() == 'rain' for weather in weather_data['weather'])
                update_weather_info(temperature, rain)
            else:
                # If weather data fails, show error in the display but keep window visible
                if temp_window and temp_window.winfo_exists():
                    temp_value.config(text="Error", fg="#FF0000")
                    temp_window.deiconify()
                    temp_window.attributes("-topmost", True)
        else:
            prompt_for_city()
    except Exception as e:
        log_error(f"Error in display_weather: {e}")
        # Ensure window stays visible even on error
        if temp_window and temp_window.winfo_exists():
            temp_value.config(text="Error", fg="#FF0000")
            temp_window.deiconify()
            temp_window.attributes("-topmost", True)

# Function to prompt user to enter city name
def prompt_for_city():
    try:
        global root
        def save_and_fetch():
            city = city_entry.get()
            if city:
                save_city(city)
                prompt_window.destroy()
                # Don't call display_weather here, let the normal refresh handle it
                root.after(1000, display_weather)  # Delay slightly to ensure window is ready
            else:
                messagebox.showwarning("Input Error", "Please enter a city name.")

        # Create a new window to prompt for city name
        prompt_window = tk.Toplevel(root)
        prompt_window.title("Enter City")
        prompt_window.geometry("300x150")
        prompt_window.configure(bg="#000000")
        prompt_window.attributes("-topmost", True)

        city_label = tk.Label(prompt_window, text="Enter City Name:", font=("Helvetica", 12), fg="#ECF0F1", bg="#000000")
        city_label.pack(pady=5)

        city_entry = tk.Entry(prompt_window, width=20, font=("Helvetica", 12))
        city_entry.pack(pady=5)
        city_entry.focus()

        save_button = tk.Button(prompt_window, text="Save and Get Weather", command=save_and_fetch, font=("Helvetica", 12), bg="#FF0000", fg="#ECF0F1", relief=tk.FLAT)
        save_button.pack(pady=10)
        
        # Bind Enter key to save_and_fetch
        city_entry.bind('<Return>', lambda event: save_and_fetch())
        
    except Exception as e:
        log_error(f"Error in prompt_for_city: {e}")

# Function to save the city name to a file
def save_city(city):
    with open(CITY_FILE, 'w') as file:
        file.write(city)

# Function to load the city name from a file
def load_city():
    try:
        with open(CITY_FILE, 'r') as file:
            return file.read().strip()
    except FileNotFoundError:
        return ""

# Function to prevent the parent window from closing
def on_closing():
    quit_application()

# Function to refresh the temperature every 30 minutes
def refresh_temperature():
    try:
        if app_running:
            # Check if window still exists, recreate if necessary
            if not temp_window or not temp_window.winfo_exists():
                log_error("Temperature window lost, attempting to recreate")
                recreate_temperature_window()
            
            display_weather()
            
            if app_running:
                root.after(UPDATE_INTERVAL, refresh_temperature)
    except Exception as e:
        log_error(f"Error in refresh_temperature: {e}")
        if app_running:
            root.after(UPDATE_INTERVAL, refresh_temperature)

# Function to recreate the temperature window if it gets lost
def recreate_temperature_window():
    global temp_window, temp_value, rain_status
    try:
        if root and root.winfo_exists():
            temp_window, temp_value, rain_status = create_temperature_window()
            log_error("Temperature window recreated successfully")
            # Display weather immediately after recreation
            display_weather()
    except Exception as e:
        log_error(f"Failed to recreate temperature window: {e}")

# Function to log errors when running without console
def log_error(error_msg):
    try:
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open('weather_app_error.log', 'a') as f:
            f.write(f"[{timestamp}] {error_msg}\n")
    except:
        pass

# Function to setup and run the tray icon
def setup_tray():
    global tray_icon
    try:
        tray_icon = create_tray_icon()
        # Use run() instead of run_detached() for better compatibility
        tray_icon.run()
    except Exception as e:
        error_msg = f"Tray icon setup failed: {e}\n{traceback.format_exc()}"
        log_error(error_msg)

# Modified GUI Setup
def main():
    global root, temp_window, temp_value, rain_status
    
    try:
        # Create root window but keep it completely hidden
        root = tk.Tk()
        root.withdraw()  # Hide immediately
        
        # For Windows, ensure proper window handling
        if sys.platform == "win32":
            root.wm_state('withdrawn')
            root.attributes("-alpha", 0)
            root.geometry("1x1+0+0")
        
        # Initialize the temperature window and labels
        temp_window, temp_value, rain_status = create_temperature_window()
        
        # Check if city is saved and display weather immediately
        if load_city():
            display_weather()
        else:
            prompt_for_city()
        
        # Start the automatic refresh
        root.after(UPDATE_INTERVAL, refresh_temperature)
        
        # Setup tray icon after initial setup
        tray_thread = threading.Thread(target=setup_tray, daemon=True)
        tray_thread.start()
        
        # Handle application closing
        root.protocol("WM_DELETE_WINDOW", quit_application)
        
        # Run the main loop
        root.mainloop()
        
    except Exception as e:
        error_msg = f"Application error: {e}\n{traceback.format_exc()}"
        log_error(error_msg)
        quit_application()

if __name__ == "__main__":
    main()
