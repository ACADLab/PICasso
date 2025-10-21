# picasso/utils/env.py
"""Environment loader for PICasso.

This module attempts to load a `.env` file from the current working directory
(or any parent) using `python-dotenv`. If the package isn't installed, it
silently no-ops so PICasso still works with regular environment variables.
"""
from __future__ import annotations
from typing import Optional

def load_env(dotenv_path: Optional[str] = None) -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
    except Exception:
        return  # optional dependency not installed; ignore
    if dotenv_path:
        load_dotenv(dotenv_path)
    else:
        load_dotenv()  # default: find .env in CWD / parents