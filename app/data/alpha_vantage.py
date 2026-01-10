import os
import csv
import requests
from datetime import date, datetime, timedelta
from app.data.provider import Provider

class AlphaProvider(Provider):
    CACHE_FILE = "app/data/cache/earnings_cache.csv"

    def __init__(self, av_api_key: str):
        self.av_api_key = av_api_key
        self.EARNINGS_URL = f'https://www.alphavantage.co/query?function=EARNINGS_CALENDAR&horizon=3month&apikey={self.av_api_key}'

    def get_upcoming_earnings(self, within_days: int):
        upcoming = []
        today = date.today()
        end = today + timedelta(days=within_days)

        if os.path.exists(self.CACHE_FILE):
            with open(self.CACHE_FILE, newline='') as f:
                cr = csv.DictReader(f)
                for row in cr:
                    ticker = row.get('symbol')
                    earnings_date = row.get('reportDate')

                    if not ticker or not earnings_date:
                        continue

                    edate = datetime.fromisoformat(earnings_date).date()

                    if today <= edate <= end:
                        upcoming.append({
                            "ticker": ticker,
                            "date": edate
                        })
            return upcoming

        with requests.Session() as s:
            r = s.get(self.EARNINGS_URL)
            decoded_content = r.content.decode('utf-8')
            cr = csv.DictReader(decoded_content.splitlines())

            with open(self.CACHE_FILE, "w", newline='') as f:
                writer = csv.DictWriter(f, fieldnames=cr.fieldnames)
                writer.writeheader()

                for row in cr:
                    writer.writerow(row)

                    ticker = row.get('symbol')
                    earnings_date = row.get('reportDate')

                    if not ticker or not earnings_date:
                        continue

                    edate = datetime.fromisoformat(earnings_date).date()

                    if today <= edate <= end:
                        upcoming.append({
                            "ticker": ticker,
                            "date": edate
                        })

        return upcoming
