# main.py

import os
import time
from datetime import datetime, timedelta

from src.daily_reporter import FXDailyReporter
from src.data_fetcher import FXDataFetcher
from src.system_logger import SystemLogger
from src.visualizer import BacktestVisualizer

# Webhook URL
REPORT_WEBHOOK_URL = os.getenv("DISCORD_REPORT_WEBHOOK_URL")  # #daily-summary
LOG_WEBHOOK_URL = os.getenv("DISCORD_LOG_WEBHOOK_URL")  # #system-logs

# 9通貨ペアの定義
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
    logger = SystemLogger(webhook_url=LOG_WEBHOOK_URL)
    fetcher = FXDataFetcher(pairs=PAIRS, base_dir=BASE_DATA_DIR)

    # 前日確定分をターゲット（日次集計用）
    target_date = (datetime.now() - timedelta(days=1)).date()

    logger.info(
        "パイプライン起動",
        "実行時刻の最新1本を取得し `data/{symbol}/data.json` に追記します。",
    )

    # 1. データの取得 & 追記保存
    bulk_df = fetcher.fetch_bulk_data_with_retry(max_retries=5)
    if bulk_df.empty:
        logger.error(
            "取得失敗",
            "Yahoo Financeからのデータ取得に失敗（またはレートリミット到達）しました。",
        )
        return

    save_success = fetcher.append_latest_data_to_json(bulk_df)
    if not save_success:
        logger.error(
            "JSON追記失敗",
            f"`{BASE_DATA_DIR}/{{symbol}}/data.json` への追記に失敗しました。",
        )
        return

    logger.info(
        "JSON追記完了",
        "全対象ペアの最新データ追記・保存処理が完了しました。",
    )

    # 2. 蓄積データの読み込み・検証・レポート配信
    for pair_name, symbol in PAIRS.items():
        try:
            df_pair = fetcher.load_pair_data_from_json(symbol)
            if df_pair.empty:
                continue

            reporter = FXDailyReporter(pips_value=0.01, logger=logger)
            df_day = df_pair[df_pair.index.date == target_date].sort_index()
            actual_count = len(df_day)

            # 288本（前日分）が揃ったタイミングで送信
            if actual_count == 288:
                logger.info(
                    "完全データ検知",
                    f"[{pair_name}] 前日[{target_date}] の288本蓄積完了を確認。レポートを配信します。",
                )

                df_verified = (
                    reporter.extract_verified_full_day_with_logging(
                        df_pair, target_date=target_date, pair_label=pair_name
                    )
                )
                if not df_verified.empty:
                    chart_filename = f"chart_{symbol.replace('=X', '')}.png"
                    BacktestVisualizer.plot_daily_line_chart(
                        df_verified,
                        pair_title=f"{pair_name} ({symbol})",
                        target_date=target_date,
                        save_path=chart_filename,
                    )

                    report = reporter.generate_report(
                        df_verified, pair_name=pair_name
                    )
                    success = reporter.send_discord_webhook(
                        report, REPORT_WEBHOOK_URL, image_path=chart_filename
                    )

                    if success:
                        logger.info(
                            "送信完了",
                            f"[{pair_name}] の確定日次レポートを送信しました。",
                        )
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
