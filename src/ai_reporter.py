import os
import time
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
            self.logger.warning("AI設定不足", "GEMINI_API_KEY が設定されていません。")
            return
        try:
            genai.configure(api_key=self.api_key)
            # 無料枠で安定して動作する推奨モデル
            self.model = genai.GenerativeModel("gemini-2.5-flash")
        except Exception as e:
            self.logger.error("AI認証失敗", f"Gemini API の初期化に失敗しました:\n{e}")

    def generate_timeline_report(
        self, pair_name: str, symbol: str, target_date: date, df_day: pd.DataFrame
    ) -> str:
        """日次データを分析して簡潔なAIコメントを生成"""
        if self.model is None or df_day.empty:
            return ""

        try:
            df = df_day.copy()
            df.columns = df.columns.astype(str).str.lower()

            # ローソク足データ(open/high/low/close) または Tickerデータ(ask/bid等) の両方に対応
            if "open" in df.columns and "close" in df.columns:
                open_price = float(df["open"].iloc[0])
                high_price = float(df["high"].astype(float).max()) if "high" in df.columns else None
                low_price = float(df["low"].astype(float).min()) if "low" in df.columns else None
                close_price = float(df["close"].iloc[-1])
            elif "bid" in df.columns:
                open_price = float(df["bid"].iloc[0])
                high_price = float(df["bid"].astype(float).max())
                low_price = float(df["bid"].astype(float).min())
                close_price = float(df["bid"].iloc[-1])
            elif "ask" in df.columns:
                open_price = float(df["ask"].iloc[0])
                high_price = float(df["ask"].astype(float).max())
                low_price = float(df["ask"].astype(float).min())
                close_price = float(df["ask"].iloc[-1])
            else:
                return ""

            if None in (open_price, high_price, low_price, close_price):
                return ""

            prompt = (
                f"あなたはプロのFXアナリストです。以下のデータに基づいて、{pair_name}（対象日: {target_date}）の"
                f"1日の相場動向（トレンド、ボラティリティ、注目点など）を3〜4行程度で要約・分析してください。\n\n"
                f"・始値: {open_price}\n"
                f"・高値: {high_price}\n"
                f"・安値: {low_price}\n"
                f"・終値: {close_price}\n"
            )

            # 無料枠のレートリミット対策（429エラー発生時に最大3回リトライ）
            response = None
            for attempt in range(1, 4):
                try:
                    response = self.model.generate_content(prompt)
                    break
                except Exception as req_err:
                    if attempt == 3:
                        raise req_err
                    time.sleep(attempt * 2)

            if response and response.text:
                return f"🤖 **【AI相場分析】**\n{response.text.strip()}"
            return ""

        except Exception as e:
            self.logger.error(
                "AIレポート生成エラー",
                f"[{pair_name}] Geminiレポート生成失敗: {e}"
            )
            return ""
