import yaml
import os

class Config():
    secrets_path = os.environ.get("SECRETS_FILE_PATH")
    with open(secrets_path) as file:
        key_file = yaml.safe_load(file)

    POLYGON_API_KEY = key_file["POLYGON_API_KEY"]

    # High Beta S&P 500 stocks that are liquid and not high option pricing
    STOCKS = [
        "AMD",
        "TSM",
        "INTC",
        "CRM",
        "ADBE",
        "ORCL",
        "NOW",
        "META",
        "NFLX",
        "AMZN",
        "EBAY",
        "SQ",
        "PYPL",
        "COIN",
        "MU",
        "QCOM",
        "AVGO",
        "BA",
        "CAT",
        "DE",
        "UNH",
        "ABBV",
        "MRK",
        "XOM",
        "CVX",
        "SLB"
    ]

    EARNINGS_LOOKAHEAD_DAYS = 30
    TARGET_DTE_RANGE = (20, 40)

    MIN_IV_RANK = 40
    MAX_ENTRY_IV_RANK = 70
    EXIT_IV_RANK = 80

    MIN_VEGA_THETA_RATIO = 4
    ATM_DELTA_RANGE = (0.40, 0.60)

    MIN_OPTION_VOLUME = 100
    MIN_OPEN_INTEREST = 500
    MAX_BID_ASK_SPREAD_PCT = 0.05

    EXIT_DAYS_BEFORE_EARNINGS = 2
    TARGET_PNL = 0.30

config = Config()