#!/usr/bin/env python3
"""
Weather App - Double-click to run
This is a .pyw file that runs without showing a console window
"""

import sys
import os
import subprocess

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def install_missing_packages():
    """Try to install missing packages automatically"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pystray", "pillow", "requests"])
        return True
    except:
        return False

def create_simple_weather_app():
    """Create a simple version without system tray if pystray fails"""
    try:
        import tkinter as tk
        import requests
        from tkinter import messagebox
        import json
        
        # Simple weather app without tray
        root = tk.Tk()
        root.title("Weather App")
        root.geometry("200x100")
        root.attributes("-topmost", True)
        
        # Import the weather functions from TempRain
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from TempRain import get_weather, load_city, save_city, prompt_for_city
        
        # Create simple display
        temp_label = tk.Label(root, text="Loading...", font=("Arial", 12))
        temp_label.pack(pady=20)
        
        def update_simple_weather():
            city = load_city()
            if city:
                weather_data = get_weather(city)
                if weather_data:
                    temp = weather_data["main"]["temp"]
                    temp_label.config(text=f"{city}: {temp}°F")
            root.after(1800000, update_simple_weather)  # Update every 30 minutes
        
        update_simple_weather()
        root.mainloop()
        
    except Exception as e:
        with open('fallback_error.log', 'w') as f:
            f.write(f"Fallback app failed: {e}")

# Try to import and run the main application
try:
    import pystray
    from TempRain import main
    main()
except ImportError as e:
    # Log the import error
    with open('startup_error.log', 'w') as f:
        f.write(f"Missing dependency: {e}\nAttempting to install packages...\n")
    
    # Try to install missing packages
    if install_missing_packages():
        try:
            # Try again after installation
            import pystray
            from TempRain import main
            main()
        except Exception as e2:
            with open('startup_error.log', 'a') as f:
                f.write(f"Still failed after installation: {e2}\nStarting simple version...\n")
            create_simple_weather_app()
    else:
        # If installation fails, use simple version
        with open('startup_error.log', 'a') as f:
            f.write("Package installation failed. Starting simple version...\n")
        create_simple_weather_app()
        
except Exception as e:
    # Log any other startup errors
    with open('startup_error.log', 'w') as f:
        f.write(f"Failed to start weather app: {e}")
    create_simple_weather_app()
