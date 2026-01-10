from app.data.massive import MassiveProvider
from app.data.alpha_vantage import AlphaProvider
from app.strategy.strategy import Strategy
from app.models.models import StraddleCandidate
from app.config.config import config
from datetime import date, timedelta

class LongStraddleIVStrategy(Strategy):
    def generate_candidates(self, polygon_provider: MassiveProvider, alpha_provider: AlphaProvider):
        candidates = []
        for e in alpha_provider.get_upcoming_earnings(config.EARNINGS_LOOKAHEAD_DAYS):
            ticker, edate = e["ticker"], e["date"]
            print(f"Trying {ticker}...")

            spot = polygon_provider.get_stock_price(ticker)
            chain = polygon_provider.get_option_chain(ticker)

            calls, puts = [], []
            for o in chain:
                dte = (o.expiration - date.today()).days
                if config.TARGET_DTE_RANGE[0] <= dte <= config.TARGET_DTE_RANGE[1]:
                    if abs(o.strike - spot) / spot < 0.02:
                        (calls if o.option_type == "call" else puts).append(o)

            if not calls or not puts:
                continue

            call = min(calls, key=lambda x: abs(x.delta - 0.5))
            put = min(puts, key=lambda x: abs(x.delta + 0.5))

            theta = abs(call.theta + put.theta)
            if theta == 0:
                continue

            if (call.vega + put.vega) / theta < config.MIN_VEGA_THETA_RATIO:
                continue

            iv_hist = polygon_provider.get_historical_iv(ticker, date.today()-timedelta(days=252), date.today())
            iv_rank = polygon_provider.get_iv_rank(iv_hist, call.iv)

            if not (config.MIN_IV_RANK <= iv_rank <= config.MAX_ENTRY_IV_RANK):
                continue

            candidates.append(StraddleCandidate(ticker, edate, call, put, iv_rank))

        return candidates

