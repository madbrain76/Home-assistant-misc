#!/usr/bin/env python3
"""Get device list from YoLink local hub and display in table format"""

import os
import sys
import json
import argparse
import requests
from datetime import datetime
from urllib3.exceptions import InsecureRequestWarning
from tabulate import tabulate

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description='Get device list from YoLink local hub and display in table format',
    formatter_class=argparse.RawDescriptionHelpFormatter,
    epilog='''
COLUMN VISIBILITY:
  By default, all columns are displayed. You can hide specific columns:
  
  -noid, --hide-device-id    Hide the Device ID column (useful for cleaner display)

SORTING:
  Default: Sorted by device Type (alphabetically), then by Name.
  --sort-by-contact: Sort by Last radio contact (oldest first), then Type, then Name.

AVAILABLE COLUMNS:
  Type                Device type (e.g., Motion sensor, Door sensor)
  Name                Device name as configured in YoLink
  Device ID           Unique device identifier (can be hidden with -noid)
  Model               YoLink model number (e.g., YS7804-UC)
  Battery             Battery level percentage (0-100%%)
  Temp                Device temperature reading (N/A for non-temperature devices)
  Last radio contact  Last communication timestamp with hub (local time)
  No motion delay     Motion detection timeout in seconds (motion sensors only)
  Sensitivity         Motion detection sensitivity level (motion sensors only)
  State               Current device state (e.g., "no motion", "dry", "open")
  Version             Firmware version

ENVIRONMENT VARIABLES (required):
  YOLINK_URL          YoLink hub URL (e.g., https://192.168.1.100:8003)
  YOLINK_TOKEN        YoLink API access token

EXAMPLES:
  # Display all devices with all columns (sorted by Type, then Name)
  %(prog)s
  
  # Hide Device ID column for cleaner output
  %(prog)s -noid
  
  # Sort by Last radio contact (oldest first)
  %(prog)s --sort-by-contact
  
  # Output full JSON responses for debugging
  %(prog)s --json
  
  # Combine options
  %(prog)s -noid --sort-by-contact --json > output.txt

OUTPUT FORMAT:
  Default: Human-readable table with aligned columns
  --json:  Appends detailed JSON responses after the table
''')
parser.add_argument('-noid', '--hide-device-id', action='store_true', 
                    help='Hide the Device ID column for cleaner display')
parser.add_argument('--sort-by-contact', action='store_true',
                    help='Sort by Last radio contact (oldest first), then Type, then Name')
parser.add_argument('--json', action='store_true', 
                    help='Output full JSON response for each device (appended after table)')
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

# Function to format temperature with aligned C symbol (ASCII only)
def format_temperature(temp_value, device_type):
    """Format temperature as 7-char string
    
    N/A: centered ( N/A  )
    Temps: right-aligned (  17  C)
    """
    if temp_value is None:
        return f"{'N/A':^7}"  # Center N/A in 7 chars
    
    if device_type == 'THSensor':
        # Temperature sensors: 1 decimal, right-align to 5 chars, then C directly
        temp_str = f"{temp_value:>5.1f}C"
    else:
        # Other sensors: integers only, right-align to 3 chars, then 2 spaces and C
        if temp_value == int(temp_value):
            temp_str = f"{int(temp_value):>3}  C"
        else:
            temp_str = f"{temp_value:>5.1f}C"
    
    return f"{temp_str:>7}"  # Right-align in 7 chars


# Function to format reportAt timestamp
def format_report_time(report_at_str):
    """Format ISO 8601 timestamp to local YYYY-MM-DD HH:MM:SS format (19 chars centered)
    
    Example: 2025-12-09T08:54:34.042Z -> 2025-12-09 08:54:34 (in local timezone)
    If parsing fails, return N/A centered
    """
    if not report_at_str:
        return f"{'N/A':^19}"
    
    try:
        # Parse ISO 8601 timestamp (UTC)
        dt_utc = datetime.fromisoformat(report_at_str.replace('Z', '+00:00'))
        # Convert to local timezone
        dt_local = dt_utc.astimezone()
        time_str = dt_local.strftime('%Y-%m-%d %H:%M:%S')
        # Center in 19 chars
        return f"{time_str:^19}"
    except Exception:
        return f"{'N/A':^19}"



# Function to get device properties
def get_device_properties(device_id, device_token, device_type):
    """Get device state/properties from YoLink API
    Returns: (state_data, full_response) tuple
    """
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
            return None, result
        
        # Extract state data
        state_data = result.get('data', {}).get('state', {})
        return state_data, result
    except Exception as e:
        print(f"Warning: Could not fetch properties for {device_id}: {e}", file=sys.stderr)
        return None, None

# Print table
print()
table_data = []
json_responses = []  # Store JSON responses for --json output
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
        temperature = None
        version = 'N/A'
        state_str = 'N/A'
        nomotion = 'N/A'
        sensitivity = 'N/A'
        report_time = f"{'N/A':^19}"
        if device_token:
            properties, device_json_response = get_device_properties(device_id, device_token, device_type)
            if device_json_response:
                json_responses.append({
                    'deviceId': device_id,
                    'name': device_name,
                    'response': device_json_response
                })
                # Extract reportAt timestamp
                report_at = device_json_response.get('data', {}).get('reportAt')
                if report_at:
                    report_time = format_report_time(report_at)
            if properties:
                
                # Extract battery level (0-4 maps to 0-100%)
                if 'battery' in properties:
                    battery_level = int((properties['battery'] / 4) * 100)
                    battery = f"{battery_level}%"
                # Extract temperature (devTemperature is the source of truth)
                temp_value = None
                if 'devTemperature' in properties:
                    temp_value = float(properties['devTemperature'])
                elif 'temperature' in properties:
                    temp_value = float(properties['temperature'])
                elif 'temp' in properties:
                    temp_value = float(properties['temp'])
                
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
        
        # Format temperature if not already formatted (N/A case)
        if temperature is None:
            temperature = format_temperature(None, device_type)
        
        table_data.append([format_device_type(device_type, model), device_name, device_id, model, battery, temperature, report_time, nomotion, sensitivity, state_str, version])
    
    # Print header with wrapped "No motion delay" and "Last radio contact" (3 lines, centered)
    if args.hide_device_id:
        print(f"{'Type':<20} {'Name':<35} {'Model':<10} {'Battery':>8} {'Temp':>7} {'Last':^19} {'No':^10} {'Sensitivity':^11} {'State':^16} {'Version':^8}")
        print(f"{'':<20} {'':<35} {'':<10} {'':<8} {'':<7} {'radio':^19} {'motion':^10} {'':<11} {'':<16} {'':<8}")
        print(f"{'':<20} {'':<35} {'':<10} {'':<8} {'':<7} {'contact':^19} {'delay':^10} {'':<11} {'':<16} {'':<8}")
        print("-" * 175)
    else:
        print(f"{'Type':<20} {'Name':<35} {'Device ID':<18} {'Model':<10} {'Battery':>8} {'Temp':>7} {'Last':^19} {'No':^10} {'Sensitivity':^11} {'State':^16} {'Version':^8}")
        print(f"{'':<20} {'':<35} {'':<18} {'':<10} {'':<8} {'':<7} {'radio':^19} {'motion':^10} {'':<11} {'':<16} {'':<8}")
        print(f"{'':<20} {'':<35} {'':<18} {'':<10} {'':<8} {'':<7} {'contact':^19} {'delay':^10} {'':<11} {'':<16} {'':<8}")
        print("-" * 193)
    
    # Sort by device type, then by name (or by contact time if requested)
    if args.sort_by_contact:
        # Sort by Last radio contact (oldest first), then Type, then Name
        # Strip whitespace from centered timestamp for proper sorting
        table_data.sort(key=lambda row: (row[6].strip(), row[0], row[1]))
    else:
        # Default: Sort by Type, then Name
        table_data.sort(key=lambda row: (row[0], row[1]))
    
    # Print rows with proper alignment
    for row in table_data:
        if args.hide_device_id:
            print(f"{row[0]:<20} {row[1]:<35} {row[3]:<10} {row[4]:>8} {row[5]:>7} {row[6]:^19} {row[7]:^10} {row[8]:^11} {row[9]:^16} {row[10]:^8}")
        else:
            print(f"{row[0]:<20} {row[1]:<35} {row[2]:<18} {row[3]:<10} {row[4]:>8} {row[5]:>7} {row[6]:^19} {row[7]:^10} {row[8]:^11} {row[9]:^16} {row[10]:^8}")

# Output JSON responses if requested
if args.json and json_responses:
    print("\n" + "="*80)
    print("JSON RESPONSES FOR EACH DEVICE")
    print("="*80 + "\n")
    for entry in json_responses:
        print(f"Device: {entry['name']} ({entry['deviceId']})")
        print("-" * 80)
        print(json.dumps(entry['response'], indent=2))
        print()

sys.exit(0)
