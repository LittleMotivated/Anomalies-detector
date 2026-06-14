"""
scripts/data_analyzer.py

Специализированный модуль расчётов: скользящие статистики и
методы выявления аномалий в котировках акций.


Используемые методы детекции:
    1. Z-Score   — отклонение от скользящего среднего в сигмах.
    2. IQR       — выход за пределы скользящего межквартильного
                   размаха (устойчив к выбросам).
    3. Объёмно-ценовой — одновременно аномальная лог-доходность
                   и аномальный объём торгов.

Соглашения о DataFrame с котировками:
    Колонки: 'Open', 'High', 'Low', 'Close', 'Volume'.
    Индекс:  pandas.DatetimeIndex, отсортированный по возрастанию.
"""

import numpy as np
import pandas as pd


def rolling_mean(series: pd.Series, window: int) -> pd.Series:
    """Скользящее среднее с заданным окном.

    :param series: входной числовой ряд (например, цены закрытия).
    :param window: размер окна в количестве наблюдений; должно быть > 1.
    :return:       pandas.Series той же длины; первые (window-1) точек = NaN.
    """
    if window < 2:
        raise ValueError("Размер окна должен быть не менее 2.")
    return series.rolling(window=window, min_periods=window).mean()


def rolling_std(series: pd.Series, window: int) -> pd.Series:
    """Скользящее стандартное отклонение (несмещённая оценка, ddof=1).

    :param series: входной числовой ряд.
    :param window: размер окна.
    :return:       pandas.Series со скользящим СКО; первые (window-1) = NaN.
    """
    if window < 2:
        raise ValueError("Размер окна должен быть не менее 2.")
    return series.rolling(window=window, min_periods=window).std(ddof=1)


def log_returns(close: pd.Series) -> pd.Series:
    """Логарифмические доходности по ценам закрытия.

    Формула: r_t = ln(C_t / C_{t-1}).

    :param close: ряд цен закрытия (строго положительные значения).
    :return:      pandas.Series лог-доходностей; первая точка = NaN.
    """
    if (close <= 0).any():
        raise ValueError("Цены закрытия должны быть строго положительными.")
    return np.log(close / close.shift(1))


def detect_anomalies_zscore(
    prices: pd.Series,
    window: int,
    sigma_threshold: float,
) -> pd.Series:
    """Детекция аномалий методом Z-Score (скользящих сигм).

    Для каждой точки x_t вычисляются скользящее среднее mu_t и
    скользящее стандартное отклонение sigma_t по предыдущим
    `window` наблюдениям. Точка помечается как аномалия, если
    |x_t - mu_t| / sigma_t > sigma_threshold.

    :param prices:           ряд цен.
    :param window:           размер скользящего окна (>= 2).
    :param sigma_threshold:  пороговое значение в сигмах (> 0).
    :return: pandas.Series типа bool той же длины и с тем же
             индексом; True означает аномалию. Точки, для которых
             статистики не определены (начало ряда), помечены False.
    """
    if sigma_threshold <= 0:
        raise ValueError("Порог в сигмах должен быть положительным.")

    mu = rolling_mean(prices, window)
    sigma = rolling_std(prices, window)

    z = (prices - mu) / sigma.replace(0, np.nan)
    flags = z.abs() > sigma_threshold
    return flags.fillna(False).astype(bool)


def detect_anomalies_iqr(
    prices: pd.Series,
    window: int,
    iqr_multiplier: float,
) -> pd.Series:
    """Детекция аномалий методом скользящего IQR.

    В скользящем окне `window` вычисляются первый (Q1) и третий
    (Q3) квартили, межквартильный размах IQR = Q3 - Q1. Точка
    помечается как аномалия, если она лежит вне диапазона
        [Q1 - k * IQR,  Q3 + k * IQR],
    где k = `iqr_multiplier`. Метод устойчив к выбросам в окне,
    т.к. квартили — порядковые статистики.

    :param prices:         ряд цен.
    :param window:         размер скользящего окна (>= 4).
    :param iqr_multiplier: множитель IQR (классическое значение 1.5).
    :return: pandas.Series типа bool с разметкой аномалий.
    """
    if window < 4:
        raise ValueError("Для IQR размер окна должен быть не менее 4.")
    if iqr_multiplier <= 0:
        raise ValueError("Множитель IQR должен быть положительным.")

    q1 = prices.rolling(window=window, min_periods=window).quantile(0.25)
    q3 = prices.rolling(window=window, min_periods=window).quantile(0.75)
    iqr = q3 - q1

    lower = q1 - iqr_multiplier * iqr
    upper = q3 + iqr_multiplier * iqr

    flags = (prices < lower) | (prices > upper)
    return flags.fillna(False).astype(bool)


def detect_anomalies_volume_price(
    close: pd.Series,
    volume: pd.Series,
    window: int,
    price_sigma_threshold: float,
    volume_multiplier: float,
    min_volume: float = 0.0,
) -> pd.Series:
    """Определение совместных ценово-объёмных аномалий.

    Точка считается аномалией, если одновременно выполнены условия:
      1) |r_t| > price_sigma_threshold * sigma^{r}_t,
         где r_t = ln(C_t / C_{t-1}) — лог-доходность, а
         sigma^{r}_t — скользящее СКО лог-доходностей в окне.
      2) V_t > volume_multiplier * mean(V_{t-window..t-1}),
         причём V_t >= min_volume.

    :param close:                  ряд цен закрытия.
    :param volume:                 ряд объёмов торгов (той же длины и с тем же индексом).
    :param window:                 размер окна.
    :param price_sigma_threshold:  порог по доходности в сигмах (> 0).
    :param volume_multiplier:      во сколько раз объём превышает скользящее среднее (> 1).
    :param min_volume:             минимальный абсолютный объём для учёта.
    :return: pandas.Series типа bool с разметкой совместных аномалий.
    """
    if not close.index.equals(volume.index):
        raise ValueError("Индексы цен и объёмов должны совпадать.")
    if price_sigma_threshold <= 0:
        raise ValueError("Порог по доходности должен быть положительным.")
    if volume_multiplier <= 1:
        raise ValueError("Множитель объёма должен быть строго больше 1.")

    r = log_returns(close)
    sigma_r = rolling_std(r, window)
    price_flag = (r.abs() > price_sigma_threshold * sigma_r).fillna(False)

    vol_mean = rolling_mean(volume.astype(float), window)
    volume_flag = ((volume > volume_multiplier * vol_mean)
                   & (volume >= min_volume)).fillna(False)

    flags = price_flag & volume_flag
    return flags.astype(bool)


def detect_anomalies(
    df: pd.DataFrame,
    method: str,
    window: int,
    params: dict,
) -> pd.Series:
    """Универсальная обёртка над тремя методами детекции.

    Позволяет GUI вызывать единый интерфейс независимо от
    выбранного пользователем метода.

    :param df:     DataFrame с обязательными столбцами 'Close' и 'Volume'.
    :param method: имя метода: 'zscore', 'iqr' или 'volume_price'.
    :param window: размер окна.
    :param params: словарь параметров, специфичных для метода:
                   - 'zscore':       {'sigma_threshold': float}
                   - 'iqr':          {'iqr_multiplier': float}
                   - 'volume_price': {'price_sigma_threshold': float,
                                      'volume_multiplier': float,
                                      'min_volume': float (опц.)}
    :return: pandas.Series типа bool с разметкой аномалий.
    :raises ValueError: при неизвестном методе или отсутствии нужных столбцов.
    """
    required = {"Close", "Volume"}
    if not required.issubset(df.columns):
        raise ValueError(
            f"DataFrame должен содержать столбцы {required}. "
            f"Найдено: {set(df.columns)}."
        )

    method = method.lower()
    if method == "zscore":
        return detect_anomalies_zscore(
            df["Close"], window, params["sigma_threshold"]
        )
    if method == "iqr":
        return detect_anomalies_iqr(
            df["Close"], window, params["iqr_multiplier"]
        )
    if method == "volume_price":
        return detect_anomalies_volume_price(
            df["Close"],
            df["Volume"],
            window,
            params["price_sigma_threshold"],
            params["volume_multiplier"],
            params.get("min_volume", 0.0),
        )
    raise ValueError(f"Неизвестный метод детекции: {method!r}.")


def compute_zscore_series(
    prices: pd.Series,
    window: int,
) -> pd.Series:
    """Возвращает ряд скользящих Z-оценок.

    :param prices: ряд цен.
    :param window: размер окна.
    :return:       pandas.Series значений z_t = (x_t - mu_t) / sigma_t.
    """
    mu = rolling_mean(prices, window)
    sigma = rolling_std(prices, window)
    return (prices - mu) / sigma.replace(0, np.nan)


def average_volume_by_period(
    df: pd.DataFrame,
    freq: str = "M",
) -> pd.Series:
    """Средний объём торгов, агрегированный по периоду.

    :param df:   DataFrame с колонкой 'Volume' и DatetimeIndex.
    :param freq: правило resample (например, 'M' — месяц, 'W' — неделя).
    :return:     pandas.Series со средним объёмом по периодам.
    """
    if "Volume" not in df.columns:
        raise ValueError("DataFrame должен содержать колонку 'Volume'.")
    return df["Volume"].resample(freq).mean()
