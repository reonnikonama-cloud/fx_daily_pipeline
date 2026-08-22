# src/sheets_storage.py

import os
import json
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from typing import Optional, Any


class GoogleSheetsStorage:
    """Google スプレッドシートへの日次データ同期クラス（年別横並びレイアウト対応）"""

    SCOPES = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    # 1年分あたりのデータ列数（7列）
    NUM_COLS_PER_YEAR = 7
    # 年と年の間の空き列数
    YEAR_SPACING_COLS = 1
    
    HEADERS = ["timestamp_jst", "open", "high", "low", "close", "volume", "status"]

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
        1日分(df_day)のデータを対象のワークシートへ書き込む。
        年判定を行い、該当する年の列ブロックの末尾へ追記する。
        """
        if not self.spreadsheet or df_day.empty:
            return False

        try:
            # データの日付から西暦（年）を取得
            first_idx = df_day.index[0]
            data_year = int(first_idx.year) if hasattr(first_idx, "year") else int(str(first_idx)[:4])

            # 対象のワークシートを取得（無ければ作成）
            try:
                worksheet = self.spreadsheet.worksheet(symbol)
            except gspread.WorksheetNotFound:
                worksheet = self.spreadsheet.add_worksheet(title=symbol, rows=1000, cols=50)

            # 1行目の既存ヘッダー一覧を取得して年の位置を特定
            header_row_values = worksheet.row_values(1)
            
            # シート内に記録されている最小の年を判定（初回書き込み時の年基準）
            start_col = self._get_or_create_year_column_offset(worksheet, header_row_values, data_year)

            # 書き込み用リストの作成
            records_to_append = []
            for idx, row in df_day.iterrows():
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

            # 対象年ブロックの「現在の最終行」を検索して追記セル範囲（A1記法）を算出
            # 例: 1列目(timestamp_jst)の値が入っている全行を取得
            col_values = worksheet.col_values(start_col)
            next_row = len(col_values) + 1

            # 書き込み範囲の指定 (例: A25:G312)
            start_cell = gspread.utils.rowcol_to_a1(next_row, start_col)
            end_cell = gspread.utils.rowcol_to_a1(next_row + len(records_to_append) - 1, start_col + self.NUM_COLS_PER_YEAR - 1)
            cell_range = f"{start_cell}:{end_cell}"

            # 一括書き込み (update)
            worksheet.update(values=records_to_append, range_name=cell_range, value_input_option="USER_ENTERED")

            if self.logger:
                self.logger.info("Sheets同期完了", f"[{symbol}] {data_year}年ブロック ({cell_range}) に {len(records_to_append)} 行追記しました。")
            return True

        except Exception as e:
            if self.logger:
                self.logger.error("Sheets書き込みエラー", f"[{symbol}] スプレッドシートへの書き込み中にエラーが発生しました: {e}")
            return False

    def _get_or_create_year_column_offset(self, worksheet: gspread.Worksheet, header_row: list, target_year: int) -> int:
        """
        対象年の列開始位置（1-based column index）を取得する。
        新しい年であれば、自動的に新しい列にヘッダーを作成する。
        """
        # 1行目から "timestamp_jst" が存在する列インデックス（1-based）をすべて探す
        timestamp_cols = [i + 1 for i, val in enumerate(header_row) if val == "timestamp_jst"]

        if not timestamp_cols:
            # 完全新規シートの場合：1列目（A列）からスタート
            start_col = 1
            self._write_year_header(worksheet, start_col, target_year)
            return start_col

        # 既存の列から「どの年に対応しているか」を2行目のタイムスタンプなどから簡易判定
        # 各 timestamp 列の直上の 1行目にヘッダーがあるので、一番右のブロックを確認
        # 簡易化のため、最初のブロックを基準とした年差分で列オフセットを計算
        # ※ ここでは既存のタイムスタンプ年をチェック
        first_col_val = worksheet.cell(2, timestamp_cols[0]).value
        base_year = int(first_col_val[:4]) if first_col_val and len(first_col_val) >= 4 else target_year

        year_diff = target_year - base_year
        if year_diff < 0:
            year_diff = 0  # 過去データが入った場合は先頭に寄せる

        # 1年につき (7列 + 空白1列 = 8列) シフト
        block_width = self.NUM_COLS_PER_YEAR + self.YEAR_SPACING_COLS
        target_start_col = 1 + (year_diff * block_width)

        # もし新しい年のブロックで、まだヘッダーが未作成なら書き込む
        if target_start_col > len(header_row) or header_row[target_start_col - 1] != "timestamp_jst":
            self._write_year_header(worksheet, target_start_col, target_year)

        return target_start_col

    def _write_year_header(self, worksheet: gspread.Worksheet, start_col: int, year: int) -> None:
        """指定列からヘッダー行を書き込む"""
        start_cell = gspread.utils.rowcol_to_a1(1, start_col)
        end_cell = gspread.utils.rowcol_to_a1(1, start_col + self.NUM_COLS_PER_YEAR - 1)
        worksheet.update(values=[self.HEADERS], range_name=f"{start_cell}:{end_cell}", value_input_option="USER_ENTERED")
