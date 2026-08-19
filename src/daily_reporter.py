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
            return 0.0001, 5
        return 0.01, 3

    def _calculate_session_stats(self, df_day: pd.DataFrame, start_time_str: str, end_time_str: str, pips_value: float) -> str:
        """特定時間帯（セッション）の値幅・変動をテキスト化"""
        try:
            target_date_str = df_day.index[0].strftime("%Y-%m-%d")
            start_dt = pd.Timestamp(f"{target_date_str} {start_time_str}", tz="Asia/Tokyo")
            end_dt = pd.Timestamp(f"{target_date_str} {end_time_str}", tz="Asia/Tokyo")

            df_session = df_day[(df_day.index >= start_dt) & (df_day.index <= end_dt)]

            if df_session.empty:
                return "データなし"

            s_open = float(df_session["Open"].iloc[0])
            s_close = float(df_session["Close"].iloc[-1])
            s_high = float(df_session["High"].max())
            s_low = float(df_session["Low"].min())

            range_pips = (s_high - s_low) / pips_value
            change_pips = (s_close - s_open) / pips_value

            return f"値幅 {range_pips:.1f}pips ({change_pips:+.1f}pips)"
        except Exception:
            return "計算不能"

    def extract_verified_full_day_with_logging(
        self, df: pd.DataFrame, target_date: date = None, pair_label: str = ""
    ) -> pd.DataFrame:
        """00:00 〜 23:55 (288本) の連続性を検証して抽出"""
        if df.empty:
            if self.logger:
                self.logger.error("データなし", f"[{pair_label}] 入力データフレームが空です。")
            return pd.DataFrame()

        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index, utc=True, errors="coerce")
            df = df[df.index.notnull()]
            df.index = df.index.tz_convert("Asia/Tokyo")

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
                f"[{pair_label}] [{target_date}] のデータ検証を開始します（全{total_expected}本）。",
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
                    f"[{pair_label}] [{target_date}] 取得数: {actual_count}/288 (開始: {start_time}, 最終: {end_time})。",
                )
            return pd.DataFrame()

    def generate_report_text(self, df_day: pd.DataFrame, pair_name: str = "") -> str:
        """2パターン対応：全体サマリー ＋ 時間帯別市場ダイジェスト"""
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

        # 市場別の動向分析
        tokyo_stat = self._calculate_session_stats(df_day, "09:00:00", "15:00:00", pips_value)
        london_stat = self._calculate_session_stats(df_day, "16:00:00", "21:00:00", pips_value)
        ny_overlap_stat = self._calculate_session_stats(df_day, "21:00:00", "23:55:00", pips_value)

        fmt = f"{{:.{digits}f}}"

        return (
            f"📊 **【{pair_name}】日次確定レポート ({target_date_str})**\n"
            f"```text\n"
            f"【日次サマリー】\n"
            f"・始値 (Open)    : {fmt.format(open_p)}\n"
            f"・高値 (High)    : {fmt.format(high_p)}\n"
            f"・安値 (Low)     : {fmt.format(low_p)}\n"
            f"・終値 (Close)   : {fmt.format(close_p)}\n"
            f"・日中全値幅   : {range_pips:.1f} pips ({change_pips:+.1f} pips)\n"
            f"----------------------------------------\n"
            f"【市場別セッション動向】\n"
            f"・東京市場 (09-15時) : {tokyo_stat}\n"
            f"・欧州単独 (16-21時) : {london_stat}\n"
            f"・欧州/NY  (21-24時) : {ny_overlap_stat}\n"
            f"```"
        )
