# FX Daily Pipeline 📈

GMOコインのパブリック API から自動で主要 8 通貨ペアの 5 分足 TICKER データを収集・蓄積し、日次チャートの生成および Discord へのレポート自動送信を行うデータパイプラインシステムです。

---

## 🌟 主な機能

- **自動データ収集**: GMOコイン API より 5 分周期で最新の TICKER 生データを取得
- **JST タイムゾーン自動統一**: 収集したデータを日本標準時（JST）で管理・永続化（月次でデータ自動分割）
- **データ検証 & チャート生成**: 前日分（288本＝24時間）のデータが完全揃った段階で日次ラインチャートを自動生成
- **Discord 連携**: 
  - 確定日次レポート（要約情報＋チャート画像）を専用チャンネルへ配信
  - パイプラインのシステムステータス・実行ログをリアルタイムで通知

---

## 📊 対象通貨ペア（8ペア）

| 通貨ペア名 | GMOコイン シンボル |
| :--- | :--- |
| 米ドル/円 | `USD_JPY` |
| ユーロ/円 | `EUR_JPY` |
| 英ポンド/円 | `GBP_JPY` |
| 豪ドル/円 | `AUD_JPY` |
| スイスフラン/円 | `CHF_JPY` |
| NZドル/円 | `NZD_JPY` |
| カナダドル/円 | `CAD_JPY` |
| ユーロ/ドル | `EUR_USD` |

---

## 📁 ディレクトリ構造

```text
fx_daily_pipeline/
├── .github/
│   └── workflows/          # GitHub Actions 実行ワークフロー定義
├── data/                    # 自動生成されるデータ蓄積フォルダ
│   ├── USD_JPY/
│   │   └── data.json
│   └── ...
├── src/
│   ├── data_fetcher.py     # GMOコイン API データ取得クラス
│   ├── daily_reporter.py    # 日次レポートテキスト生成クラス
│   ├── discord_client.py   # Discord Webhook 送信クライアント
│   ├── json_storage.py     # JSON ストレージ管理クラス (JST変換/保存)
│   ├── system_logger.py    # システム動作ログ管理クラス (JST時刻対応)
│   └── visualizer.py       # チャート描画クラス
├── main.py                  # メイン実行エントリポイント
├── requirements.txt         # 依存ライブラリ一覧
└── README.md                # 本ドキュメント
