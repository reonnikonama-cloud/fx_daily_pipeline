# src/daily_reporter.py

from datetime import date, datetime, timedelta
import pandas as pd
from src.system_logger import SystemLogger


class FXDailyReporter:
    """日次確定データの検証およびサマリーレポート生成"""

    def __init__(self, pips_value: float = 0.01, logger: SystemLogger = None):
        self.pips_value = pips_value
        self.logger = logger

    def extract_verified_full_day_with_logging(
        self, df: pd.DataFrame, target_date: date = None, pair_label: str = ""
    ) -> pd.DataFrame:
        """00:00 〜 23:55 (288本) の連続性を検証してログ出力しながら抽出"""
        if df.empty:
            if self.logger:
                self.logger.error("データなし", f"[{pair_label}] 入力データフレームが空です。")
            return pd.DataFrame()

        if target_date is None:
            target_date = (datetime.now() - timedelta(days=1)).date()

        df_day = df[df.index.date == target_date].sort_index()
        if df_day.empty:
            if self.logger:
                self.logger.warning("対象データなし", f"[{pair_label}] [{target_date}] のデータが存在しません。")
            return pd.DataFrame()

        total_expected = 288
        actual_count = len(df_day)

        if self.logger:
            self.logger.info(
                "検証開始",
                f"[{pair_label}] [{target_date}] のデータ検証を開始します（全{total_expected}本を順次確認）。",
            )

        for idx, (timestamp, row) in enumerate(df_day.iterrows(), start=1):
            time_str = timestamp.strftime("%H:%M")
            close_price = float(row["Close"])
            if self.logger:
                self.logger.progress(
                    current_count=idx,
                    total_count=total_expected,
                    timestamp_str=time_str,
                    price=close_price,
                    pair_label=pair_label,
                )

        start_time = df_day.index[0].strftime("%H:%M")
        end_time = df_day.index[-1].strftime("%H:%M")

        if start_time == "00:00" and end_time == "23:55" and actual_count == total_expected:
            if self.logger:
                self.logger.info(
                    "完全取得完了",
                    f"[{pair_label}] [{target_date}] 00:00〜23:55 全288本の正常検証が完了しました。",
                )
            return df_day
        else:
            if self.logger:
                self.logger.warning(
                    "データ不完全停止",
                    f"[{pair_label}] [{target_date}] データの途絶を検知しました。"
                    f"取得数: {actual_count}/288 (開始: {start_time}, 最終: {end_time})。",
                )
            return pd.DataFrame()

    def generate_report_text(self, df_day: pd.DataFrame, pair_name: str = "") -> str:
        """日次確定データから送信用テキストを生成"""
        if df_day.empty:
            return ""

        open_p = float(df_day["Open"].iloc[0])
        high_p = float(df_day["High"].max())
        low_p = float(df_day["Low"].min())
        close_p = float(df_day["Close"].iloc[-1])

        range_pips = (high_p - low_p) / self.pips_value
        change_pips = (close_p - open_p) / self.pips_value
        target_date_str = df_day.index[0].strftime("%Y-%m-%d")

        return (
            f"📊 **【{pair_name}】日次確定レポート ({target_date_str})**\n"
            f"```text\n"
            f"・始値 (Open)   : {open_p:.3f}\n"
            f"・高値 (High)   : {high_p:.3f}\n"
            f"・安値 (Low)    : {low_p:.3f}\n"
            f"・終値 (Close)  : {close_p:.3f}\n"
            f"----------------------------------------\n"
            f"・日中値幅     : {range_pips:.1f} pips\n"
            f"・前日比変動   : {change_pips:+.1f} pips\n"
            f"```"
        )
