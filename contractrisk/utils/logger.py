"""
utils/logger.py
----------------
Zentrales Logging für den ContractRisk Scanner.

Statt verstreuter `print()`-Aufrufe verwendet die gesamte Anwendung einen
einzigen, zentral konfigurierten Logger. Logs landen sowohl in einer
Log-Datei (contractrisk.log) als auch, während der Entwicklung, auf der
Konsole.

Verwendung in anderen Modulen:

    from contractrisk.utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Vertrag erfolgreich importiert: %s", dateiname)
"""

from __future__ import annotations

import logging
import sys

from contractrisk.config import LOG_FILE_PATH

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def _configure_root_logger() -> None:
    """Konfiguriert den Root-Logger genau einmal pro Prozess."""
    global _configured
    if _configured:
        return

    root_logger = logging.getLogger("contractrisk")
    root_logger.setLevel(logging.DEBUG)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    # Datei-Handler: schreibt alle Meldungen ab INFO in die Log-Datei
    try:
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    except OSError:
        # Falls das Log-Verzeichnis nicht beschreibbar ist, läuft die
        # Anwendung trotzdem weiter - nur ohne Datei-Log.
        pass

    # Konsolen-Handler: nützlich während der Entwicklung in PyCharm
    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Liefert einen konfigurierten Logger für das aufrufende Modul."""
    _configure_root_logger()
    return logging.getLogger(f"contractrisk.{name}")
