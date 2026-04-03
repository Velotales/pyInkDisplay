"""
Apprise notification wrapper for pyInkDisplay.

Sends push notifications to a local Apprise container for key events
(errors, updates applied, low battery). Silent no-op when not configured.
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)


def sendNotification(apprise_url: str, title: str, message: str) -> bool:
    """
    Send a notification via the Apprise container REST API.

    Args:
        apprise_url (str): Base URL of the Apprise container
            (e.g. 'http://localhost:8000').
        title (str): Notification title.
        message (str): Notification body.

    Returns:
        bool: True on success, False on failure.
    """
    try:
        response = requests.post(
            f"{apprise_url.rstrip('/')}/notify",
            json={"title": title, "body": message},
            timeout=5,
        )
        response.raise_for_status()
        logger.info("Notification sent: %s", title)
        return True
    except requests.exceptions.RequestException as e:
        logger.error("Failed to send notification '%s': %s", title, e)
        return False


def notifyIfConfigured(
    apprise_config: Optional[dict], title: str, message: str
) -> None:
    """
    Send a notification if Apprise is configured; silently skip if not.

    Args:
        apprise_config (dict or None): The 'apprise' config section.
        title (str): Notification title.
        message (str): Notification body.
    """
    if not apprise_config or not apprise_config.get("url"):
        return
    sendNotification(apprise_config["url"], title, message)
