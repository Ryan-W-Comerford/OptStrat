from app.config.config import config

class Provider():
    def __init__(self):
        self.config = config

    def get_stocks(self):
        return config.STOCKS

    def get_upcoming_earnings(self):
        pass

    def get_stock_price(self):
        pass
