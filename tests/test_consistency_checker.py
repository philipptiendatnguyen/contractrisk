"""
tests/test_consistency_checker.py
-------------------------------------
Unit-Tests für die Widerspruchserkennung (unterschiedliche Werte für
denselben Begriff im Dokument).
"""

from __future__ import annotations

import unittest

from contractrisk.analysis.consistency_checker import detect_contradictions


class TestDetectContradictions(unittest.TestCase):
    def test_no_contradiction_for_single_mention(self) -> None:
        text = "Die Kündigungsfrist von drei Monaten gilt für alle Kunden."
        findings = detect_contradictions(text)
        self.assertEqual(findings, [])

    def test_no_contradiction_for_identical_repeated_values(self) -> None:
        text = (
            "Die Kündigungsfrist von drei Monaten gilt ab Vertragsbeginn. "
            "Zur Klarstellung: Die Kündigungsfrist von drei Monaten beginnt "
            "mit Zugang der Kündigung."
        )
        findings = detect_contradictions(text)
        self.assertEqual(findings, [])

    def test_detects_conflicting_notice_periods(self) -> None:
        text = (
            "Die Kündigungsfrist von drei Monaten gilt für Bestandskunden. "
            "Abweichend davon gilt eine Kündigungsfrist von einem Monat für Neukunden."
        )
        findings = detect_contradictions(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kategorie, "Widersprüchliche Kündigungsfrist")
        self.assertEqual(findings[0].confidence, "mittel")

    def test_detects_conflicting_prices(self) -> None:
        text = (
            "Die monatliche Gebühr beträgt 49,90 EUR. "
            "An anderer Stelle: Die monatliche Gebühr beträgt 59,90 EUR."
        )
        findings = detect_contradictions(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].kategorie, "Widersprüchliche Preisangabe")

    def test_finding_references_both_text_passages(self) -> None:
        text = (
            "Kündigungsfrist von drei Monaten. "
            "Kündigungsfrist von sechs Monaten."
        )
        findings = detect_contradictions(text)
        self.assertIn("drei Monaten", findings[0].fundstelle_text)
        self.assertIn("sechs Monaten", findings[0].fundstelle_text)


if __name__ == "__main__":
    unittest.main()
