#!/usr/bin/env python3
"""Get device list from YoLink local hub and display in table format"""

import os
import sys
import json
import requests
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

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
print(f"Fetching device list from {api_url}...", file=sys.stderr)

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

# Print table
print()
print(f"{'Device ID':<40} {'Device Name':<30} {'Device Type':<20}")
print("-" * 90)

if not devices:
    print("No devices found")
else:
    for device in devices:
        device_id = device.get('deviceId', 'N/A')
        device_name = device.get('name', 'N/A')
        device_type = device.get('type', 'N/A')
        
        print(f"{device_id:<40} {device_name:<30} {device_type:<20}")

sys.exit(0)
