# FX Daily Pipeline 📈

GMOコインのパブリック API から自動で主要 8 通貨ペアの 5 分足 TICKER データを収集・蓄積し、Google スプレッドシートへの保存、Gemini AI による時系列ニュース分析付きレポートの生成、および Discord への一体型レポート自動送信を行う全自動データパイプラインシステムです。

---

## 🌟 主な機能

- **自動データ収集 & 休場自動スキップ**: GMOコイン API より 5 分周期で最新の TICKER 生データを取得（土日の市場休場時は自動判定してスキップ）。
- **JST タイムゾーン完全統一**: 収集したデータを日本標準時（JST）で管理・永続化（月次/年次でデータを最適化保存）。
- **Google スプレッドシート自動連携**: 前日データ確定時（288本＝24時間分）、年別・通貨ペア別にスプレッドシートへ自動保存・横展開。
- **Gemini AI 時系列市場分析**: Google Search Grounding（検索連携）を活用し、前日の為替変動要因やニュースを自動検索して時系列レポートを生成。
- **データ検証 & チャート生成**: 前日分の完全データを検証後、日次ラインチャート（画像）を自動描画。
- **Discord 連携（一体型配信）**: 
  - 通貨ペアごとに「基本数値サマリー ＋ Gemini AI分析テキスト ＋ チャート画像」を1つのメッセージにまとめて配信。
  - パイプラインのシステムステータス・実行ログを専用チャンネルへリアルタイム通知。

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

## ⚙️ 必要な環境変数 (Secrets)

| 変数名 | 説明 |
| :--- | :--- |
| `GEMINI_API_KEY` | Google AI Studio で発行した Gemini API キー |
| `GCP_SA_KEY_JSON` | Google Cloud サービスアカウントの JSON 鍵（Base64エンコード） |
| `SPREADSHEET_ID` | 保存先 Google スプレッドシートの ID |
| `DISCORD_REPORT_WEBHOOK_URL` | レポート送信用 Discord Webhook URL |
| `DISCORD_LOG_WEBHOOK_URL` | システムログ送信用 Discord Webhook URL |

---

## 🏗 ディレクトリ構造

```text
fx_daily_pipeline/
├── data/                    # 通貨ペアごとのローカル蓄積データ
├── src/
│   ├── ai_reporter.py       # Gemini API + Web検索によるレポート生成
│   ├── data_fetcher.py      # GMOコイン API データ取得
│   ├── daily_reporter.py     # 日次データ検証・数値集計
│   ├── discord_client.py    # Discord Webhook 送信
│   ├── json_storage.py      # ローカル JSON 保存・管理
│   ├── pipeline_manager.py  # 日次パイプライン制御（司令塔）
│   ├── sheets_storage.py    # Google スプレッドシート自動保存
│   ├── system_logger.py     # システムログ管理
│   └── visualizer.py        # 日次チャート画像描画
├── main.py                  # エントリーポイント
└── README.md
