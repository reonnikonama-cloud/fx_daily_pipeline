# src/ai_reporter.py

import os
import pandas as pd
from typing import Optional, Any
from google import genai
from google.genai import types


class GeminiAIReporter:
    """Gemini API (Google Search Grounding有効) を使用した時系列FXレポート生成クラス"""

    def __init__(self, logger: Optional[Any] = None) -> None:
        self.logger = logger
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.client: Optional[genai.Client] = None

        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                if self.logger:
                    self.logger.error("Gemini初期化エラー", f"Gemini Clientの初期化に失敗しました: {e}")
        else:
            if self.logger:
                self.logger.info("Geminiスキップ", "GEMINI_API_KEY が設定されていません。")

    def generate_timeline_report(self, pair_name: str, symbol: str, target_date: Any, df_day: pd.DataFrame) -> Optional[str]:
        """
        日次確定データとGoogle検索結果を組み合わせ、時系列アナリストレポートを生成する
        """
        if not self.client or df_day.empty:
            return None

        try:
            date_str = target_date.strftime("%Y-%m-%d") if hasattr(target_date, "strftime") else str(target_date)

            # 5分足データから主要な統計量を算出
            open_p = df_day["open"].iloc[0]
            close_p = df_day["close"].iloc[-1]
            high_p = df_day["high"].max()
            low_p = df_day["low"].min()
            
            # 本日の高値・安値を付けた時刻を取得
            high_time = df_day["high"].idxmax().strftime("%H:%M") if hasattr(df_day["high"].idxmax(), "strftime") else "不明"
            low_time = df_day["low"].idxmin().strftime("%H:%M") if hasattr(df_day["low"].idxmin(), "strftime") else "不明"

            prompt = f"""
あなたはプロのFX市場アナリストです。
以下の確定した取引価格データと、Google検索で取得した【{date_str}】の最新為替ニュース・経済指標結果を照合し、プロレベルの「時系列AI市場分析レポート」を作成してください。

### 対象通貨ペア・日付
- 通貨ペア: {pair_name} ({symbol})
- 対象日: {date_str} (JST)

### 本日の価格データサマリー
- 始値: {open_p}
- 終値: {close_p}
- 日中高値: {high_p} (記録時刻: {high_time} JST)
- 日中安値: {low_p} (記録時刻: {low_time} JST)

### 必須指示
1. Google検索を用いて、**{date_str}における{pair_name}（{symbol}）の主要ニュース、各国の中央銀行発言、経済指標結果、地政学リスク**を検索してください。
2. 上記の価格データ（特に高値/安値を記録した時間帯や大きな値動きがあった時間帯）と、検索したニュース・イベントを**タイムライン（時系列）で紐付けて**解説してください。
3. 出力フォーマットは以下の形式に厳密に従ってください（Discordで見やすいプレーンテキスト）。

---
🤖 **【{pair_name}】{date_str} 時系列AIアナリストレポート**

■ **本日の市場総括**
（2〜3行で一日の全体の動きと背景要因を要約）

■ **時系列ニュース＆価格要因分析 (JST)**
- **東京市場 (09:00〜15:00)**: （価格推移と主なニュース・動向）
- **欧州市場 (15:00〜21:00)**: （価格推移と主なニュース・動向）
- **NY市場 (21:00〜06:00)**: （価格推移と主なニュース・経済指標・指標結果）

■ **明日の注目ポイント・展望**
（翌日以降の注目指標やテクニカル的な警戒水準を1〜2点挙げる）
---
"""

            # Gemini 2.5 Flash モデル ＋ Google Search Grounding を有効化して実行
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],  # Google検索ツールを自動実行
                    temperature=0.3,
                ),
            )

            report_text = response.text
            if self.logger:
                self.logger.info("AIレポート生成完了", f"[{pair_name}] の時系列AIアナリストレポートを生成しました。")

            return report_text

        except Exception as e:
            if self.logger:
                self.logger.error("AIレポート生成エラー", f"[{pair_name}] Geminiレポート生成失敗: {e}")
            return None
