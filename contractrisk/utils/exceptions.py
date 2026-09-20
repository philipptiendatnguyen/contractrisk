"""
utils/exceptions.py
--------------------
Eigene, sprechende Exception-Klassen für den ContractRisk Scanner.

Statt generischer `except Exception`-Blöcke verwenden wir spezifische
Fehlerklassen, damit die GUI gezielt reagieren und verständliche
Fehlermeldungen anzeigen kann.
"""


class ContractRiskError(Exception):
    """Basisklasse für alle anwendungsspezifischen Fehler."""


class InvalidRuleConfigError(ContractRiskError):
    """Wird ausgelöst, wenn die Regelbibliothek (rules.json) fehlerhaft,
    unvollständig oder syntaktisch ungültig ist."""


class UnreadableContractFileError(ContractRiskError):
    """Wird ausgelöst, wenn eine Vertragsdatei nicht gelesen werden kann
    (z. B. falsches Encoding, Datei nicht gefunden, leere Datei, defektes
    Dateiformat)."""


class UnsupportedFileFormatError(UnreadableContractFileError):
    """Wird ausgelöst, wenn ein Dateiformat erkannt wird, aber technisch
    nicht (oder nicht zuverlässig) ausgelesen werden kann - z. B. das alte
    binäre .doc-Format. Erbt bewusst von `UnreadableContractFileError`,
    damit bestehender Fehlerbehandlungscode ohne Änderung weiterhin
    funktioniert; die Fehlermeldung erklärt dem Nutzer verständlich,
    warum das Format nicht unterstützt wird und was er stattdessen tun
    kann (z. B. Konvertierung in ein unterstütztes Format)."""


class DateParsingError(ContractRiskError):
    """Wird ausgelöst, wenn ein erkanntes Datums-/Fristmuster nicht
    eindeutig in ein konkretes Kalenderdatum umgerechnet werden kann."""


class DatabaseError(ContractRiskError):
    """Wird ausgelöst bei Fehlern im Zusammenhang mit der SQLite-Datenbank
    (Verbindungsfehler, fehlgeschlagene Queries etc.)."""


class ReportExportError(ContractRiskError):
    """Wird ausgelöst, wenn ein Report oder eine Zeitleiste nicht
    exportiert werden konnte (z. B. ungültiger Zielpfad)."""
