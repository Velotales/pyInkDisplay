from unittest.mock import MagicMock, patch

from pyinkdisplay.notifications import notify_if_configured, send_notification


def test_send_notification_posts_to_apprise():
    """POSTs title and body to the Apprise /notify endpoint."""
    with patch("pyinkdisplay.notifications.requests.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        mock_post.return_value.raise_for_status = MagicMock()
        result = send_notification(
            "http://apprise.local:8000", "Test Title", "Test body"
        )
    mock_post.assert_called_once_with(
        "http://apprise.local:8000/notify",
        json={"title": "Test Title", "body": "Test body"},
        timeout=5,
    )
    assert result is True


def test_send_notification_returns_false_on_request_error():
    """Returns False when the HTTP request fails."""
    import requests as req

    with patch(
        "pyinkdisplay.notifications.requests.post",
        side_effect=req.exceptions.ConnectionError("refused"),
    ):
        result = send_notification("http://apprise.local:8000", "Title", "Body")
    assert result is False


def test_notify_if_configured_sends_when_url_present():
    """Calls send_notification when apprise_config contains a url."""
    with patch(
        "pyinkdisplay.notifications.send_notification"
    ) as mock_send:
        notify_if_configured(
            {"url": "http://apprise.local:8000"}, "Title", "Body"
        )
    mock_send.assert_called_once_with("http://apprise.local:8000", "Title", "Body")


def test_notify_if_configured_skips_when_no_config():
    """Does nothing when apprise_config is None."""
    with patch(
        "pyinkdisplay.notifications.send_notification"
    ) as mock_send:
        notify_if_configured(None, "Title", "Body")
    mock_send.assert_not_called()


def test_notify_if_configured_skips_when_url_missing():
    """Does nothing when apprise_config has no url key."""
    with patch(
        "pyinkdisplay.notifications.send_notification"
    ) as mock_send:
        notify_if_configured({}, "Title", "Body")
    mock_send.assert_not_called()
