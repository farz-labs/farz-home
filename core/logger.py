import sys
import logging
import structlog
from structlog.stdlib import BoundLogger


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
        processors.append(structlog.dev.ConsoleRenderer(colors=True))
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
