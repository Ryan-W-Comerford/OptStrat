import os

import yaml


class Config:
    def __init__(self):
        secrets_path = os.environ.get("SECRETS_FILE_PATH")
        if not secrets_path:
            raise EnvironmentError("SECRETS_FILE_PATH environment variable is not set")
        if not os.path.exists(secrets_path):
            raise FileNotFoundError(f"Secrets file not found: {secrets_path}")

        with open(secrets_path) as f:
            key_file = yaml.safe_load(f)

        self.MASSIVE_API_KEY: str = key_file["MASSIVE_API_KEY"]
        self.ALPHA_API_KEY: str = key_file["ALPHA_API_KEY"]
        self.ANTHROPIC_API_KEY: str = key_file.get("ANTHROPIC_API_KEY", "")

        # High-beta S&P 500 stocks with liquid options and reliable IV expansion into earnings.
        # Criteria: beta > 1.2, avg options volume > 10k/day, quarterly earnings cadence.
        # Sorted by tier — Tier 1 are the highest-conviction names for this strategy.
        self.STOCKS: list[str] = [
            # --- Tier 1: Mega-cap tech (highest options volume, most reliable IV expansion) ---
            "NVDA", "TSLA", "AAPL", "META", "AMZN", "GOOGL", "MSFT",

            # --- Tier 1: Semiconductors (earnings binary, huge IV swings) ---
            "AMD", "MU", "AVGO", "QCOM", "TSM", "LRCX", "MRVL",

            # --- Tier 1: Software / SaaS (consistent IV run-up into earnings) ---
            "CRM", "ADBE", "NOW", "ORCL", "SNOW",

            # --- Tier 1: Cybersecurity (high-beta, growth-multiple names) ---
            "CRWD", "PANW",

            # --- Tier 1: Fintech / Crypto (volatile, earnings-driven) ---
            "COIN", "SQ", "PYPL",

            # --- Tier 1: High-beta growth (strong earnings reactions) ---
            "NFLX", "UBER", "PLTR",

            # --- Tier 2: Industrials / Financials (lower IV but solid liquidity) ---
            "BA", "GS", "UNH", "CAT",

            # --- Tier 2: Lower-beta semis (still liquid, lower IV expansion) ---
            "INTC",

            # --- Tier 3: Lower-beta (marginal for straddles — use ivRankScreen to time) ---
            "ABBV", "MRK", "XOM", "CVX", "EBAY",
        ]

        self.EARNINGS_LOOKAHEAD_DAYS: int = 55
        self.TARGET_DTE_RANGE: tuple[int, int] = (15, 50)

        self.MIN_IV_RANK: float = 30.0
        self.MAX_ENTRY_IV_RANK: float = 80.0
        self.EXIT_IV_RANK: float = 85.0

        self.MIN_VEGA_THETA_RATIO: float = 0.0  # disabled — unreliable with delayed greeks
        self.ATM_DELTA_RANGE: tuple[float, float] = (0.35, 0.65)

        self.MIN_OPTION_VOLUME: int = 50
        self.MIN_OPEN_INTEREST: int = 250
        self.MAX_BID_ASK_SPREAD_PCT: float = 0.15

        self.EXIT_DAYS_BEFORE_EARNINGS: int = 1
        self.TARGET_PNL: float = 0.30

        # Trade history DB — SQLite, auto-created on first run. Set TRADE_DB_PATH in secrets.yaml
        self.TRADE_DB_PATH: str = key_file.get("TRADE_DB_PATH", "app/data/history/trades.db")


config = Config()
# NOTE: appending TRADE_DB_PATH — paste into Config.__init__ before config = Config()