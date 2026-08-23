# src/pipeline_manager.py

import os
import time
from datetime import date
import pandas as pd

from src.json_storage import JSONStorage
from src.sheets_storage import GoogleSheetsStorage
from src.ai_reporter import GeminiAIReporter
from src.system_logger import SystemLogger
from src.daily_reporter import FXDailyReporter
from src.visualizer import BacktestVisualizer
from src.discord_client import DiscordClient

class PipelineManager:
    """日次データ処理・レポート生成・外部連携を一括管理するマネージャー"""

    def __init__(self, base_dir: str, report_webhook_url: str, logger: SystemLogger):
        self.storage = JSONStorage(base_dir=base_dir)
        self.sheets_storage = GoogleSheetsStorage(logger=logger)
        self.reporter = FXDailyReporter(logger=logger)
        self.ai_reporter = GeminiAIReporter(logger=logger)
        self.report_webhook_url = report_webhook_url
        self.logger = logger

    def process_daily_reports(self, pairs: dict, target_date: date):
        """指定日の288本蓄積データを確認し、集計・スプレッドシート・AI・Discord連携を実行"""
        for pair_name, symbol in pairs.items():
            try:
                self._process_single_pair(pair_name, symbol, target_date)
                time.sleep(0.5)
            except Exception as e:
                self.logger.error(
                    "個別例外エラー",
                    f"[{pair_name}] 処理中に予期せぬ例外が発生しました:\n{e}",
                )

    def _process_single_pair(self, pair_name: str, symbol: str, target_date: date):
        df_accumulated = self.storage.load_pair_data(symbol)
        if df_accumulated.empty:
            return

        df_day = df_accumulated[df_accumulated.index.date == target_date].sort_index()
        actual_count = len(df_day)

        if actual_count != 288:
            self.logger.info(
                "データ蓄積中",
                f"[{pair_name}] 前日[{target_date}] の蓄積本数: {actual_count}/288本",
            )
            return

        # 288本確定時の処理
        self.logger.info(
            "完全データ検知",
            f"[{pair_name}] 前日[{target_date}] の288本蓄積完了を確認。処理を開始します。",
        )

        df_verified = self.reporter.extract_verified_full_day_with_logging(
            df_accumulated, target_date=target_date, pair_label=pair_name
        )

        if df_verified.empty:
            return

        # 1. スプレッドシート保存
        self.sheets_storage.append_daily_data(symbol, df_verified)

        # 2. チャート生成
        chart_filename = f"chart_{symbol}.png"
        BacktestVisualizer.plot_daily_line_chart(
            df_verified,
            pair_title=f"{pair_name} ({symbol})",
            target_date=target_date,
            save_path=chart_filename,
        )

        # 3. テキストレポート生成（基本数値 + AI分析）
        basic_report = self.reporter.generate_report_text(df_verified, pair_name=pair_name)
        ai_report = self.ai_reporter.generate_timeline_report(
            pair_name=pair_name, symbol=symbol, target_date=target_date, df_day=df_verified
        )

        full_report = basic_report
        if ai_report:
            full_report += f"\n\n{ai_report}"

        # 4. Discordへの一括送信
        success = DiscordClient.send_multipart(
            self.report_webhook_url, full_report, image_path=chart_filename
        )

        if success:
            self.logger.info("送信完了", f"[{pair_name}] の一体型日次レポート（画像＋AI分析付き）を送信しました。")

        # 画像のクリーンアップ
        if os.path.exists(chart_filename):
            os.remove(chart_filename)
