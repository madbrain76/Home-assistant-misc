#!/usr/bin/env python3
"""Get device list from YoLink local hub and display in table format"""

import os
import sys
import json
import argparse
import requests
from urllib3.exceptions import InsecureRequestWarning
from tabulate import tabulate

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Get device list from YoLink local hub')
parser.add_argument('-noid', '--hide-device-id', action='store_true', help='Hide the Device ID column')
args = parser.parse_args()

# Get environment variables
yolink_url = os.environ.get('YOLINK_URL')
yolink_token = os.environ.get('YOLINK_TOKEN')

# Validate environment variables
if not yolink_url or not yolink_token:
    print("Error: Missing required environment variables:", file=sys.stderr)
    if not yolink_url:
        print("  - YOLINK_URL", file=sys.stderr)
    if not yolink_token:
        print("  - YOLINK_TOKEN", file=sys.stderr)
    sys.exit(1)

api_url = f"{yolink_url}/open/yolink/v2/api"
print(f"Fetching device list from {api_url}...")

try:
    response = requests.post(
        api_url,
        json={"method": "Home.getDeviceList"},
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {yolink_token}"
        },
        verify=False,
        timeout=10
    )
    response.raise_for_status()
    data = response.json()
    
except requests.exceptions.RequestException as e:
    print(f"Error: Failed to fetch devices: {e}", file=sys.stderr)
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"Error: Invalid JSON response: {e}", file=sys.stderr)
    sys.exit(1)

# Check for API errors
code = data.get('code', '0')
desc = data.get('desc', '')

if code not in ['0', '000000']:
    print(f"Error: {desc}", file=sys.stderr)
    sys.exit(1)

if any(keyword in desc.lower() for keyword in ['error', 'expired', 'invalid']):
    print(f"Error: {desc}", file=sys.stderr)
    sys.exit(1)

# Extract device list
devices = data.get('data', {}).get('devices', [])

# Function to extract model from appEui
def get_model_from_appeui(appeui):
    """Extract model number from appEui (e.g., d88b4c7804000000 -> YS7804-UC)"""
    if appeui and len(appeui) >= 10:
        model_code = appeui[6:10]  # Extract characters 6-9
        return f"YS{model_code}-UC"
    return "N/A"

# Function to format device type
def format_device_type(device_type, model=None):
    """Format device type with human-readable names"""
    # Special case for garage door sensors
    if model == 'YS7706-UC':
        return 'Garage door sensor'
    
    type_mapping = {
        'MotionSensor': 'Motion sensor',
        'THSensor': 'Temperature sensor',
        'DoorSensor': 'Door sensor',
        'LeakSensor': 'Leak sensor',
    }
    return type_mapping.get(device_type, device_type)

# Function to format temperature with aligned °C symbol
def format_temperature(temp_value, device_type):
    """Format temperature with consistent alignment so °C symbols line up
    
    High-res (THSensor): -14.8°C (7 chars)
    Low-res (others):   11  °C (7 chars, with spaces before °C)
    """
    if temp_value is None:
        return 'N/A'
    
    if device_type == 'THSensor':
        # Temperature sensors: 1 decimal, right-align to 5 chars, then °C directly
        return f"{temp_value:>5.1f}°C"
    else:
        # Other sensors: integers only, right-align to 3 chars, then 2 spaces and °C
        if temp_value == int(temp_value):
            return f"{int(temp_value):>3}  °C"
        else:
            return f"{temp_value:>5.1f}°C"

# Function to get device properties
def get_device_properties(device_id, device_token, device_type):
    """Get device state/properties from YoLink API"""
    try:
        method = f"{device_type}.getState"
        response = requests.post(
            api_url,
            json={
                "method": method,
                "targetDevice": device_id,
                "token": device_token,
                "params": {}
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {yolink_token}"
            },
            verify=False,
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        
        # Check for API errors
        code = result.get('code', '0')
        if code not in ['0', '000000']:
            return None
        
        # Extract state data
        state_data = result.get('data', {}).get('state', {})
        return state_data
    except Exception as e:
        print(f"Warning: Could not fetch properties for {device_id}: {e}", file=sys.stderr)
        return None

# Print table
print()
table_data = []
headers = ['Type', 'Name', 'Device ID', 'Model', 'Battery', 'Temp', 'No motion delay', 'Sensitivity', 'State', 'Version']

if not devices:
    print("No devices found")
else:
    for device in devices:
        device_id = device.get('deviceId', 'N/A')
        device_name = device.get('name', 'N/A')
        device_type = device.get('type', 'N/A')
        device_token = device.get('token', '')
        appeui = device.get('appEui', '')
        model = get_model_from_appeui(appeui)
        
        # Get device properties
        battery = 'N/A'
        temperature = 'N/A'
        version = 'N/A'
        state_str = 'N/A'
        nomotion = 'N/A'
        sensitivity = 'N/A'
        if device_token:
            properties = get_device_properties(device_id, device_token, device_type)
            if properties:
                
                # Extract battery level (0-4 maps to 0-100%)
                if 'battery' in properties:
                    battery_level = int((properties['battery'] / 4) * 100)
                    battery = f"{battery_level}%"
                # Extract temperature (try multiple field names)
                # For Temperature sensors, always show 1 decimal. For others, only show decimals if present.
                temp_value = None
                if 'temperature' in properties:
                    temp_value = float(properties['temperature'])
                elif 'temp' in properties:
                    temp_value = float(properties['temp'])
                elif 'devTemperature' in properties:
                    temp_value = float(properties['devTemperature'])
                
                if temp_value is not None:
                    temperature = format_temperature(temp_value, device_type)
                # Extract firmware version
                if 'version' in properties:
                    version = properties['version']
                
                # Extract state info based on device type
                if device_type == 'MotionSensor':
                    # For motion sensors, show the state (alert or off)
                    raw_state = properties.get('state', 'N/A')
                    if raw_state == 'alert':
                        state_str = 'motion detected'
                    elif raw_state in ['normal', 'off']:
                        state_str = 'no motion'
                    else:
                        state_str = raw_state.lower()
                    nomotion = str(properties.get('nomotionDelay', 'N/A'))
                    sensitivity = str(properties.get('sensitivity', 'N/A'))
                elif device_type == 'LeakSensor':
                    # For leak sensors, show dry or wet
                    raw_state = properties.get('state', 'N/A')
                    if raw_state == 'alert':
                        state_str = 'wet'
                    elif raw_state in ['normal', 'off']:
                        state_str = 'dry'
                    else:
                        state_str = raw_state.lower()
                elif 'state' in properties:
                    state_str = properties['state'][:20].lower()
                elif properties:
                    # Show first key-value pair as state
                    first_key = next(iter(properties), None)
                    if first_key:
                        state_str = f"{first_key}: {str(properties[first_key])[:15]}".lower()
        
        table_data.append([format_device_type(device_type, model), device_name, device_id, model, battery, temperature, nomotion, sensitivity, state_str, version])
    
    # Print header with wrapped "No motion delay" (3 lines, centered)
    if args.hide_device_id:
        print(f"{'Type':<20} {'Name':<35} {'Model':<10} {'Battery':>8} {'Temp':>9} {'No':^10} {'Sensitivity':^11} {'State':^16} {'Version':^8}")
        print(f"{'':<20} {'':<35} {'':<10} {'':<8} {'':<9} {'motion':^10} {'':<11} {'':<16} {'':<8}")
        print(f"{'':<20} {'':<35} {'':<10} {'':<8} {'':<9} {'delay':^10} {'':<11} {'':<16} {'':<8}")
        print("-" * 157)
    else:
        print(f"{'Type':<20} {'Name':<35} {'Device ID':<18} {'Model':<10} {'Battery':>8} {'Temp':>9} {'No':^10} {'Sensitivity':^11} {'State':^16} {'Version':^8}")
        print(f"{'':<20} {'':<35} {'':<18} {'':<10} {'':<8} {'':<9} {'motion':^10} {'':<11} {'':<16} {'':<8}")
        print(f"{'':<20} {'':<35} {'':<18} {'':<10} {'':<8} {'':<9} {'delay':^10} {'':<11} {'':<16} {'':<8}")
        print("-" * 175)
    
    # Sort by device type, then by name
    table_data.sort(key=lambda row: (row[0], row[1]))
    
    # Print rows with proper alignment
    for row in table_data:
        if args.hide_device_id:
            print(f"{row[0]:<20} {row[1]:<35} {row[3]:<10} {row[4]:>8} {row[5]:>9} {row[6]:^10} {row[7]:^11} {row[8]:^16} {row[9]:^8}")
        else:
            print(f"{row[0]:<20} {row[1]:<35} {row[2]:<18} {row[3]:<10} {row[4]:>8} {row[5]:>9} {row[6]:^10} {row[7]:^11} {row[8]:^16} {row[9]:^8}")

sys.exit(0)
