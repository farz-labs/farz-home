import sys
import logging
from pathlib import Path
from datetime import datetime
from loguru import logger as _loguru_logger


def _tui_sink(message):
    """Custom sink for TUI buffer integration."""
    try:
        from interfaces.tui import is_tui_active, add_log_to_buffer

        if is_tui_active():
            record = message.record
            formatted = f"{record['message']}"
            add_log_to_buffer(formatted)
    except (ImportError, Exception):
        pass


class InterceptHandler(logging.Handler):
    """Intercept standard logging and redirect to Loguru."""

    def emit(self, record: logging.LogRecord):
        try:
            level = _loguru_logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        frame, depth = sys._getframe(6), 6
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        _loguru_logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# Remove default handler
_loguru_logger.remove()

# Console output
_loguru_logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> - <level>{message}</level>",
    level="INFO",
    colorize=True,
)

# File output with rotation
logs_dir = Path("logs")
logs_dir.mkdir(exist_ok=True)
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
_loguru_logger.add(
    logs_dir / f"session_{timestamp}.log",
    rotation="100 MB",
    retention="7 days",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function} - {message}",
)

# TUI sink
_loguru_logger.add(_tui_sink, level="INFO", format="{message}")


# Patch Loguru logger to handle keyword arguments like log_with_tui did
class LoggerWrapper:
    """Wrapper to add keyword argument support to Loguru."""

    def __init__(self, logger_instance):
        self._logger = logger_instance

    def _format_message(self, msg: str, **kwargs) -> str:
        """Format message with keyword arguments."""
        if kwargs:
            ctx = " ".join(f"{k}={v}" for k, v in kwargs.items())
            return f"{msg} {ctx}"
        return msg

    def info(self, msg: str, **kwargs):
        self._logger.info(self._format_message(msg, **kwargs))

    def error(self, msg: str, **kwargs):
        self._logger.error(self._format_message(msg, **kwargs))

    def warning(self, msg: str, **kwargs):
        self._logger.warning(self._format_message(msg, **kwargs))

    def debug(self, msg: str, **kwargs):
        self._logger.debug(self._format_message(msg, **kwargs))

    def critical(self, msg: str, **kwargs):
        self._logger.critical(self._format_message(msg, **kwargs))

    def __getattr__(self, name):
        """Forward other attributes to original logger."""
        return getattr(self._logger, name)


# Replace logger with wrapped version
logger = LoggerWrapper(_loguru_logger)

# Setup stdlib logging to use Loguru
logging.basicConfig(handlers=[InterceptHandler()], level=logging.INFO)

for logger_name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
    logging.getLogger(logger_name).handlers = [InterceptHandler()]
