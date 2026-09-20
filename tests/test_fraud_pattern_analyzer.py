"""
tests/test_fraud_pattern_analyzer.py
----------------------------------------
Unit-Tests für die Kombinationsanalyse mehrerer gleichzeitig auftretender
Betrugsindikatoren.
"""

from __future__ import annotations

import unittest

from contractrisk.analysis.fraud_pattern_analyzer import detect_combined_fraud_signals
from contractrisk.domain.models import RiskFinding


def _make_finding(rule_id: str, kategorie: str, typ: str = "betrug", start: int = 0) -> RiskFinding:
    return RiskFinding(
        rule_id=rule_id, kategorie=kategorie, schweregrad="hoch",
        erklaerung="Test", fundstelle_text="Testfundstelle",
        start_index=start, end_index=start + 5, typ=typ,
    )


class TestDetectCombinedFraudSignals(unittest.TestCase):
    def test_no_findings_yields_no_combined_signal(self) -> None:
        self.assertEqual(detect_combined_fraud_signals([]), [])

    def test_single_fraud_category_yields_no_combined_signal(self) -> None:
        findings = [_make_finding("r1", "Kategorie A")]
        self.assertEqual(detect_combined_fraud_signals(findings), [])

    def test_two_distinct_fraud_categories_trigger_combined_signal(self) -> None:
        findings = [
            _make_finding("r1", "Kategorie A", start=0),
            _make_finding("r2", "Kategorie B", start=20),
        ]
        combined = detect_combined_fraud_signals(findings)
        self.assertEqual(len(combined), 1)
        self.assertEqual(combined[0].kategorie, "Mehrere gleichzeitige Betrugsindikatoren")
        self.assertIn("Kategorie A", combined[0].erklaerung)
        self.assertIn("Kategorie B", combined[0].erklaerung)
        self.assertEqual(combined[0].confidence, "hoch")
        self.assertEqual(combined[0].typ, "betrug")

    def test_multiple_matches_of_same_category_do_not_count_as_distinct(self) -> None:
        findings = [
            _make_finding("r1", "Kategorie A", start=0),
            _make_finding("r1", "Kategorie A", start=30),
        ]
        # Zwei Treffer DERSELBEN Kategorie sind kein "mehrere unabhängige
        # Indikatoren"-Signal.
        self.assertEqual(detect_combined_fraud_signals(findings), [])

    def test_contract_clause_findings_are_ignored(self) -> None:
        findings = [
            _make_finding("r1", "Kategorie A", typ="vertragsklausel", start=0),
            _make_finding("r2", "Kategorie B", typ="vertragsklausel", start=20),
        ]
        self.assertEqual(detect_combined_fraud_signals(findings), [])

    def test_combined_finding_positioned_at_first_fraud_finding(self) -> None:
        findings = [
            _make_finding("r1", "Kategorie A", start=50),
            _make_finding("r2", "Kategorie B", start=10),
        ]
        combined = detect_combined_fraud_signals(findings)
        self.assertEqual(combined[0].start_index, 10)


if __name__ == "__main__":
    unittest.main()
