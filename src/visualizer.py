# src/visualizer.py

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd


class BacktestVisualizer:
    """FXチャートの可視化クラス"""

    @staticmethod
    def plot_daily_line_chart(
        df: pd.DataFrame, pair_title: str = "", target_date=None, save_path: str = "realtime_intraday.png"
    ):
        """1日分（288本）の折れ線チャートを描画・保存"""
        if df.empty:
            return

        if target_date is None:
            target_date = df.index[-1].date()

        df_day = df[df.index.date == target_date].copy()
        if df_day.empty:
            return

        fig, ax = plt.subplots(figsize=(12, 5), dpi=100)

        ax.plot(df_day.index, df_day["Close"], color="#1f77b4", linewidth=1.5, label="Close")

        day_high = df_day["High"].max()
        day_low = df_day["Low"].min()
        ax.axhline(day_high, color="#d62728", linestyle="--", alpha=0.6, linewidth=1, label=f"High: {day_high:.3f}")
        ax.axhline(day_low, color="#2ca02c", linestyle="--", alpha=0.6, linewidth=1, label=f"Low: {day_low:.3f}")

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.set_title(f"{pair_title} Intraday Rate [{target_date} 00:00 - 23:55]", fontsize=11)
        ax.set_ylabel("Price")
        ax.legend(loc="upper left", frameon=True)

        plt.tight_layout()
        plt.savefig(save_path)
        plt.close(fig)

        print(f" [Visualizer] 折れ線チャートを {save_path} に保存しました。")
