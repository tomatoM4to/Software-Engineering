import logging
import os

from rich.console import Console
from rich.highlighter import RegexHighlighter
from rich.logging import RichHandler
from rich.theme import Theme


class LogCategoryFilter(logging.Filter):
    """Attach a category tag to each log record based on logger name."""

    def filter(self, record: logging.LogRecord) -> bool:
        source = " ".join(
            [
                record.name,
                getattr(record, "module", ""),
                getattr(record, "pathname", ""),
                record.getMessage(),  # Include the actual log message
            ]
        ).lower()

        if "auth" in source:
            record.category_tag = "[AUTH]"
        elif "scheduler" in source or "ohlcv" in source:
            record.category_tag = "[SCHED]"
        else:
            record.category_tag = "[APP]"
        return True


class LogCategoryHighlighter(RegexHighlighter):
    """Highlight category tags in different colors."""

    base_style = "logging.category."
    highlights = [
        r"(?P<auth_tag>\[AUTH\])",
        r"(?P<sched_tag>\[SCHED\])",
        r"(?P<app_tag>\[APP\])",
    ]


def setup_logging() -> None:
    """Configure root logger with Rich handler for better readability."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    console = Console(
        stderr=True,
        theme=Theme(
            {
                "logging.category.auth_tag": "bold bright_cyan",
                "logging.category.sched_tag": "bold bright_green",
                "logging.category.app_tag": "dim white",
            }
        ),
    )
    handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        highlighter=LogCategoryHighlighter(),
        show_time=True,
        show_level=True,
        show_path=True,
    )
    handler.addFilter(LogCategoryFilter())
    handler.setFormatter(logging.Formatter("%(category_tag)s %(message)s"))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)