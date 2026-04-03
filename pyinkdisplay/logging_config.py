"""
Configurable logging backends for pyInkDisplay.

Supported backends: console (default), seq, syslog.
loki is reserved for future implementation.
"""

import logging
import logging.handlers

_FMT = "%(asctime)s - %(levelname)s - %(module)s:%(funcName)s - %(message)s"


def setup_logging(config: dict) -> None:
    """
    Configure the root logger from the 'logging' section of config.yaml.

    Args:
        config (dict): The 'logging' config section, e.g.
            {
                "backend": "syslog",
                "level": "INFO",
                "syslog": {"host": "...", "port": 514},
            }
    """
    backend = config.get("backend", "console")
    level_name = config.get("level", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    if backend == "seq":
        _setup_seq(config.get("seq", {}), level)
    elif backend == "syslog":
        _setup_syslog(config.get("syslog", {}), level)
    elif backend == "loki":
        logging.basicConfig(level=level, format=_FMT)
        logging.warning(
            "Loki backend is not yet implemented"
            " — falling back to console logging."
        )
    else:
        logging.basicConfig(level=level, format=_FMT)
        logging.info("Console logging enabled.")


def _setup_seq(seq_config: dict, level: int) -> None:
    """Configure Seq structured logging via the seqlog package."""
    try:
        import seqlog  # type: ignore[import-untyped]

        seqlog.log_to_seq(
            server_url=seq_config.get("url", "http://localhost:5341"),
            level=level,
            override_root_logger=True,
        )
        logging.info("Seq logging enabled.")
    except ImportError:
        logging.basicConfig(level=level, format=_FMT)
        logging.warning(
            "seqlog package not installed"
            " — falling back to console logging."
        )


def _setup_syslog(syslog_config: dict, level: int) -> None:
    """Configure remote syslog via SysLogHandler."""
    handler = logging.handlers.SysLogHandler(
        address=(
            syslog_config.get("host", "localhost"),
            int(syslog_config.get("port", 514)),
        )
    )
    handler.setFormatter(logging.Formatter(_FMT))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    logging.info("Syslog logging enabled.")
