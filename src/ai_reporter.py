# src/ai_reporter.py

import os
import pandas as pd
from datetime import date
import google.generativeai as genai
from src.system_logger import SystemLogger


class GeminiAIReporter:
    """Gemini APIを使用してFXデータのAI分析レポートを生成するクラス"""

    def __init__(self, logger: SystemLogger):
        self.logger = logger
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = None
        self._setup_client()

    def _setup_client(self):
        """Gemini API クライアントの設定"""
        if not self.api_key:
            self.logger.warning("AI設定不足", "GEMINI_API_KEY が設定されていません。AI分析はスキップされます。")
            return
        try:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel("gemini-1.5-flash")
        except Exception as e:
            self.logger.error("AI認証失敗", f"Gemini API の初期化に失敗しました:\n{e}")

    def generate_timeline_report(
        self, pair_name: str, symbol: str, target_date: date, df_day: pd.DataFrame
    ) -> str:
        """日次データを分析して簡潔なAIコメントを生成"""
        if self.model is None or df_day.empty:
            return ""

        try:
            # カラム名をすべて小文字に統一（'Open'/'open' の表記揺れ対策）
            df = df_day.copy()
            df.columns = [str(c).lower() for c in df.columns]

            # 各価格指標の取得
            open_price = float(df["open"].iloc[0]) if "open" in df.columns else 0.0
            high_price = float(df["high"].max()) if "high" in df.columns else 0.0
            low_price = float(df["low"].min()) if "low" in df.columns else 0.0
            close_price = float(df["close"].iloc[-1]) if "close" in df.columns else 0.0

            # プロンプトの作成
            prompt = (
                f"あなたはプロのFXアナリストです。以下のデータに基づいて、{pair_name}（{target_date}）の"
                f"1日の相場動向を3〜4行程度で簡潔に要約・分析してください。\n\n"
                f"・始値: {open_price}\n"
                f"・高値: {high_price}\n"
                f"・安値: {low_price}\n"
                f"・終値: {close_price}\n"
            )

            response = self.model.generate_content(prompt)
            return response.text.strip() if response.text else ""

        except Exception as e:
            self.logger.error(
                "AIレポート生成エラー",
                f"[{pair_name}] Geminiレポート生成失敗: {e}"
            )
            return ""
