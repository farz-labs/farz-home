import sys
import logging
from pathlib import Path
from datetime import datetime
import structlog
from structlog.stdlib import BoundLogger
from structlog.types import EventDict
from interfaces.tui import is_tui_active, add_log_to_buffer

# Session log file path
_session_log_file = None


def _get_session_log_path() -> Path:
    """Generate a unique log file path for this session."""
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return logs_dir / f"session_{timestamp}.log"


def _init_session_log_file():
    """Initialize the session log file on first use."""
    global _session_log_file
    if _session_log_file is None:
        _session_log_file = _get_session_log_path()


def tui_aware_console_renderer(logger, method_name, event_dict: EventDict) -> EventDict:
    try:
        if is_tui_active():
            return {}
    except (ImportError, Exception):
        pass
    return event_dict


def log_with_tui(level: str, event: str, **context):
    """Log to TUI buffer and also save to session log file."""
    _init_session_log_file()

    # Format the log message
    if context:
        formatted = f"{event}: {', '.join(f'{k}={v}' for k, v in context.items())}"
    else:
        formatted = event

    # Add timestamp for file logging
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    file_log_entry = f"[{timestamp}] [{level.upper()}] {formatted}\n"

    # Write to session log file
    try:
        with open(_session_log_file, "a", encoding="utf-8") as f:
            f.write(file_log_entry)
    except Exception as e:
        print(f"Failed to write to log file: {e}", file=sys.stderr)

    # Send to TUI if active
    try:
        if is_tui_active():
            add_log_to_buffer(formatted)
    except (ImportError, Exception):
        pass


def setup_logger(level: int = logging.INFO) -> BoundLogger:
    """
    Configures a hybrid logger:
    - Pretty colors/formatting for humans (Console)
    - JSON for machines (when not in a terminal)
    - File logging for each session
    """
    _init_session_log_file()

    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="%H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if sys.stderr.isatty():
        processors.extend(
            [
                tui_aware_console_renderer,
                structlog.dev.ConsoleRenderer(colors=True),
            ]
        )
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Create handlers separately
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))

    file_handler = logging.FileHandler(_session_log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter("%(message)s"))

    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=[console_handler, file_handler],
    )

    return structlog.get_logger()


app_logger: BoundLogger = setup_logger()
