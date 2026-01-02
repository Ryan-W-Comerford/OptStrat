import requests
import yfinance as yf
import random
from datetime import date, timedelta
from app.models.models import OptionContract
from app.data.provider import Provider
from app.config.config import config

class PolygonProvider(Provider):
    def __init__(self, api_key: str):
        self.key = api_key
        self.base = "https://api.polygon.io"
        self._earnings_cache = {}
        self.lookups = 0
        self.MAX_YAHOO_LOOKUPS = 5

    def get_stocks(self) -> list[str]:
        return config.STOCKS

    def get_upcoming_earnings(self, within_days: int):
        today = date.today()
        end = today + timedelta(days=within_days)

        upcoming = []

        random_stocks = random.sample(self.get_stocks(), 5)

        for ticker in random_stocks:
            if self.lookups >= self.MAX_YAHOO_LOOKUPS:
                break

            earnings_date = self._get_cached_earnings_date(ticker)
            self.lookups += 1

            if not earnings_date:
                continue

            if today <= earnings_date <= end:
                upcoming.append({
                    "ticker": ticker,
                    "date": earnings_date
                })

        return upcoming

    def _get_cached_earnings_date(self, ticker: str):
        if ticker in self._earnings_cache:
            return self._earnings_cache[ticker]

        try:
            stock = yf.Ticker(ticker)
            cal = stock.calendar

            if cal is None or cal.empty:
                self._earnings_cache[ticker] = None
                return None

            earnings_date = cal.loc["Earnings Date"][0]

            if hasattr(earnings_date, "date"):
                earnings_date = earnings_date.date()

            self._earnings_cache[ticker] = earnings_date
            return earnings_date
        except Exception as e:
            self._earnings_cache[ticker] = None
            return None

    def get_stock_price(self, ticker: str) -> float:
        r = requests.get(
            f"{self.base}/v2/aggs/ticker/{ticker}/prev",
            params={"apiKey": self.key}
        ).json()
        return r["results"][0]["c"]

    def get_option_chain(self, ticker: str):
        r = requests.get(
            f"{self.base}/v3/reference/options/contracts",
            params={
                "apiKey": self.key,
                "underlying_ticker": ticker,
                "limit": 1000
            }
        ).json()

        chain = []
        for c in r.get("results", []):
            g = c.get("greeks")
            if not g:
                continue

            chain.append(OptionContract(
                symbol=c["ticker"],
                strike=c["strike_price"],
                expiration=date.fromisoformat(c["expiration_date"]),
                option_type=c["contract_type"],
                delta=g.get("delta", 0),
                theta=g.get("theta", 0),
                vega=g.get("vega", 0),
                iv=c.get("implied_volatility", 0),
            ))
        return chain

    def get_historical_iv(self, ticker: str, start: date, end: date):
        r = requests.get(
            f"{self.base}/v2/aggs/ticker/{ticker}/range/1/day/{start}/{end}",
            params={"apiKey": self.key}
        ).json()

        return [
            abs(x["h"] - x["l"]) / x["o"]
            for x in r.get("results", [])
        ]

    def get_iv_rank(self, iv_series: list[float], current_iv: float) -> float:
        low, high = min(iv_series), max(iv_series)
        return 100 * (current_iv - low) / (high - low) if high != low else 50