# src/daily_reporter.py

from typing import List, Dict, Any, Optional


class FXDailyReporter:
    """日次市場データの集計および Discord レポート用テキスト生成クラス"""

    def __init__(self, logger: Optional[Any] = None) -> None:
        """
        初期化（main.py から logger が渡されても対応できるように実装）
        """
        self.logger = logger

    def generate_report(self, pair_name: str, target_date: str, records: List[Dict[str, Any]]) -> str:
        """
        1日分のデータから統計量を計算し、レポート文面を生成する
        """
        if not records:
            return f"⚠️ **[{pair_name}]** {target_date} のデータが存在しません。"

        # 価格リスト抽出
        closes = [r["close"] for r in records]
        highs = [r["high"] for r in records]
        lows = [r["low"] for r in records]

        # 統計量計算
        open_price = records[0]["open"]
        close_price = records[-1]["close"]
        high_price = max(highs)
        low_price = min(lows)

        # 差分（変動幅）と変動率の計算
        price_diff = close_price - open_price
        change_pct = (price_diff / open_price) * 100

        # pips の計算（クロス円は 0.01 = 1 pip、EUR_USD 等のドルストレートは 0.0001 = 1 pip）
        is_jpy_pair = "JPY" in pair_name or "円" in pair_name
        pips_multiplier = 100.0 if is_jpy_pair else 10000.0
        pips_diff = price_diff * pips_multiplier

        # 符号表記の整形
        sign = "+" if price_diff >= 0 else ""
        price_fmt = ".3f" if is_jpy_pair else ".5f"

        # レポート文面組み立て
        report = (
            f"📊 **【日次サマリー】{pair_name}** (`{target_date}`)\n"
            f"```text\n"
            f"・始値 (Open)  : {open_price:{price_fmt}}\n"
            f"・終値 (Close) : {close_price:{price_fmt}}\n"
            f"・高値 (High)  : {high_price:{price_fmt}}\n"
            f"・安値 (Low)   : {low_price:{price_fmt}}\n"
            f"----------------------------------------\n"
            f"・変動幅 (pips): {sign}{pips_diff:.1f} pips\n"
            f"・変動率 (%)   : {sign}{change_pct:.2f}%\n"
            f"```"
        )

        return report
