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
        日次確定データとGoogle検索結果を組み合わせ、時系列アナリストレポートを生成する（ハルシネーション防止指針適用）
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
あなたは客観的なデータと事実のみを扱う厳格なFX市場分析AIです。
提供された確定価格データと、Google検索で取得した【{date_str}】の事実情報（ニュース・指標）に基づき、論理的かつ厳格な時系列アナリストレポートを作成してください。

### 対象通貨ペア・日付
- 通貨ペア: {pair_name} ({symbol})
- 対象日: {date_str} (JST)

### 確定価格データサマリー
- 始値: {open_p}
- 終値: {close_p}
- 日中高値: {high_p} (記録時刻: {high_time} JST)
- 日中安値: {low_p} (記録時刻: {low_time} JST)

---
### ⚠️ 厳格なハルシネーション防止・分析ルール（必読）
1. **事実（Fact）の限定**: Google検索で確認できる実際のニュース・指標発表・要人発言のみを扱ってください。**検索結果に存在しないイベントや数値を捏造・想像で記述することを固く禁じます。**
2. **根拠の提示（参照元）**: 分析の根拠となったニュースや指標情報については、参照したWebサイト名または概要・URLをレポート内に明記してください。事実確認が取れないニュースは「明確なファンダメンタルズ要因なし」として扱ってください。
3. **論理破綻の防止**: 「〇〇の指標発表で〇〇円動いた」と分析する際は、時間帯（JST）と価格データの変動タイミングが合致しているか厳密に検証してください。因果関係に論理的飛躍や破綻が見られる場合は、事実ではなく「仮説」として記述し、論理的矛盾が生じないよう注意してください。
4. **不明な事項**: 検索しても価格変動の直接的要因が不明な場合は、無理に理由を作らず「目立った材料なし／テクニカル的な需給要因」と記載してください。

---
### 出力フォーマット
🤖 **【{pair_name}】{date_str} 時系列AIアナリストレポート**

■ **本日の市場総括**
（2〜3行で一日の全体の動きとファンダメンタルズ背景を論理的に要約）

■ **時系列ニュース＆価格要因分析 (JST)**
- **東京市場 (09:00〜15:00)**: （価格推移と確認された事実ニュース）
- **欧州市場 (15:00〜21:00)**: （価格推移と確認された事実ニュース）
- **NY市場 (21:00〜06:00)**: （価格推移と確認された経済指標・事実ニュース）

■ **参照・根拠情報（ソース）**
- （検索で参照した主要ニュースやソース情報を箇条書きで提示）

■ **明日の注目ポイント・展望**
（確定している翌日以降の経済指標スケジュールやテクニカル水準を記述）
"""

            # Gemini 2.5 Flash モデル ＋ Google Search Grounding を有効化して実行
            response = self.client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[{"google_search": {}}],  # Google検索ツールを自動実行
                    temperature=0.1,  # ハルシネーション防止のためランダム性を低く設定
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
