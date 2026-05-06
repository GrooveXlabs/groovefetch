"""GrooveFetch — AI-native adaptive web scraper."""

from .core import GrooveFetch
from .schema import Schema
from .fetchers import HTTPFetcher, StealthFetcher

__version__ = "0.1.0"
__all__ = ["GrooveFetch", "Schema", "HTTPFetcher", "StealthFetcher"]
