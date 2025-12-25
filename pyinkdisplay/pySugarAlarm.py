"""

MIT License

Copyright (c) 2025 Velotales

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

"""

import logging
import time
from datetime import datetime, timedelta

import pytz
import requests

logger = logging.getLogger(__name__)

# Import the PiSugar module
try:
    from pisugar import PiSugarServer, connect_tcp
except ImportError:
    logger.error("PiSugar module not found. Please ensure 'pisugar' is installed.")

    # Define dummy classes if PiSugar is not available, to allow the code structure to be seen
    # In a real scenario, you'd want to handle this more robustly, perhaps by exiting.
    class PiSugarServer:
        def __init__(self, *args, **kwargs):
            logger.warning("Dummy PiSugarServer initialized. PiSugar module not found.")

        def get_rtc_time(self):
            raise PiSugarConnectionError("PiSugar module not available.")

        def get_battery_power_plugged(self):
            raise PiSugarConnectionError("PiSugar module not available.")

        def rtc_pi2rtc(self):
            raise PiSugarConnectionError("PiSugar module not available.")

        def rtc_alarm_set(self, *args, **kwargs):
            raise PiSugarConnectionError("PiSugar module not available.")

    class connect_tcp:
        def __init__(self, *args, **kwargs):
            logger.warning("Dummy connect_tcp initialized. PiSugar module not found.")

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

    def get_battery_level(self, retries=3, delay=2) -> int:
        """
        Gets the current battery level (percentage) from the PiSugar board.
        Returns:
            int: Battery level percentage (0-100)
        Raises:
            PiSugarConnectionError: If connection to PiSugar cannot be established.
            PiSugarError: If there's an error retrieving battery level from PiSugar.
        """
        lastException = None
        for attempt in range(1, retries + 1):
            try:
                self._ensurePiSugarConnection()
                level = self.pisugar.get_battery_level()
                logger.info("PiSugar battery level: %s%%", level)
                return level
            except PiSugarConnectionError:
                logger.error(
                    (
                        "Cannot check battery level: Not connected to PiSugar. "
                        "Please ensure pisugar-server is running."
                    )
                )
                lastException = PiSugarConnectionError("Not connected to PiSugar.")
            except Exception as e:
                logger.warning(
                    "Attempt %s failed to get battery level from PiSugar: %s",
                    attempt,
                    e,
                )
                lastException = PiSugarError(
                    f"Error getting battery level from PiSugar: {e}"
                )
            if attempt < retries:
                logger.info(
                    "Retrying get_battery_level in %s seconds (attempt %s/%s)...",
                    delay,
                    attempt + 1,
                    retries,
                )
                time.sleep(delay)
        logger.error("get_battery_level failed after %s attempts.", retries)
        raise lastException

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

        logger.info("Initializing PiSugarAlarm.")

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
            logger.error("Network check failed for %s: %s", url, e)
            return False

    @staticmethod
    def _calculateFutureAlarmDatetime(
        baseDatetime: datetime, secondsInFuture: int
    ) -> datetime:
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
        logger.info("Attempting to connect to PiSugar server...")
        try:
            self.connection, self.eventConnection = connect_tcp()
            self.pisugar = PiSugarServer(self.connection, self.eventConnection)
            logger.info("Successfully connected to PiSugar server.")
        except Exception as e:
            raise PiSugarConnectionError(
                (
                    f"Failed to connect to PiSugar: {e}. "
                    "Please ensure pisugar-server is running and you have "
                    "permissions (try with 'sudo')."
                )
            )

    def _syncRtc(self, initialRtcTime: datetime):
        """
        Synchronizes the RTC clock to the Raspberry Pi's system time.
        Args:
            initialRtcTime (datetime): The RTC time before synchronization.
        """
        logger.info("Syncing RTC clock to Pi...")
        try:
            self.pisugar.rtc_pi2rtc()
            logger.info("RTC clock sync initiated.")
        except Exception as e:
            logger.warning(
                (
                    "Warning: RTC clock sync might have failed: %s. "
                    "Please ensure pisugar-server is running and you have "
                    "permissions (try with 'sudo')."
                ),
                e,
            )
        # Do not exit here, attempt to proceed with potentially unsynced RTC time

        try:
            rtcDatetimeAfterSync = self.pisugar.get_rtc_time()
            logger.info(
                "%s - RTC clock synced to Pi, previous time was %s",
                rtcDatetimeAfterSync,
                initialRtcTime,
            )
        except Exception as e:
            raise PiSugarError(
                (
                    f"Error getting RTC time after sync from PiSugar: {e}. "
                    "Please ensure pisugar-server is running and you have permissions "
                    "(try with 'sudo')."
                )
            )
        return rtcDatetimeAfterSync

    def _ensurePiSugarConnection(self):
        """
        Ensures that a connection to the PiSugar server is established.
        If already connected (self.pisugar is not None), does nothing.
        If not, it attempts to establish the connection.
        Raises PiSugarConnectionError if connection fails.
        """
        if self.pisugar is None:
            logger.info(
                "PiSugar connection not established. Attempting to connect now."
            )
            try:
                self._connectToPiSugar()
            except PiSugarConnectionError as e:
                logger.error("Failed to establish PiSugar connection: %s", e)
                raise

    def isSugarPowered(self, retries=3, delay=2) -> bool:
        """
        Checks if the PiSugar is currently plugged into power, with retry logic.
        This method ensures connection to PiSugar before attempting to get status.
        Args:
            retries (int): Number of times to retry on failure.
            delay (int or float): Delay in seconds between retries.
        Returns:
            bool: True if powered (plugged in), False otherwise.
        Raises:
            PiSugarConnectionError: If connection to PiSugar cannot be established.
            PiSugarError: If there's an error retrieving power status from PiSugar.
        """
        lastException = None
        for attempt in range(1, retries + 1):
            try:
                self._ensurePiSugarConnection()
                isPlugged = self.pisugar.get_battery_power_plugged()
                logger.info("PiSugar power plugged status: %s", isPlugged)
                return isPlugged
            except PiSugarConnectionError:
                logger.error(
                    "Cannot check power status: Not connected to PiSugar. "
                    "Please ensure pisugar-server is running."
                )
                lastException = PiSugarConnectionError("Not connected to PiSugar.")
            except Exception as e:
                logger.warning(
                    "Attempt %s failed to get power status from PiSugar: %s",
                    attempt,
                    e,
                )
                lastException = PiSugarError(
                    f"Error getting battery power plugged status from PiSugar: {e}"
                )
            if attempt < retries:
                logger.info(
                    "Retrying isSugarPowered in %s seconds (attempt %s/%s)...",
                    delay,
                    attempt + 1,
                    retries,
                )
                time.sleep(delay)
        # If we reach here, all attempts failed
        logger.error("isSugarPowered failed after %s attempts.", retries)
        raise lastException

    def setAlarm(self, secondsInFuture: int):
        """
        Main method to set the PiSugar alarm.

        Args:
            secondsInFuture (int): The number of seconds from the current RTC time
                                   to set the alarm.
        """
        logger.info("Starting alarm setup.")

        # 1. Check network connectivity
        logger.info("Checking network connectivity...")
        while not self._isOnline(self.pingUrl):
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            logger.error(
                "%s - Failed test to %s, waiting for connectivity",
                current_time,
                self.pingUrl,
            )
            time.sleep(5)

        # Ensure connection to PiSugar
        try:
            self._ensurePiSugarConnection()
        except PiSugarConnectionError as e:
            logger.error("Connection error during alarm setup: %s", e)
            raise PiSugarError(f"Failed to connect to PiSugar: {e}")

        # Get initial RTC time
        try:
            initialRtcTime = self.pisugar.get_rtc_time()
            logger.info("Initial RTC time from PiSugar: %s", initialRtcTime)
        except Exception as e:
            logger.error(f"Failed to get initial RTC time from PiSugar: {e}")
            logger.error(
                "Please ensure pisugar-server is running and you have permissions."
            )
            logger.error("Try running with 'sudo'. Exiting.")
            raise PiSugarError(f"Failed to set RTC time: {e}")

        # Sync RTC and get updated time
        try:
            rtcDatetime = self._syncRtc(initialRtcTime)
        except PiSugarError as e:
            logger.error("RTC sync error: %s", e)
            raise PiSugarError(f"Failed to sync RTC time: {e}")

        # Determine timezone offset for logging
        try:
            localTz = datetime.now(pytz.utc).astimezone().tzinfo
            timezoneOffsetSeconds = localTz.utcoffset(datetime.now()).total_seconds()
            hours = int(timezoneOffsetSeconds // 3600)
            minutes = int((timezoneOffsetSeconds % 3600) // 60)
            timezoneOffset = (
                f"{'+' if hours >= 0 else '-'}{abs(hours):02d}:{abs(minutes):02d}"
            )
        except Exception as e:
            logger.error(
                "Could not determine timezone offset: %s. Defaulting to +00:00.",
                e,
            )
            timezoneOffset = "+00:00"

        # Calculate future alarm datetime
        nextAlarmDatetime = None
        try:
            nextAlarmDatetime = self._calculateFutureAlarmDatetime(
                rtcDatetime, secondsInFuture
            )
            logger.info(
                "Calculated next alarm (in %s seconds): %s",
                secondsInFuture,
                nextAlarmDatetime.isoformat(),
            )
        except ValueError as e:
            logger.error(f"Error calculating future alarm time: {e}. Exiting.")
            raise PiSugarError(f"Failed to set future calculate alarm time: {e}")

        # Set the alarm using PiSugar
        if nextAlarmDatetime:
            nextAlarmFormatted = (
                nextAlarmDatetime.strftime("%Y-%m-%dT%H:%M:%S") + timezoneOffset
            )

            try:
                # 127 means repeat every day
                self.pisugar.rtc_alarm_set(nextAlarmDatetime, 127)
                nowStr = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info("%s - Alarm set for [%s]", nowStr, nextAlarmFormatted)
            except Exception as e:  # Catching a general exception for alarm setting
                nowStr = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.error(
                    "%s - Error while setting alarm using PiSugar module: %s",
                    nowStr,
                    e,
                )
                logger.error(
                    "Please ensure pisugar-server is running and you have permissions."
                )
                logger.error("Try running with 'sudo'.")
                raise PiSugarError(f"Failed to set next alarm: {e}")
        else:
            logger.error("Error: Could not determine next alarm time. Exiting.")
            raise PiSugarError(
                "Failed to set next alarm time: Could not determine next alarm datetime."
            )
