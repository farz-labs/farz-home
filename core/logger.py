import sys
import logging
import structlog

from structlog.stdlib import BoundLogger
from structlog.types import EventDict

from interfaces.tui import is_tui_active, add_log_to_buffer


def tui_aware_console_renderer(logger, method_name, event_dict: EventDict) -> EventDict:
    try:
        if is_tui_active():
            return {}
    except (ImportError, Exception):
        pass
    return event_dict


def log_with_tui(level: str, event: str, **context):
    try:
        if is_tui_active():
            if context:
                formatted = (
                    f"{event}: {', '.join(f'{k}={v}' for k, v in context.items())}"
                )
            else:
                formatted = event
            add_log_to_buffer(formatted)
    except (ImportError, Exception):
        pass


def setup_logger(level: int = logging.INFO) -> BoundLogger:
    """
    Configures a hybrid logger:
    - Pretty colors/formatting for humans (Console)
    - JSON for machines (when not in a terminal)
    """

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

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=level,
    )

    return structlog.get_logger()


app_logger: BoundLogger = setup_logger()
