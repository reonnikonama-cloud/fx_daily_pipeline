# src/visualizer.py

from datetime import date
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd


class BacktestVisualizer:
    """4大市場およびサマータイム自動判定に対応したチャート描画クラス"""

    @staticmethod
    def is_summer_time(target_date: date) -> bool:
        """3月第2日曜日 〜 11月第1日曜日がサマータイム（米国基準）かを判定"""
        year = target_date.year
        # 3月第2日曜日
        march_sundays = [d for d in pd.date_range(f"{year}-03-01", f"{year}-03-31") if d.weekday() == 6]
        dst_start = march_sundays[1].date()

        # 11月第1日曜日
        nov_sundays = [d for d in pd.date_range(f"{year}-11-01", f"{year}-11-30") if d.weekday() == 6]
        dst_end = nov_sundays[0].date()

        return dst_start <= target_date < dst_end

    @classmethod
    def plot_daily_line_chart(
        cls,
        df_verified: pd.DataFrame,
        pair_title: str,
        target_date: date,
        save_path: str = "chart.png",
    ):
        """サマータイムを考慮した4大市場ハイライト付きチャート作成"""
        if df_verified.empty:
            return

        is_dst = cls.is_summer_time(target_date)

        # サマータイムの有無による時間帯シフト（1時間前倒し）
        # ロンドン: 通常17:00- / 夏16:00-
        # NY: 通常22:00- / 夏21:00-
        london_start = "16:00:00" if is_dst else "17:00:00"
        ny_start = "21:00:00" if is_dst else "22:00:00"
        season_label = "Summer Time" if is_dst else "Standard Time"

        plt.figure(figsize=(12, 6), dpi=150)
        ax = plt.gca()

        # 価格ライン描画
        plt.plot(
            df_verified.index,
            df_verified["Close"],
            label="Price (Close)",
            color="#1f77b4",
            linewidth=1.8,
        )

        # ----------------------------------------------------
        # 4大市場セッションの背景ハイライト (JST)
        # ----------------------------------------------------
        # 1. ウェリントン・シドニー (05:00 - 14:00 ※夏場は04:00-)
        syd_start = "04:00:00" if is_dst else "05:00:00"
        syd_end = "13:00:00" if is_dst else "14:00:00"
        ax.axvspan(
            pd.Timestamp(f"{target_date} {syd_start}", tz="Asia/Tokyo"),
            pd.Timestamp(f"{target_date} {syd_end}", tz="Asia/Tokyo"),
            color="#fff3e0",
            alpha=0.35,
            label="Sydney/Wellington",
        )

        # 2. 東京市場 (09:00 - 19:00)
        ax.axvspan(
            pd.Timestamp(f"{target_date} 09:00:00", tz="Asia/Tokyo"),
            pd.Timestamp(f"{target_date} 19:00:00", tz="Asia/Tokyo"),
            color="#e3f2fd",
            alpha=0.35,
            label="Tokyo (09:00-19:00)",
        )

        # 3. ロンドン市場 (夏16:00- / 冬17:00-)
        ax.axvspan(
            pd.Timestamp(f"{target_date} {london_start}", tz="Asia/Tokyo"),
            pd.Timestamp(f"{target_date} 23:55:00", tz="Asia/Tokyo"),
            color="#e8f5e9",
            alpha=0.35,
            label=f"London ({london_start[:5]}-)",
        )

        # 4. ニューヨーク市場 (夏21:00- / 冬22:00-)
        ax.axvspan(
            pd.Timestamp(f"{target_date} {ny_start}", tz="Asia/Tokyo"),
            pd.Timestamp(f"{target_date} 23:55:00", tz="Asia/Tokyo"),
            color="#ffebee",
            alpha=0.35,
            label=f"New York ({ny_start[:5]}-)",
        )

        # 軸・タイトルの設定
        plt.title(f"{pair_title} - Daily Movement [{season_label}] ({target_date})", fontsize=14, fontweight="bold")
        plt.xlabel("Time (JST)", fontsize=10)
        plt.ylabel("Price", fontsize=10)
        plt.grid(True, linestyle="--", alpha=0.5)

        # X軸フォーマット
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=df_verified.index.tz))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        plt.xticks(rotation=0)

        # 凡例表示
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys(), loc="upper left", framealpha=0.9, fontsize=8)

        plt.tight_layout()
        plt.savefig(save_path)
        plt.close()
