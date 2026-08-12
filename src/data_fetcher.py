import json
import os
import time
import pandas as pd
import yfinance as yf


class FXDataFetcher:

    def __init__(self, pairs: dict, base_dir: str = "data"):
        self.pairs = pairs
        self.base_dir = base_dir

    def fetch_bulk_data_with_retry(self, max_retries: int = 5) -> pd.DataFrame:
        """429エラー(Rate Limit)対策を入れた一括取得"""
        ticker_symbols = list(self.pairs.values())

        for attempt in range(1, max_retries + 1):
            try:
                print(
                    f"データ一括取得試行中... ({attempt}/{max_retries})"
                )
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
            print(
                f"429回避のため {wait_time} 秒待機して再試行します..."
            )
            time.sleep(wait_time)

        return pd.DataFrame()

    def append_latest_data_to_json(self, bulk_df: pd.DataFrame) -> bool:
        """最新の1本を追記保存（月が変わった場合は既存構成を崩さず自動リセットして今月分を開始）"""
        if bulk_df.empty:
            return False

        saved_any = False

        for pair_name, symbol in self.pairs.items():
            try:
                if (
                    isinstance(bulk_df.columns, pd.MultiIndex)
                    and symbol in bulk_df.columns.levels[0]
                ):
                    df_pair = bulk_df[symbol].copy().dropna(subset=["Close"])
                elif not isinstance(bulk_df.columns, pd.MultiIndex):
                    df_pair = bulk_df.copy().dropna(subset=["Close"])
                else:
                    continue

                if df_pair.empty:
                    continue

                latest_row = df_pair.iloc[-1:]

                # タイムゾーンを Asia/Tokyo に変換
                latest_dt = latest_row.index[0]
                if latest_dt.tzinfo is not None:
                    latest_dt = latest_dt.tz_convert("Asia/Tokyo")
                else:
                    latest_dt = latest_dt.tz_localize("UTC").tz_convert(
                        "Asia/Tokyo"
                    )

                latest_ts = latest_dt.strftime("%Y-%m-%d %H:%M:%S")
                current_ym = latest_dt.strftime("%Y-%m")  # 例: "2026-08"

                new_record = {
                    "timestamp": latest_ts,
                    "open": float(latest_row["Open"].iloc[0]),
                    "high": float(latest_row["High"].iloc[0]),
                    "low": float(latest_row["Low"].iloc[0]),
                    "close": float(latest_row["Close"].iloc[0]),
                    "volume": (
                        int(latest_row["Volume"].iloc[0])
                        if "Volume" in latest_row
                        else 0
                    ),
                }

                pair_dir = os.path.join(self.base_dir, symbol)
                os.makedirs(pair_dir, exist_ok=True)
                json_path = os.path.join(pair_dir, "data.json")

                existing_records = []
                if os.path.exists(json_path):
                    with open(json_path, "r", encoding="utf-8") as f:
                        try:
                            existing_records = json.load(f)
                        except json.JSONDecodeError:
                            existing_records = []

                # --- 【新規機能：月次自動リセット】 ---
                # 既存データ内に古い月（例: 7月）のデータが残っている状態で新しい月（8月）に入った場合、
                # 既存構成（data/通貨ペア/data.json）を崩さずにリストを空にして今月分を新規作成
                if existing_records:
                    last_record_ts = existing_records[-1].get("timestamp", "")
                    if last_record_ts:
                        last_ym = last_record_ts[:7]  # "YYYY-MM"
                        if last_ym != current_ym:
                            print(
                                f"[{symbol}] 月の更新を検知 ({last_ym} -> {current_ym})。今月分データを新規蓄積するため data.json を初期化します。"
                            )
                            existing_records = []

                existing_timestamps = {
                    r["timestamp"] for r in existing_records
                }
                if new_record["timestamp"] not in existing_timestamps:
                    existing_records.append(new_record)

                    with open(json_path, "w", encoding="utf-8") as f:
                        json.dump(
                            existing_records, f, ensure_ascii=False, indent=2
                        )

                    print(
                        f"[{symbol}] 最新データを追記完了 ({latest_ts}) / 当月蓄積本数: {len(existing_records)}本"
                    )
                else:
                    print(
                        f"[{symbol}] 既に同一時刻データ存在のためスキップ ({latest_ts})"
                    )

                saved_any = True

            except Exception as e:
                print(f"JSON追記処理エラー ({symbol}): {e}")

        return saved_any

    def load_pair_data_from_json(self, symbol: str) -> pd.DataFrame:
        """data/{symbol}/data.json からデータを読み込んで DataFrame 化"""
        json_path = os.path.join(self.base_dir, symbol, "data.json")

        if not os.path.exists(json_path):
            return pd.DataFrame()

        with open(json_path, "r", encoding="utf-8") as f:
            records = json.load(f)

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)
        df["Datetime"] = pd.to_datetime(df["timestamp"])
        df.set_index("Datetime", inplace=True)
        df.rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            },
            inplace=True,
        )
        return df
