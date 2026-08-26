import os
import sys
from datetime import datetime, timezone, timedelta
from src.system_logger import SystemLogger
from src.pipeline_manager import PipelineManager


def get_jst_now():
    """JST (UTC+9) の現在日時を取得"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst)


def main():
    # 各種環境変数の取得
    report_webhook = os.getenv("DISCORD_REPORT_WEBHOOK_URL", "")
    log_webhook = os.getenv("DISCORD_SYSTEM_LOG_WEBHOOK_URL", "")
    gemini_api_key = os.getenv("GEMINI_API_KEY", "")
    google_creds = os.getenv("GOOGLE_CREDENTIALS_BASE64", "")
    spreadsheet_id = os.getenv("SPREADSHEET_ID", "")

    logger = SystemLogger(webhook_url=log_webhook)

    # PipelineManager の初期化（必要な環境変数を一括渡す）
    manager = PipelineManager(
        base_dir="data",
        report_webhook_url=report_webhook,
        logger=logger,
        gemini_api_key=gemini_api_key,
        google_credentials_base64=google_creds,
        spreadsheet_id=spreadsheet_id,
    )

    pairs = {
        "米ドル/円": "USD_JPY",
        "ユーロ/円": "EUR_JPY",
        "英ポンド/円": "GBP_JPY",
        "豪ドル/円": "AUD_JPY",
        "NZドル/円": "NZD_JPY",
        "カナダドル/円": "CAD_JPY",
        "ユーロ/ドル": "EUR_USD",
    }

    now_jst = get_jst_now()

    # Actions起動遅延（0:00〜0:20頃の起動）への防振対策
    if now_jst.hour == 0 and now_jst.minute < 30:
        target_date = (now_jst - timedelta(days=1)).date()
    else:
        target_date = now_jst.date()

    logger.info("デイリーレポート開始", f"対象日: {target_date} (JST 23:58定時実行)")

    try:
        # レポート集計・AI生成・Discord送信・シート保存を一括実行
        manager.process_daily_reports(pairs, target_date=target_date)
        logger.info("デイリーレポート完了", "処理が正常に終了しました。")
    except Exception as e:
        logger.error("デイリーレポートエラー", f"実行中にエラーが発生しました: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
