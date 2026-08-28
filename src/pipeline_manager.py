# src/pipeline_manager.py

import os
import time
import json
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

    def __init__(
        self,
        base_dir: str,
        report_webhook_url: str,
        logger: SystemLogger,
        gemini_api_key: str = "",
        google_credentials_base64: str = "",
        spreadsheet_id: str = "",
    ):
        self.storage = JSONStorage(base_dir=base_dir)
        
        # 受け取った引数を各連携ストレージ・コンポーネントへ引き継ぐ
        self.sheets_storage = GoogleSheetsStorage(
            logger=logger,
            credentials_base64=google_credentials_base64,
            spreadsheet_id=spreadsheet_id,
        )
        self.reporter = FXDailyReporter(logger=logger)
        self.ai_reporter = GeminiAIReporter(logger=logger, api_key=gemini_api_key)
        
        self.report_webhook_url = report_webhook_url
        self.logger = logger
        self.sent_log_file = os.path.join(base_dir, "sent_reports.json")

    def _is_already_sent(self, symbol: str, target_date: date) -> bool:
        """指定日のレポートが送信済みかチェック"""
        if not os.path.exists(self.sent_log_file):
            return False
        try:
            with open(self.sent_log_file, "r", encoding="utf-8") as f:
                sent_data = json.load(f)
            return sent_data.get(symbol) == str(target_date)
        except Exception:
            return False

    def _mark_as_sent(self, symbol: str, target_date: date):
        """送信完了フラグを記録"""
        sent_data = {}
        if os.path.exists(self.sent_log_file):
            try:
                with open(self.sent_log_file, "r", encoding="utf-8") as f:
                    sent_data = json.load(f)
            except Exception:
                sent_data = {}
        
        sent_data[symbol] = str(target_date)
        with open(self.sent_log_file, "w", encoding="utf-8") as f:
            json.dump(sent_data, f, ensure_ascii=False, indent=2)

    def process_daily_reports(self, pairs: dict, target_date: date):
        """指定日の蓄積データを確認し、集計・スプレッドシート・AI・Discord連携を実行"""
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
        # 送信済みチェック（同一日の連続送信をスキップ）
        if self._is_already_sent(symbol, target_date):
            return

        df_accumulated = self.storage.load_pair_data(symbol)
        if df_accumulated.empty:
            return

        df_day = df_accumulated[df_accumulated.index.date == target_date].sort_index()
        actual_count = len(df_day)

        if actual_count == 0:
            return

        is_monday = target_date.weekday() == 0
        required_count = 200 if is_monday else 288

        latest_time = df_day.index[-1].time()
        is_day_complete = (actual_count >= required_count) and (
            latest_time.hour == 23 and latest_time.minute >= 50
        )

        if is_day_complete:
            self.logger.info(
                "完全データ検知",
                f"[{pair_name}] 前日[{target_date}] のデータ確定を確認。処理を開始します。",
            )

            df_verified = self.reporter.extract_verified_full_day(
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

            # 3. テキストレポート生成
            basic_report = self.reporter.generate_report_text(
                df_verified, pair_name=pair_name
            )
            ai_report = self.ai_reporter.generate_timeline_report(
                pair_name=pair_name,
                symbol=symbol,
                target_date=target_date,
                df_day=df_verified,
            )

            full_report = basic_report
            if ai_report:
                full_report += f"\n\n{ai_report}"

            # 4. Discordへの送信
            success = DiscordClient.send_multipart(
                self.report_webhook_url, full_report, image_path=chart_filename
            )

            if success:
                # 送信成功時にフラグを記録
                self._mark_as_sent(symbol, target_date)
                self.logger.info(
                    "送信完了",
                    f"[{pair_name}] の一体型日次レポートを送信しました。",
                )

            if os.path.exists(chart_filename):
                os.remove(chart_filename)
