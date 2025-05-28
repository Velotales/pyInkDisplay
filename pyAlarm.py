import requests
import time
import sys
from datetime import datetime, timedelta
import pytz
import logging

# Import the PiSugar module - assuming it's installed and available
# If these imports cause issues, ensure the pisugar library is correctly set up.
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
            return None, None # Return dummy connections
    
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
    _DEFAULT_PING_URL = "http://clients3.google.com/generate_204"

    def __init__(self, ping_url: str = None):
        """
        Initializes the PiSugarAlarm instance.

        Args:
            ping_url (str, optional): URL to ping for network connectivity.
                                      Defaults to _DEFAULT_PING_URL if None.
        """
        self.ping_url = ping_url if ping_url else self._DEFAULT_PING_URL
        self.pisugar = None
        self.conn = None
        self.event_conn = None
        
        # Set up logging for the class instance
        logging.basicConfig(level=logging.INFO,
                            format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s') # Added %(funcName)s
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"{self.__class__.__name__}: Initializing PiSugarAlarm.")

    @staticmethod
    def _is_online(url: str) -> bool:
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
    def _calculate_future_alarm_datetime(base_datetime: datetime, seconds_in_future: int) -> datetime:
        """
        Internal static method to calculate a future datetime by adding a specified
        number of seconds to a given base datetime.

        Args:
            base_datetime (datetime): The starting datetime (e.g., current RTC time),
                                      preferably timezone-aware.
            seconds_in_future (int): The number of seconds from the base_datetime
                                     to set the alarm.
        Returns:
            datetime: The calculated future datetime object, retaining timezone information.
        Raises:
            ValueError: If seconds_in_future is not a non-negative integer.
        """
        if not isinstance(seconds_in_future, int) or seconds_in_future < 0:
            raise ValueError("seconds_in_future must be a non-negative integer.")
        return base_datetime + timedelta(seconds=seconds_in_future)

    def _connect_to_pisugar(self):
        """
        Establishes connection to the PiSugar server.
        Raises:
            PiSugarConnectionError: If connection fails.
        """
        self.logger.info("Attempting to connect to PiSugar server...")
        try:
            self.conn, self.event_conn = connect_tcp()
            self.pisugar = PiSugarServer(self.conn, self.event_conn)
            self.logger.info("Successfully connected to PiSugar server.")
        except Exception as e: # Catching a general exception for connection issues
            raise PiSugarConnectionError(
                f"Failed to connect to PiSugar: {e}. "
                "Please ensure pisugar-server is running and you have permissions (try with 'sudo')."
            )

    def _sync_rtc(self, initial_rtc_time: datetime):
        """
        Synchronizes the RTC clock to the Raspberry Pi's system time.
        Args:
            initial_rtc_time (datetime): The RTC time before synchronization.
        """
        self.logger.info("Syncing RTC clock to Pi...")
        try:
            self.pisugar.rtc_pi2rtc()
            self.logger.info("RTC clock sync initiated.")
        except Exception as e: # Catching a general exception for sync issues
            self.logger.warning(
                f"Warning: RTC clock sync might have failed: {e}. "
                "Please ensure pisugar-server is running and you have permissions (try with 'sudo')."
            )
            # Do not exit here, attempt to proceed with potentially unsynced RTC time
        
        try:
            rtc_datetime_after_sync = self.pisugar.get_rtc_time()
            self.logger.info(
                f"{rtc_datetime_after_sync} - RTC clock synced to Pi, "
                f"previous time was {initial_rtc_time}"
            )
        except Exception as e: # Catching a general exception for getting RTC time
            raise PiSugarError(
                f"Error getting RTC time after sync from PiSugar: {e}. "
                "Please ensure pisugar-server is running and you have permissions (try with 'sudo')."
            )
        return rtc_datetime_after_sync

    def set_alarm(self, seconds_in_future: int):
        """
        Main method to set the PiSugar alarm.

        Args:
            seconds_in_future (int): The number of seconds from the current RTC time
                                     to set the alarm.
        """
        self.logger.info(f"{self.__class__.__name__}: Starting alarm setup.")

        # 1. Check network connectivity
        self.logger.info("Checking network connectivity...")
        while not self._is_online(self.ping_url):
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.logger.error(f"{current_time} - Failed test to {self.ping_url}, waiting for connectivity")
            time.sleep(5) # Wait a bit before retrying
        self.logger.info("Connected.")

        # 2. Connect to PiSugar
        try:
            self._connect_to_pisugar()
        except PiSugarConnectionError as e:
            self.logger.error(f"Connection error: {e}")
            sys.exit(1)

        # 3. Get initial RTC time
        try:
            initial_rtc_time = self.pisugar.get_rtc_time()
            self.logger.info(f"Initial RTC time from PiSugar: {initial_rtc_time}")
        except Exception as e: # Catching a general exception for initial RTC time
            self.logger.error(f"Failed to get initial RTC time from PiSugar: {e}")
            self.logger.error("Please ensure pisugar-server is running and you have permissions (try with 'sudo'). Exiting.")
            sys.exit(1)

        # 4. Sync RTC and get updated time
        try:
            rtc_datetime = self._sync_rtc(initial_rtc_time)
        except PiSugarError as e:
            self.logger.error(f"RTC sync error: {e}")
            sys.exit(1)

        # 5. Determine timezone offset for logging
        try:
            local_tz = datetime.now(pytz.utc).astimezone().tzinfo
            timezone_offset_seconds = local_tz.utcoffset(datetime.now()).total_seconds()
            hours = int(timezone_offset_seconds // 3600)
            minutes = int((timezone_offset_seconds % 3600) // 60)
            timezone_offset = f"{'+' if hours >= 0 else '-'}{abs(hours):02d}:{abs(minutes):02d}"
        except Exception as e:
            self.logger.error(f"Could not determine timezone offset: {e}. Defaulting to +00:00.")
            timezone_offset = "+00:00"

        # 6. Calculate future alarm datetime
        next_alarm_datetime = None
        try:
            next_alarm_datetime = self._calculate_future_alarm_datetime(rtc_datetime, seconds_in_future)
            self.logger.info(f"Calculated next alarm (in {seconds_in_future} seconds): {next_alarm_datetime.isoformat()}")
        except ValueError as e:
            self.logger.error(f"Error calculating future alarm time: {e}. Exiting.")
            sys.exit(1)

        # 7. Set the alarm using PiSugar
        if next_alarm_datetime:
            next_alarm_formatted = next_alarm_datetime.strftime("%Y-%m-%dT%H:%M:%S") + timezone_offset
            self.logger.info(f"Final next alarm for PiSugar: {next_alarm_formatted}")
            
            try:
                # 127 means repeat every day
                self.pisugar.rtc_alarm_set(next_alarm_datetime, 127) 
                self.logger.info(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Alarm set for [{next_alarm_formatted}]")
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
    alarm_manager = PiSugarAlarm() 
    
    # Set the alarm for 800 seconds in the future
    alarm_manager.set_alarm(seconds_in_future=800) 
