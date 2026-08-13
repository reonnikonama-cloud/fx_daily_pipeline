# src/data_fetcher.py

import time
import pandas as pd
import yfinance as yf


class FXDataFetcher:
    """Yahoo Finance からの FX データ取得モジュール"""

    def __init__(self, pairs: dict):
        self.pairs = pairs

    def fetch_bulk_data_with_retry(self, max_retries: int = 5) -> pd.DataFrame:
        """Rate Limit (429) 回避を考慮した一括取得"""
        ticker_symbols = list(self.pairs.values())

        for attempt in range(1, max_retries + 1):
            try:
                print(f"データ一括取得試行中... ({attempt}/{max_retries})")
                bulk_df = yf.download(
                    tickers=ticker_symbols,
                    period="1d",
                    interval="5m",
                    group_by="ticker",
                    progress=False,
                )

                if not bulk_df.empty:
                    return bulk_df

            except Exception as e:
                print(f"取得エラー発生 ({attempt}/{max_retries}): {e}")

            wait_time = attempt * 10
            print(f"429回避のため {wait_time} 秒待機して再試行します...")
            time.sleep(wait_time)

        return pd.DataFrame()

    def extract_pair_df(self, bulk_df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """一括取得DataFrameから特定シンボルのデータフレームを切り出す"""
        if bulk_df.empty:
            return pd.DataFrame()

        if isinstance(bulk_df.columns, pd.MultiIndex) and symbol in bulk_df.columns.levels[0]:
            return bulk_df[symbol].copy().dropna(subset=["Close"])
        elif not isinstance(bulk_df.columns, pd.MultiIndex):
            return bulk_df.copy().dropna(subset=["Close"])

        return pd.DataFrame()
