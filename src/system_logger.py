# src/system_logger.py

import json
import urllib.request
from datetime import datetime


class SystemLogger:
    """システム動作ログおよびデータ取得進捗を Discord のプライベートログチャンネルへ送信するロガー"""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url

    def _send_to_discord(self, level: str, title: str, message: str, color_emoji: str):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        content = (
            f"{color_emoji} **[{level}] {title}** (`{timestamp}`)\n"
            f"```text\n{message}\n```"
        )

        print(f"[{level}] {title}: {message}")

        if not self.webhook_url or not self.webhook_url.startswith("http"):
            return

        payload = {"content": content}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "FXSystemLogger/1.0",
        }

        try:
            req = urllib.request.Request(
                self.webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                pass
        except Exception as e:
            print(f" [SystemLogger] ログ送信失敗: {e}")

    def info(self, title: str, message: str):
        self._send_to_discord("INFO", title, message, "🟢")

    def progress(self, current_count: int, total_count: int, timestamp_str: str, price: float, pair_label: str = ""):
        percentage = (current_count / total_count) * 100
        prefix = f"[{pair_label}] " if pair_label else ""
        message = f"{prefix}[{current_count:03d}/{total_count}] 時刻: {timestamp_str} | Close: {price:.3f} ({percentage:.1f}%)"
        self._send_to_discord("DATA_CHECK", "データ取得進捗", message, "🟦")

    def warning(self, title: str, message: str):
        self._send_to_discord("WARN", title, message, "🟡")

    def error(self, title: str, message: str):
        self._send_to_discord("ERROR", title, message, "🔴")
