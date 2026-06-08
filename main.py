import tkinter as tk  # Library for GUI
from tkinter import ttk

# from yfinance import *
# import yfinance


class MainWindow:
    def __init__(self):
        """Init main window, configure main widgets"""

        # Setup main window
        self.root = tk.Tk()
        self.root.title("Anomalies Detector")
        self.root.geometry("1366x768")
        self.root.configure(background="#ffffff")
        
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True)

        self.configure_style()
        self.setup_layout()
        self.setup_main_tab()
        self.setup_control_panel()

    def configure_style(self):
        """Configure styles of Labels, Entries..."""
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TLabel", font=("Fira Code", 20))

        style.configure("TButton", background="red", font=("Fira Code", 15))

    def setup_layout(self):
        """Setup main window layout"""
        
        self.main_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.main_tab, text="Main")
        
        self.data_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.data_tab, text="Data")
        
        # Main paned panel
        self.paned_panel = tk.PanedWindow(
            self.data_tab, orient="horizontal", sashrelief="groove", sashwidth=5
        )
        # Left panel with settings
        self.control_panel = ttk.Frame(self.paned_panel)
        # Right panel with plot and anomalies
        self.data_panel = tk.PanedWindow(
            self.paned_panel, orient="vertical", sashrelief="groove", sashwidth=5
        )
        # Panel with plot
        self.plot_panel = ttk.Frame(self.data_panel)
        # Panel with anomalies list
        self.anomalies_panel = ttk.Frame(self.data_panel)

        # ttk.Label(self.control_panel, text="Control panel").pack()
        ttk.Label(self.plot_panel, text="Plot panel").pack()
        ttk.Label(self.anomalies_panel, text="Anomalies panel").pack()

        self.data_panel.add(self.plot_panel)
        self.data_panel.add(self.anomalies_panel)
        self.data_panel.pack(fill="both", expand=True)

        self.paned_panel.add(self.control_panel, minsize=200)
        self.paned_panel.add(self.data_panel)
        self.paned_panel.pack(fill="both", expand=True)

    def setup_main_tab(self):
        """Load main tab and stocks list"""

    def setup_control_panel(self):
        """Setup control panel Entries, Labels..."""
        ttk.Label(self.control_panel, text="TICKER", style="TLabel").pack(pady=20)
        self.ticker_input = ttk.Entry(self.control_panel, justify="center")
        self.ticker_input.pack()

        ttk.Label(self.control_panel, text="START DATE", style="TLabel").pack(pady=20)
        self.start_date_input = ttk.Entry(self.control_panel, justify="center")
        self.start_date_input.pack()

        ttk.Label(self.control_panel, text="END DATE", style="TLabel").pack(pady=20)
        self.end_date_input = ttk.Entry(self.control_panel, justify="center")
        self.end_date_input.pack()

        self.load_button = ttk.Button(
            self.control_panel,
            text="Load data",
            command=self.load_data(),
            style="TButton",
        )
        self.load_button.pack(pady=30)

        self.analyze_button = ttk.Button(
            self.control_panel,
            text="Start analysing",
            command=self.analyse_data(),
            style="TButton",
        )
        self.analyze_button.pack(pady=30)

    def load_data(self):
        pass

    def analyse_data(self):
        pass

    def run(self):
        """Run main loop"""
        self.root.mainloop()


if __name__ == "__main__":
    app = MainWindow()
    app.run()
