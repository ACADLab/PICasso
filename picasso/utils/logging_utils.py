"""Opinionated logging setup for PICasso."""
import logging
import os
from typing import Optional

_DEFAULT_LEVEL = os.getenv("PICASSO_LOGLEVEL", "INFO").upper()

def configure_logging(level: Optional[str] = None) -> None:
    """Configure the root logger with our standard format."""
    level_name = (level or _DEFAULT_LEVEL).upper()
    logging.basicConfig(
        level=getattr(logging, level_name, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
