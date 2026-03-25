from __future__ import annotations
from contextlib import contextmanager
from datetime import date, datetime, timedelta

from massive import RESTClient

from app.config.config import config
from app.data.provider import Provider
from app.models.models import OptionContract


class MassiveProvider(Provider):
    def __init__(self, api_key: str):
        self.key = api_key

    @contextmanager
    def get_client(self):
        client = RESTClient(self.key)
        try:
            yield client
        finally:
            if hasattr(client, "close"):
                client.close()

    def get_stock_price(self, ticker: str) -> float:
        with self.get_client() as client:
            snapshot = client.get_snapshot_ticker("stocks", ticker)
            # last_quote/last_trade are None on Stocks Starter — use min.close (most recent minute)
            # then day.close as fallback; both are available on the $29 plan
            price = None
            if snapshot:
                if snapshot.min and snapshot.min.close:
                    price = snapshot.min.close
                elif snapshot.day and snapshot.day.close:
                    price = snapshot.day.close
                elif snapshot.prev_day and snapshot.prev_day.close:
                    price = snapshot.prev_day.close  # market closed / weekend fallback
            if price is None:
                raise ValueError(f"No price available for {ticker}")
            return float(price)

    def get_option_chain(self, ticker: str) -> list[OptionContract]:
        # Fetch only contracts within our DTE window (+/- 5 day buffer)
        # This cuts requests from ~1300 down to ~50-100 per ticker
        today = date.today()
        min_exp = today + timedelta(days=config.TARGET_DTE_RANGE[0] - 5)
        max_exp = today + timedelta(days=config.TARGET_DTE_RANGE[1] + 10)

        chain = []
        with self.get_client() as client:
            for o in client.list_snapshot_options_chain(
                ticker,
                params={
                    "expiration_date.gte": str(min_exp),
                    "expiration_date.lte": str(max_exp),
                    "limit": 250,
                },
            ):
                details = o.details
                greeks = o.greeks
                day = o.day
                last_quote = o.last_quote  # has .bid and .ask

                expiration = details.expiration_date
                if isinstance(expiration, str):
                    expiration = datetime.fromisoformat(expiration).date()
                elif isinstance(expiration, datetime):
                    expiration = expiration.date()

                bid = last_quote.bid if last_quote else 0.0
                ask = last_quote.ask if last_quote else 0.0

                # $29 plan: last_quote is None — fall back to day.close as mid-price
                if bid == 0.0 and ask == 0.0 and day and day.close:
                    mid = float(day.close)
                    bid = mid
                    ask = mid

                chain.append(OptionContract(
                    symbol=details.ticker,
                    strike=details.strike_price,
                    expiration=expiration,
                    option_type=(details.contract_type or "").lower(),
                    delta=float(greeks.delta or 0.0) if greeks else 0.0,
                    theta=float(greeks.theta or 0.0) if greeks else 0.0,
                    vega=float(greeks.vega or 0.0) if greeks else 0.0,
                    iv=float(o.implied_volatility or 0.0),
                    volume=int(day.volume or 0) if day else 0,
                    open_interest=int(o.open_interest or 0),
                    bid=bid or 0.0,
                    ask=ask or 0.0,
                ))
        return chain

    def get_option_day_close(self, option_symbol: str, on_date: date) -> float | None:
        """
        Return the day.close price for an option contract on a given date.
        Uses the daily aggregates endpoint — available on $29 plan.
        Falls back to nearest trading day within 3 days if exact date has no data.
        """
        with self.get_client() as client:
            aggs = list(client.list_aggs(
                option_symbol,
                multiplier=1,
                timespan="day",
                from_=str(on_date),
                to=str(on_date + timedelta(days=3)),
                limit=4,
            ))
        return float(aggs[0].close) if aggs else None

    def get_closing_price(self, ticker: str, on_date: date) -> float | None:
        """Return the closing price on or after on_date (handles weekends/holidays)."""
        with self.get_client() as client:
            aggs = list(client.list_aggs(
                ticker,
                multiplier=1,
                timespan="day",
                from_=str(on_date),
                to=str(on_date + timedelta(days=4)),
                limit=5,
            ))
        return float(aggs[0].close) if aggs else None

    def get_historical_iv(self, ticker: str, start: date, end: date) -> list[float]:
        return self._get_historical_iv_range(ticker, start, end)

    def _get_historical_iv_range(self, ticker: str, start: date, end: date) -> list[float]:
        import math
        closes = []
        with self.get_client() as client:
            for agg in client.list_aggs(
                ticker,
                multiplier=1,
                timespan="day",
                from_=str(start),
                to=str(end),
                limit=50000,
            ):
                if agg.close:
                    closes.append(agg.close)

        if len(closes) < 2:
            return []

        # Annualized realized vol from daily log returns — same scale as options IV (e.g. 0.30 = 30%)
        log_returns = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
        window = 20  # rolling 20-day vol windows
        iv_series = []
        for i in range(window, len(log_returns) + 1):
            sample = log_returns[i - window:i]
            mean = sum(sample) / window
            variance = sum((r - mean) ** 2 for r in sample) / (window - 1)
            iv_series.append(math.sqrt(variance * 252))  # annualize
        return iv_series

    def get_iv_as_of(self, ticker: str, as_of: date):
        """Return the most recent realized IV ending on as_of (20-day window)."""
        from datetime import timedelta
        start = as_of - timedelta(days=60)  # 60 calendar days ensures 20+ trading days
        series = self._get_historical_iv_range(ticker, start, as_of)
        return series[-1] if series else None

    def get_iv_rank(self, iv_series: list[float], current_iv: float) -> float:
        if not iv_series:
            return 50.0
        low, high = min(iv_series), max(iv_series)
        return 100.0 * (current_iv - low) / (high - low) if high != low else 50.0

    def get_upcoming_earnings(self, within_days: int) -> list[dict]:
        raise NotImplementedError("Use AlphaProvider for earnings data")