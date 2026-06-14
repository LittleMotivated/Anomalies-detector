"""
scripts/bulk_load.py

Массовая загрузка котировок нескольких акций через yfinance.
Полезен для одноразового пополнения локального справочника: один
успешный сеанс с работающим VPN — и дальше можно работать офлайн
сколько угодно, без зависимости от статуса Yahoo.

Логика:
    1. Идём по списку тикеров с паузой ~2.5 сек между запросами
       (из-за ограничений Yahoo/MOEX).
    2. Для каждого тикера: скачиваем котировки, метаданные, сохраняем в
       справочники в памяти.
    3. В конце сохраняем CSV.
"""

import argparse
import time

import config as cfg
from library import file_operations as fo

DEFAULT_TICKERS = [
    "SBER", "GAZP", "LKOH", "GMKN", "ROSN",
    "NVTK", "TATN", "MGNT", "PLZL", "MOEX",
    "AAPL", "MSFT", "GOOGL", "NVDA", "TSLA",
]


def bulk_load(
    tickers: list,
    start: str,
    end: str,
    sleep_sec: float = 2.5,
) -> None:
    """Загрузить котировки списка тикеров и пополнить справочники.

    :param tickers:   список тикеров в формате Yahoo Finance.
    :param start:     начальная дата.
    :param end:       конечная дата.
    :param sleep_sec: пауза между запросами в секундах.
    """
    settings = cfg.load_settings()
    cfg.ensure_data_directories(settings)

    stocks = fo.load_stocks(settings.paths.stocks_file)
    prices = fo.load_prices(settings.paths.prices_file)

    print(f"Стартовое состояние: {len(stocks)} акций, {len(prices)} котировок")
    print(f"К загрузке: {len(tickers)} тикеров, период {start}..{end}")
    print(f"Пауза между запросами: {sleep_sec} сек\n")

    success: list = []
    failed: list = []

    for i, ticker in enumerate(tickers, 1):
        print(f"[{i:2d}/{len(tickers)}] {ticker:10s} ... ",
              end="", flush=True)

        try:
            ohlcv = fo.fetch_quotes(ticker, start, end)
        except Exception as exc:
            print(f"Ошибка: {type(exc).__name__}")
            failed.append((ticker, f"{type(exc).__name__}: {exc}"))
            time.sleep(sleep_sec)
            continue

        try:
            info = fo.fetch_quote_info(ticker)
        except Exception:
            info = {"name": "", "sector": ""}

        name = info["name"] or ticker
        sector = info["sector"] or "—"

        stocks, stock_id = fo.add_stock(stocks, ticker, name, sector)
        prices = fo.append_prices(prices, stock_id, ohlcv)

        print(f"OK — {len(ohlcv)} дней, «{name[:40]}»")
        success.append(ticker)
        time.sleep(sleep_sec)

    try:
        fo.save_stocks(stocks, settings.paths.stocks_file)
        fo.save_prices(prices, settings.paths.prices_file)
    except OSError as exc:
        print(f"\n[!] Ошибка записи CSV: {exc}")
        return

    print("\n" + "=" * 60)
    print(f"Успешно загружено:   {len(success)} тикеров")
    if success:
        print(f"  {', '.join(success)}")
    print(f"Не удалось загрузить: {len(failed)} тикеров")
    for ticker, err in failed:
        print(f"  {ticker:10s}  {err[:100]}")
    print(f"\nВ справочнике теперь: {len(stocks)} акций, "
          f"{len(prices)} котировок")
    print("Файлы записаны в:")
    print(f"  {settings.paths.stocks_file}")
    print(f"  {settings.paths.prices_file}")


def _parse_args() -> argparse.Namespace:
    """Разобрать аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description="Массовая загрузка котировок акций из Yahoo Finance.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "tickers", nargs="*", default=DEFAULT_TICKERS,
        help="Список тикеров через пробел (по умолчанию — встроенный список).",
    )
    parser.add_argument("--start", default="2024-01-01",
                        help="Начальная дата ISO.")
    parser.add_argument("--end", default="2025-06-01",
                        help="Конечная дата ISO.")
    parser.add_argument("--sleep", type=float, default=2.5,
                        help="Пауза между запросами в секундах.")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    bulk_load(args.tickers, args.start, args.end, args.sleep)
