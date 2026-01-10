from datetime import date, timedelta, datetime
from app.models.models import OptionContract
from app.data.provider import Provider
from massive import RESTClient
from contextlib import contextmanager

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
            quote = client.quote(ticker)
            return float(quote["last"])

    def get_option_chain(self, ticker: str):
        chain = []
        with self.get_client() as client:
            for o in client.options_contracts(ticker):
                expiration = o.get("expirationDate")
                if isinstance(expiration, str):
                    expiration = datetime.fromisoformat(expiration).date()
                elif isinstance(expiration, datetime):
                    expiration = expiration.date()

                greeks = o.get("greeks") or {}

                chain.append(OptionContract(
                    symbol=o.get("symbol"),
                    strike=o.get("strikePrice"),
                    expiration=expiration,
                    option_type=o.get("type").lower(), 
                    delta=greeks.get("delta", 0),
                    theta=greeks.get("theta", 0),
                    vega=greeks.get("vega", 0),
                    iv=o.get("impliedVolatility", 0),
                ))

        return chain

    def get_historical_iv(self, ticker: str, start: date, end: date):
        iv_series = []
        with self.get_client() as client:
            for agg in client.aggregates(ticker, "1d", start=start, end=end):
                h, l, o = agg["high"], agg["low"], agg["open"]
                if o != 0:
                    iv_series.append(abs(h - l) / o)

        return iv_series

    def get_iv_rank(self, iv_series: list[float], current_iv: float) -> float:
        low, high = min(iv_series), max(iv_series)
        return 100 * (current_iv - low) / (high - low) if high != low else 50
