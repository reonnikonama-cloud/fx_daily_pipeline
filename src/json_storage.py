# src/json_storage.py

import json
import os
import pandas as pd


class JSONStorage:
    """ローカルJSONファイルへのデータ保存・管理・読み込みクラス"""

    def __init__(self, base_dir: str = "data"):
        self.base_dir = base_dir

    def save_pair_data(self, symbol: str, data: list) -> bool:
        """fetch_data_main.py との互換用メソッド（リスト形式のデータを受け取って追記）"""
        if not data:
            return False

        success = True
        # リスト型で渡された場合、各レコードを append_raw_ticker へ渡す
        if isinstance(data, list):
            for item in data:
                res = self.append_raw_ticker(symbol, item)
                if not res:
                    success = False
        elif isinstance(data, dict):
            success = self.append_raw_ticker(symbol, data)

        return success

    def append_raw_ticker(self, symbol: str, ticker_data: dict) -> bool:
        """APIから取得した Ticker 生データ（dict）に JST 変換を施し data.json へ追記"""
        if not ticker_data:
            return False

        pair_dir = os.path.join(self.base_dir, symbol)
        os.makedirs(pair_dir, exist_ok=True)
        json_path = os.path.join(pair_dir, "data.json")

        # UTCタイムスタンプから JST 日時文字列(YYYY-MM-DDTHH:MM:SS)を生成
        raw_ts = ticker_data.get("timestamp", "")
        if raw_ts:
            try:
                dt_utc = pd.to_datetime(raw_ts, utc=True)
                dt_jst = dt_utc.tz_convert("Asia/Tokyo")
                ticker_data["timestamp_jst"] = dt_jst.strftime("%Y-%m-%dT%H:%M:%S")
                current_ym = dt_jst.strftime("%Y-%m")
            except Exception:
                current_ym = raw_ts[:7] if raw_ts else ""
        else:
            current_ym = ""

        existing_records = []
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                try:
                    existing_records = json.load(f)
                except json.JSONDecodeError:
                    existing_records = []

        # 月次自動リセット判定 (JST 基準の YYYY-MM で判定)
        if existing_records and current_ym:
            last_record = existing_records[-1]
            last_ts = last_record.get("timestamp_jst") or last_record.get("timestamp", "")
            last_ym = last_ts[:7] if last_ts else ""

            if last_ym and last_ym != current_ym:
                print(f"[{symbol}] JST基準での月の更新を検知 ({last_ym} -> {current_ym})。今月分用に data.json を初期化します。")
                existing_records = []

        # 重複追記防止 (timestamp 比較)
        existing_timestamps = {r.get("timestamp") for r in existing_records}
        if raw_ts not in existing_timestamps:
            existing_records.append(ticker_data)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(existing_records, f, ensure_ascii=False, indent=2)
            print(f"[{symbol}] 生データを追記完了 (JST: {ticker_data.get('timestamp_jst', raw_ts)}) / 当月蓄積本数: {len(existing_records)}本")
        else:
            print(f"[{symbol}] 既に同一時刻データが存在するためスキップ ({raw_ts})")

        return True

    def load_pair_data(self, symbol: str) -> pd.DataFrame:
        """data/{symbol}/data.json を読み込み、JST 基準の DatetimeIndex を持つ DataFrame に整形"""
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

        # timestamp_jst が存在すれば優先利用、なければ UTC の timestamp から JST へ変換
        if "timestamp_jst" in df.columns:
            df["Datetime"] = pd.to_datetime(df["timestamp_jst"]).dt.tz_localize("Asia/Tokyo")
        else:
            df["Datetime"] = pd.to_datetime(df["timestamp"], utc=True, errors="coerce")
            df = df[df["Datetime"].notnull()]
            df["Datetime"] = df["Datetime"].dt.tz_convert("Asia/Tokyo")

        df.dropna(subset=["Datetime"], inplace=True)
        df.set_index("Datetime", inplace=True)

        # 数値型へ変換
        df["bid"] = df["bid"].astype(float)
        df["ask"] = df["ask"].astype(float)

        # チャート・レポート互換用カラム (Close/Open/High/Low)
        df["Close"] = df["bid"]
        df["Open"] = df["bid"]
        df["High"] = df["bid"]
        df["Low"] = df["bid"]

        return df
