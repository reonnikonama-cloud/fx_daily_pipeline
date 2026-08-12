# main.py

import json
import os
import time
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf

from src.daily_reporter import FXDailyReporter
from src.system_logger import SystemLogger
from src.visualizer import BacktestVisualizer

# Webhook URL
REPORT_WEBHOOK_URL = os.getenv("DISCORD_REPORT_WEBHOOK_URL")  # #daily-summary
LOG_WEBHOOK_URL = os.getenv("DISCORD_LOG_WEBHOOK_URL")  # #system-logs

# 9通貨ペアの定義
PAIRS = {
    "米ドル/円": "JPY=X",
    "ユーロ/円": "EURJPY=X",
    "英ポンド/円": "GBPJPY=X",
    "スイスフラン/円": "CHFJPY=X",
    "カナダドル/円": "CADJPY=X",
    "豪ドル/円": "AUDJPY=X",
    "NZドル/円": "NZDJPY=X",
    "人民元/円": "CNYJPY=X",
    "インドルピー/円": "INRJPY=X",
}

BASE_DATA_DIR = "data"


def fetch_bulk_data_with_retry(
    symbols: list, max_retries: int = 5
) -> pd.DataFrame:
    """429エラー(Rate Limit)対策を入れた一括取得ロジック"""
    for attempt in range(1, max_retries + 1):
        try:
            print(f"データ一括取得試行中... ({attempt}/{max_retries})")
            bulk_df = yf.download(
                tickers=symbols,
                period="5d",
                interval="5m",
                group_by="ticker",
                progress=False,
            )

            if not bulk_df.empty:
                return bulk_df

        except Exception as e:
            print(f"取得エラー発生 ({attempt}/{max_retries}): {e}")

        wait_time = attempt * 10
        print(f"429回避のため {wait_time} 秒待機して再試行します...")
        time.sleep(wait_time)

    return pd.DataFrame()


def save_split_data_to_json(
    bulk_df: pd.DataFrame, base_dir: str = BASE_DATA_DIR
) -> bool:
    """一括取得データを各通貨の data/{symbol}/data.json へ確実に保存する"""
    if bulk_df.empty:
        return False

    saved_any = False

    for pair_name, symbol in PAIRS.items():
        try:
            if (
                isinstance(bulk_df.columns, pd.MultiIndex)
                and symbol in bulk_df.columns.levels[0]
            ):
                df_pair = bulk_df[symbol].copy().dropna(subset=["Close"])
            elif not isinstance(bulk_df.columns, pd.MultiIndex):
                df_pair = bulk_df.copy().dropna(subset=["Close"])
            else:
                continue

            if df_pair.empty:
                continue

            records = []
            for idx, row in df_pair.iterrows():
                records.append(
                    {
                        "timestamp": idx.strftime("%Y-%m-%d %H:%M:%S"),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": (
                            int(row["Volume"]) if "Volume" in row else 0
                        ),
                    }
                )

            pair_dir = os.path.join(base_dir, symbol)
            os.makedirs(pair_dir, exist_ok=True)

            json_path = os.path.join(pair_dir, "data.json")
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)

            saved_any = True
            print(f"[{symbol}] data.json 保存成功 ({len(records)} 件)")

        except Exception as e:
            print(f"JSON保存処理エラー ({symbol}): {e}")

    return saved_any


def load_pair_data_from_json(
    symbol: str, base_dir: str = BASE_DATA_DIR
) -> pd.DataFrame:
    """data/{symbol}/data.json からデータを読み込んで DataFrame 化"""
    json_path = os.path.join(base_dir, symbol, "data.json")

    if not os.path.exists(json_path):
        return pd.DataFrame()

    with open(json_path, "r", encoding="utf-8") as f:
        records = json.load(f)

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["Datetime"] = pd.to_datetime(df["timestamp"])
    df.set_index("Datetime", inplace=True)
    df.rename(
        columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume",
        },
        inplace=True,
    )
    return df


def main():
    logger = SystemLogger(webhook_url=LOG_WEBHOOK_URL)

    # 運用ルール：基本は「前日分」を対象とする（翌日00:00以降に前日分が確定するため）
    target_date = (datetime.now() - timedelta(days=1)).date()
    today_date = datetime.now().date()

    # 判定：今日（当日）のデータをチェックしているか、前日分の確定データを処理しているか
    # ※ cron-job.org で翌日未明（00:00以降）に回す場合は target_date は「前日」になります。
    logger.info(
        "パイプライン起動",
        f"処理対象日: [{target_date}] (実行現在日: [{today_date}])",
    )

    # Step 1: 一括取得 ➔ ディレクトリ分離 data.json 保存（時間帯問わず常に実行してファイルを生成・更新）
    ticker_symbols = list(PAIRS.values())
    bulk_df = fetch_bulk_data_with_retry(ticker_symbols, max_retries=5)

    if bulk_df.empty:
        logger.error(
            "取得失敗",
            "Yahoo Financeからのデータ一括取得に失敗（またはレートリミット到達）しました。",
        )
        return

    save_success = save_split_data_to_json(bulk_df, base_dir=BASE_DATA_DIR)
    if not save_success:
        logger.error(
            "JSON保存失敗",
            f"`{BASE_DATA_DIR}/{{symbol}}/data.json` の生成に失敗しました。",
        )
        return

    logger.info(
        "JSON保存完了",
        f"全対象ペアの `{BASE_DATA_DIR}/{{symbol}}/data.json` が正常に生成・更新されました。",
    )

    # Step 2: 各通貨の data.json から読み込んで処理・レポート検証
    for pair_name, symbol in PAIRS.items():
        try:
            df_pair = load_pair_data_from_json(symbol, base_dir=BASE_DATA_DIR)

            if df_pair.empty:
                logger.warning(
                    "データ未存在",
                    f"[{pair_name}] の JSON ファイルが読み込めませんでした。",
                )
                continue

            reporter = FXDailyReporter(pips_value=0.01, logger=logger)

            # 対象日のデータ抽出
            df_day = df_pair[df_pair.index.date == target_date].sort_index()
            actual_count = len(df_day)

            # 【判定分岐】
            # 1. 288本完全揃っている場合（あるいは翌日00:00以降の本番フェーズ）
            if actual_count == 288:
                logger.info(
                    "完全データ検知",
                    f"[{pair_name}] [{target_date}] 288本完全データを確認。正式レポートを作成します。",
                )

                # 正式な検証ログ＆レポート送信
                df_verified = (
                    reporter.extract_verified_full_day_with_logging(
                        df_pair, target_date=target_date, pair_label=pair_name
                    )
                )
                if not df_verified.empty:
                    chart_filename = f"chart_{symbol.replace('=X', '')}.png"
                    BacktestVisualizer.plot_daily_line_chart(
                        df_verified,
                        pair_title=f"{pair_name} ({symbol})",
                        target_date=target_date,
                        save_path=chart_filename,
                    )

                    report = reporter.generate_report(
                        df_verified, pair_name=pair_name
                    )
                    success = reporter.send_discord_webhook(
                        report, REPORT_WEBHOOK_URL, image_path=chart_filename
                    )

                    if success:
                        logger.info(
                            "送信完了",
                            f"[{pair_name}] の日次確定レポートを送信しました。",
                        )
                    if os.path.exists(chart_filename):
                        os.remove(chart_filename)

            else:
                # 2. まだ288本に達していない場合（日中テスト・途中経過の確認用）
                logger.warning(
                    "途中経過データ確認",
                    f"[{pair_name}] [{target_date}] 現在の取得本数: {actual_count}/288本。"
                    "（※日中実行またはデータ蓄積中のため、本番レポート送信はスキップしファイル生成チェックのみ行いました）",
                )

            time.sleep(0.5)

        except Exception as e:
            logger.error(
                "個別例外エラー",
                f"[{pair_name}] 処理中に予期せぬ例外が発生しました:\n{e}",
            )

    logger.info("全処理完了", "パイプラインの実行が正常に終了しました。")


if __name__ == "__main__":
    main()
