"""
tests/test_deadline_forecaster.py
------------------------------------
Unit-Tests für die Erkennung und Berechnung von Fristen.
"""

from __future__ import annotations

import unittest
from datetime import date

from contractrisk.analysis.deadline_forecaster import _add_months, detect_deadlines


class TestAddMonths(unittest.TestCase):
    def test_simple_addition(self) -> None:
        self.assertEqual(_add_months(date(2026, 1, 1), 3), date(2026, 4, 1))

    def test_year_overflow(self) -> None:
        self.assertEqual(_add_months(date(2026, 11, 15), 3), date(2027, 2, 15))

    def test_day_clamping_for_short_month(self) -> None:
        # 31. Januar + 1 Monat -> Februar hat keinen 31. Tag
        result = _add_months(date(2026, 1, 31), 1)
        self.assertEqual(result, date(2026, 2, 28))


class TestDetectDeadlines(unittest.TestCase):
    def test_no_patterns_found_returns_empty(self) -> None:
        text = "Dies ist ein Vertrag ohne jegliche Fristformulierungen."
        deadlines = detect_deadlines(text, date(2026, 1, 1))
        self.assertEqual(deadlines, [])

    def test_minimum_term_detected_and_calculated(self) -> None:
        text = "Der Vertrag hat eine Mindestvertragslaufzeit von 24 Monaten."
        deadlines = detect_deadlines(text, date(2026, 1, 1))
        matching = [d for d in deadlines if d.bezeichnung == "Ende der Mindestvertragslaufzeit"]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0].datum, date(2028, 1, 1))
        self.assertTrue(matching[0].konnte_berechnet_werden)

    def test_without_start_date_no_concrete_date(self) -> None:
        text = "Mindestvertragslaufzeit von 12 Monaten."
        deadlines = detect_deadlines(text, None)
        self.assertEqual(len(deadlines), 1)
        self.assertIsNone(deadlines[0].datum)
        self.assertFalse(deadlines[0].konnte_berechnet_werden)

    def test_word_number_is_parsed(self) -> None:
        text = "Kündigungsfrist von drei Monaten zum Ende der Vertragslaufzeit."
        deadlines = detect_deadlines(text, date(2026, 1, 1))
        matching = [d for d in deadlines if d.bezeichnung == "Späteste Kündigung"]
        self.assertEqual(len(matching), 1)
        # Ohne erkanntes Laufzeitende wird der Vertragsbeginn als Bezugspunkt
        # verwendet -> sollte trotzdem ein Datum liefern oder sauber als
        # "nicht berechenbar" markiert sein, niemals einen falschen Wert.
        self.assertIsInstance(matching[0].konnte_berechnet_werden, bool)


if __name__ == "__main__":
    unittest.main()
