# src/system_logger.py

from datetime import datetime
import pytz
from src.discord_client import DiscordClient

JST = pytz.timezone("Asia/Tokyo")


class SystemLogger:
    """システム動作ログおよびデータ取得進捗を管理するロガー"""

    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url

    def _log(self, level: str, title: str, message: str, color_emoji: str):
        # サーバー環境（UTC）であっても JST の現在時刻を取得してフォーマット
        timestamp = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
        content = (
            f"{color_emoji} **[{level}] {title}** (`{timestamp}`)\n"
            f"```text\n{message}\n```"
        )

        print(f"[{level}] {title} ({timestamp}): {message}")

        if self.webhook_url:
            DiscordClient.send_message(self.webhook_url, content)

    def info(self, title: str, message: str):
        self._log("INFO", title, message, "🟢")

    def progress(self, current_count: int, total_count: int, timestamp_str: str, price: float, pair_label: str = ""):
        percentage = (current_count / total_count) * 100
        prefix = f"[{pair_label}] " if pair_label else ""
        message = f"{prefix}[{current_count:03d}/{total_count}] 時刻: {timestamp_str} | Close: {price:.3f} ({percentage:.1f}%)"
        self._log("DATA_CHECK", "データ取得進捗", message, "🟦")

    def warning(self, title: str, message: str):
        self._log("WARN", title, message, "🟡")

    def error(self, title: str, message: str):
        self._log("ERROR", title, message, "🔴")
