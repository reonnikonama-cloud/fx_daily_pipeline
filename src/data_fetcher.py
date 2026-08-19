# src/data_fetcher.py

import time
import requests
import pandas as pd


class FXDataFetcher:
    """GMOコイン Public API からの FX/板データ取得モジュール"""

    BASE_URL = "https://forex-api.coin.z.com/public/v1"

    # デフォルトの対象6通貨ペア
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

                    # 指定された6通貨ペアに絞り込み
                    target_symbols = list(self.pairs.values())
                    df_filtered = df[df["symbol"].isin(target_symbols)].copy()

                    return df_filtered
                else:
                    print(f"APIエラー: {data.get('messages')}")

            except Exception as e:
                print(f"Ticker取得エラー ({attempt}/{max_retries}): {e}")

            time.sleep(attempt * 2)

        return pd.DataFrame()

    def fetch_orderbook(self, symbol: str) -> dict:
        """
        指定した通貨ペアの板情報（Orderbook）を取得し、
        買板・売板の比率（Bid/Ask Ratio）を計算する
        """
        url = f"{self.BASE_URL}/orderbooks?symbol={symbol}"

        try:
            res = requests.get(url, timeout=10)
            res.raise_for_status()
            data = res.json()

            if data.get("status") != 0:
                return {}

            asks = data["data"]["asks"]  # 売り注文
            bids = data["data"]["bids"]  # 買い注文

            total_ask_size = sum(float(item["size"]) for item in asks)
            total_bid_size = sum(float(item["size"]) for item in bids)
            total_size = total_ask_size + total_bid_size

            bid_ratio = round((total_bid_size / total_size) * 100, 2) if total_size > 0 else 50.0
            ask_ratio = round((total_ask_size / total_size) * 100, 2) if total_size > 0 else 50.0

            return {
                "symbol": symbol,
                "best_bid": float(bids[0]["price"]) if bids else 0.0,
                "best_ask": float(asks[0]["price"]) if asks else 0.0,
                "bid_size_total": total_bid_size,
                "ask_size_total": total_ask_size,
                "bid_ratio": bid_ratio,
                "ask_ratio": ask_ratio,
                "sentiment": "買優勢" if bid_ratio > 55 else ("売優勢" if ask_ratio > 55 else "拮抗"),
            }

        except Exception as e:
            print(f"[{symbol}] Orderbook取得エラー: {e}")
            return {}

    def fetch_all_orderbooks(self) -> pd.DataFrame:
        """全対象通貨ペアの板情報を一括取得してデータフレーム化"""
        orderbooks = []
        for symbol in self.pairs.values():
            ob = self.fetch_orderbook(symbol)
            if ob:
                orderbooks.append(ob)
            time.sleep(0.1)  # API負荷軽減用のわずかなウェイト

        return pd.DataFrame(orderbooks)


# テスト実行用
if __name__ == "__main__":
    fetcher = FXDataFetcher()

    print("=== Ticker 取得テスト ===")
    tickers_df = fetcher.fetch_tickers()
    print(tickers_df[["symbol", "bid", "ask", "high", "low"]])

    print("\n=== Orderbook 需給分析取得テスト ===")
    orderbook_df = fetcher.fetch_all_orderbooks()
    print(orderbook_df[["symbol", "best_bid", "best_ask", "bid_ratio", "ask_ratio", "sentiment"]])
