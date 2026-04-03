import logging
from unittest.mock import MagicMock, patch

from pyinkdisplay.logging_config import setup_logging


def test_setup_logging_console_calls_basicConfig():
    """Console backend calls logging.basicConfig with INFO level."""
    with patch("pyinkdisplay.logging_config.logging.basicConfig") as mock_config:
        setup_logging({"backend": "console", "level": "INFO"})
    mock_config.assert_called_once()
    call_kwargs = mock_config.call_args[1]
    assert call_kwargs["level"] == logging.INFO


def test_setup_logging_defaults_to_console():
    """Empty config dict uses console backend at INFO level."""
    with patch("pyinkdisplay.logging_config.logging.basicConfig") as mock_config:
        setup_logging({})
    mock_config.assert_called_once()


def test_setup_logging_syslog_adds_handler():
    """Syslog backend adds a SysLogHandler to the root logger."""
    with patch(
        "pyinkdisplay.logging_config.logging.handlers.SysLogHandler"
    ) as mock_handler_cls, \
         patch("pyinkdisplay.logging_config.logging.getLogger") as mock_get_logger:
        mock_root = MagicMock()
        mock_get_logger.return_value = mock_root
        mock_handler_cls.return_value = MagicMock()

        setup_logging({
            "backend": "syslog",
            "level": "WARNING",
            "syslog": {"host": "logserver.local", "port": "514"},
        })

    mock_handler_cls.assert_called_once_with(address=("logserver.local", 514))
    mock_root.addHandler.assert_called_once()
    mock_root.setLevel.assert_called_once_with(logging.WARNING)


def test_setup_logging_loki_falls_back_to_console():
    """Loki backend logs a warning and falls back to console."""
    with patch("pyinkdisplay.logging_config.logging.basicConfig") as mock_config, \
         patch("pyinkdisplay.logging_config.logging.warning") as mock_warning:
        setup_logging({"backend": "loki"})
    mock_config.assert_called_once()
    mock_warning.assert_called_once()
