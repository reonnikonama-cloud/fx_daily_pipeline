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

            # データが正常に取得できているか検証
            if not bulk_df.empty:
                return bulk_df

        except Exception as e:
            print(f"取得エラー発生 ({attempt}/{max_retries}): {e}")

        # 429対策：リトライごとに待機時間を伸ばす (10秒, 20秒, 30秒...)
        wait_time = attempt * 10
        print(f"429回避のため {wait_time} 秒待機して再試行します...")
        time.sleep(wait_time)

    return pd.DataFrame()


def save_split_data_to_json(
    bulk_df: pd.DataFrame, base_dir: str = BASE_DATA_DIR
) -> bool:
    """一括取得データを各通貨の data/{symbol}/data.json へ保存"""
    if bulk_df.empty:
        return False

    saved_any = False

    for pair_name, symbol in PAIRS.items():
        try:
            # MultiIndex構造からの抽出
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

            # JSON用データ形式へ整形
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

            # ディレクトリの作成 (例: data/JPY=X/)
            pair_dir = os.path.join(base_dir, symbol)
            os.makedirs(pair_dir, exist_ok=True)

            # json書き出し
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
        print(f"ファイル未存在: {json_path}")
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
    target_date = (datetime.now() - timedelta(days=1)).date()

    # ----------------------------------------------------
    # Step 1: 一括取得 ➔ ディレクトリ分離 data.json 保存
    # ----------------------------------------------------
    logger.info(
        "一括取得開始",
        f"対象日 [{target_date}] のデータを取得し、`{BASE_DATA_DIR}/{{symbol}}/data.json` へ保存します。",
    )

    ticker_symbols = list(PAIRS.values())

    # 429リトライ機能付き一括ダウンロード
    bulk_df = fetch_bulk_data_with_retry(ticker_symbols, max_retries=5)

    if bulk_df.empty:
        logger.error(
            "取得失敗",
            "Yahoo Financeからのデータ一括取得に失敗（またはレートリミット到達）したため処理を中断します。",
        )
        return

    # 各通貨の json ファイルへ保存
    save_success = save_split_data_to_json(bulk_df, base_dir=BASE_DATA_DIR)

    if not save_success:
        logger.error(
            "JSON保存失敗",
            f"`{BASE_DATA_DIR}/{{symbol}}/data.json` の生成・保存に失敗しました。",
        )
        return

    logger.info(
        "JSON保存完了",
        f"全対象ペアの `{BASE_DATA_DIR}/{{symbol}}/data.json` 生成が完了しました。",
    )

    # ----------------------------------------------------
    # Step 2: 各通貨の data.json から読み込んで処理
    # ----------------------------------------------------
    for pair_name, symbol in PAIRS.items():
        logger.info(
            "個別処理開始",
            f"=== 【{pair_name}】({symbol}) のデータ検証・出力処理を開始 ===",
        )

        try:
            # 作成された data.json から読み込み
            df_pair = load_pair_data_from_json(symbol, base_dir=BASE_DATA_DIR)

            if df_pair.empty:
                logger.warning(
                    "データ未存在",
                    f"[{pair_name}] の JSON ファイル ({BASE_DATA_DIR}/{symbol}/data.json) が読み込めませんでした。",
                )
                continue

            reporter = FXDailyReporter(pips_value=0.01, logger=logger)
            df_day = reporter.extract_verified_full_day_with_logging(
                df_pair, target_date=target_date, pair_label=pair_name
            )

            if df_day.empty:
                logger.warning(
                    "処理スキップ",
                    f"[{pair_name}] は288本完全データが不揃いのため出力を保留します。",
                )
                continue

            chart_filename = f"chart_{symbol.replace('=X', '')}.png"
            BacktestVisualizer.plot_daily_line_chart(
                df_day,
                pair_title=f"{pair_name} ({symbol})",
                target_date=target_date,
                save_path=chart_filename,
            )

            report = reporter.generate_report(df_day, pair_name=pair_name)
            success = reporter.send_discord_webhook(
                report, REPORT_WEBHOOK_URL, image_path=chart_filename
            )

            if success:
                logger.info(
                    "送信完了",
                    f"[{pair_name}] のレポート・画像を正常送信しました。",
                )

            if os.path.exists(chart_filename):
                os.remove(chart_filename)

            # API連打防止用の小休憩（0.5秒）
            time.sleep(0.5)

        except Exception as e:
            logger.error(
                "個別例外エラー",
                f"[{pair_name}] 処理中に予期せぬ例外が発生しました:\n{e}",
            )

    logger.info(
        "全処理完了",
        "全9通貨ペアの個別データ読み込み・検証・配信が完了しました。",
    )


if __name__ == "__main__":
    main()
