# fetch_data_main.py

import os
import sys
from datetime import datetime
import pytz
from src.system_logger import SystemLogger
from src.json_storage import JSONStorage
from src.data_fetcher import FXDataFetcher

JST = pytz.timezone("Asia/Tokyo")


def get_target_total_count() -> int:
    """現在の曜日（JST）に応じて、目標データ本数を返す（月曜: 200本 / 火〜金: 288本）"""
    weekday = datetime.now(JST).weekday()
    if weekday == 0:
        return 200
    return 288


def main():
    log_webhook = os.getenv("DISCORD_LOG_WEBHOOK_URL", "").strip()
    
    if not log_webhook:
        print("[WARNING] DISCORD_LOG_WEBHOOK_URL が設定されていないため、Discord通知はスキップされます。")
    elif not log_webhook.startswith("http"):
        print(f"[ERROR] Webhook URL の形式が不正です (httpから始まっていません): {log_webhook[:10]}...")

    logger = SystemLogger(webhook_url=log_webhook)
    storage = JSONStorage(base_dir="data")

    fetcher = FXDataFetcher()

    pairs = {
        "米ドル/円": "USD_JPY",
        "ユーロ/円": "EUR_JPY",
        "英ポンド/円": "GBP_JPY",
        "豪ドル/円": "AUD_JPY",
        "NZドル/円": "NZD_JPY",
        "カナダドル/円": "CAD_JPY",
        "スイスフラン/円": "CHF_JPY",
        "ユーロ/ドル": "EUR_USD",
    }

    total_target_count = get_target_total_count()

    logger.info("パイプライン起動", "GMOコイン APIよりレート一括取得を開始します。")

    try:
        df_tickers = fetcher.fetch_bulk_data_with_retry(max_retries=5)

        if df_tickers.empty:
            logger.error("データ取得失敗", "Ticker データの取得結果が空でした。")
            sys.exit(1)

        success_count = 0
        close_skipped = False

        for pair_name, symbol in pairs.items():
            try:
                df_symbol = df_tickers[df_tickers["symbol"] == symbol]

                if not df_symbol.empty:
                    # status のチェック (CLOSE の場合は保存せずに正常スキップ)
                    status_val = df_symbol.iloc[0].get("status", "")
                    if status_val == "CLOSE":
                        close_skipped = True
                        continue

                    data_to_save = df_symbol.to_dict(orient="records")
                    if storage.save_pair_data(symbol, data_to_save):
                        success_count += 1

                        # 保存・整形済みの DataFrame (df_current) から安全に最新値・タイムスタンプを取得
                        df_current = storage.load_pair_data(symbol)
                        current_count = len(df_current)

                        if not df_current.empty:
                            latest_row = df_current.iloc[-1]
                            timestamp_str = str(latest_row.name)
                            latest_price = float(latest_row.get("bid", 0.0))
                        else:
                            timestamp_str = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
                            latest_price = 0.0

                        # ログ通知
                        logger.progress(
                            current_count=current_count,
                            total_count=total_target_count,
                            timestamp_str=timestamp_str,
                            price=latest_price,
                            pair_label=pair_name,
                        )
                    else:
                        logger.error("保存失敗", f"[{pair_name} ({symbol})] のデータ保存に失敗しました。")
                else:
                    logger.error("データ抽出スキップ", f"[{pair_name} ({symbol})] のデータが見つかりませんでした。")

            except Exception as pair_err:
                logger.error("ペア処理エラー", f"[{pair_name} ({symbol})] の処理中に例外が発生: {str(pair_err)}")

        # 閉場状態（CLOSE）でスキップされた場合の正常終了通知
        if close_skipped and success_count == 0:
            logger.info("市場閉場", "市場閉場（status: CLOSE）のためデータ保存・蓄積をスキップしました。")
        else:
            logger.info("全処理完了", f"蓄積データの更新が完了しました。（成功: {success_count}/{len(pairs)}）")

    except Exception as e:
        logger.error("システムエラー", f"データ収集処理中に例外が発生しました: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
