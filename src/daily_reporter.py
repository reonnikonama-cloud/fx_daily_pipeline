# src/daily_reporter.py

from datetime import date, datetime, timedelta
import pandas as pd
from src.system_logger import SystemLogger


class FXDailyReporter:
    """日次確定データの検証およびサマリーレポート生成"""

    def __init__(self, logger: SystemLogger = None):
        self.logger = logger

    def _get_pair_config(self, pair_name: str) -> tuple[float, int]:
        """通貨ペアに応じた pips 基準値と表示桁数を取得"""
        if "USD" in pair_name and "JPY" not in pair_name:
            # 対米ドル（例: EUR_USD）
            return 0.0001, 5
        # 対円（例: USD_JPY, EUR_JPY, NZD_JPY, CAD_JPY等）
        return 0.01, 3

    def extract_verified_full_day_with_logging(
        self, df: pd.DataFrame, target_date: date = None, pair_label: str = ""
    ) -> pd.DataFrame:
        """00:00 〜 23:55 (288本) の連続性を検証してログ出力しながら抽出"""
        if df.empty:
            if self.logger:
                self.logger.error("データなし", f"[{pair_label}] 入力データフレームが空です。")
            return pd.DataFrame()

        # インデックスが DatetimeIndex でない場合の安全策補正
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, utc=True, errors="coerce")
            df = df[df.index.notnull()]
            df.index = df.index.tz_convert("Asia/Tokyo")

        if target_date is None:
            target_date = (datetime.now() - timedelta(days=1)).date()

        # 日付フィルタリング（DatetimeIndexから安全にdate抽出）
        df_day = df[df.index.date == target_date].sort_index()

        if df_day.empty:
            if self.logger:
                self.logger.warning("対象データなし", f"[{pair_label}] [{target_date}] のデータが存在しません。")
            return pd.DataFrame()

        total_expected = 288
        actual_count = len(df_day)
        _, digits = self._get_pair_config(pair_label)

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

        pips_value, digits = self._get_pair_config(pair_name)

        open_p = float(df_day["Open"].iloc[0])
        high_p = float(df_day["High"].max())
        low_p = float(df_day["Low"].min())
        close_p = float(df_day["Close"].iloc[-1])

        range_pips = (high_p - low_p) / pips_value
        change_pips = (close_p - open_p) / pips_value
        target_date_str = df_day.index[0].strftime("%Y-%m-%d")

        fmt = f"{{:.{digits}f}}"

        return (
            f"📊 **【{pair_name}】日次確定レポート ({target_date_str})**\n"
            f"```text\n"
            f"・始値 (Open)    : {fmt.format(open_p)}\n"
            f"・高値 (High)    : {fmt.format(high_p)}\n"
            f"・安値 (Low)     : {fmt.format(low_p)}\n"
            f"・終値 (Close)   : {fmt.format(close_p)}\n"
            f"----------------------------------------\n"
            f"・日中値幅     : {range_pips:.1f} pips\n"
            f"・前日比変動   : {change_pips:+.1f} pips\n"
            f"```"
        )
