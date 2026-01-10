import logging
import sys


class LogsFormatter(logging.Formatter):
    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record):
        # Get original format
        log_message = super().format(record)

        # Add color if in terminal
        if sys.stderr.isatty():
            levelname = record.levelname
            color = self.COLORS.get(levelname, "")
            if color:
                log_message = f"{color}{log_message}{self.RESET}"

        return log_message


def setup_logger(name="AppLogger", level=logging.DEBUG):
    """Create and configure a colorful logger"""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        formatter = LogsFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


app_logger = setup_logger()
