# src/daily_reporter.py

import pandas as pd
from datetime import date
from src.system_logger import SystemLogger


class FXDailyReporter:
    """日次データの検証・整形およびテキストレポート生成クラス"""

    def __init__(self, logger: SystemLogger):
        self.logger = logger

    def extract_verified_full_day(self, df_accumulated: pd.DataFrame, target_date: date, pair_label: str = "") -> pd.DataFrame:
        """
        指定日(target_date)のデータを抽出し、検証済みのデータフレームを返す
        """
        if df_accumulated.empty:
            return pd.DataFrame()

        # 日付フィルタリング
        df_day = df_accumulated[df_accumulated.index.date == target_date].sort_index()

        if df_day.empty:
            self.logger.warning(
                "データ抽出失敗",
                f"[{pair_label}] 指定日[{target_date}] のデータが存在しません。"
            )
            return pd.DataFrame()

        return df_day

    def generate_report_text(self, df_day: pd.DataFrame, pair_name: str) -> str:
        """
        抽出された日次データから基本数値レポートテキストを生成
        """
        if df_day.empty:
            return f"【{pair_name}】データが存在しません。"

        open_price = df_day["open"].iloc[0]
        high_price = df_day["high"].max()
        low_price = df_day["low"].min()
        close_price = df_day["close"].iloc[-1]
        
        change = close_price - open_price
        change_pips = change * 100 if "JPY" in pair_name or "円" in pair_name else change * 10000

        report = (
            f"📊 **【日次確定レポート】{pair_name}**\n"
            f"・始値 (Open): {open_price:.3f}\n"
            f"・高値 (High): {high_price:.3f}\n"
            f"・安値 (Low): {low_price:.3f}\n"
            f"・終値 (Close): {close_price:.3f}\n"
            f"・日中変動: {change_pips:+.1f} pips"
        )
        return report
