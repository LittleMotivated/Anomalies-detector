"""
library/file_operations.py

Универсальные функции работы с файлами и внешними источниками
данных.

Содержит:
    - Чтение и запись справочников (stocks.csv, daily_prices.csv)
      в формате CSV с поддержкой UTF-8;
    - Загрузку исторических котировок через библиотеку yfinance;
    - Операции над справочниками: добавление и
      удаление акций, добавление котировок;
    - Экспорт текстовых отчётов.

Схемы таблиц (3НФ):
    stocks.csv:
        id (int), ticker (str), name (str), sector (str)
    daily_prices.csv:
        id (int), stock_id (int), date (date),
        open (float), close (float), volume (int),
        high (float), low (float)
"""

from datetime import date, datetime
from pathlib import Path
from typing import Optional, Tuple, Union

import pandas as pd

STOCKS_COLUMNS: Tuple[str, ...] = ("id", "ticker", "name", "sector")
PRICES_COLUMNS: Tuple[str, ...] = (
    "id", "stock_id", "date",
    "open", "close", "volume", "high", "low",
)

def load_stocks(path: Path) -> pd.DataFrame:
    """Загрузить справочник акций из CSV.

    Если файл отсутствует, возвращается пустой DataFrame с
    корректным форматом.

    :param path: путь к stocks.csv.
    :return:     DataFrame со столбцами STOCKS_COLUMNS.
    :raises ValueError: при несовпадении формата существующего файла.
    """
    if not path.exists():
        return pd.DataFrame({
            "id": pd.Series(dtype="int64"),
            "ticker": pd.Series(dtype="string"),
            "name": pd.Series(dtype="string"),
            "sector": pd.Series(dtype="string"),
        })
    df = pd.read_csv(path, encoding="utf-8", dtype={
        "id": "int64", "ticker": "string",
        "name": "string", "sector": "string",
    })
    _validate_columns(df, STOCKS_COLUMNS, path)
    return df


def save_stocks(stocks: pd.DataFrame, path: Path) -> None:
    """Сохранить справочник акций в CSV (перезаписывая файл).

    :param stocks: DataFrame со столбцами STOCKS_COLUMNS.
    :param path:   путь к stocks.csv.
    :raises ValueError: при несовпадении формата.
    :raises OSError:    при ошибках записи.
    """
    _validate_columns(stocks, STOCKS_COLUMNS, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stocks.to_csv(path, index=False, encoding="utf-8")


def load_prices(path: Path) -> pd.DataFrame:
    """Загрузить справочник котировок из CSV.

    Если файл отсутствует, возвращается пустой DataFrame с
    корректным форматом.

    :param path: путь к daily_prices.csv.
    :return:     DataFrame со столбцами PRICES_COLUMNS;
                 колонка 'date' приведена к datetime64[ns].
    :raises ValueError: при несовпадении формата существующего файла.
    """
    if not path.exists():
        df = pd.DataFrame({
            "id": pd.Series(dtype="int64"),
            "stock_id": pd.Series(dtype="int64"),
            "date": pd.Series(dtype="datetime64[ns]"),
            "open": pd.Series(dtype="float64"),
            "close": pd.Series(dtype="float64"),
            "volume": pd.Series(dtype="int64"),
            "high": pd.Series(dtype="float64"),
            "low": pd.Series(dtype="float64"),
        })
        return df
    df = pd.read_csv(path, encoding="utf-8", parse_dates=["date"])
    _validate_columns(df, PRICES_COLUMNS, path)
    return df


def save_prices(prices: pd.DataFrame, path: Path) -> None:
    """Сохранить справочник котировок в CSV.

    Дата записывается в формате ISO (YYYY-MM-DD).

    :param prices: DataFrame в формате PRICES_COLUMNS.
    :param path:   путь к daily_prices.csv.
    :raises ValueError: при несовпадении формата.
    :raises OSError:    при ошибках записи.
    """
    _validate_columns(prices, PRICES_COLUMNS, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = prices.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False, encoding="utf-8")


def get_prices_for_ticker(
    stocks: pd.DataFrame,
    prices: pd.DataFrame,
    ticker: str,
) -> pd.DataFrame:
    """Сформировать DataFrame котировок выбранной акции
    в формате, ожидаемом модулем data_analyzer.

    Выполняет фильтрацию по stock_id, сортирует по дате
    и переименовывает колонки в OHLCV-формат с DatetimeIndex.

    :param stocks: справочник акций.
    :param prices: справочник котировок.
    :param ticker: тикер искомой акции.
    :return: DataFrame с колонками ('Open', 'High', 'Low',
             'Close', 'Volume'), индекс — DatetimeIndex.
    :raises KeyError: если тикер не найден в справочнике.
    """
    ticker_norm = ticker.strip().upper()
    matches = stocks[stocks["ticker"].str.upper() == ticker_norm]
    if matches.empty:
        raise KeyError(f"Тикер {ticker!r} не найден в справочнике акций.")

    stock_id = int(matches.iloc[0]["id"])
    rows = prices[prices["stock_id"] == stock_id].copy()
    rows = rows.sort_values("date")
    rows.index = pd.to_datetime(rows["date"])
    rows.index.name = "Date"

    return rows.rename(columns={
        "open": "Open", "high": "High", "low": "Low",
        "close": "Close", "volume": "Volume",
    })[["Open", "High", "Low", "Close", "Volume"]]


def fetch_yfinance(
    ticker: str,
    start: Union[str, date, datetime],
    end: Union[str, date, datetime],
) -> pd.DataFrame:
    """Загрузить исторические котировки акции из Yahoo Finance.

    Возвращаемый DataFrame имеет тот же формат, что и
    get_prices_for_ticker, и может быть передан в data_analyzer
    напрямую.

    :param ticker: тикер в формате Yahoo Finance
                   (например 'AAPL'; для российских акций — 'SBER.ME').
    :param start:  начальная дата (включительно).
    :param end:    конечная дата (не включительно).
    :return: DataFrame со столбцами ('Open', 'High', 'Low',
             'Close', 'Volume') и DatetimeIndex.
    :raises ImportError: если библиотека yfinance не установлена.
    :raises ValueError:  если данные не получены.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError(
            "Для загрузки котировок необходима библиотека yfinance."
        ) from exc

    raw = yf.download(
        ticker,
        start=start,
        end=end,
        progress=False,
        auto_adjust=True,
    )

    if raw is None or raw.empty:
        raise ValueError(
            f"Не удалось загрузить данные для тикера {ticker!r} "
            f"за период {start}..{end}. Проверьте корректность тикера "
            f"и доступность сети."
        )

    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)

    keep = ["Open", "High", "Low", "Close", "Volume"]
    missing = set(keep) - set(raw.columns)
    if missing:
        raise ValueError(
            f"yfinance вернул данные без колонок {missing} "
            f"для тикера {ticker!r}."
        )

    out = raw[keep].copy()
    out.index = pd.to_datetime(out.index)
    out.index.name = "Date"
    return out


def fetch_stock_info(ticker: str) -> dict:
    """Получить информацию об акции (название, сектор).

    :param ticker: тикер в формате Yahoo Finance.
    :return: словарь {'name': str, 'sector': str}.
    :raises ImportError: если yfinance не установлен.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise ImportError(
            "Для получения информации необходима yfinance."
        ) from exc

    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        info = {}

    return {
        "name": info.get("longName") or info.get("shortName") or "",
        "sector": info.get("sector") or "",
    }

# Известные российские тикеры — маршрутизируются в MOEX даже без суффикса .ME
_KNOWN_RU_TICKERS = frozenset({
    "SBER", "SBERP", "GAZP", "LKOH", "GMKN", "ROSN", "NVTK",
    "TATN", "TATNP", "MGNT", "MTSS", "VTBR", "SNGS", "SNGSP",
    "ALRS", "PLZL", "POLY", "MOEX", "AFLT", "CHMF", "NLMK",
    "PHOR", "RUAL", "YDEX", "MAGN", "AFKS", "IRAO", "FEES",
    "HYDR", "RTKM", "RTKMP", "BSPB", "TCSG",
})


def _normalize_ru_ticker(ticker: str) -> str:
    """Удалить суффиксы Yahoo-стиля (.ME, .MOEX) из тикера.

    :param ticker: тикер в любом регистре, с суффиксом или без.
    :return:       тикер без суффикса, в верхнем регистре.
    """
    t = ticker.upper().strip()
    for suffix in (".ME", ".MOEX"):
        if t.endswith(suffix):
            return t[:-len(suffix)]
    return t


def _is_moex_ticker(ticker: str) -> bool:
    """Определить, направлять ли запрос в MOEX, а не в Yahoo.

    MOEX выбирается для тикеров с суффиксом .ME / .MOEX и для
    известных российских тикеров из _KNOWN_RU_TICKERS.

    :param ticker: тикер в любом формате.
    :return:       True, если запрос идёт в MOEX.
    """
    t = ticker.upper().strip()
    if t.endswith(".ME") or t.endswith(".MOEX"):
        return True
    return _normalize_ru_ticker(t) in _KNOWN_RU_TICKERS


def fetch_moex(
    ticker: str,
    start: Union[str, date, datetime],
    end: Union[str, date, datetime],
) -> pd.DataFrame:
    """Загрузить котировки с Московской биржи через apimoex.

    Возвращаемый DataFrame имеет тот же формат, что и fetch_yfinance:
    колонки OHLCV с DatetimeIndex.

    :param ticker: тикер в формате MOEX ('SBER') или с суффиксом
                   ('SBER.ME').
    :param start:  начальная дата (включительно).
    :param end:    конечная дата (включительно).
    :return: DataFrame со столбцами ('Open', 'High', 'Low',
             'Close', 'Volume') и DatetimeIndex.
    :raises ImportError: если apimoex не установлен.
    :raises ValueError:  если данные не получены.
    """
    try:
        import apimoex
        import requests
    except ImportError as exc:
        raise ImportError(
            "Для загрузки с MOEX необходимы apimoex и requests."
        ) from exc

    ticker_norm = _normalize_ru_ticker(ticker)
    start_str = str(start)[:10]
    end_str = str(end)[:10]

    with requests.Session() as session:
        data = apimoex.get_board_history(
            session,
            security=ticker_norm,
            start=start_str,
            end=end_str,
            columns=("TRADEDATE", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"),
        )

    if not data:
        raise ValueError(
            f"MOEX не вернула данных для тикера {ticker_norm!r} "
            f"за период {start}..{end}. Проверьте корректность тикера"
        )

    df = pd.DataFrame(data).rename(columns={
        "TRADEDATE": "Date",
        "OPEN":      "Open",
        "HIGH":      "High",
        "LOW":       "Low",
        "CLOSE":     "Close",
        "VOLUME":    "Volume",
    })
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.set_index("Date").sort_index()
    df.index.name = "Date"
    df["Volume"] = df["Volume"].astype("int64")
    return df[["Open", "High", "Low", "Close", "Volume"]]


def fetch_moex_info(ticker: str) -> dict:
    """Получить название акции с MOEX.

    :param ticker: тикер в формате MOEX или с суффиксом.
    :return: словарь {'name': str, 'sector': str}.
    :raises ImportError: если apimoex не установлен.
    """
    try:
        import apimoex
        import requests
    except ImportError as exc:
        raise ImportError(
            "Для информации MOEX необходима apimoex."
        ) from exc

    ticker_norm = _normalize_ru_ticker(ticker)

    try:
        with requests.Session() as session:
            results = apimoex.find_securities(
                session, ticker_norm,
                columns=("secid", "name", "shortname"),
            )
    except Exception:
        return {"name": "", "sector": ""}

    if not results:
        return {"name": "", "sector": ""}

    match = next(
        (r for r in results
         if str(r.get("secid", "")).upper() == ticker_norm),
        results[0],
    )
    return {
        "name": match.get("name") or match.get("shortname") or "",
        "sector": "—",
    }

def fetch_quotes(
    ticker: str,
    start: Union[str, date, datetime],
    end: Union[str, date, datetime],
) -> pd.DataFrame:
    """Универсальная загрузка котировок с автовыбором источника.

    Использует MOEX для тикеров с суффиксом .ME / .MOEX и для
    известных российских тикеров без суффикса. Для остальных используется yfinance.

    :param ticker: тикер в любом формате.
    :param start:  начальная дата.
    :param end:    конечная дата.
    :return: DataFrame OHLCV с DatetimeIndex.
    """
    if _is_moex_ticker(ticker):
        return fetch_moex(ticker, start, end)
    return fetch_yfinance(ticker, start, end)


def fetch_quote_info(ticker: str) -> dict:
    """Универсальные данные с автовыбором источника.

    :param ticker: тикер в любом формате.
    :return: словарь {'name': str, 'sector': str}.
    """
    if _is_moex_ticker(ticker):
        return fetch_moex_info(ticker)
    return fetch_stock_info(ticker)

def add_stock(
    stocks: pd.DataFrame,
    ticker: str,
    name: str,
    sector: str,
) -> Tuple[pd.DataFrame, int]:
    """Добавить новую акцию в справочник.

    Возвращает новый DataFrame. Если акция с таким тикером уже
    есть, исходный справочник возвращается без изменений.

    :param stocks: справочник акций.
    :param ticker: тикер новой акции.
    :param name:   полное наименование компании.
    :param sector: сектор экономики.
    :return: кортеж (новый_DataFrame, id_акции).
    """
    ticker_norm = ticker.strip().upper()
    existing = stocks[stocks["ticker"].str.upper() == ticker_norm]
    if not existing.empty:
        return stocks, int(existing.iloc[0]["id"])

    new_id = int(stocks["id"].max() + 1) if not stocks.empty else 1
    new_row = pd.DataFrame([{
        "id": new_id,
        "ticker": ticker_norm,
        "name": name,
        "sector": sector,
    }])
    updated = pd.concat([stocks, new_row], ignore_index=True)
    return updated, new_id


def append_prices(
    prices: pd.DataFrame,
    stock_id: int,
    ohlcv: pd.DataFrame,
) -> pd.DataFrame:
    """Добавить котировки в справочник для указанной акции.

    Дубликаты по (stock_id, date) автоматически удаляются:
    приоритет имеют новые записи (последняя версия).

    :param prices:   текущий справочник котировок.
    :param stock_id: ID акции, к которой относятся котировки.
    :param ohlcv:    DataFrame с колонками 'Open', 'High', 'Low',
                     'Close', 'Volume' и DatetimeIndex.
    :return: новый справочник котировок.
    """
    if ohlcv.empty:
        return prices

    next_id = int(prices["id"].max() + 1) if not prices.empty else 1
    new_rows = pd.DataFrame({
        "id": range(next_id, next_id + len(ohlcv)),
        "stock_id": stock_id,
        "date": pd.to_datetime(ohlcv.index),
        "open": ohlcv["Open"].astype("float64").values,
        "close": ohlcv["Close"].astype("float64").values,
        "volume": ohlcv["Volume"].astype("int64").values,
        "high": ohlcv["High"].astype("float64").values,
        "low": ohlcv["Low"].astype("float64").values,
    })

    combined = pd.concat([prices, new_rows], ignore_index=True)
    deduped = combined.drop_duplicates(
        subset=["stock_id", "date"], keep="last",
    ).reset_index(drop=True)

    deduped["id"] = range(1, len(deduped) + 1)
    return deduped

def export_text_report(
    ohlcv: pd.DataFrame,
    path: Path,
    ticker: Optional[str] = None,
) -> None:
    """Сохранить текстовый отчёт «Дата | Цена закрытия | Объём»
    в формате csv

    :param ohlcv:  DataFrame с колонками 'Close' и 'Volume' и DatetimeIndex.
    :param path:   путь к создаваемому файлу.
    :param ticker: опциональный тикер для шапки отчёта.
    :raises ValueError: при отсутствии обязательных колонок.
    """
    required = {"Close", "Volume"}
    if not required.issubset(ohlcv.columns):
        raise ValueError(
            f"DataFrame должен содержать колонки {required}."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    report = pd.DataFrame({
        "Дата": pd.to_datetime(ohlcv.index).strftime("%Y-%m-%d"),
        "Цена закрытия": ohlcv["Close"].round(4).values,
        "Объём": ohlcv["Volume"].astype("int64").values,
    })

    with path.open("w", encoding="utf-8") as fh:
        if ticker:
            fh.write(f"# Отчёт по акции: {ticker}\n")
            if len(report) > 0:
                fh.write(
                    f"# Период: {report['Дата'].iloc[0]}"
                    f"..{report['Дата'].iloc[-1]}\n"
                )
            fh.write(f"# Количество записей: {len(report)}\n")
        report.to_csv(fh, index=False)

def _validate_columns(
    df: pd.DataFrame,
    expected: Tuple[str, ...],
    path: Path,
) -> None:
    """Проверить, что у DataFrame ровно ожидаемый набор колонок.

    :param df:       проверяемый DataFrame.
    :param expected: ожидаемый набор имён колонок.
    :param path:     путь к исходному файлу (для сообщения об ошибке).
    :raises ValueError: при отсутствующих или лишних колонках.
    """
    missing = set(expected) - set(df.columns)
    extra = set(df.columns) - set(expected)
    if missing or extra:
        raise ValueError(
            f"Некорректный формат файла {path}.\n"
            f"  Ожидаемые колонки:      {list(expected)}\n"
            f"  Отсутствуют:            {sorted(missing) or '-'}\n"
            f"  Лишние:                 {sorted(extra) or '-'}"
        )
