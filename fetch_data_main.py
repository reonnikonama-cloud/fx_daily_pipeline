# fetch_data_main.py

import os
import sys
from src.system_logger import SystemLogger
from src.json_storage import JSONStorage
from src.data_fetcher import FXDataFetcher


def main():
    log_webhook = os.getenv("DISCORD_SYSTEM_LOG_WEBHOOK_URL", "")
    logger = SystemLogger(webhook_url=log_webhook)
    storage = JSONStorage(base_dir="data")

    # GMOコイン Public API 用インスタンス生成（認証不要）
    fetcher = FXDataFetcher()

    # 取得対象ペア定義（スイスフラン/円を追加）
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

    logger.info("パイプライン起動", "GMOコイン APIよりレート一括取得を開始します。")

    try:
        # 1. 一括で全通貨ペアの Ticker データを取得
        df_tickers = fetcher.fetch_bulk_data_with_retry(max_retries=5)

        if df_tickers.empty:
            logger.error("データ取得失敗", "Ticker データの取得結果が空でした。")
            sys.exit(1)

        success_count = 0

        # 2. 通貨ペアごとに抽出して JSONStorage へ保存（フォルダ名は symbol に統一）
        for pair_name, symbol in pairs.items():
            df_symbol = df_tickers[df_tickers["symbol"] == symbol]

            if not df_symbol.empty:
                # Dict 形式（リスト内辞書）として抽出し保存
                data_to_save = df_symbol.to_dict(orient="records")
                if storage.save_pair_data(symbol, data_to_save):
                    success_count += 1
                else:
                    logger.error("保存失敗", f"[{pair_name} ({symbol})] のデータ保存に失敗しました。")
            else:
                logger.error("データ抽出スキップ", f"[{pair_name} ({symbol})] のデータが見つかりませんでした。")

        logger.info("全処理完了", f"蓄積データの更新が完了しました。（成功: {success_count}/{len(pairs)}）")

    except Exception as e:
        logger.error("システムエラー", f"データ収集処理中に例外が発生しました: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
