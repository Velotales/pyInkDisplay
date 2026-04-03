"""
Apprise notification wrapper for pyInkDisplay.

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

Sends push notifications to a local Apprise container for key events
(errors, updates applied, low battery). Silent no-op when not configured.
"""

import logging
from typing import Optional

import requests  # type: ignore[import-untyped]

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
