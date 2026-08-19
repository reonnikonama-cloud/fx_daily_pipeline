# src/visualizer.py

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd


class BacktestVisualizer:
    """日次チャートの描画・画像生成クラス"""

    @staticmethod
    def plot_daily_line_chart(
        df_verified: pd.DataFrame,
        pair_title: str,
        target_date,
        save_path: str = "chart.png",
    ):
        """市場時間帯背景ハイライト付きの線グラフを作成"""
        if df_verified.empty:
            return

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
        # 市場セッション背景ハイライト (JST基準)
        # ----------------------------------------------------
        # 1. 東京市場 (09:00 - 15:00)
        ax.axvspan(
            pd.Timestamp(f"{target_date} 09:00:00", tz="Asia/Tokyo"),
            pd.Timestamp(f"{target_date} 15:00:00", tz="Asia/Tokyo"),
            color="#e3f2fd",
            alpha=0.5,
            label="Tokyo (09:00-15:00)",
        )

        # 2. ロンドン市場 (16:00 - 24:00) ※当日の23:55まで
        ax.axvspan(
            pd.Timestamp(f"{target_date} 16:00:00", tz="Asia/Tokyo"),
            pd.Timestamp(f"{target_date} 23:55:00", tz="Asia/Tokyo"),
            color="#e8f5e9",
            alpha=0.5,
            label="London (16:00-)",
        )

        # 3. ニューヨーク市場 (21:00 - 23:55) ※当日の範囲
        ax.axvspan(
            pd.Timestamp(f"{target_date} 21:00:00", tz="Asia/Tokyo"),
            pd.Timestamp(f"{target_date} 23:55:00", tz="Asia/Tokyo"),
            color="#ffebee",
            alpha=0.5,
            label="New York (21:00-)",
        )

        # 軸・タイトルの設定
        plt.title(f"{pair_title} - Daily Movement ({target_date})", fontsize=14, fontweight="bold")
        plt.xlabel("Time (JST)", fontsize=10)
        plt.ylabel("Price", fontsize=10)
        plt.grid(True, linestyle="--", alpha=0.5)

        # X軸フォーマット (HH:MM 表示)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=df_verified.index.tz))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
        plt.xticks(rotation=0)

        # 凡例表示（重複しないように設定）
        handles, labels = ax.get_legend_handles_labels()
        by_label = dict(zip(labels, handles))
        plt.legend(by_label.values(), by_label.keys(), loc="upper left", framealpha=0.9)

        plt.tight_layout()
        plt.savefig(save_path)
        plt.close()
