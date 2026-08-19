# main.py

import os
import time
from datetime import datetime, timedelta
import pandas as pd

from src.data_fetcher import FXDataFetcher
from src.json_storage import JSONStorage
from src.system_logger import SystemLogger
from src.daily_reporter import FXDailyReporter
from src.visualizer import BacktestVisualizer
from src.discord_client import DiscordClient

# Webhook 設定
REPORT_WEBHOOK_URL = os.getenv("DISCORD_REPORT_WEBHOOK_URL")  # #daily-summary
LOG_WEBHOOK_URL = os.getenv("DISCORD_LOG_WEBHOOK_URL")        # #system-logs

# 確定した6通貨ペア（表示名 : GMOコインシンボル）
PAIRS = {
    "米ドル/円": "USD_JPY",
    "ユーロ/円": "EUR_JPY",
    "英ポンド/円": "GBP_JPY",
    "豪ドル/円": "AUD_JPY",
    "スイスフラン/円": "CHF_JPY",
    "ユーロ/ドル": "EUR_USD",
}

BASE_DATA_DIR = "data"


def main():
    # 0. 共通コンポーネントの初期化
    logger = SystemLogger(webhook_url=LOG_WEBHOOK_URL)
    fetcher = FXDataFetcher(pairs=PAIRS)
    storage = JSONStorage(base_dir=BASE_DATA_DIR)
    reporter = FXDailyReporter(pips_value=0.01, logger=logger)

    target_date = (datetime.now() - timedelta(days=1)).date()

    logger.info(
        "パイプライン起動",
        "GMOコイン APIより実行時刻の最新データ・板情報を取得し `data/{symbol}/data.json` に追記します。",
    )

    # 1. 最新価格（Ticker）および板情報（Orderbook）の取得
    tickers_df = fetcher.fetch_bulk_data_with_retry(max_retries=5)
    if tickers_df.empty:
        logger.error("取得失敗", "GMOコイン APIからのデータ取得に失敗しました。")
        return

    # 全ペアの板情報（需給データ）を取得
    orderbooks_df = fetcher.fetch_all_orderbooks()

    # 2. JSONファイルへの追記・保存
    save_any = False
    now_ts = pd.Timestamp.now()

    for pair_name, symbol in PAIRS.items():
        # 対象シンボルの Ticker データを抽出
        df_ticker = tickers_df[tickers_df["symbol"] == symbol].copy() if not tickers_df.empty else pd.DataFrame()

        if not df_ticker.empty:
            # 取得データを時系列DataFrameとして整形
            row_data = {
                "Open": float(df_ticker["bid"].values[0]),
                "High": float(df_ticker["high"].values[0]) if "high" in df_ticker.columns else float(df_ticker["bid"].values[0]),
                "Low": float(df_ticker["low"].values[0]) if "low" in df_ticker.columns else float(df_ticker["bid"].values[0]),
                "Close": float(df_ticker["bid"].values[0]),
                "Ask": float(df_ticker["ask"].values[0]),
                "Volume": float(df_ticker["volume"].values[0]) if "volume" in df_ticker.columns else 0.0,
            }

            # 板情報（買板・売板比率）があれば結合
            if not orderbooks_df.empty and symbol in orderbooks_df["symbol"].values:
                ob_row = orderbooks_df[orderbooks_df["symbol"] == symbol].iloc[0]
                row_data["BidRatio"] = ob_row["bid_ratio"]
                row_data["AskRatio"] = ob_row["ask_ratio"]
                row_data["Sentiment"] = ob_row["sentiment"]

            df_single = pd.DataFrame([row_data], index=[now_ts])

            if storage.append_pair_data(symbol, df_single):
                save_any = True

    if not save_any:
        logger.error("JSON追記失敗", f"`{BASE_DATA_DIR}/{{symbol}}/data.json` への追記に失敗しました。")
        return

    logger.info("JSON追記完了", "全対象6ペアの最新データおよび板情報の追記・保存処理が完了しました。")

    # 3. 蓄積データの検証・チャート生成・レポート送信
    for pair_name, symbol in PAIRS.items():
        try:
            df_accumulated = storage.load_pair_data(symbol)
            if df_accumulated.empty:
                continue

            df_day = df_accumulated[df_accumulated.index.date == target_date].sort_index()
            actual_count = len(df_day)

            # 蓄積数が288本（5分足×24時間分）に達したら確定レポート処理
            if actual_count == 288:
                logger.info(
                    "完全データ検知",
                    f"[{pair_name}] 前日[{target_date}] の288本蓄積完了を確認。レポート処理を開始します。",
                )

                df_verified = reporter.extract_verified_full_day_with_logging(
                    df_accumulated, target_date=target_date, pair_label=pair_name
                )

                if not df_verified.empty:
                    # チャート描画
                    chart_filename = f"chart_{symbol}.png"
                    BacktestVisualizer.plot_daily_line_chart(
                        df_verified,
                        pair_title=f"{pair_name} ({symbol})",
                        target_date=target_date,
                        save_path=chart_filename,
                    )

                    # レポート生成 & 送信
                    report_text = reporter.generate_report_text(df_verified, pair_name=pair_name)
                    success = DiscordClient.send_multipart(
                        REPORT_WEBHOOK_URL, report_text, image_path=chart_filename
                    )

                    if success:
                        logger.info("送信完了", f"[{pair_name}] の確定日次レポートを送信しました。")

                    if os.path.exists(chart_filename):
                        os.remove(chart_filename)
            else:
                logger.info(
                    "データ蓄積中",
                    f"[{pair_name}] 前日[{target_date}] の蓄積本数: {actual_count}/288本",
                )

            time.sleep(0.5)

        except Exception as e:
            logger.error(
                "個別例外エラー",
                f"[{pair_name}] 処理中に予期せぬ例外が発生しました:\n{e}",
            )

    logger.info("全処理完了", "パイプラインの実行が正常に終了しました。")


if __name__ == "__main__":
    main()
