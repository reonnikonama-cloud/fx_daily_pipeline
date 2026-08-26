# fetch_data_main.py

import os
from src.system_logger import SystemLogger
from src.json_storage import JSONStorage
# ※既存のAPI取得モジュール（例: OANDA fetcher等）をインポート
# from src.data_fetcher import OandaDataFetcher


def main():
    log_webhook = os.getenv("DISCORD_SYSTEM_LOG_WEBHOOK_URL", "")
    logger = SystemLogger(webhook_url=log_webhook)
    storage = JSONStorage(base_dir="data")

    pairs = {
        "米ドル/円": "USD_JPY",
        "ユーロ/円": "EUR_JPY",
        "英ポンド/円": "GBP_JPY",
        "豪ドル/円": "AUD_JPY",
        "NZドル/円": "NZD_JPY",
        "カナダドル/円": "CAD_JPY",
        "ユーロ/ドル": "EUR_USD",
    }

    logger.info("データ収集開始", "最新レートの取得・蓄積を開始します。")

    # TODO: 各通貨ペアのデータ取得＆JSONStorageへの追加保存処理
    # 例:
    # fetcher = OandaDataFetcher(...)
    # for pair_name, symbol in pairs.items():
    #     df_new = fetcher.get_latest_candles(symbol)
    #     storage.save_pair_data(symbol, df_new)

    logger.info("データ収集完了", "蓄積データの更新が完了しました。")


if __name__ == "__main__":
    main()
