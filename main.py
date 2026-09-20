"""
main.py
--------
Einstiegspunkt des ContractRisk Scanners.

In PyCharm: Rechtsklick auf diese Datei -> "Run 'main'", oder eine
Run-Konfiguration mit main.py als Skript anlegen (siehe README.md).
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import messagebox

from contractrisk.gui.app import ContractRiskApp
from contractrisk.utils.logger import get_logger

logger = get_logger("main")


def main() -> None:
    try:
        app = ContractRiskApp()
        app.run()
    except Exception as exc:  # Sicherheitsnetz: kein rohes Traceback für den Nutzer
        logger.exception("Unerwarteter Fehler beim Start der Anwendung")
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror(
                "ContractRisk Scanner - Fehler",
                f"Die Anwendung konnte nicht gestartet werden:\n\n{exc}",
            )
        finally:
            sys.exit(1)


if __name__ == "__main__":
    main()
