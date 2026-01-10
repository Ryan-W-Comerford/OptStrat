from app.data.massive import MassiveProvider

class Strategy:
    def generate_candidates(self, provider: MassiveProvider):
        raise NotImplementedError

    def simulate_trade(self, provider: MassiveProvider, candidate):
        raise NotImplementedError