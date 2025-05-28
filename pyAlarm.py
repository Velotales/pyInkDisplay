import requests
import time
import sys
from datetime import datetime, timedelta
import pytz
import logging

# Import the PiSugar module
from pisugar import PiSugarServer, connect_tcp 

def isOnline(url):
    """Function to test network connectivity."""
    try:
        response = requests.get(url, timeout=5)
        return response.status_code == 204
    except requests.exceptions.RequestException:
        return False

def calculateFutureAlarmDatetime(base_datetime: datetime, seconds_in_future: int) -> datetime:
    """
    Calculates a future datetime by adding a specified number of seconds
    to a given base datetime.

    Args:
        base_datetime (datetime): The starting datetime (e.g., current RTC time),
                                  preferably timezone-aware.
        seconds_in_future (int): The number of seconds from the base_datetime to set the alarm.

    Returns:
        datetime: The calculated future datetime object, retaining timezone information.
    """
    if not isinstance(seconds_in_future, int) or seconds_in_future < 0:
        raise ValueError("seconds_in_future must be a non-negative integer.")
    
    return base_datetime + timedelta(seconds=seconds_in_future)

def main():
    """
    Main execution logic for the PiSugar3 alarm programming script.
    Handles network connectivity, RTC synchronization, time calculation,
    and setting the alarm using the PiSugar module.
    """

    # Set up logging
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    logging.info(f'{main.__name__}: Starting')    

    URL = "http://clients3.google.com/generate_204"  # URL to ping to check network
    MAX_RETRIES = 4  # Retries for the online connectivity check
    RETRY_COUNT = 0

     # Check whether system is online, if not wait 15 seconds
    logging.info(f'{main.__name__}: Checking network connectivity...')
    while not isOnline(URL):
        
        currentTime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        logging.error(f'{main.__name__}: {currentTime} - Failed test to {URL}, waiting for connectivity')
        # Removed time.sleep(15) and RETRY_COUNT for indefinite waiting as per last update
        # If you want delays or retries, they should be re-added here.
    logging.info(f'{main.__name__}: Connected')

    conn, event_conn = connect_tcp()
    pisugar = PiSugarServer(conn, event_conn)

    # Store time before RTC sync
    try:
        initialRtcTime = pisugar.get_rtc_time()
        logging.info(f'{main.__name__}: Initial RTC time from PiSugar: {initialRtcTime}')
    except (PiSugarConnectionError, PiSugarError) as e:
        logging.error(f'{main.__name__}: Failed to get initial RTC time from PiSugar: {e}')
        logging.error(f"{main.__name__}: Please ensure pisugar-server is running and you have permissions (try with 'sudo'). Exiting.")
        sys.exit()


    # When network is up, sync the RTC clock to the Pi
    logging.info(f'{main.__name__}: Syncing RTC clock to Pi...')
    try:
        pisugar.rtc_pi2rtc()
        logging.info(f'{main.__name__}: RTC clock sync initiated.')
    except (PiSugarConnectionError, PiSugarError) as e:
        logging.warning(f'{main.__name__}: Warning: RTC clock sync might have failed: {e}')
        logging.warning(f"{main.__name__}: Please ensure pisugar-server is running and you have permissions (try with 'sudo').")
        # Do not exit here, attempt to proceed with potentially unsynced RTC time

    # Store the rtc time after sync
    try:
        rtcDateTime = pisugar.get_rtc_time() # This now returns a datetime.datetime object
        logging.info(f'{main.__name__}: {rtcDateTime} - RTC clock synced to Pi, previous time was {initialRtcTime}')
    except (PiSugarConnectionError, PiSugarError) as e:
        logging.error(f'{main.__name__}: Error getting RTC time after sync from PiSugar: {e}. Exiting.')
        logging.error(f"{main.__name__}: Please ensure pisugar-server is running and you have permissions (try with 'sudo').")
        sys.exit()
    
    # Debug prints - removed from default for cleaner output, but can be re-enabled
    # logging.info(f"DEBUG: Type of rtcDateTime: {type(rtcDateTime)}")
    # logging.info(f"DEBUG: Value of rtcDateTime: '{rtcDateTime}'")

    # Get the current local timezone for accurate offset
    try:
        localTZ = datetime.now(pytz.utc).astimezone().tzinfo
        timezoneOffsetSeconds = localTZ.utcoffset(datetime.now()).total_seconds()
        hours = int(timezoneOffsetSeconds // 3600)
        minutes = int((timezoneOffsetSeconds % 3600) // 60)
        timezoneOffset = f"{'+' if hours >= 0 else '-'}{abs(hours):02d}:{abs(minutes):02d}"
    except Exception as e:
        logging.error(f"{main.__name__}: Could not determine timezone offset: {e}. Defaulting to +00:00.")
        timezoneOffset = "+00:00"

    currentDate = datetime.now().strftime("%Y-%m-%d")
    currentHour = datetime.now().hour

    seconds_to_add = 300 # Change this to your desired number of seconds
    nextAlarmDatetime = None
    # Use the new function to calculate nextAlarmDatetime
    try:
        nextAlarmDatetime = calculateFutureAlarmDatetime(rtcDateTime, seconds_to_add)
        logging.info(f"Calculated next alarm (in {seconds_to_add} seconds): {nextAlarmDatetime.isoformat()}")
    except ValueError as e:
        logging.error(f"{main.__name__}: Error calculating future alarm time: {e}. Exiting.")
        sys.exit(1)

    if nextAlarmDatetime:
        # Create a formatted string for logging, if desired
        nextAlarmFormatted = nextAlarmDatetime.strftime("%Y-%m-%dT%H:%M:%S") + timezoneOffset
        logging.info(f"Final next alarm for PiSugar: {nextAlarmFormatted}")
        
        try:
            pisugar.rtc_alarm_set(nextAlarmDatetime, 127) # 127 means repeat every day
            logging.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Alarm set for [{nextAlarmFormatted}]")
            # Removed sys.exit(0) as per your previous update
        except (PiSugarConnectionError, PiSugarError) as e:
            logging.error(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Error while setting alarm using PiSugar module: {e}")
            logging.error("Please ensure pisugar-server is running and you have permissions (try with 'sudo').")
            sys.exit(1)
    else:
        logging.error("Error: Could not determine next alarm time. Exiting.")
        sys.exit(1)

if __name__ == "__main__":
    main()
