"""
analysis/deadline_forecaster.py
---------------------------------
Prognose-Modul: erkennt typische Fristformulierungen im Vertragstext und
rechnet sie - ausgehend von einem vom Nutzer angegebenen Vertragsstart-
/Stichtag - in konkrete Kalenderdaten um.

Funktionsweise (bewusst regelbasiert, ohne NLP/ML):
1. Regex-Muster erkennen Formulierungen wie "Kündigungsfrist von drei
   Monaten zum Ende der Vertragslaufzeit" oder "automatische Verlängerung
   um 12 Monate".
2. Aus dem erkannten Zeitraum (Zahl + Einheit) und dem Stichtag wird ein
   konkretes Datum berechnet.
3. Kann ein Muster nicht eindeutig interpretiert werden, wird dies über
   `konnte_berechnet_werden=False` markiert, statt eine falsche Prognose
   zu erzeugen (siehe Architekturvorgabe "robuste Fristenerkennung").

Die Berechnung "spätester Kündigungstermin" arbeitet mit einer einfachen,
nachvollziehbaren Logik: Ausgehend vom Vertragsende (Beginn + Laufzeit in
Monaten, ggf. mehrfach um die Verlängerungsdauer fortgeschrieben bis ein
zukünftiger Zyklus erreicht ist) wird die Kündigungsfrist rückwärts
abgezogen. Das bildet die in Deutschland übliche Formulierung "Kündigung
mit einer Frist von X Monaten zum Ende der Laufzeit" ab.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from contractrisk.domain.models import Deadline
from contractrisk.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Hilfsfunktionen zur Zahlwort-Erkennung (typisch in deutschen Verträgen:
# "drei Monaten" statt "3 Monaten")
# ---------------------------------------------------------------------------

_WORD_TO_NUMBER = {
    "ein": 1, "eine": 1, "einem": 1, "einen": 1,
    "zwei": 2, "drei": 3, "vier": 4, "fünf": 5, "funf": 5,
    "sechs": 6, "sieben": 7, "acht": 8, "neun": 9, "zehn": 10,
    "elf": 11, "zwölf": 12, "zwolf": 12,
    "vierundzwanzig": 24, "sechsunddreißig": 36, "sechsunddreissig": 36,
}


def _parse_amount(amount_text: str) -> int | None:
    """Wandelt eine Zahl als Ziffer ODER als deutsches Zahlwort in ein int um."""
    amount_text = amount_text.strip().lower()
    if amount_text.isdigit():
        return int(amount_text)
    return _WORD_TO_NUMBER.get(amount_text)


def _add_months(start: date, months: int) -> date:
    """Addiert eine Anzahl von Monaten zu einem Datum, mit korrekter
    Behandlung von Monatsend-Überläufen (z. B. 31. Januar + 1 Monat)."""
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1

    # Tag ggf. auf den letzten gültigen Tag des Zielmonats begrenzen
    day = start.day
    while True:
        try:
            return date(year, month, day)
        except ValueError:
            day -= 1


# ---------------------------------------------------------------------------
# Regex-Muster für Fristformulierungen
# ---------------------------------------------------------------------------

_NUMBER_PATTERN = r"(\d{1,3}|[A-Za-zäöüß]+)"

# "Kündigungsfrist von drei Monaten" / "Kündigungsfrist von 3 Monaten"
_NOTICE_PERIOD_PATTERN = re.compile(
    rf"K(?:ü|ue)ndigungsfrist\s+von\s+{_NUMBER_PATTERN}\s+(Monat[en]*|Wochen?|Tag[en]*)",
    flags=re.IGNORECASE,
)

# "verlängert sich ... um jeweils weitere 12 Monate" / "um 12 Monate"
_RENEWAL_PERIOD_PATTERN = re.compile(
    rf"verl(?:ä|ae)ngert sich.{{0,60}}?um\s+(?:jeweils\s+weitere\s+)?{_NUMBER_PATTERN}\s+(Monat[en]*|Jahr[en]*)",
    flags=re.IGNORECASE,
)

# "Mindestvertragslaufzeit von 24 Monaten"
_MINIMUM_TERM_PATTERN = re.compile(
    rf"Mindestvertragslaufzeit\s+von\s+{_NUMBER_PATTERN}\s+(Monat[en]*|Jahr[en]*)",
    flags=re.IGNORECASE,
)

_UNIT_TO_DAYS_FACTOR = {
    "tag": 1,
    "woche": 7,
    "monat": 30,
    "jahr": 365,
}


def _unit_to_months(unit_text: str) -> float:
    """Normiert eine erkannte Zeiteinheit auf Monate (für die
    Monats-basierte Datumsarithmetik)."""
    unit_lower = unit_text.lower()
    if unit_lower.startswith("jahr"):
        return 12.0
    if unit_lower.startswith("monat"):
        return 1.0
    if unit_lower.startswith("woche"):
        return 7 / 30
    if unit_lower.startswith("tag"):
        return 1 / 30
    return 1.0


@dataclass
class _DetectedPeriod:
    """Ein aus dem Text erkannter Zeitraum (z. B. 'drei Monate')."""

    amount_months: float
    quelle_text: str
    konnte_geparst_werden: bool


def _find_first_period(pattern: re.Pattern, text: str) -> _DetectedPeriod | None:
    match = pattern.search(text)
    if match is None:
        return None

    amount_raw, unit_raw = match.group(1), match.group(2)
    amount = _parse_amount(amount_raw)
    quelle = match.group(0)

    if amount is None:
        logger.info("Zeitangabe konnte nicht geparst werden: '%s'", quelle)
        return _DetectedPeriod(amount_months=0, quelle_text=quelle, konnte_geparst_werden=False)

    months = amount * _unit_to_months(unit_raw)
    return _DetectedPeriod(amount_months=months, quelle_text=quelle, konnte_geparst_werden=True)


def detect_deadlines(text: str, contract_start_date: date | None) -> list[Deadline]:
    """Analysiert den Vertragstext auf Fristformulierungen und berechnet,
    sofern ein Vertragsstart-/Stichtag übergeben wurde, konkrete Termine.

    Wird kein `contract_start_date` übergeben, werden die erkannten
    Formulierungen zwar zurückgegeben, aber ohne konkretes Datum
    (`konnte_berechnet_werden=False`) - der Nutzer wird in der GUI
    aufgefordert, einen Stichtag anzugeben.
    """
    deadlines: list[Deadline] = []

    minimum_term = _find_first_period(_MINIMUM_TERM_PATTERN, text)
    renewal_period = _find_first_period(_RENEWAL_PERIOD_PATTERN, text)
    notice_period = _find_first_period(_NOTICE_PERIOD_PATTERN, text)

    if minimum_term is None and renewal_period is None and notice_period is None:
        logger.info("Keine Fristformulierungen im Text erkannt.")
        return deadlines

    if contract_start_date is None:
        # Formulierungen wurden erkannt, aber ohne Stichtag ist keine
        # konkrete Datumsberechnung möglich.
        for period, bezeichnung in (
            (minimum_term, "Ende der Mindestvertragslaufzeit"),
            (renewal_period, "Automatische Verlängerung"),
            (notice_period, "Späteste Kündigung"),
        ):
            if period is not None:
                deadlines.append(
                    Deadline(
                        bezeichnung=bezeichnung,
                        datum=None,
                        quelle_text=period.quelle_text,
                        konnte_berechnet_werden=False,
                        hinweis="Kein Vertragsstart-/Stichtag angegeben.",
                    )
                )
        return deadlines

    # --- Ende der Mindestlaufzeit berechnen -------------------------------
    end_of_minimum_term: date | None = None
    if minimum_term is not None and minimum_term.konnte_geparst_werden:
        end_of_minimum_term = _add_months(contract_start_date, round(minimum_term.amount_months))
        deadlines.append(
            Deadline(
                bezeichnung="Ende der Mindestvertragslaufzeit",
                datum=end_of_minimum_term,
                quelle_text=minimum_term.quelle_text,
                konnte_berechnet_werden=True,
            )
        )
    elif minimum_term is not None:
        deadlines.append(
            Deadline(
                bezeichnung="Ende der Mindestvertragslaufzeit",
                datum=None,
                quelle_text=minimum_term.quelle_text,
                konnte_berechnet_werden=False,
                hinweis="Zeitangabe nicht eindeutig erkannt.",
            )
        )

    # --- Nächsten Verlängerungszyklus in der Zukunft ermitteln ------------
    reference_end_date = end_of_minimum_term or contract_start_date
    next_renewal_date: date | None = None

    if renewal_period is not None and renewal_period.konnte_geparst_werden and reference_end_date:
        cycle_months = max(round(renewal_period.amount_months), 1)
        candidate = reference_end_date
        # Fortschreiben, bis der nächste Verlängerungstermin in der Zukunft liegt
        safety_counter = 0
        while candidate <= date.today() and safety_counter < 240:
            candidate = _add_months(candidate, cycle_months)
            safety_counter += 1
        next_renewal_date = candidate

        deadlines.append(
            Deadline(
                bezeichnung="Automatische Verlängerung",
                datum=next_renewal_date,
                quelle_text=renewal_period.quelle_text,
                konnte_berechnet_werden=True,
            )
        )
    elif renewal_period is not None:
        deadlines.append(
            Deadline(
                bezeichnung="Automatische Verlängerung",
                datum=None,
                quelle_text=renewal_period.quelle_text,
                konnte_berechnet_werden=False,
                hinweis="Zeitangabe nicht eindeutig erkannt.",
            )
        )

    # --- Spätesten Kündigungstermin berechnen ------------------------------
    if notice_period is not None and notice_period.konnte_geparst_werden:
        bezugstermin = next_renewal_date or end_of_minimum_term
        if bezugstermin is not None:
            notice_days = round(notice_period.amount_months * 30)
            latest_notice_date = _subtract_days(bezugstermin, notice_days)
            deadlines.append(
                Deadline(
                    bezeichnung="Späteste Kündigung",
                    datum=latest_notice_date,
                    quelle_text=notice_period.quelle_text,
                    konnte_berechnet_werden=True,
                )
            )
        else:
            deadlines.append(
                Deadline(
                    bezeichnung="Späteste Kündigung",
                    datum=None,
                    quelle_text=notice_period.quelle_text,
                    konnte_berechnet_werden=False,
                    hinweis="Kein Bezugstermin (Laufzeitende) ermittelbar.",
                )
            )
    elif notice_period is not None:
        deadlines.append(
            Deadline(
                bezeichnung="Späteste Kündigung",
                datum=None,
                quelle_text=notice_period.quelle_text,
                konnte_berechnet_werden=False,
                hinweis="Zeitangabe nicht eindeutig erkannt.",
            )
        )

    logger.info("Fristenerkennung abgeschlossen: %d Fristen erkannt", len(deadlines))
    return deadlines


def _subtract_days(d: date, days: int) -> date:
    """Kleine lesbare Hilfsfunktion, um `timedelta`-Importe im Hauptcode
    zu vermeiden."""
    from datetime import timedelta
    return d - timedelta(days=days)
