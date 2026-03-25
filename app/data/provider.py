from __future__ import annotations
from abc import ABC, abstractmethod


class Provider(ABC):
    """Abstract base class for all data providers."""

    @abstractmethod
    def get_stock_price(self, ticker: str) -> float:
        pass

    @abstractmethod
    def get_upcoming_earnings(self, within_days: int) -> list[dict]:
        pass

    def get_option_day_close(self, option_symbol: str, on_date) -> float | None:
        """Return day.close for an option on a given date. Optional — not all providers support this."""
        return None