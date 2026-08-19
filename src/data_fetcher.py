# src/data_fetcher.py

import time
import requests
import pandas as pd


class FXDataFetcher:
    """GMOコイン Public API からの FX データ取得モジュール"""

    BASE_URL = "https://forex-api.coin.z.com/public/v1"

    DEFAULT_PAIRS = {
        "USD_JPY": "USD_JPY",
        "EUR_JPY": "EUR_JPY",
        "GBP_JPY": "GBP_JPY",
        "AUD_JPY": "AUD_JPY",
        "CHF_JPY": "CHF_JPY",
        "EUR_USD": "EUR_USD",
    }

    def __init__(self, pairs: dict = None):
        self.pairs = pairs if pairs else self.DEFAULT_PAIRS

    def fetch_tickers(self, max_retries: int = 3) -> pd.DataFrame:
        """6通貨ペアのリアルタイムレート（Ticker）を取得"""
        url = f"{self.BASE_URL}/ticker"

        for attempt in range(1, max_retries + 1):
            try:
                res = requests.get(url, timeout=10)
                res.raise_for_status()
                data = res.json()

                if data.get("status") == 0:
                    tickers = data.get("data", [])
                    df = pd.DataFrame(tickers)

                    target_symbols = list(self.pairs.values())
                    df_filtered = df[df["symbol"].isin(target_symbols)].copy()

                    return df_filtered
                else:
                    print(f"APIエラー: {data.get('messages')}")

            except Exception as e:
                print(f"Ticker取得エラー ({attempt}/{max_retries}): {e}")

            time.sleep(attempt * 2)

        return pd.DataFrame()

    def fetch_bulk_data_with_retry(self, max_retries: int = 5) -> pd.DataFrame:
        """Tickerデータ（現在価格情報）を一括取得して返すラッパー"""
        print("GMOコイン APIよりデータ一括取得中...")
        return self.fetch_tickers(max_retries=max_retries)

    def fetch_all_orderbooks(self) -> pd.DataFrame:
        """FX APIには板情報がないため空のDataFrameを返す"""
        return pd.DataFrame()


if __name__ == "__main__":
    fetcher = FXDataFetcher()
    df = fetcher.fetch_bulk_data_with_retry()
    print(df)
