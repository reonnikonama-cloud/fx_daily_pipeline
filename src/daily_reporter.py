# src/daily_reporter.py

from datetime import date, datetime, timedelta
import pandas as pd
from src.system_logger import SystemLogger


class FXDailyReporter:
    """日次確定データの検証および4大市場・サマータイム対応レポート生成"""

    def __init__(self, logger: SystemLogger = None):
        self.logger = logger

    def _get_pair_config(self, pair_name: str) -> tuple[float, int]:
        """通貨ペアに応じた pips 基準値と表示桁数を取得"""
        if "USD" in pair_name and "JPY" not in pair_name:
            return 0.0001, 5
        return 0.01, 3

    @staticmethod
    def is_summer_time(target_date: date) -> bool:
        """3月第2日曜日 〜 11月第1日曜日がサマータイムかを判定"""
        year = target_date.year
        march_sundays = [d for d in pd.date_range(f"{year}-03-01", f"{year}-03-31") if d.weekday() == 6]
        dst_start = march_sundays[1].date()

        nov_sundays = [d for d in pd.date_range(f"{year}-11-01", f"{year}-11-30") if d.weekday() == 6]
        dst_end = nov_sundays[0].date()

        return dst_start <= target_date < dst_end

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
        """サマータイム自動切り替え対応の文章化サマリーレポート生成"""
        if df_day.empty:
            return ""

        pips_value, digits = self._get_pair_config(pair_name)
        target_date = df_day.index[0].date()
        target_date_str = target_date.strftime("%Y-%m-%d")

        is_dst = self.is_summer_time(target_date)
        season_mode = "夏時間 (サマータイム)" if is_dst else "標準時間 (冬時間)"

        open_p = float(df_day["Open"].iloc[0])
        high_p = float(df_day["High"].max())
        low_p = float(df_day["Low"].min())
        close_p = float(df_day["Close"].iloc[-1])

        range_pips = (high_p - low_p) / pips_value
        change_pips = (close_p - open_p) / pips_value

        # 夏時間／標準時間に応じた時間帯設定
        syd_times = ("04:00:00", "13:00:00") if is_dst else ("05:00:00", "14:00:00")
        lon_times = ("16:00:00", "21:00:00") if is_dst else ("17:00:00", "22:00:00")
        ny_times = ("21:00:00", "23:55:00") if is_dst else ("22:00:00", "23:55:00")

        # 4大市場の動向計算
        sydney_stat = self._calculate_session_stats(df_day, syd_times[0], syd_times[1], pips_value)
        tokyo_stat = self._calculate_session_stats(df_day, "09:00:00", "19:00:00", pips_value)
        london_stat = self._calculate_session_stats(df_day, lon_times[0], lon_times[1], pips_value)
        ny_stat = self._calculate_session_stats(df_day, ny_times[0], ny_times[1], pips_value)

        fmt = f"{{:.{digits}f}}"

        return (
            f"📊 **【{pair_name}】日次確定レポート ({target_date_str})**\n"
            f"※適用モード: `{season_mode}`\n"
            f"```text\n"
            f"【日次全般サマリー】\n"
            f"・始値 (Open)    : {fmt.format(open_p)}\n"
            f"・高値 (High)    : {fmt.format(high_p)}\n"
            f"・安値 (Low)     : {fmt.format(low_p)}\n"
            f"・終値 (Close)   : {fmt.format(close_p)}\n"
            f"・日中全値幅   : {range_pips:.1f} pips ({change_pips:+.1f} pips)\n"
            f"----------------------------------------\n"
            f"【主要市場別セッション動向】\n"
            f"・オセアニア帯 ({syd_times[0][:5]}-{syd_times[1][:5]}) : {sydney_stat}\n"
            f"・東京市場帯   (09:00-19:00) : {tokyo_stat}\n"
            f"・欧州単独帯   ({lon_times[0][:5]}-{lon_times[1][:5]}) : {london_stat}\n"
            f"・欧米重複帯   ({ny_times[0][:5]}-24:00) : {ny_stat}\n"
            f"```"
        )
