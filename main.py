"""
scripts/main.py

Главная точка входа в приложение «Бот для отслеживания аномалий
котировок акций». Реализует трёхвкладочный GUI на tkinter:

    Вкладка 1: «Библиотека акций» — справочник, добавление новых
               акций через yfinance, выбор для анализа.
    Вкладка 2: «График и аномалии» — свечной график mplfinance,
               панель управления детектором, список найденных
               аномалий.
    Вкладка 3: «Настройки детекции» — расширенные параметры
               (ручной множитель сигмы, минимальный объём, цвета).
"""

import tkinter as tk
from dataclasses import replace
from tkinter import messagebox, ttk

import matplotlib.pyplot as plt
import mplfinance as mpf
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from scripts import config as cfg
from scripts import data_analyzer as da
from library import file_operations as fo

METHOD_LABELS = {
    "Z-Score (классический)":         "zscore",
    "IQR (устойчивый к выбросам)":    "iqr",
    "Объёмно-ценовой":                "volume_price",
}
SENSITIVITY_LABELS = {
    "Низкая":  "low",
    "Средняя": "medium",
    "Высокая": "high",
}

FACTORY_DEFAULTS = {
    "manual_sigma":  "",
    "min_volume":    "1000.0",
    "anomaly_color": "#E53935",
}


class MainWindow:
    """Главное окно приложения."""

    def __init__(self) -> None:
        """Инициализировать окно, загрузить настройки и данные."""
        # Загрузка настроек и подготовка структуры каталогов
        self.settings = cfg.load_settings()
        cfg.ensure_data_directories(self.settings)

        # Состояние приложения: данные, доступные всем обработчикам
        self.stocks = fo.load_stocks(self.settings.paths.stocks_file)
        self.prices = fo.load_prices(self.settings.paths.prices_file)
        self.current_ticker: str | None = None
        self.current_df = None       # OHLCV выбранной акции
        self.current_mask = None     # маска аномалий

        # Состояние встроенного графика matplotlib (для корректной
        # пересборки при перерисовке — иначе будут утечки памяти).
        self._chart_fig = None
        self._chart_canvas = None

        # Создание главного окна
        self.root = tk.Tk()
        self.root.title("Бот для отслеживания аномалий котировок акций")
        self.root.geometry(
            f"{self.settings.interface.window_width}"
            f"x{self.settings.interface.window_height}"
        )
        self.root.configure(background=self.settings.interface.bg_color)

        # Notebook с тремя вкладками
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.configure_style()
        self.setup_layout()
        self.setup_stocks_tab()
        self.setup_chart_tab()
        self.setup_settings_tab()

        # Заполнить таблицу акций текущим содержимым справочника
        self._refresh_stocks_table()

    def configure_style(self) -> None:
        """Настроить шрифты и темы виджетов из settings.ini."""
        style = ttk.Style()
        style.theme_use("default")
        font = (self.settings.interface.font_family,
                self.settings.interface.font_size)
        title_font = (self.settings.interface.font_family,
                      self.settings.interface.font_size + 4, "bold")

        style.configure("TLabel", font=font)
        style.configure("TButton", font=font)
        style.configure("TEntry", font=font)
        style.configure("TCombobox", font=font)
        style.configure("Title.TLabel", font=title_font)
        style.configure("Treeview", font=font, rowheight=24)
        style.configure("Treeview.Heading", font=font)

    def setup_layout(self) -> None:
        """Создать три вкладки."""
        self.stocks_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.stocks_tab, text="Библиотека акций")

        self.chart_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.chart_tab, text="График и аномалии")

        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Настройки детекции")

    def setup_stocks_tab(self) -> None:
        """Заполнить вкладку «Библиотека акций»: таблица + форма добавления."""
        ttk.Label(
            self.stocks_tab,
            text="Справочник акций",
            style="Title.TLabel",
        ).pack(pady=10)

        # Таблица акций
        table_frame = ttk.Frame(self.stocks_tab)
        table_frame.pack(fill="both", expand=True, padx=10, pady=5)

        columns = ("ticker", "name", "sector")
        self.stocks_table = ttk.Treeview(
            table_frame, columns=columns, show="headings", height=15,
        )
        self.stocks_table.heading("ticker", text="Тикер")
        self.stocks_table.heading("name", text="Название компании")
        self.stocks_table.heading("sector", text="Сектор")
        self.stocks_table.column("ticker", width=100, anchor="center")
        self.stocks_table.column("name", width=400, anchor="w")
        self.stocks_table.column("sector", width=200, anchor="w")

        scroll = ttk.Scrollbar(
            table_frame, orient="vertical",
            command=self.stocks_table.yview,
        )
        self.stocks_table.configure(yscrollcommand=scroll.set)
        self.stocks_table.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.stocks_table.bind("<<TreeviewSelect>>", self.on_stock_selected)

        # Форма добавления новой акции
        form_frame = ttk.LabelFrame(
            self.stocks_tab, text="Добавить акцию", padding=10,
        )
        form_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(form_frame, text="Тикер:").grid(
            row=0, column=0, padx=5, sticky="e")
        self.ticker_input = ttk.Entry(form_frame, width=15)
        self.ticker_input.grid(row=0, column=1, padx=5)

        ttk.Label(form_frame, text="Начало (YYYY-MM-DD):").grid(
            row=0, column=2, padx=5, sticky="e")
        self.start_date_input = ttk.Entry(form_frame, width=15)
        self.start_date_input.insert(0, "2024-01-01")
        self.start_date_input.grid(row=0, column=3, padx=5)

        ttk.Label(form_frame, text="Конец (YYYY-MM-DD):").grid(
            row=0, column=4, padx=5, sticky="e")
        self.end_date_input = ttk.Entry(form_frame, width=15)
        self.end_date_input.insert(0, "2025-06-01")
        self.end_date_input.grid(row=0, column=5, padx=5)

        ttk.Button(
            form_frame,
            text="Добавить",
            command=self.on_add_stock_clicked,
        ).grid(row=0, column=6, padx=10)

    def setup_chart_tab(self) -> None:
        """Заполнить вкладку «График и аномалии»: настройки + график + список."""
        paned = tk.PanedWindow(
            self.chart_tab, orient="horizontal",
            sashrelief="groove", sashwidth=5,
        )
        paned.pack(fill="both", expand=True)

        self.control_panel = ttk.Frame(paned)
        self._build_detector_controls(self.control_panel)

        right = tk.PanedWindow(
            paned, orient="vertical",
            sashrelief="groove", sashwidth=5,
        )

        self.plot_panel = ttk.Frame(right)
        ttk.Label(
            self.plot_panel,
            text="Здесь будет свечной график\n",
            anchor="center", justify="center",
        ).pack(fill="both", expand=True, padx=10, pady=10)

        self.anomalies_panel = ttk.Frame(right)
        self._build_anomalies_list(self.anomalies_panel)

        right.add(self.plot_panel)
        right.add(self.anomalies_panel)

        paned.add(self.control_panel, minsize=260)
        paned.add(right)

    def _build_detector_controls(self, parent: ttk.Frame) -> None:
        """Настройки детектора (метод, чувствительность, окно)."""
        ttk.Label(parent, text="Параметры детектора",
                  style="Title.TLabel").pack(pady=10)

        # Текущая выбранная акция
        ttk.Label(parent, text="Акция:").pack(anchor="w", padx=15)
        self.current_ticker_var = tk.StringVar(value="не выбрана")
        ttk.Label(parent, textvariable=self.current_ticker_var,
                  foreground="#1976D2").pack(anchor="w", padx=15, pady=(0, 10))

        # Метод детекции
        ttk.Label(parent, text="Метод детекции:").pack(
            anchor="w", padx=15, pady=(10, 2))
        self.method_var = tk.StringVar()
        self.method_combo = ttk.Combobox(
            parent, textvariable=self.method_var,
            values=list(METHOD_LABELS.keys()),
            state="readonly",
        )
        # По умолчанию берём из settings.ini
        default_label = next(
            (k for k, v in METHOD_LABELS.items()
             if v == self.settings.detector.method),
            list(METHOD_LABELS.keys())[0],
        )
        self.method_combo.set(default_label)
        self.method_combo.pack(fill="x", padx=15)

        # Чувствительность
        ttk.Label(parent, text="Чувствительность:").pack(
            anchor="w", padx=15, pady=(10, 2))
        self.sensitivity_var = tk.StringVar(value="Средняя")
        self.sensitivity_combo = ttk.Combobox(
            parent, textvariable=self.sensitivity_var,
            values=list(SENSITIVITY_LABELS.keys()),
            state="readonly",
        )
        self.sensitivity_combo.pack(fill="x", padx=15)

        # Окно анализа
        ttk.Label(parent, text="Окно анализа (свечи):").pack(
            anchor="w", padx=15, pady=(10, 2))
        self.window_var = tk.StringVar(
            value=str(self.settings.detector.window))
        ttk.Entry(parent, textvariable=self.window_var
                  ).pack(fill="x", padx=15)

        # Кнопки действий
        ttk.Button(parent, text="Обновить",
                   command=self.on_update_clicked
                   ).pack(fill="x", padx=15, pady=(20, 5))
        ttk.Button(parent, text="Экспорт графика (PNG)",
                   command=self.on_export_clicked
                   ).pack(fill="x", padx=15, pady=5)
        ttk.Button(parent, text="Текстовый отчёт",
                   command=self.on_text_report_clicked
                   ).pack(fill="x", padx=15, pady=5)

    def _build_anomalies_list(self, parent: ttk.Frame) -> None:
        """Список найденных аномалий внизу второй вкладки."""
        ttk.Label(parent, text="Найденные аномалии",
                  style="Title.TLabel").pack(anchor="w", padx=10, pady=5)

        columns = ("date", "close", "volume", "note")
        self.anomalies_table = ttk.Treeview(
            parent, columns=columns, show="headings", height=6,
        )
        self.anomalies_table.heading("date", text="Дата")
        self.anomalies_table.heading("close", text="Цена закрытия")
        self.anomalies_table.heading("volume", text="Объём")
        self.anomalies_table.heading("note", text="Метод")
        self.anomalies_table.column("date", width=120, anchor="center")
        self.anomalies_table.column("close", width=130, anchor="e")
        self.anomalies_table.column("volume", width=130, anchor="e")
        self.anomalies_table.column("note", width=150, anchor="w")
        self.anomalies_table.pack(fill="both", expand=True, padx=10, pady=5)

    def setup_settings_tab(self) -> None:
        """Заполнить вкладку «Настройки детекции»: расширенные параметры."""
        ttk.Label(self.settings_tab, text="Расширенные настройки детекции",
                  style="Title.TLabel").pack(pady=10)

        form = ttk.Frame(self.settings_tab)
        form.pack(pady=10)

        # Пользовательский множитель сигмы (для Z-Score)
        ttk.Label(form, text="Множитель сигмы (пользовательский):").grid(
            row=0, column=0, sticky="e", padx=10, pady=5)
        self.manual_sigma_var = tk.StringVar(
            value=("" if self.settings.zscore.manual_sigma is None
                   else str(self.settings.zscore.manual_sigma))
        )
        ttk.Entry(form, textvariable=self.manual_sigma_var, width=15
                  ).grid(row=0, column=1, padx=10)
        ttk.Label(form, text="(пусто = использовать пресет)",
                  foreground="gray"
                  ).grid(row=0, column=2, sticky="w", padx=10)

        # Минимальный объём для V/P
        ttk.Label(form, text="Минимальный объём (V/P):").grid(
            row=1, column=0, sticky="e", padx=10, pady=5)
        self.min_volume_var = tk.StringVar(
            value=str(self.settings.detector.min_volume))
        ttk.Entry(form, textvariable=self.min_volume_var, width=15
                  ).grid(row=1, column=1, padx=10)

        # Цвет маркера аномалий
        ttk.Label(form, text="Цвет маркера аномалий:").grid(
            row=2, column=0, sticky="e", padx=10, pady=5)
        self.anomaly_color_var = tk.StringVar(
            value=self.settings.markers.anomaly_color)
        ttk.Entry(form, textvariable=self.anomaly_color_var, width=15
                  ).grid(row=2, column=1, padx=10)
        ttk.Label(form, text="(hex, например #E53935)",
                  foreground="gray"
                  ).grid(row=2, column=2, sticky="w", padx=10)

        # Кнопки
        btns = ttk.Frame(self.settings_tab)
        btns.pack(pady=20)
        ttk.Button(btns, text="Сохранить настройки",
                   command=self.on_settings_save_clicked
                   ).pack(side="left", padx=10)
        ttk.Button(btns, text="Сброс по умолчанию",
                   command=self.on_settings_reset_clicked
                   ).pack(side="left", padx=10)

    def on_add_stock_clicked(self) -> None:
        """Загрузить котировки и добавить акцию в справочник."""
        ticker = self.ticker_input.get().strip().upper()
        start = self.start_date_input.get().strip()
        end = self.end_date_input.get().strip()

        if not ticker:
            messagebox.showerror("Ошибка", "Укажите тикер.")
            return
        if not start or not end:
            messagebox.showerror("Ошибка", "Укажите обе даты в формате YYYY-MM-DD.")
            return

        try:
            ohlcv = fo.fetch_quotes(ticker, start, end)
        except Exception as exc:
            messagebox.showerror(
                "Ошибка загрузки",
                f"Не удалось загрузить {ticker}:\n{exc}",
            )
            return

        try:
            info = fo.fetch_quote_info(ticker)
        except Exception:
            info = {"name": "", "sector": ""}

        name = info["name"] or ticker
        sector = info["sector"] or "—"

        # Обновляем справочники
        self.stocks, stock_id = fo.add_stock(self.stocks, ticker, name, sector)
        self.prices = fo.append_prices(self.prices, stock_id, ohlcv)

        # Сохраняем на диск
        try:
            fo.save_stocks(self.stocks, self.settings.paths.stocks_file)
            fo.save_prices(self.prices, self.settings.paths.prices_file)
        except OSError as exc:
            messagebox.showerror("Ошибка записи", str(exc))
            return

        self._refresh_stocks_table()
        self.ticker_input.delete(0, tk.END)
        messagebox.showinfo(
            "Готово",
            f"Акция {ticker} добавлена.\n"
            f"Загружено {len(ohlcv)} торговых дней.",
        )

    def on_stock_selected(self, _event=None) -> None:
        """Обработать клик по строке таблицы акций.

        Подгружает котировки выбранной акции, сразу запускает
        пересчёт аномалий и переключает на вкладку графика.
        """
        selection = self.stocks_table.selection()
        if not selection:
            return
        item = self.stocks_table.item(selection[0])
        if not item["values"]:
            return

        ticker = str(item["values"][0])
        self.current_ticker = ticker
        self.current_ticker_var.set(ticker)

        try:
            self.current_df = fo.get_prices_for_ticker(
                self.stocks, self.prices, ticker,
            )
        except KeyError as exc:
            messagebox.showerror("Ошибка", str(exc))
            return

        if self.current_df.empty:
            messagebox.showwarning(
                "Нет данных",
                f"Для {ticker} нет загруженных котировок.",
            )
            return

        self._compute_and_draw()
        self.notebook.select(self.chart_tab)

    def on_update_clicked(self) -> None:
        """Пересчитать аномалии с текущими параметрами и обновить график."""
        if self.current_df is None:
            messagebox.showwarning(
                "Не выбрана акция",
                "Сначала выберите акцию в библиотеке.",
            )
            return
        self._compute_and_draw()

    def on_export_clicked(self) -> None:
        """Сохранить текущий график в work/graphics/<ticker>_candlestick.png."""
        if self._chart_fig is None or self.current_ticker is None:
            messagebox.showwarning(
                "Нет графика",
                "Сначала постройте график (выберите акцию или нажмите «Обновить»).",
            )
            return

        out_path = (self.settings.paths.graphics_dir
                    / f"{self.current_ticker}_candlestick.png")
        try:
            self._chart_fig.savefig(out_path, dpi=110, bbox_inches="tight")
        except OSError as exc:
            messagebox.showerror("Ошибка записи", str(exc))
            return
        messagebox.showinfo("Готово", f"График сохранён:\n{out_path}")

    def on_text_report_clicked(self) -> None:
        """Сохранить текстовый отчёт в work/output/<ticker>_report.csv."""
        if self.current_df is None or self.current_ticker is None:
            messagebox.showwarning(
                "Не выбрана акция",
                "Сначала выберите акцию в библиотеке.",
            )
            return

        out_path = (self.settings.paths.output_dir
                    / f"{self.current_ticker}_report.csv")
        try:
            fo.export_text_report(
                self.current_df, out_path, ticker=self.current_ticker,
            )
        except (ValueError, OSError) as exc:
            messagebox.showerror("Ошибка", str(exc))
            return
        messagebox.showinfo("Готово", f"Отчёт сохранён:\n{out_path}")

    def on_settings_save_clicked(self) -> None:
        """Сохранить изменения настроек в settings.ini."""
        # 1. Читаем и проверяем поля
        raw_sigma = self.manual_sigma_var.get().strip()
        try:
            manual_sigma = float(raw_sigma) if raw_sigma else None
            if manual_sigma is not None and manual_sigma <= 0:
                raise ValueError("Множитель сигмы должен быть положительным.")
        except ValueError as exc:
            messagebox.showerror("Некорректное значение", str(exc))
            return

        try:
            min_volume = float(self.min_volume_var.get().strip())
            if min_volume < 0:
                raise ValueError("Минимальный объём не может быть отрицательным.")
        except ValueError as exc:
            messagebox.showerror("Некорректное значение", str(exc))
            return

        color = self.anomaly_color_var.get().strip()
        if not (color.startswith("#") and len(color) == 7):
            messagebox.showerror(
                "Некорректное значение",
                "Цвет должен быть в формате #RRGGBB (например, #E53935).",
            )
            return

        # 2. Обновляем структуру Settings через replace
        new_settings = replace(
            self.settings,
            zscore=replace(self.settings.zscore, manual_sigma=manual_sigma),
            detector=replace(self.settings.detector, min_volume=min_volume),
            markers=replace(self.settings.markers, anomaly_color=color),
        )

        # 3. Записываем на диск
        try:
            cfg.save_settings(new_settings)
        except OSError as exc:
            messagebox.showerror("Ошибка записи", str(exc))
            return

        self.settings = new_settings
        messagebox.showinfo(
            "Готово",
            "Настройки сохранены в settings.ini.\n"
            "Новые значения применятся сразу.",
        )

    def on_settings_reset_clicked(self) -> None:
        """Сбросить поля формы к значениям по умолчанию.

        Запись в settings.ini не происходит — пользователю
        нужно дополнительно нажать «Сохранить».
        """
        self.manual_sigma_var.set(FACTORY_DEFAULTS["manual_sigma"])
        self.min_volume_var.set(FACTORY_DEFAULTS["min_volume"])
        self.anomaly_color_var.set(FACTORY_DEFAULTS["anomaly_color"])
        messagebox.showinfo(
            "Сброс",
            "Поля сброшены к значениям по умолчанию.\n"
            "Чтобы записать их в файл, нажмите «Сохранить настройки».",
        )

    def _refresh_stocks_table(self) -> None:
        """Перерисовать таблицу акций из текущего self.stocks."""
        for row in self.stocks_table.get_children():
            self.stocks_table.delete(row)
        for _, row in self.stocks.iterrows():
            self.stocks_table.insert(
                "", "end",
                values=(row["ticker"], row["name"], row["sector"]),
            )

    def _compute_and_draw(self) -> None:
        """Запустить детектор, перерисовать график и обновить список аномалий."""
        if self.current_df is None:
            return

        # 1. Считываем параметры
        method_label = self.method_combo.get()
        method = METHOD_LABELS[method_label]
        sensitivity = SENSITIVITY_LABELS[self.sensitivity_combo.get()]

        try:
            window = int(self.window_var.get())
            if window < 4:
                raise ValueError("Окно должно быть > 3 (минимум для IQR).")
        except ValueError as exc:
            messagebox.showerror("Некорректное окно", str(exc))
            return

        # 2. Подбираем параметры под выбранный метод
        if method == "zscore":
            params = {
                "sigma_threshold":
                    cfg.resolve_zscore_threshold(self.settings, sensitivity),
            }
        elif method == "iqr":
            params = {
                "iqr_multiplier":
                    cfg.resolve_iqr_multiplier(self.settings, sensitivity),
            }
        else:  # volume_price
            p_th, v_mult = cfg.resolve_volume_price_thresholds(
                self.settings, sensitivity,
            )
            params = {
                "price_sigma_threshold": p_th,
                "volume_multiplier":     v_mult,
                "min_volume":            self.settings.detector.min_volume,
            }

        # 3. Вызываем детектор
        try:
            self.current_mask = da.detect_anomalies(
                self.current_df, method, window, params,
            )
        except (ValueError, KeyError) as exc:
            messagebox.showerror("Ошибка детекции", str(exc))
            return

        # 4. Обновляем график и список
        self._redraw_chart(method_label)
        self._refresh_anomalies_list(method_label)

    def _redraw_chart(self, method_label: str) -> None:
        """Перестроить свечной график в plot_panel.

        :param method_label: имя метода для заголовка.
        """
        if self._chart_canvas is not None:
            self._chart_canvas.get_tk_widget().destroy()
            self._chart_canvas = None
        if self._chart_fig is not None:
            plt.close(self._chart_fig)
            self._chart_fig = None

        for w in self.plot_panel.winfo_children():
            w.destroy()

        df = self.current_df
        mask = self.current_mask

        addplots = None
        if mask is not None and mask.any():
            markers = df["High"] * 1.02
            markers = markers.where(mask, other=float("nan"))
            addplots = [mpf.make_addplot(
                markers,
                type="scatter", marker="v",
                color=self.settings.markers.anomaly_color,
                markersize=self.settings.markers.marker_size,
            )]

        fig, _axes = mpf.plot(
            df,
            type="candle",
            volume=True,
            addplot=addplots,
            style="yahoo",
            figsize=(10, 6),
            title=f"\n{self.current_ticker} — {method_label}",
            ylabel="Цена",
            ylabel_lower="Объём",
            returnfig=True,
        )

        self._chart_fig = fig
        self._chart_canvas = FigureCanvasTkAgg(fig, master=self.plot_panel)
        self._chart_canvas.draw()
        self._chart_canvas.get_tk_widget().pack(fill="both", expand=True)

    def _refresh_anomalies_list(self, method_label: str) -> None:
        """Перерисовать список найденных аномалий внизу второй вкладки.

        :param method_label: имя метода — отображается
                             в столбце «Метод» рядом с каждой аномалией.
        """
        for row in self.anomalies_table.get_children():
            self.anomalies_table.delete(row)

        df = self.current_df
        mask = self.current_mask
        if df is None or mask is None or not mask.any():
            return

        for idx in df.index[mask]:
            self.anomalies_table.insert(
                "", "end",
                values=(
                    idx.strftime("%Y-%m-%d"),
                    f"{df.loc[idx, 'Close']:.2f}",
                    f"{int(df.loc[idx, 'Volume']):,}".replace(",", " "),
                    method_label,
                ),
            )

    def run(self) -> None:
        """Запустить главный цикл tkinter."""
        self.root.mainloop()


if __name__ == "__main__":
    MainWindow().run()
