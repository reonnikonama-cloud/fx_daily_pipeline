# main.py

import os
from datetime import datetime, timedelta
import pytz

from src.data_fetcher import FXDataFetcher
from src.json_storage import JSONStorage
from src.system_logger import SystemLogger
from src.pipeline_manager import PipelineManager

REPORT_WEBHOOK_URL = os.getenv("DISCORD_REPORT_WEBHOOK_URL")
LOG_WEBHOOK_URL = os.getenv("DISCORD_LOG_WEBHOOK_URL")

PAIRS = {
    "米ドル/円": "USD_JPY",
    "ユーロ/円": "EUR_JPY",
    "英ポンド/円": "GBP_JPY",
    "豪ドル/円": "AUD_JPY",
    "スイスフラン/円": "CHF_JPY",
    "NZドル/円": "NZD_JPY",
    "カナダドル/円": "CAD_JPY",
    "ユーロ/ドル": "EUR_USD",
}

BASE_DATA_DIR = "data"
JST = pytz.timezone("Asia/Tokyo")


def main():
    logger = SystemLogger(webhook_url=LOG_WEBHOOK_URL)
    fetcher = FXDataFetcher(pairs=PAIRS)
    storage = JSONStorage(base_dir=BASE_DATA_DIR)
    pipeline_manager = PipelineManager(
        base_dir=BASE_DATA_DIR,
        report_webhook_url=REPORT_WEBHOOK_URL,
        logger=logger,
    )

    now_jst = datetime.now(JST)
    target_date = (now_jst - timedelta(days=1)).date()

    logger.info(
        "パイプライン起動",
        f"実行時刻({now_jst.strftime('%Y-%m-%d %H:%M:%S')} JST) のデータ取得を開始します。",
    )

    # ステップ1: APIから最新Ticker取得
    tickers_df = fetcher.fetch_bulk_data_with_retry(max_retries=5)
    if tickers_df.empty:
        logger.error("取得失敗", "GMOコイン APIからのデータ取得に失敗しました。")
        return

    # ステップ2: TickerデータのJSON保存
    save_any, skipped_pairs = _save_tickers(storage, tickers_df, PAIRS)

    if skipped_pairs:
        logger.info("休場スキップ", f"休場中のためスキップ: {', '.join(skipped_pairs)}")

    if not save_any and len(skipped_pairs) == len(PAIRS):
        logger.info("全ペア休場中", "全ペア休場中のため正常終了します。")
        return

    # ステップ3: 288本確定データの検証・集計・AIレポート・Discord送信処理
    pipeline_manager.process_daily_reports(PAIRS, target_date)

    logger.info("全処理完了", "パイプラインの実行が正常に終了しました。")


def _save_tickers(storage, tickers_df, pairs):
    save_any = False
    skipped_pairs = []

    for _, symbol in pairs.items():
        df_ticker = tickers_df[tickers_df["symbol"] == symbol].copy() if not tickers_df.empty else None
        if df_ticker is not None and not df_ticker.empty:
            raw_record = df_ticker.iloc[0].to_dict()
            if raw_record.get("status") == "OPEN":
                if storage.append_raw_ticker(symbol, raw_record):
                    save_any = True
            else:
                skipped_pairs.append(symbol)

    return save_any, skipped_pairs


if __name__ == "__main__":
    main()
