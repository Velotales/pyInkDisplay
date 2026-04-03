import logging
from unittest.mock import MagicMock, patch

from pyinkdisplay.pyLoggingConfig import setupLogging


def test_setup_logging_console_calls_basicConfig():
    """Console backend calls logging.basicConfig with INFO level."""
    with patch("pyinkdisplay.pyLoggingConfig.logging.basicConfig") as mock_config:
        setupLogging({"backend": "console", "level": "INFO"})
    mock_config.assert_called_once()
    call_kwargs = mock_config.call_args[1]
    assert call_kwargs["level"] == logging.INFO


def test_setup_logging_defaults_to_console():
    """Empty config dict uses console backend at INFO level."""
    with patch("pyinkdisplay.pyLoggingConfig.logging.basicConfig") as mock_config:
        setupLogging({})
    mock_config.assert_called_once()


def test_setup_logging_syslog_adds_handler():
    """Syslog backend adds a SysLogHandler to the root logger."""
    with patch(
        "pyinkdisplay.pyLoggingConfig.logging.handlers.SysLogHandler"
    ) as mock_handler_cls, \
         patch("pyinkdisplay.pyLoggingConfig.logging.getLogger") as mock_get_logger:
        mock_root = MagicMock()
        mock_get_logger.return_value = mock_root
        mock_handler_cls.return_value = MagicMock()

        setupLogging({
            "backend": "syslog",
            "level": "WARNING",
            "syslog": {"host": "logserver.local", "port": "514"},
        })

    mock_handler_cls.assert_called_once_with(address=("logserver.local", 514))
    mock_root.addHandler.assert_called_once()
    mock_root.setLevel.assert_called_once_with(logging.WARNING)


def test_setup_logging_loki_falls_back_to_console():
    """Loki backend logs a warning and falls back to console."""
    with patch("pyinkdisplay.pyLoggingConfig.logging.basicConfig") as mock_config, \
         patch("pyinkdisplay.pyLoggingConfig.logging.warning") as mock_warning:
        setupLogging({"backend": "loki"})
    mock_config.assert_called_once()
    mock_warning.assert_called_once()


def test_setup_logging_seq_calls_seqlog(monkeypatch):
    """Seq backend calls seqlog.log_to_seq with the configured URL."""
    mock_seqlog = MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "seqlog", mock_seqlog)

    setupLogging({
        "backend": "seq",
        "level": "DEBUG",
        "seq": {"url": "http://seq.local:5341"},
    })

    mock_seqlog.log_to_seq.assert_called_once_with(
        server_url="http://seq.local:5341",
        level=logging.DEBUG,
        override_root_logger=True,
    )


def test_setup_logging_seq_falls_back_when_seqlog_missing():
    """Falls back to console logging when seqlog is not installed."""
    with patch("pyinkdisplay.pyLoggingConfig.logging.basicConfig") as mock_config, \
         patch("builtins.__import__", side_effect=lambda name, *a, **kw: (
             (_ for _ in ()).throw(ImportError())
             if name == "seqlog"
             else __import__(name, *a, **kw)
         )):
        setupLogging({"backend": "seq", "seq": {"url": "http://seq.local:5341"}})
    mock_config.assert_called_once()
