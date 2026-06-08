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

        self.configure_style()
        self.setup_layout()
        self.setup_control_panel()

    def configure_style(self):
        """Configure styles of Labels, Entries..."""
        style = ttk.Style()
        style.theme_use("default")
        style.configure("TLabel", font=("Fira Code", 20))

    def setup_layout(self):
        """Setup main window layout"""
        # Main paned panel
        self.paned_panel = tk.PanedWindow(
            self.root, orient="horizontal", sashrelief="groove", sashwidth=5
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
        # ttk.Label(self.plot_panel, text="Plot panel").pack()
        # ttk.Label(self.anomalies_panel, text="Anomalies panel").pack()

        self.data_panel.add(self.plot_panel)
        self.data_panel.add(self.anomalies_panel)
        self.data_panel.pack(fill="both", expand=True)

        self.paned_panel.add(self.control_panel, minsize=200)
        self.paned_panel.add(self.data_panel)
        self.paned_panel.pack(fill="both", expand=True)

    def setup_control_panel(self):
        """Setup control panel Entries, Labels..."""
        # self.control_panel.columnconfigure(0, minsize=100, weight=1)
        # self.control_panel.columnconfigure(1, minsize=150, weight=1)
        ttk.Label(self.control_panel, text="TICKER", style="TLabel").pack(
            pady=20
        )  # grid(row=0, column=0, padx=5)
        ttk.Entry(
            self.control_panel, justify="center"
        ).pack()  # grid(row=1, column=0, padx=5, sticky="ew")
        ttk.Label(self.control_panel, text="START DATE", style="TLabel").pack(
            pady=20
        )  # grid(row=2, column=0, padx=5)
        ttk.Entry(
            self.control_panel, justify="center"
        ).pack()  # grid(row=2, column=1, padx=5, sticky="ew")

        ttk.Label(self.control_panel, text="END DATE", style="TLabel").pack(
            pady=20
        )  # grid(row=3, column=0, padx=5)
        ttk.Entry(
            self.control_panel, justify="center"
        ).pack()  # grid(row=3, column=1, padx=5, sticky="ew")

    def run(self):
        """Run main loop"""
        self.root.mainloop()


if __name__ == "__main__":
    app = MainWindow()
    app.run()
