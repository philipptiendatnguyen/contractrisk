"""
tests/test_risk_scoring.py
------------------------------
Unit-Tests für die Risiko-Scoring-Berechnung.
"""

from __future__ import annotations

import unittest

from contractrisk.analysis.risk_scoring import (
    calculate_risk_score,
    determine_risk_level,
    split_scores,
    summarize_findings_by_category,
)
from contractrisk.domain.models import RiskFinding


def _make_finding(schweregrad: str, kategorie: str = "Testkategorie") -> RiskFinding:
    return RiskFinding(
        rule_id="test", kategorie=kategorie, schweregrad=schweregrad,
        erklaerung="Test", fundstelle_text="Test", start_index=0, end_index=1,
    )


class TestCalculateRiskScore(unittest.TestCase):
    def test_empty_findings_yield_zero(self) -> None:
        self.assertEqual(calculate_risk_score([]), 0.0)

    def test_single_high_severity_finding(self) -> None:
        score = calculate_risk_score([_make_finding("hoch")])
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)

    def test_score_increases_with_more_findings(self) -> None:
        score_one = calculate_risk_score([_make_finding("mittel")])
        score_two = calculate_risk_score([_make_finding("mittel"), _make_finding("mittel")])
        self.assertGreater(score_two, score_one)

    def test_score_is_capped_at_100(self) -> None:
        many_findings = [_make_finding("hoch") for _ in range(50)]
        score = calculate_risk_score(many_findings)
        self.assertLessEqual(score, 100.0)

    def test_high_severity_weighs_more_than_low(self) -> None:
        score_high = calculate_risk_score([_make_finding("hoch")])
        score_low = calculate_risk_score([_make_finding("niedrig")])
        self.assertGreater(score_high, score_low)


class TestDetermineRiskLevel(unittest.TestCase):
    def test_zero_is_niedrig(self) -> None:
        self.assertEqual(determine_risk_level(0), "niedrig")

    def test_high_score_is_hoch(self) -> None:
        self.assertEqual(determine_risk_level(90), "hoch")

    def test_mid_score_is_mittel(self) -> None:
        self.assertEqual(determine_risk_level(50), "mittel")


class TestSummarizeFindingsByCategory(unittest.TestCase):
    def test_counts_per_category(self) -> None:
        findings = [
            _make_finding("hoch", "Kategorie A"),
            _make_finding("hoch", "Kategorie A"),
            _make_finding("mittel", "Kategorie B"),
        ]
        summary = summarize_findings_by_category(findings)
        self.assertEqual(summary["Kategorie A"], 2)
        self.assertEqual(summary["Kategorie B"], 1)

    def test_empty_findings_yield_empty_summary(self) -> None:
        self.assertEqual(summarize_findings_by_category([]), {})


class TestSplitScores(unittest.TestCase):
    def _make_typed_finding(self, typ: str, schweregrad: str = "hoch") -> RiskFinding:
        return RiskFinding(
            rule_id="test", kategorie="Testkategorie", schweregrad=schweregrad,
            erklaerung="Test", fundstelle_text="Test", start_index=0, end_index=1, typ=typ,
        )

    def test_empty_findings_yield_zero_zero(self) -> None:
        self.assertEqual(split_scores([]), (0.0, 0.0))

    def test_only_contract_findings_yield_zero_fraud_score(self) -> None:
        findings = [self._make_typed_finding("vertragsklausel")]
        contract_score, fraud_score = split_scores(findings)
        self.assertGreater(contract_score, 0)
        self.assertEqual(fraud_score, 0.0)

    def test_only_fraud_findings_yield_zero_contract_score(self) -> None:
        findings = [self._make_typed_finding("betrug")]
        contract_score, fraud_score = split_scores(findings)
        self.assertEqual(contract_score, 0.0)
        self.assertGreater(fraud_score, 0)

    def test_mixed_findings_split_correctly(self) -> None:
        findings = [
            self._make_typed_finding("vertragsklausel"),
            self._make_typed_finding("betrug"),
            self._make_typed_finding("betrug"),
        ]
        contract_score, fraud_score = split_scores(findings)
        self.assertGreater(contract_score, 0)
        self.assertGreater(fraud_score, contract_score)


if __name__ == "__main__":
    unittest.main()
