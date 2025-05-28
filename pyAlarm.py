import requests
import time
import sys
from datetime import datetime, timedelta
import pytz
import logging

# Import the PiSugar module
try:
    from pisugar import PiSugarServer, connect_tcp
except ImportError:
    logging.error("PiSugar module not found. Please ensure 'pisugar' is installed.")
    # Define dummy classes if PiSugar is not available, to allow the code structure to be seen
    # In a real scenario, you'd want to handle this more robustly, perhaps by exiting.
    class PiSugarServer:
        def __init__(self, *args, **kwargs):
            logging.warning("Dummy PiSugarServer initialized. PiSugar module not found.")
        def get_rtc_time(self):
            raise PiSugarConnectionError("PiSugar module not available.")
        def rtc_pi2rtc(self):
            raise PiSugarConnectionError("PiSugar module not available.")
        def rtc_alarm_set(self, *args, **kwargs):
            raise PiSugarConnectionError("PiSugar module not available.")
    class connect_tcp:
        def __init__(self, *args, **kwargs):
            logging.warning("Dummy connect_tcp initialized. PiSugar module not found.")
        def __call__(self):
            return None, None 
    
# Custom exceptions for PiSugar operations
class PiSugarConnectionError(Exception):
    """Raised when there's a problem connecting to or communicating with PiSugar."""
    pass

class PiSugarError(Exception):
    """Raised for general errors from the PiSugar module."""
    pass

class PiSugarAlarm:
    """
    A class to manage PiSugar3 alarm programming, including network connectivity
    checks, RTC synchronization, and alarm setting.
    """

    # Class-level constants for network check
    _defaultPingUrl = "http://clients3.google.com/generate_204"

    def __init__(self, pingUrl: str = None):
        """
        Initializes the PiSugarAlarm instance.

        Args:
            pingUrl (str, optional): URL to ping for network connectivity.
                                      Defaults to _defaultPingUrl if None.
        """
        self.pingUrl = pingUrl if pingUrl else self._defaultPingUrl
        self.pisugar = None
        self.connection = None 
        self.eventConnection = None
        
        # Set up logging for the class instance
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s') 
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"{self.__class__.__name__}: Initializing PiSugarAlarm.")

    @staticmethod
    def _isOnline(url: str) -> bool:
        """
        Internal static method to test network connectivity.
        Args:
            url (str): The URL to ping.
        Returns:
            bool: True if online, False otherwise.
        """
        try:
            response = requests.get(url, timeout=5)
            return response.status_code == 204
        except requests.exceptions.RequestException as e:
            logging.error(f"Network check failed for {url}: {e}")
            return False

    @staticmethod
    def _calculateFutureAlarmDatetime(baseDatetime: datetime, secondsInFuture: int) -> datetime:
        """
        Internal static method to calculate a future datetime by adding a specified
        number of seconds to a given base datetime.

        Args:
            baseDatetime (datetime): The starting datetime (e.g., current RTC time),
                                      preferably timezone-aware.
            secondsInFuture (int): The number of seconds from the baseDatetime
                                     to set the alarm.
        Returns:
            datetime: The calculated future datetime object, retaining timezone information.
        Raises:
            ValueError: If secondsInFuture is not a non-negative integer.
        """
        if not isinstance(secondsInFuture, int) or secondsInFuture < 0:
            raise ValueError("secondsInFuture must be a non-negative integer.")
        return baseDatetime + timedelta(seconds=secondsInFuture)

    def _connectToPiSugar(self):
        """
        Establishes connection to the PiSugar server.
        Raises:
            PiSugarConnectionError: If connection fails.
        """
        self.logger.info("Attempting to connect to PiSugar server...")
        try:
            self.connection, self.eventConnection = connect_tcp()
            self.pisugar = PiSugarServer(self.connection, self.eventConnection)
            self.logger.info("Successfully connected to PiSugar server.")
        except Exception as e: 
            raise PiSugarConnectionError(
                f"Failed to connect to PiSugar: {e}. "
                "Please ensure pisugar-server is running and you have permissions (try with 'sudo')."
            )

    def _syncRtc(self, initialRtcTime: datetime):
        """
        Synchronizes the RTC clock to the Raspberry Pi's system time.
        Args:
            initialRtcTime (datetime): The RTC time before synchronization.
        """
        self.logger.info("Syncing RTC clock to Pi...")
        try:
            self.pisugar.rtc_pi2rtc()
            self.logger.info("RTC clock sync initiated.")
        except Exception as e: 
            self.logger.warning(
                f"Warning: RTC clock sync might have failed: {e}. "
                "Please ensure pisugar-server is running and you have permissions (try with 'sudo')."
            )
            # Do not exit here, attempt to proceed with potentially unsynced RTC time
        
        try:
            rtcDatetimeAfterSync = self.pisugar.get_rtc_time() 
            self.logger.info(
                f"{rtcDatetimeAfterSync} - RTC clock synced to Pi, "
                f"previous time was {initialRtcTime}"
            )
        except Exception as e: 
            raise PiSugarError(
                f"Error getting RTC time after sync from PiSugar: {e}. "
                "Please ensure pisugar-server is running and you have permissions (try with 'sudo')."
            )
        return rtcDatetimeAfterSync

    def setAlarm(self, secondsInFuture: int): 
        """
        Main method to set the PiSugar alarm.

        Args:
            secondsInFuture (int): The number of seconds from the current RTC time
                                     to set the alarm.
        """
        self.logger.info(f"{self.__class__.__name__}: Starting alarm setup.")

        # 1. Check network connectivity
        self.logger.info("Checking network connectivity...")
        while not self._isOnline(self.pingUrl): 
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.error(f"{current_time} - Failed test to {self.pingUrl}, waiting for connectivity")
            time.sleep(5) 
        self.logger.info("Connected.")

        # Connect to PiSugar
        try:
            self._connectToPiSugar() 
        except PiSugarConnectionError as e:
            self.logger.error(f"Connection error: {e}")
            sys.exit(1)

        # Get initial RTC time
        try:
            initialRtcTime = self.pisugar.get_rtc_time() 
            self.logger.info(f"Initial RTC time from PiSugar: {initialRtcTime}")
        except Exception as e: 
            self.logger.error(f"Failed to get initial RTC time from PiSugar: {e}")
            self.logger.error("Please ensure pisugar-server is running and you have permissions (try with 'sudo'). Exiting.")
            sys.exit(1)

        # Sync RTC and get updated time
        try:
            rtcDatetime = self._syncRtc(initialRtcTime) 
        except PiSugarError as e:
            self.logger.error(f"RTC sync error: {e}")
            sys.exit(1)

        # Determine timezone offset for logging
        try:
            localTz = datetime.now(pytz.utc).astimezone().tzinfo
            timezoneOffsetSeconds = localTz.utcoffset(datetime.now()).total_seconds() 
            hours = int(timezoneOffsetSeconds // 3600)
            minutes = int((timezoneOffsetSeconds % 3600) // 60)
            timezoneOffset = f"{'+' if hours >= 0 else '-'}{abs(hours):02d}:{abs(minutes):02d}" 
        except Exception as e:
            self.logger.error(f"Could not determine timezone offset: {e}. Defaulting to +00:00.")
            timezoneOffset = "+00:00"

        # Calculate future alarm datetime
        nextAlarmDatetime = None 
        try:
            nextAlarmDatetime = self._calculateFutureAlarmDatetime(rtcDatetime, secondsInFuture) 
            self.logger.info(f"Calculated next alarm (in {secondsInFuture} seconds): {nextAlarmDatetime.isoformat()}") 
        except ValueError as e:
            self.logger.error(f"Error calculating future alarm time: {e}. Exiting.")
            sys.exit(1)

        # Set the alarm using PiSugar
        if nextAlarmDatetime:
            nextAlarmFormatted = nextAlarmDatetime.strftime("%Y-%m-%dT%H:%M:%S") + timezoneOffset 
            self.logger.info(f"Final next alarm for PiSugar: {nextAlarmFormatted}")
            
            try:
                # 127 means repeat every day
                self.pisugar.rtc_alarm_set(nextAlarmDatetime, 127) 
                self.logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Alarm set for [{nextAlarmFormatted}]")
            except Exception as e: # Catching a general exception for alarm setting
                self.logger.error(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Error while setting alarm using PiSugar module: {e}")
                self.logger.error("Please ensure pisugar-server is running and you have permissions (try with 'sudo').")
                sys.exit(1)
        else:
            self.logger.error("Error: Could not determine next alarm time. Exiting.")
            sys.exit(1)

# Example usage:
if __name__ == "__main__":
    # You can customize the ping URL if needed, otherwise it uses the default
    alarmManager = PiSugarAlarm() # Renamed from alarm_manager
    
    # Set the alarm for 800 seconds in the future
    alarmManager.setAlarm(secondsInFuture=800) # Renamed set_alarm and seconds_in_future
