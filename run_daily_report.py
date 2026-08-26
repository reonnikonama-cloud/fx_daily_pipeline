# run_daily_report.py

import os
from datetime import datetime, timezone, timedelta
from src.system_logger import SystemLogger
from src.pipeline_manager import PipelineManager


def get_jst_now():
    """JST (UTC+9) の現在日時を取得"""
    jst = timezone(timedelta(hours=9))
    return datetime.now(jst)


def main():
    report_webhook = os.getenv("DISCORD_REPORT_WEBHOOK_URL", "")
    log_webhook = os.getenv("DISCORD_SYSTEM_LOG_WEBHOOK_URL", "")

    logger = SystemLogger(webhook_url=log_webhook)
    manager = PipelineManager(
        base_dir="data",
        report_webhook_url=report_webhook,
        logger=logger,
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

    # Actions起動遅延（0:00〜0:20頃の起動）への防振対策：
    # 日付を跨いでしまっていた場合は「前日」を対象日付として補正
    if now_jst.hour == 0 and now_jst.minute < 30:
        target_date = (now_jst - timedelta(days=1)).date()
    else:
        target_date = now_jst.date()

    logger.info("デイリーレポート開始", f"対象日: {target_date} (JST 23:58定時実行)")

    # レポート集計・AI生成・Discord送信・シート保存を一括実行
    manager.process_daily_reports(pairs, target_date=target_date)

    logger.info("デイリーレポート完了", "処理が正常に終了しました。")


if __name__ == "__main__":
    main()
