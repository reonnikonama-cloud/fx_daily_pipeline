# src/json_storage.py

import json
import os
import pandas as pd


class JSONStorage:
    """ローカルJSONファイルへのデータ保存・管理・読み込みクラス"""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir

    def append_raw_ticker(self, symbol: str, ticker_data: dict) -> bool:
        """APIから取得した Ticker 生データ（dict）をそのまま data.json へ追記"""
        if not ticker_data:
            return False

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

        # 月次自動リセット判定 (timestamp の先頭 YYYY-MM で比較)
        current_ts = ticker_data.get("timestamp", "")
        current_ym = current_ts[:7] if current_ts else ""

        if existing_records and current_ym:
            last_record_ts = existing_records[-1].get("timestamp", "")
            if last_record_ts and last_record_ts[:7] != current_ym:
                print(f"[{symbol}] 月の更新を検知 ({last_record_ts[:7]} -> {current_ym})。今月分用に data.json を初期化します。")
                existing_records = []

        # 重複追記防止 (タイムスタンプ比較)
        existing_timestamps = {r.get("timestamp") for r in existing_records}
        if current_ts not in existing_timestamps:
            existing_records.append(ticker_data)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(existing_records, f, ensure_ascii=False, indent=2)
            print(f"[{symbol}] 生データを追記完了 ({current_ts}) / 当月蓄積本数: {len(existing_records)}本")
        else:
            print(f"[{symbol}] 既に同一時刻データが存在するためスキップ ({current_ts})")

        return True

    def load_pair_data(self, symbol: str) -> pd.DataFrame:
        """data/{symbol}/data.json を読み込み、レポート・チャート用の DataFrame に整形"""
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

        # utc=True を指定して UTC DatetimeIndex として変換（FutureWarningおよびtzエラーの回避）
        df["Datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
        df.dropna(subset=["Datetime"], inplace=True)
        df.set_index("Datetime", inplace=True)

        # JST（日本標準時）へ変換
        df.index = df.index.tz_convert("Asia/Tokyo")

        # 数値型へ変換
        df["bid"] = df["bid"].astype(float)
        df["ask"] = df["ask"].astype(float)

        # チャート・レポート互換用カラム (Close/Open/High/Low)
        df["Close"] = df["bid"]
        df["Open"] = df["bid"]
        df["High"] = df["bid"]
        df["Low"] = df["bid"]

        return df
