# src/json_storage.py

import json
import os
import pandas as pd


class JSONStorage:
    """ローカルJSONファイルへのデータ保存・管理・読み込みクラス"""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir

    def append_pair_data(self, symbol: str, df_pair: pd.DataFrame) -> bool:
        """指定シンボルの最新1行を抽出して data.json へ追記（月更新時の自動初期化含む）"""
        if df_pair.empty:
            return False

        latest_row = df_pair.iloc[-1:]
        latest_dt = latest_row.index[0]

        # タイムゾーンを Asia/Tokyo に統一
        if latest_dt.tzinfo is not None:
            latest_dt = latest_dt.tz_convert("Asia/Tokyo")
        else:
            latest_dt = latest_dt.tz_localize("UTC").tz_convert("Asia/Tokyo")

        latest_ts = latest_dt.strftime("%Y-%m-%d %H:%M:%S")
        current_ym = latest_dt.strftime("%Y-%m")

        new_record = {
            "timestamp": latest_ts,
            "open": float(latest_row["Open"].iloc[0]),
            "high": float(latest_row["High"].iloc[0]),
            "low": float(latest_row["Low"].iloc[0]),
            "close": float(latest_row["Close"].iloc[0]),
            "volume": int(latest_row["Volume"].iloc[0]) if "Volume" in latest_row else 0,
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

        # 月次自動リセット判定
        if existing_records:
            last_record_ts = existing_records[-1].get("timestamp", "")
            if last_record_ts and last_record_ts[:7] != current_ym:
                print(f"[{symbol}] 月の更新を検知 ({last_record_ts[:7]} -> {current_ym})。今月分用に data.json を初期化します。")
                existing_records = []

        existing_timestamps = {r["timestamp"] for r in existing_records}
        if new_record["timestamp"] not in existing_timestamps:
            existing_records.append(new_record)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(existing_records, f, ensure_ascii=False, indent=2)
            print(f"[{symbol}] 最新データを追記完了 ({latest_ts}) / 当月蓄積本数: {len(existing_records)}本")
        else:
            print(f"[{symbol}] 既に同一時刻データが存在するためスキップ ({latest_ts})")

        return True

    def load_pair_data(self, symbol: str) -> pd.DataFrame:
        """data/{symbol}/data.json を読み込んで DataFrame 化"""
        json_path = os.path.join(self.base_dir, symbol, "data.json")
        if not os.path.exists(json_path):
            return pd.DataFrame()

        with open(json_path, "r", encoding="utf-8") as f:
            try:
                records = json.load(f)
            except json.JSONDecodeError:
                return pd.DataFrame()

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
