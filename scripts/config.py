"""
scripts/config.py

Загрузка и сохранение параметров приложения из/в settings.ini.

Модуль преобразует строковые значения конфигурационного файла
в типизированные структуры (frozen dataclass), которые удобно
передавать в остальные модули проекта.

Соглашение о путях:
    Все относительные пути в секции [Paths] разрешаются
    относительно каталога, в котором лежит сам settings.ini.
    Это делает приложение переносимым: его можно запускать
    из любого рабочего каталога.

Публичный API:
    load_settings(path=None)            -> Settings
    save_settings(settings, path=None)  -> None
    resolve_zscore_threshold(...)       — порог сигм по пресету.
    resolve_iqr_multiplier(...)         — множитель IQR по пресету.
    resolve_volume_price_thresholds(...) — пара порогов для V/P-метода.
    ensure_data_directories(settings)   — создать каталоги при старте.
"""

import configparser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

@dataclass(frozen=True)
class Paths:
    """Каталоги и файлы данных (абсолютные пути)."""
    data_dir: Path
    graphics_dir: Path
    output_dir: Path
    stocks_file: Path
    prices_file: Path


@dataclass(frozen=True)
class Interface:
    """Параметры внешнего вида GUI."""
    font_family: str
    font_size: int
    bg_color: str
    fg_color: str
    window_width: int
    window_height: int
    default_candles_n: int


@dataclass(frozen=True)
class DetectorDefaults:
    """Общие настройки детектора аномалий."""
    method: str
    window: int
    min_volume: float


@dataclass(frozen=True)
class ZScoreParams:
    """Параметры метода Z-Score."""
    sensitivity_low: float
    sensitivity_medium: float
    sensitivity_high: float
    manual_sigma: Optional[float]


@dataclass(frozen=True)
class IQRParams:
    """Параметры метода IQR."""
    sensitivity_low: float
    sensitivity_medium: float
    sensitivity_high: float


@dataclass(frozen=True)
class VolumePriceParams:
    """Параметры объёмно-ценового метода."""
    price_sigma_low: float
    price_sigma_medium: float
    price_sigma_high: float
    volume_mult_low: float
    volume_mult_medium: float
    volume_mult_high: float


@dataclass(frozen=True)
class Markers:
    """Цвета и размеры маркеров на графике."""
    anomaly_color: str
    normal_color: str
    volume_bar_color: str
    marker_size: int


@dataclass(frozen=True)
class Settings:
    """Полный набор настроек приложения.

    Поле `source_file` хранит путь к файлу, из которого настройки
    были загружены: используется по умолчанию в save_settings().
    """
    paths: Paths
    interface: Interface
    detector: DetectorDefaults
    zscore: ZScoreParams
    iqr: IQRParams
    volume_price: VolumePriceParams
    markers: Markers
    source_file: Path

def _find_settings_file(explicit: Optional[Path] = None) -> Path:
    """Найти settings.ini

    :param explicit: явно указанный пользователем путь либо None.
    :return:         разрешённый абсолютный путь.
    :raises FileNotFoundError: если файл не найден.
    """
    if explicit is not None:
        p = Path(explicit).resolve()
        if not p.exists():
            raise FileNotFoundError(f"settings.ini не найден: {p}")
        return p

    path = Path.cwd() / "settings.ini"
    if path.exists():
        return path.resolve()

def _parse_paths(parser: configparser.ConfigParser, base_dir: Path) -> Paths:
    """Разобрать секцию [Paths], разрешая относительные пути.

    :param parser:   ConfigParser, уже прочитавший settings.ini.
    :param base_dir: каталог, относительно которого разрешаются пути.
    :return:         объект Paths с абсолютными путями.
    """
    section = parser["Paths"]

    def _abs(key: str) -> Path:
        p = Path(section[key])
        return p if p.is_absolute() else (base_dir / p).resolve()

    return Paths(
        data_dir=_abs("data_dir"),
        graphics_dir=_abs("graphics_dir"),
        output_dir=_abs("output_dir"),
        stocks_file=_abs("stocks_file"),
        prices_file=_abs("prices_file"),
    )


def _parse_interface(parser: configparser.ConfigParser) -> Interface:
    """Разобрать секцию [Interface]."""
    s = parser["Interface"]
    return Interface(
        font_family=s["font_family"],
        font_size=s.getint("font_size"),
        bg_color=s["bg_color"],
        fg_color=s["fg_color"],
        window_width=s.getint("window_width"),
        window_height=s.getint("window_height"),
        default_candles_n=s.getint("default_candles_n"),
    )


def _parse_detector(parser: configparser.ConfigParser) -> DetectorDefaults:
    """Разобрать секцию [Detector]."""
    s = parser["Detector"]
    return DetectorDefaults(
        method=s["default_method"].strip().lower(),
        window=s.getint("default_window"),
        min_volume=s.getfloat("min_volume"),
    )


def _parse_zscore(parser: configparser.ConfigParser) -> ZScoreParams:
    """Разобрать секцию [Detector.ZScore]."""
    s = parser["Detector.ZScore"]
    raw_manual = s.get("manual_sigma", "").strip()
    manual = float(raw_manual) if raw_manual else None
    return ZScoreParams(
        sensitivity_low=s.getfloat("sensitivity_low"),
        sensitivity_medium=s.getfloat("sensitivity_medium"),
        sensitivity_high=s.getfloat("sensitivity_high"),
        manual_sigma=manual,
    )


def _parse_iqr(parser: configparser.ConfigParser) -> IQRParams:
    """Разобрать секцию [Detector.IQR]."""
    s = parser["Detector.IQR"]
    return IQRParams(
        sensitivity_low=s.getfloat("sensitivity_low"),
        sensitivity_medium=s.getfloat("sensitivity_medium"),
        sensitivity_high=s.getfloat("sensitivity_high"),
    )


def _parse_volume_price(parser: configparser.ConfigParser) -> VolumePriceParams:
    """Разобрать секцию [Detector.VolumePrice]."""
    s = parser["Detector.VolumePrice"]
    return VolumePriceParams(
        price_sigma_low=s.getfloat("price_sigma_low"),
        price_sigma_medium=s.getfloat("price_sigma_medium"),
        price_sigma_high=s.getfloat("price_sigma_high"),
        volume_mult_low=s.getfloat("volume_mult_low"),
        volume_mult_medium=s.getfloat("volume_mult_medium"),
        volume_mult_high=s.getfloat("volume_mult_high"),
    )


def _parse_markers(parser: configparser.ConfigParser) -> Markers:
    """Разобрать секцию [Markers]."""
    s = parser["Markers"]
    return Markers(
        anomaly_color=s["anomaly_color"],
        normal_color=s["normal_color"],
        volume_bar_color=s["volume_bar_color"],
        marker_size=s.getint("marker_size"),
    )


def load_settings(path: Optional[Path] = None) -> Settings:
    """Загрузить настройки из settings.ini.

    Все относительные пути в секции [Paths] разрешаются относительно
    каталога, в котором лежит settings.ini. Сами каталоги, если они
    не существуют, не создаются автоматически — для этого есть
    функция ensure_data_directories().

    :param path: явный путь к settings.ini.
    :return:     заполненный объект Settings.
    :raises FileNotFoundError: если файл не найден.
    :raises configparser.Error: при ошибках синтаксиса ini-файла.
    :raises KeyError: при отсутствии обязательной секции/ключа.
    """
    ini_path = _find_settings_file(path)
    parser = configparser.ConfigParser(inline_comment_prefixes=(";",))

    with ini_path.open(encoding="utf-8") as fh:
        parser.read_file(fh)

    base_dir = ini_path.parent

    return Settings(
        paths=_parse_paths(parser, base_dir),
        interface=_parse_interface(parser),
        detector=_parse_detector(parser),
        zscore=_parse_zscore(parser),
        iqr=_parse_iqr(parser),
        volume_price=_parse_volume_price(parser),
        markers=_parse_markers(parser),
        source_file=ini_path,
    )


def save_settings(
    settings: Settings,
    path: Optional[Path] = None,
) -> None:
    """Записать текущие настройки в settings.ini.

    Используется вкладкой «Настройки детекции» для сохранения
    изменений, сделанных пользователем в GUI.

    :param settings: объект Settings, обычно полученный из load_settings()
                     и затем обновлённый через dataclasses.replace().
    :param path:     путь для записи; по умолчанию — settings.source_file.
    :raises OSError: при ошибках записи.
    """
    target = Path(path) if path is not None else settings.source_file
    parser = configparser.ConfigParser(inline_comment_prefixes=(";",))

    parser["Paths"] = {
        "data_dir": settings.paths.data_dir.as_posix(),
        "graphics_dir": settings.paths.graphics_dir.as_posix(),
        "output_dir": settings.paths.output_dir.as_posix(),
        "stocks_file": settings.paths.stocks_file.as_posix(),
        "prices_file": settings.paths.prices_file.as_posix(),
    }
    parser["Interface"] = {
        "font_family": settings.interface.font_family,
        "font_size": str(settings.interface.font_size),
        "bg_color": settings.interface.bg_color,
        "fg_color": settings.interface.fg_color,
        "window_width": str(settings.interface.window_width),
        "window_height": str(settings.interface.window_height),
        "default_candles_n": str(settings.interface.default_candles_n),
    }
    parser["Detector"] = {
        "default_method": settings.detector.method,
        "default_window": str(settings.detector.window),
        "min_volume": str(settings.detector.min_volume),
    }
    parser["Detector.ZScore"] = {
        "sensitivity_low": str(settings.zscore.sensitivity_low),
        "sensitivity_medium": str(settings.zscore.sensitivity_medium),
        "sensitivity_high": str(settings.zscore.sensitivity_high),
        "manual_sigma": ("" if settings.zscore.manual_sigma is None
                         else str(settings.zscore.manual_sigma)),
    }
    parser["Detector.IQR"] = {
        "sensitivity_low": str(settings.iqr.sensitivity_low),
        "sensitivity_medium": str(settings.iqr.sensitivity_medium),
        "sensitivity_high": str(settings.iqr.sensitivity_high),
    }
    parser["Detector.VolumePrice"] = {
        "price_sigma_low": str(settings.volume_price.price_sigma_low),
        "price_sigma_medium": str(settings.volume_price.price_sigma_medium),
        "price_sigma_high": str(settings.volume_price.price_sigma_high),
        "volume_mult_low": str(settings.volume_price.volume_mult_low),
        "volume_mult_medium": str(settings.volume_price.volume_mult_medium),
        "volume_mult_high": str(settings.volume_price.volume_mult_high),
    }
    parser["Markers"] = {
        "anomaly_color": settings.markers.anomaly_color,
        "normal_color": settings.markers.normal_color,
        "volume_bar_color": settings.markers.volume_bar_color,
        "marker_size": str(settings.markers.marker_size),
    }

    with target.open("w", encoding="utf-8") as fh:
        parser.write(fh)


_SENSITIVITY_LEVELS = ("low", "medium", "high")


def _validate_sensitivity(sensitivity: str) -> str:
    """Проверить и нормализовать уровень чувствительности."""
    s = sensitivity.lower()
    if s not in _SENSITIVITY_LEVELS:
        raise ValueError(
            f"Неизвестный уровень чувствительности: {sensitivity!r}. "
            f"Допустимы: {_SENSITIVITY_LEVELS}."
        )
    return s


def resolve_zscore_threshold(settings: Settings, sensitivity: str) -> float:
    """Получить порог сигм для Z-Score по пресету чувствительности.

    Если в настройках задан manual_sigma — он имеет приоритет
    и возвращается независимо от выбранного пресета.

    :param settings:    объект Settings.
    :param sensitivity: 'low' | 'medium' | 'high'.
    :return:            множитель сигмы для метода Z-Score.
    :raises ValueError: при неизвестном пресете.
    """
    if settings.zscore.manual_sigma is not None:
        return settings.zscore.manual_sigma
    s = _validate_sensitivity(sensitivity)
    return getattr(settings.zscore, f"sensitivity_{s}")


def resolve_iqr_multiplier(settings: Settings, sensitivity: str) -> float:
    """Получить множитель IQR по пресету чувствительности.

    :param settings:    объект Settings.
    :param sensitivity: 'low' | 'medium' | 'high'.
    :return:            множитель IQR.
    :raises ValueError: при неизвестном пресете.
    """
    s = _validate_sensitivity(sensitivity)
    return getattr(settings.iqr, f"sensitivity_{s}")


def resolve_volume_price_thresholds(
    settings: Settings,
    sensitivity: str,
) -> tuple:
    """Получить пороги объёмно-ценового метода по пресету.

    :param settings:    объект Settings.
    :param sensitivity: 'low' | 'medium' | 'high'.
    :return:            кортеж (price_sigma_threshold, volume_multiplier).
    :raises ValueError: при неизвестном пресете.
    """
    s = _validate_sensitivity(sensitivity)
    p = getattr(settings.volume_price, f"price_sigma_{s}")
    v = getattr(settings.volume_price, f"volume_mult_{s}")
    return p, v


def ensure_data_directories(settings: Settings) -> None:
    """Создать каталоги data/graphics/output, если они отсутствуют.

    :param settings: объект Settings.
    """
    for d in (settings.paths.data_dir,
              settings.paths.graphics_dir,
              settings.paths.output_dir):
        d.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    cfg = load_settings()
    print(f"settings.ini       : {cfg.source_file}")
    print(f"data_dir           : {cfg.paths.data_dir}")
    print(f"stocks_file        : {cfg.paths.stocks_file}")
    print(f"default method     : {cfg.detector.method}")
    print(f"default window     : {cfg.detector.window}")
    print(f"z-score (medium)   : {cfg.zscore.sensitivity_medium}")
    print(f"manual sigma       : {cfg.zscore.manual_sigma}")
    print(f"iqr (medium)       : {cfg.iqr.sensitivity_medium}")
    print(f"anomaly color      : {cfg.markers.anomaly_color}")
