import requests
import socket
import time
from datetime import datetime, timedelta
import sys
import re
import pytz
import os # Import the os module for path operations

# Configuration variables
URL = "http://clients3.google.com/generate_204"  # URL to ping to check network
MAX_RETRIES = 4  # Retries for the online connectivity check
RETRY_COUNT = 0

# PiSugar3 specific: Unix socket path
PISUGAR_SOCKET_PATH = "/tmp/pisugar-server.sock"

def is_online():
    """Function to test network connectivity."""
    try:
        response = requests.get(URL, timeout=5)
        return response.status_code == 204
    except requests.exceptions.RequestException:
        return False

def send_to_pisugar(command):
    """Sends a command to the PiSugar module (PiSugar3 via Unix socket) and returns the response."""
    # Check if the Unix socket file exists
    if not os.path.exists(PISUGAR_SOCKET_PATH):
        print(f"Error: PiSugar server socket not found at {PISUGAR_SOCKET_PATH}. "
              "Ensure pisugar-server is running and configured correctly.")
        return None

    try:
        # Use AF_UNIX for Unix domain sockets
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
            s.settimeout(5)  # Timeout for connection and receive
            s.connect(PISUGAR_SOCKET_PATH)
            s.sendall(command.encode('utf-8') + b'\n')
            response = s.recv(1024).decode('utf-8').strip()
            return response
    except socket.error as e:
        # Check for permission denied specifically
        if "Permission denied" in str(e):
            print(f"Socket error: Permission denied when trying to access {PISUGAR_SOCKET_PATH}. "
                  "You might need to run this script with 'sudo'.")
        else:
            print(f"Socket error communicating with PiSugar server: {e}")
        return None
    except socket.timeout:
        print(f"Socket timeout when communicating with PiSugar server at {PISUGAR_SOCKET_PATH}.")
        return None

def set_alarm(alarm_time, repeat):
    """Sets the RTC alarm on the PiSugar module."""
    command = f"rtc_alarm_set {alarm_time} {repeat}"
    r = send_to_pisugar(command)

    if r and "done" in r.lower(): # Case-insensitive check for "done"
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Alarm set for [{alarm_time}]")
        sys.exit(0)
    else:
        print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Error while setting alarm. Response: {r}")
        sys.exit(1)

def main():
    """
    Main execution logic for the PiSugar3 alarm programming script.
    Handles network connectivity, RTC synchronization, time calculation,
    and setting the alarm.
    """
    global RETRY_COUNT # Declare RETRY_COUNT as global to modify it

    # Check whether system is online, if not wait 15 seconds
    print("Checking network connectivity...")
    while not is_online():
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{current_time}] - Failed test to {URL}, waiting for connectivity...")
        time.sleep(15)
        RETRY_COUNT += 1
        if RETRY_COUNT == MAX_RETRIES:
            print(f"[{current_time}] - Failed to connect to {URL} after {MAX_RETRIES} attempts. Exiting.")
            sys.exit(1)

    # Store time before RTC sync
    initial_rtc_time_response = send_to_pisugar("get rtc_time")
    # Ensure 'rtc_time:' is in the response before replacing
    initial_rtc_time = initial_rtc_time_response.replace("rtc_time: ", "") if initial_rtc_time_response and "rtc_time:" in initial_rtc_time_response else "N/A"

    # When network is up, sync the RTC clock to the Pi
    print('Syncing RTC clock to Pi...')
    sync_response = send_to_pisugar('rtc_pi2rtc')
    if sync_response and "done" in sync_response.lower():
        print("RTC clock sync initiated.")
    else:
        print(f"Warning: RTC clock sync might have failed. Response: {sync_response}")


    # Store the rtc time after sync
    rtc_time_response = send_to_pisugar("get rtc_time")

    if rtc_time_response and "rtc_time:" in rtc_time_response:
        rtc_time_str = rtc_time_response.replace("rtc_time: ", "")
        print(f"{rtc_time_str} - RTC clock synced to Pi, previous time was {initial_rtc_time}")
        
        # Parse the RTC time from the PiSugar module
        try:
            # PiSugar3 often returns ISO8601 format (e.g., "YYYY-MM-DDTHH:MM:SS+HH:MM" or "YYYY-MM-DD HH:MM:SSZ")
            # datetime.fromisoformat handles various ISO formats. Replace 'Z' with '+00:00' for full compatibility.
            rtc_datetime = datetime.fromisoformat(rtc_time_str.replace("Z", "+00:00"))
            rtc_date = rtc_datetime.strftime("%Y-%m-%d")
            rtc_hour = rtc_datetime.hour # This gets the hour in 24-hour format
        except ValueError:
            print(f"Error parsing RTC time from PiSugar module: '{rtc_time_str}'. Please check format. Exiting.")
            sys.exit(1)
    else:
        print(f"Get RTC time error or unexpected response: '{rtc_time_response}'. Exiting.")
        sys.exit(1)

    # Get the current local timezone for accurate offset
    try:
        # Use the local system's timezone. pytz.utc.astimezone() gets the local timezone object.
        local_tz = datetime.now(pytz.utc).astimezone().tzinfo
        # Calculate the offset for the current time
        timezone_offset_seconds = local_tz.utcoffset(datetime.now()).total_seconds()
        hours = int(timezone_offset_seconds // 3600)
        minutes = int((timezone_offset_seconds % 3600) // 60)
        timezone_offset = f"{'+' if hours >= 0 else '-'}{abs(hours):02d}:{abs(minutes):02d}"
    except Exception as e:
        print(f"Could not determine timezone offset: {e}. Defaulting to +00:00.")
        timezone_offset = "+00:00" # Fallback if timezone detection fails

    current_date = datetime.now().strftime("%Y-%m-%d")
    current_hour = datetime.now().hour # This gets the current system hour

    # Check for Daylight Saving Time transition at 2 AM
    # This part is a direct translation of the bash logic and might not be universally robust
    # for all timezones or DST rules. It assumes a specific "EDT" abbreviation and a +1 hour jump.
    try:
        # Create a dummy datetime object for 2 AM on the current date in the local timezone
        # and get its timezone abbreviation.
        # This requires the system's timezone configuration to be correct.
        # Note: pytz.timezone(os.environ.get('TZ', 'Etc/UTC')) is more robust for specific TZs
        # but for a direct translation, we rely on astimezone().tzname()
        test_dt_2am = datetime.strptime(f"{current_date} 02:00:00", "%Y-%m-%d %H:%M:%S").astimezone()
        tz_abbreviation_at_2am = test_dt_2am.tzname()

        if tz_abbreviation_at_2am == "EDT" and current_hour == 1:
            current_hour += 1
            print("Adjusting current hour due to anticipated DST transition (EDT check).")
    except Exception as e:
        print(f"Could not perform DST adjustment check: {e}. Skipping DST adjustment.")

    # Set the next alarm based on the current hour (using the RTC's date for the alarm)
    next_alarm_datetime = None
    if current_hour < 6:
        # If current system time is before 6 AM, set for 6:01 AM today (using RTC's date)
        next_alarm_datetime = rtc_datetime.replace(hour=6, minute=1, second=0, microsecond=0)
    elif current_hour < 18:
        # If current system time is before 6 PM, set for 6:01 PM today (using RTC's date)
        next_alarm_datetime = rtc_datetime.replace(hour=18, minute=1, second=0, microsecond=0)
    else:
        # If current system time is 6 PM or later, set for 6:01 AM next day (using RTC's date)
        next_day_rtc_datetime = rtc_datetime + timedelta(days=1)
        next_alarm_datetime = next_day_rtc_datetime.replace(hour=6, minute=1, second=0, microsecond=0)

    if next_alarm_datetime:
        # Format the alarm time in ISO 8601 format with timezone offset
        # Example: "2025-05-24T18:01:00+02:00"
        next_alarm_formatted = next_alarm_datetime.strftime("%Y-%m-%dT%H:%M:%S") + timezone_offset
        print(f"Calculated next alarm: {next_alarm_formatted}")
        set_alarm(next_alarm_formatted, 127)  # 127 means repeat every day
    else:
        print("Error: Could not determine next alarm time. Exiting.")
        sys.exit(1)

if __name__ == "__main__":
    main()

