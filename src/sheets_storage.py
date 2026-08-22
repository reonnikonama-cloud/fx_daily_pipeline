# src/sheets_storage.py

import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from typing import Optional, Any


class GoogleSheetsStorage:
    """Google スプレッドシートへの日次データ同期クラス"""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    def __init__(self, logger: Optional[Any] = None) -> None:
        self.logger = logger
        self.sa_key_raw = os.getenv("GCP_SA_KEY")
        self.spreadsheet_id = os.getenv("SPREADSHEET_ID")
        self.client: Optional[gspread.Client] = None
        self.spreadsheet: Optional[gspread.Spreadsheet] = None

        self._authenticate()

    def _authenticate(self) -> None:
        """環境変数から認証情報を取得して gspread クライアントを初期化"""
        if not self.sa_key_raw or not self.spreadsheet_id:
            if self.logger:
                self.logger.info("Sheetsスキップ", "GCP_SA_KEY または SPREADSHEET_ID が設定されていません。")
            return

        try:
            creds_dict = json.loads(self.sa_key_raw)
            creds = Credentials.from_service_account_info(creds_dict, scopes=self.SCOPES)
            self.client = gspread.authorize(creds)
            self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
        except Exception as e:
            if self.logger:
                self.logger.error("Sheets認証エラー", f"Google APIの認証に失敗しました: {e}")

    def append_daily_data(self, symbol: str, df_day: pd.DataFrame) -> bool:
        """
        1日分(df_day)のデータを対象のワークシートへ末尾追記(append)する
        """
        if not self.spreadsheet or df_day.empty:
            return False

        try:
            # 対象のワークシートを取得（無ければ作成）
            try:
                worksheet = self.spreadsheet.worksheet(symbol)
            except gspread.WorksheetNotFound:
                worksheet = self.spreadsheet.add_worksheet(title=symbol, rows=1000, cols=10)
                # ヘッダー行の追加
                headers = ["timestamp_jst", "open", "high", "low", "close", "volume", "status"]
                worksheet.append_row(headers)

            # DataFrame をリスト形式に変換
            records_to_append = []
            for idx, row in df_day.iterrows():
                # インデックス(JST時刻)を文字列化して先頭に配置
                timestamp_str = idx.strftime("%Y-%m-%d %H:%M:%S") if hasattr(idx, "strftime") else str(idx)
                record = [
                    timestamp_str,
                    float(row.get("open", 0.0)),
                    float(row.get("high", 0.0)),
                    float(row.get("low", 0.0)),
                    float(row.get("close", 0.0)),
                    float(row.get("volume", 0.0)),
                    str(row.get("status", "OPEN")),
                ]
                records_to_append.append(record)

            # スプレッドシートの末尾にまとめて追記
            if records_to_append:
                worksheet.append_rows(records_to_append, value_input_option="USER_ENTERED")
                if self.logger:
                    self.logger.info("Sheets同期完了", f"[{symbol}] 前日分 {len(records_to_append)} 行をスプレッドシートへ書き込みました。")
                return True

        except Exception as e:
            if self.logger:
                self.logger.error("Sheets書き込みエラー", f"[{symbol}] スプレッドシートへの書き込み中にエラーが発生しました: {e}")
            return False

        return False
