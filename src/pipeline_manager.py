# src/pipeline_manager.py

import os
import time
from datetime import date  # NameError対策のインポート
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
        df_accumulated = self.storage.load_pair_data(symbol)
        if df_accumulated.empty:
            return

        # 前日(target_date)のデータを抽出
        df_day = df_accumulated[df_accumulated.index.date == target_date].sort_index()
        actual_count = len(df_day)

        if actual_count == 0:
            return

        # 曜日判定 (0: 月曜日, 1: 火曜日 ... 6: 日曜日)
        # target_date が月曜日の場合、07:00オープン開始のため本数が少ない(約204本)
        is_monday = target_date.weekday() == 0

        # 確定条件の閾値設定（月曜は200本以上、その他営業日は288本で確定）
        required_count = 200 if is_monday else 288

        # 本数チェック ＋ 最終データが23:50以降まで存在するかチェック
        latest_time = df_day.index[-1].time()
        is_day_complete = (actual_count >= required_count) and (
            latest_time.hour == 23 and latest_time.minute >= 50
        )

        if is_day_complete:
            self.logger.info(
                "完全データ検知",
                f"[{pair_name}] 前日[{target_date}] (月曜特例: {is_monday}) のデータ確定({actual_count}本)を確認。処理を開始します。",
            )

            # メソッド名を extract_verified_full_day に修正
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

            # 3. テキストレポート生成（基本数値 + AI分析）
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

            # 4. Discordへの一括送信（画像＋AI分析テキストを1通にまとめる）
            success = DiscordClient.send_multipart(
                self.report_webhook_url, full_report, image_path=chart_filename
            )

            if success:
                self.logger.info(
                    "送信完了",
                    f"[{pair_name}] の一体型日次レポート（画像＋AI分析付き）を送信しました。",
                )

            # 画像のクリーンアップ
            if os.path.exists(chart_filename):
                os.remove(chart_filename)
        else:
            self.logger.info(
                "データ蓄積中",
                f"[{pair_name}] 前日[{target_date}] 蓄積本数: {actual_count}/{required_count}本 (最終データ: {latest_time})",
            )
