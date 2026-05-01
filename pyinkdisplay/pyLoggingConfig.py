"""
Configurable logging backends for pyInkDisplay.

MIT License

Copyright (c) 2026 Velotales

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

Supported backends: console (default), seq, syslog.
loki is reserved for future implementation.
"""

import logging
import logging.handlers

_FMT = "%(asctime)s - %(levelname)s - %(module)s:%(funcName)s - %(message)s"


def setupLogging(config: dict) -> None:
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
        _setupSeq(config.get("seq", {}), level)
    elif backend == "syslog":
        _setupSyslog(config.get("syslog", {}), level)
    elif backend == "loki":
        logging.basicConfig(level=level, format=_FMT)
        logging.warning(
            "Loki backend is not yet implemented" " — falling back to console logging."
        )
    else:
        logging.basicConfig(level=level, format=_FMT)
        logging.info("Console logging enabled.")


def _setupSeq(seq_config: dict, level: int) -> None:
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
            "seqlog package not installed" " — falling back to console logging."
        )


def _setupSyslog(syslog_config: dict, level: int) -> None:
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
