# src/sheets_storage.py

import os
import json
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from src.system_logger import SystemLogger


class GoogleSheetsStorage:
    """Google Sheets へのデータ追加・管理クラス"""

    def __init__(self, logger: SystemLogger):
        self.logger = logger
        self.spreadsheet_id = os.getenv("SPREADSHEET_ID")
        self.gcp_key_json = os.getenv("GCP_SA_KEY")
        self.gc = None
        self.sh = None
        self._authenticate()

    def _authenticate(self):
        """GCP サービスアカウントによる認証"""
        try:
            if not self.gcp_key_json or not self.spreadsheet_id:
                self.logger.error("認証エラー", "SPREADSHEET_ID または GCP_SA_KEY が設定されていません。")
                return

            info = json.loads(self.gcp_key_json)
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            creds = Credentials.from_service_account_info(info, scopes=scopes)
            self.gc = gspread.authorize(creds)
            self.sh = self.gc.open_by_key(self.spreadsheet_id)
        except Exception as e:
            self.logger.error("Sheets認証失敗", f"Google Sheets への接続に失敗しました:\n{e}")

    def append_daily_data(self, symbol: str, df_verified: pd.DataFrame):
        """確定データを対応するワークシートに追記"""
        if self.sh is None or df_verified.empty:
            return

        try:
            # ワークシートを取得（存在しなければ作成）
            try:
                worksheet = self.sh.worksheet(symbol)
            except gspread.exceptions.WorksheetNotFound:
                worksheet = self.sh.add_worksheet(title=symbol, rows=1000, cols=10)
                # ヘッダー書き込み
                worksheet.append_row(["timestamp_jst", "open", "high", "low", "close", "volume", "status"])

            # データの複製と列名の標準化 (小文字化)
            df = df_verified.copy()
            df.columns = [str(c).lower() for c in df.columns]

            # タイムスタンプが Index にある場合は列へ展開
            if "timestamp_jst" not in df.columns:
                df = df.reset_index()
                # インデックス名が timestamp_jst でない場合は先頭列をリネーム
                if "index" in df.columns:
                    df.rename(columns={"index": "timestamp_jst"}, inplace=True)
                elif df.columns[0] != "timestamp_jst":
                    df.rename(columns={df.columns[0]: "timestamp_jst"}, inplace=True)

            # 追記用データのリスト作成 (確実に数値キャストを行う)
            rows_to_append = []
            for _, row in df.iterrows():
                # タイムスタンプの文字列化
                ts_val = str(row.get("timestamp_jst", ""))
                
                # 数値データの安全な抽出
                open_val = float(row.get("open", 0.0))
                high_val = float(row.get("high", 0.0))
                low_val = float(row.get("low", 0.0))
                close_val = float(row.get("close", 0.0))
                volume_val = int(row.get("volume", 0))
                status_val = str(row.get("status", "OPEN"))

                rows_to_append.append([
                    ts_val,
                    open_val,
                    high_val,
                    low_val,
                    close_val,
                    volume_val,
                    status_val
                ])

            if rows_to_append:
                worksheet.append_rows(rows_to_append, value_input_option="USER_ENTERED")
                self.logger.info(
                    "Sheets書き込み完了",
                    f"[{symbol}] シートへ {len(rows_to_append)} 件のデータを正常に転記しました。"
                )

        except Exception as e:
            self.logger.error("Sheets書き込みエラー", f"[{symbol}] データ転記中に例外が発生しました:\n{e}")
            
