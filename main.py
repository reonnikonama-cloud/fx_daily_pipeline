# main.py

import os
import time
from datetime import datetime, timedelta

from src.data_fetcher import FXDataFetcher
from src.json_storage import JSONStorage
from src.system_logger import SystemLogger
from src.daily_reporter import FXDailyReporter
from src.visualizer import BacktestVisualizer
from src.discord_client import DiscordClient

# Webhook 設定
REPORT_WEBHOOK_URL = os.getenv("DISCORD_REPORT_WEBHOOK_URL")  # #daily-summary
LOG_WEBHOOK_URL = os.getenv("DISCORD_LOG_WEBHOOK_URL")        # #system-logs

PAIRS = {
    "米ドル/円": "JPY=X",
    "ユーロ/円": "EURJPY=X",
    "英ポンド/円": "GBPJPY=X",
    "スイスフラン/円": "CHFJPY=X",
    "カナダドル/円": "CADJPY=X",
    "豪ドル/円": "AUDJPY=X",
    "NZドル/円": "NZDJPY=X",
    "人民元/円": "CNYJPY=X",
    "インドルピー/円": "INRJPY=X",
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
        "実行時刻の最新1本を取得し `data/{symbol}/data.json` に追記します。",
    )

    # 1. 最新データの取得
    bulk_df = fetcher.fetch_bulk_data_with_retry(max_retries=5)
    if bulk_df.empty:
        logger.error("取得失敗", "Yahoo Financeからのデータ取得に失敗（またはレートリミット到達）しました。")
        return

    # 2. JSONファイルへの追記・保存
    save_any = False
    for pair_name, symbol in PAIRS.items():
        df_pair = fetcher.extract_pair_df(bulk_df, symbol)
        if not df_pair.empty:
            if storage.append_pair_data(symbol, df_pair):
                save_any = True

    if not save_any:
        logger.error("JSON追記失敗", f"`{BASE_DATA_DIR}/{{symbol}}/data.json` への追記に失敗しました。")
        return

    logger.info("JSON追記完了", "全対象ペアの最新データ追記・保存処理が完了しました。")

    # 3. 蓄積データの検証・チャート生成・レポート送信
    for pair_name, symbol in PAIRS.items():
        try:
            df_accumulated = storage.load_pair_data(symbol)
            if df_accumulated.empty:
                continue

            df_day = df_accumulated[df_accumulated.index.date == target_date].sort_index()
            actual_count = len(df_day)

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
                    chart_filename = f"chart_{symbol.replace('=X', '')}.png"
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
