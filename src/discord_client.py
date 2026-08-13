# src/discord_client.py

import json
import urllib.request


class DiscordClient:
    """Discord Webhook 通信を専門に扱う低レイヤークライアント"""

    @staticmethod
    def send_message(webhook_url: str, content: str) -> bool:
        """テキストメッセージ (JSON) を送信"""
        if not webhook_url or not webhook_url.startswith("http"):
            return False

        payload = {"content": content}
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "FXSystem/1.0",
        }

        try:
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            print(f" [DiscordClient] テキスト送信失敗: {e}")
            return False

    @staticmethod
    def send_multipart(webhook_url: str, text: str, image_path: str = None) -> bool:
        """テキストと画像ファイル (multipart/form-data) を送信"""
        if not webhook_url or not webhook_url.startswith("http"):
            return False

        boundary = "---------------------------12345678901234567890"
        body = []

        # テキストフィールド
        body.append(f"--{boundary}".encode())
        body.append(b'Content-Disposition: form-data; name="content"')
        body.append(b"")
        body.append(text.encode("utf-8"))

        # 画像フィールド
        if image_path:
            try:
                with open(image_path, "rb") as f:
                    img_data = f.read()

                body.append(f"--{boundary}".encode())
                body.append(
                    f'Content-Disposition: form-data; name="file"; filename="{image_path}"'.encode()
                )
                body.append(b"Content-Type: image/png")
                body.append(b"")
                body.append(img_data)
            except Exception as e:
                print(f" [DiscordClient] 画像読み込みエラー: {e}")

        body.append(f"--{boundary}--".encode())
        body.append(b"")

        payload = b"\r\n".join(body)
        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "User-Agent": "FXSystem/1.0",
        }

        try:
            req = urllib.request.Request(
                webhook_url, data=payload, headers=headers, method="POST"
            )
            with urllib.request.urlopen(req) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            print(f" [DiscordClient] Multipart送信失敗: {e}")
            return False
