from app.data.massive import MassiveProvider
from app.data.alpha_vantage import AlphaProvider
from app.config.config import config
from app.strategy.iv_straddle import LongStraddleIVStrategy
from app.strategy.strategy import Strategy

strategy_map = {
    "longStraddleIV": LongStraddleIVStrategy
}

class OptionsApp:
    def __init__(self):
        self.polygon_provider = MassiveProvider(config.POLYGON_API_KEY)
        self.alpha_provider = AlphaProvider(config.ALPHA_API_KEY)

    def get_strategy(self, name: str) -> Strategy:
        if name not in strategy_map:
            raise ValueError(
                f"Unknown strategy used '{name}'. "
                "Available: longStraddleIV"
            )
        
        return strategy_map[name]()
