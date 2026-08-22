# main.py

import os
import time
from datetime import datetime, timedelta
import pandas as pd
import pytz

from src.data_fetcher import FXDataFetcher
from src.json_storage import JSONStorage
from src.sheets_storage import GoogleSheetsStorage
from src.system_logger import SystemLogger
from src.daily_reporter import FXDailyReporter
from src.visualizer import BacktestVisualizer
from src.discord_client import DiscordClient

# Webhook 設定
REPORT_WEBHOOK_URL = os.getenv("DISCORD_REPORT_WEBHOOK_URL")  # #daily-summary
LOG_WEBHOOK_URL = os.getenv("DISCORD_LOG_WEBHOOK_URL")        # #system-logs

# 確定した8通貨ペア（表示名 : GMOコインシンボル）
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
    # 0. 共通コンポーネントの初期化
    logger = SystemLogger(webhook_url=LOG_WEBHOOK_URL)
    fetcher = FXDataFetcher(pairs=PAIRS)
    storage = JSONStorage(base_dir=BASE_DATA_DIR)
    reporter = FXDailyReporter(logger=logger)
    sheets_storage = GoogleSheetsStorage(logger=logger)

    # 日本時間 (JST) 基準で現在日時と前日日付を取得
    now_jst = datetime.now(JST)
    target_date = (now_jst - timedelta(days=1)).date()

    logger.info(
        "パイプライン起動",
        f"GMOコイン APIより実行時刻({now_jst.strftime('%Y-%m-%d %H:%M:%S')} JST)の最新TICKER生データを取得し `data/{{symbol}}/data.json` に保存します。",
    )

    # 1. 最新価格（Ticker）の取得
    tickers_df = fetcher.fetch_bulk_data_with_retry(max_retries=5)
    if tickers_df.empty:
        logger.error("取得失敗", "GMOコイン APIからのデータ取得に失敗しました。")
        return

    # 2. JSONファイルへの生データ追記・保存 (status: OPEN のみ対象)
    save_any = False
    skipped_pairs = []

    for pair_name, symbol in PAIRS.items():
        df_ticker = tickers_df[tickers_df["symbol"] == symbol].copy() if not tickers_df.empty else pd.DataFrame()

        if not df_ticker.empty:
            # レスポンスの dict をそのまま抽出
            raw_record = df_ticker.iloc[0].to_dict()

            # status が OPEN のデータのみ保存対象とする
            if raw_record.get("status") == "OPEN":
                if storage.append_raw_ticker(symbol, raw_record):
                    save_any = True
            else:
                skipped_pairs.append(symbol)

    if skipped_pairs:
        logger.info("休場スキップ", f"市場休場中(CLOSE)のため以下のペアの追記をスキップしました: {', '.join(skipped_pairs)}")

    if not save_any:
        # 土日などで全ペアが休場中だった場合はエラーで落ちさせず正常終了する
        if len(skipped_pairs) == len(PAIRS):
            logger.info("全ペア休場中", "すべての通貨ペアが市場休場中のため、本回の保存処理をスキップし正常終了します。")
            return
        else:
            logger.error("JSON追記失敗", f"`{BASE_DATA_DIR}/{{symbol}}/data.json` への追記に失敗しました。")
            return

    logger.info("JSON追記完了", "営業中ペアの最新生データの追記・保存処理が完了しました。")

    # 3. 蓄積データの検証・チャート生成・レポート送信・Sheets書き込み
    for pair_name, symbol in PAIRS.items():
        try:
            df_accumulated = storage.load_pair_data(symbol)
            if df_accumulated.empty:
                continue

            # load_pair_data は JST タイムゾーン付き DatetimeIndex になっているため
            # .date で比較すれば完全に JST の日付(target_date)で正しくフィルタリングされます
            df_day = df_accumulated[df_accumulated.index.date == target_date].sort_index()
            actual_count = len(df_day)

            # 蓄積数が288本（5分足×24時間分）に達したら確定処理
            if actual_count == 288:
                logger.info(
                    "完全データ検知",
                    f"[{pair_name}] 前日[{target_date}] の288本蓄積完了を確認。処理を開始します。",
                )

                df_verified = reporter.extract_verified_full_day_with_logging(
                    df_accumulated, target_date=target_date, pair_label=pair_name
                )

                if not df_verified.empty:
                    # ① Googleスプレッドシートへの追記
                    sheets_storage.append_daily_data(symbol, df_verified)

                    # ② チャート描画
                    chart_filename = f"chart_{symbol}.png"
                    BacktestVisualizer.plot_daily_line_chart(
                        df_verified,
                        pair_title=f"{pair_name} ({symbol})",
                        target_date=target_date,
                        save_path=chart_filename,
                    )

                    # ③ レポート生成 & 送信
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
